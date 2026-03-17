"""
Prediction Manager — orchestrates the prediction pipeline:
market → scenario → direct debate → signal

Uses direct LLM debate simulation instead of OASIS multi-agent framework.
Pipeline completes in ~60-90 seconds per market.
"""

from typing import Optional, Callable

from ..config import Config
from ..models.prediction import (
    PredictionMarket, PredictionRun, PredictionRunStatus,
    PredictionRunManager, TradingSignal, SentimentResult,
)
from ..services.scenario_generator import ScenarioGenerator
from ..services.debate_simulator import DebateSimulator
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_manager')


class PredictionManager:
    """Orchestrates the prediction pipeline"""

    def __init__(self, storage=None):
        self.llm_client = LLMClient()
        self.scenario_gen = ScenarioGenerator(self.llm_client)
        self.debate_sim = DebateSimulator(self.llm_client)

    def run_prediction(
        self,
        market: PredictionMarket,
        run: PredictionRun,
        progress_callback: Optional[Callable] = None,
    ) -> PredictionRun:
        """
        Execute the prediction pipeline:
        1. Generate balanced scenario context
        2. Run direct debate simulation via LLM
        3. Compute probability from debate stances
        4. Generate trading signal
        """
        try:
            run.market = market.to_dict()
            self._update(run, PredictionRunStatus.FETCHING_MARKET, "Market data loaded", progress_callback)

            # Step 1: Generate scenario (balanced context document)
            self._update(run, PredictionRunStatus.GENERATING_SCENARIO, "Generating simulation scenario...", progress_callback)
            scenario = self.scenario_gen.generate_scenario(market)
            run.scenario = scenario.to_dict()
            PredictionRunManager.save_run(run)

            # Step 2: Run direct debate simulation
            self._update(run, PredictionRunStatus.RUNNING_SIMULATION, "Simulating multi-perspective debate...", progress_callback)
            sentiment = self.debate_sim.simulate_debate(
                market=market,
                context_document=scenario.context_document,
            )
            run.sentiment = sentiment.to_dict()
            PredictionRunManager.save_run(run)

            # Step 3: Generate trading signal
            self._update(run, PredictionRunStatus.ANALYZING, "Computing trading signal...", progress_callback)
            signal = self._generate_signal(market, sentiment)
            run.signal = signal.to_dict()

            self._update(run, PredictionRunStatus.COMPLETED, "Prediction complete", progress_callback)
            return run

        except Exception as e:
            logger.error(f"Prediction pipeline failed: {e}", exc_info=True)
            run.status = PredictionRunStatus.FAILED
            run.error = str(e)
            run.progress_message = f"Failed: {str(e)}"
            PredictionRunManager.save_run(run)
            return run

    def _update(self, run: PredictionRun, status: PredictionRunStatus, message: str, callback=None):
        run.status = status
        run.progress_message = message
        PredictionRunManager.save_run(run)
        if callback:
            callback(status.value, message)
        logger.info(f"[{run.run_id}] {status.value}: {message}")

    def _generate_signal(self, market: PredictionMarket, sentiment: SentimentResult) -> TradingSignal:
        """Compare simulated probability vs market price to generate trading signal.

        Applies three calibration corrections learned from backtesting:
        1. Market regression: blend SimP 30% toward market price (markets are informative)
        2. Confidence penalty for large edges (huge disagreements usually = model error)
        3. Short-dated market dampening (less time for unlikely events)
        """
        from datetime import datetime

        market_prob = market.prices[0] if market.prices else 0.5
        raw_sim_prob = sentiment.simulated_probability

        if sentiment.total_posts_analyzed == 0 or sentiment.confidence < 0.05:
            return TradingSignal(
                direction="HOLD",
                edge=0.0,
                confidence=0.0,
                reasoning="Insufficient debate data for signal generation.",
                simulated_probability=raw_sim_prob,
                market_probability=market_prob,
            )

        # Calibration 1: Regress toward market price by 30%
        # LLMs have "possibility bias" — they overweight unlikely events.
        # Liquid markets contain real information from real money.
        MARKET_WEIGHT = 0.30
        sim_prob = (1 - MARKET_WEIGHT) * raw_sim_prob + MARKET_WEIGHT * market_prob

        # Calibration 2: Short-dated dampening
        # If market ends within 14 days, regress more aggressively (less time for surprises)
        days_to_end = None
        if market.end_date:
            try:
                end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
                days_to_end = (end_dt - datetime.now(end_dt.tzinfo)).days
                if days_to_end is not None and days_to_end < 14:
                    # Additional 20% regression for short-dated markets
                    sim_prob = 0.8 * sim_prob + 0.2 * market_prob
            except (ValueError, TypeError):
                pass

        edge = sim_prob - market_prob
        threshold = Config.PREDICTION_SIGNAL_THRESHOLD

        # Calibration 3: Confidence penalty for large edges
        # A 50%+ edge against a liquid market is almost certainly wrong.
        base_confidence = sentiment.confidence
        abs_edge = abs(edge)
        if abs_edge > 0.40:
            confidence = base_confidence * 0.2  # Massive discount
        elif abs_edge > 0.25:
            confidence = base_confidence * 0.5
        elif abs_edge > 0.15:
            confidence = base_confidence * 0.8
        else:
            confidence = base_confidence

        # Build reasoning
        parts = []
        if edge > threshold:
            direction = "BUY_YES"
            parts.append(
                f"Calibrated probability ({sim_prob:.1%}) is {edge:.1%} above "
                f"market ({market_prob:.1%})."
            )
        elif edge < -threshold:
            direction = "BUY_NO"
            parts.append(
                f"Calibrated probability ({sim_prob:.1%}) is {abs(edge):.1%} below "
                f"market ({market_prob:.1%})."
            )
        else:
            direction = "HOLD"
            parts.append(
                f"Calibrated probability ({sim_prob:.1%}) is within threshold of "
                f"market ({market_prob:.1%}). No clear edge."
            )

        if raw_sim_prob != sim_prob:
            parts.append(f"Raw debate estimate was {raw_sim_prob:.1%}, adjusted via market regression.")
        if days_to_end is not None and days_to_end < 14:
            parts.append(f"Short-dated market ({days_to_end}d remaining) — extra dampening applied.")
        if abs_edge > 0.25:
            parts.append(f"Large edge penalized — confidence reduced (markets are usually right).")

        return TradingSignal(
            direction=direction,
            edge=edge,
            confidence=confidence,
            reasoning=" ".join(parts),
            simulated_probability=sim_prob,
            market_probability=market_prob,
        )
