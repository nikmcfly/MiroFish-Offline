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
        """Compare simulated probability vs market price to generate trading signal"""
        market_prob = market.prices[0] if market.prices else 0.5
        sim_prob = sentiment.simulated_probability

        if sentiment.total_posts_analyzed == 0 or sentiment.confidence < 0.05:
            return TradingSignal(
                direction="HOLD",
                edge=0.0,
                confidence=0.0,
                reasoning="Insufficient debate data for signal generation.",
                simulated_probability=sim_prob,
                market_probability=market_prob,
            )

        edge = sim_prob - market_prob
        threshold = Config.PREDICTION_SIGNAL_THRESHOLD

        if edge > threshold:
            direction = "BUY_YES"
            reasoning = (
                f"Debate consensus ({sim_prob:.1%}) is {edge:.1%} higher than "
                f"market price ({market_prob:.1%}). Arguments favor YES."
            )
        elif edge < -threshold:
            direction = "BUY_NO"
            reasoning = (
                f"Debate consensus ({sim_prob:.1%}) is {abs(edge):.1%} lower than "
                f"market price ({market_prob:.1%}). Arguments favor NO."
            )
        else:
            direction = "HOLD"
            reasoning = (
                f"Debate consensus ({sim_prob:.1%}) is within threshold of "
                f"market price ({market_prob:.1%}). No clear edge."
            )

        return TradingSignal(
            direction=direction,
            edge=edge,
            confidence=sentiment.confidence,
            reasoning=reasoning,
            simulated_probability=sim_prob,
            market_probability=market_prob,
        )
