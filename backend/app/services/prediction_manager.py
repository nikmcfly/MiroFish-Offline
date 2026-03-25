"""
Prediction Manager — orchestrates the prediction pipeline:
market → scenario → direct debate → signal

Uses direct LLM debate simulation instead of OASIS multi-agent framework.
Pipeline completes in ~60-90 seconds per market.
"""

import requests
import json
from typing import Dict, Any, Optional, Callable

from ..config import Config
from ..models.prediction import (
    PredictionMarket, PredictionRun, PredictionRunStatus,
    PredictionRunManager, TradingSignal, SentimentResult,
)
from ..services.calibrator import Calibrator
from ..services.market_classifier import MarketClassifier, TIER_THRESHOLD_HIGH, TIER_THRESHOLD_MEDIUM
from ..services.scenario_generator import ScenarioGenerator
from ..services.debate_simulator import DebateSimulator
from ..storage.sqlite_store import SQLiteStore
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_manager')


class PredictionManager:
    """Orchestrates the prediction pipeline"""

    def __init__(self, result_store=None, sqlite_store: Optional[SQLiteStore] = None):
        self.llm_client = LLMClient()
        self.scenario_gen = ScenarioGenerator(self.llm_client)
        self.debate_sim = DebateSimulator(self.llm_client)
        self.result_store = result_store or PredictionRunManager
        self.sqlite_store = sqlite_store
        self.classifier = MarketClassifier(sqlite_store, self.llm_client) if sqlite_store else None
        self.category_profiles = self._load_category_profiles()

    def _load_category_profiles(self):
        """Load category calibration profiles from the latest completed backtest."""
        if not self.sqlite_store:
            return {}
        try:
            run_id = self.sqlite_store.get_latest_completed_run_id()
            if not run_id:
                return {}
            calibrator = Calibrator(store=self.sqlite_store)
            profiles = calibrator.load_profiles(run_id)
            if profiles:
                logger.info(f"Loaded {len(profiles)} category calibration profiles from run {run_id}")
            return profiles
        except Exception as e:
            logger.warning(f"Could not load category profiles: {e}")
            return {}

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
            self.result_store.save_run(run)

            # Step 2: Run direct debate simulation
            self._update(run, PredictionRunStatus.RUNNING_SIMULATION, "Simulating multi-perspective debate...", progress_callback)
            sentiment = self.debate_sim.simulate_debate(
                market=market,
                context_document=scenario.context_document,
            )
            run.sentiment = sentiment.to_dict()
            self.result_store.save_run(run)

            # Step 2.5: Classify market category
            category = None
            if self.classifier:
                category = self.classifier.classify(
                    market.condition_id, market.title, market.description or ""
                )

            # Step 3: Generate trading signal
            self._update(run, PredictionRunStatus.ANALYZING, "Computing trading signal...", progress_callback)
            signal = self._generate_signal(market, sentiment, category=category)
            run.signal = signal.to_dict()

            self._update(run, PredictionRunStatus.COMPLETED, "Prediction complete", progress_callback)
            return run

        except (requests.RequestException, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Prediction pipeline failed (recoverable): {e}", exc_info=True)
            run.status = PredictionRunStatus.FAILED
            run.error = str(e)
            run.progress_message = f"Failed: {str(e)}"
            self.result_store.save_run(run)
            return run
        except RuntimeError as e:
            logger.error(f"Prediction pipeline runtime error: {e}", exc_info=True)
            run.status = PredictionRunStatus.FAILED
            run.error = str(e)
            run.progress_message = f"Failed: {str(e)}"
            self.result_store.save_run(run)
            return run
        except Exception as e:
            logger.error(f"Prediction pipeline unexpected error: {e}", exc_info=True)
            run.status = PredictionRunStatus.FAILED
            run.error = str(e)
            run.progress_message = f"Failed: {str(e)}"
            self.result_store.save_run(run)
            return run

    def _update(self, run: PredictionRun, status: PredictionRunStatus, message: str, callback=None):
        run.status = status
        run.progress_message = message
        self.result_store.save_run(run)
        if callback:
            callback(status.value, message)
        logger.info(f"[{run.run_id}] {status.value}: {message}")

    def _generate_signal(
        self, market: PredictionMarket, sentiment: SentimentResult, category: Optional[str] = None
    ) -> TradingSignal:
        """Compare simulated probability vs market price to generate trading signal.

        Applies calibration corrections learned from backtesting:
        1. Market regression: blend SimP toward market price (markets are informative)
        2. Confidence penalty for large edges (huge disagreements usually = model error)
        3. Short-dated market dampening (less time for unlikely events)
        4. Category-specific offset (from per-category calibration profiles)
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

        # Calibration 1: Regress toward market price
        MARKET_WEIGHT = Config.CALIBRATION_MARKET_REGRESSION
        sim_prob = (1 - MARKET_WEIGHT) * raw_sim_prob + MARKET_WEIGHT * market_prob

        # Calibration 2: Short-dated dampening
        days_to_end = None
        if market.end_date:
            try:
                end_dt = datetime.fromisoformat(market.end_date.replace('Z', '+00:00'))
                days_to_end = (end_dt - datetime.now(end_dt.tzinfo)).days
                if days_to_end is not None and days_to_end < Config.CALIBRATION_DATE_DAMPENING_DAYS:
                    penalty = Config.CALIBRATION_SHORT_DATE_PENALTY
                    sim_prob = (1 - penalty) * sim_prob + penalty * market_prob
            except (ValueError, TypeError):
                pass

        # Calibration 4: Category-specific offset
        category_offset_applied = False
        if category and self.category_profiles:
            profile = self.category_profiles.get(category)
            if profile:
                offset = profile["offset"]
                sim_prob = max(0.01, min(0.99, sim_prob - offset))
                category_offset_applied = True

        edge = sim_prob - market_prob
        threshold = Config.PREDICTION_SIGNAL_THRESHOLD

        # Calibration 3: Confidence penalty for large edges
        base_confidence = sentiment.confidence
        abs_edge = abs(edge)
        if abs_edge > Config.CALIBRATION_HIGH_EDGE_MAX_REDUCTION:
            confidence = base_confidence * 0.2  # Massive discount
        elif abs_edge > Config.CALIBRATION_HIGH_EDGE_THRESHOLD:
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
        if days_to_end is not None and days_to_end < Config.CALIBRATION_DATE_DAMPENING_DAYS:
            parts.append(f"Short-dated market ({days_to_end}d remaining) — extra dampening applied.")
        if abs_edge > Config.CALIBRATION_HIGH_EDGE_THRESHOLD:
            parts.append(f"Large edge penalized — confidence reduced (markets are usually right).")
        if category_offset_applied and category:
            offset = self.category_profiles[category]["offset"]
            parts.append(f"Category '{category}' offset ({offset:+.3f}) applied.")

        confidence_tier = "HIGH" if abs_edge >= TIER_THRESHOLD_HIGH else ("MEDIUM" if abs_edge >= TIER_THRESHOLD_MEDIUM else "LOW")

        return TradingSignal(
            direction=direction,
            edge=edge,
            confidence=confidence,
            reasoning=" ".join(parts),
            simulated_probability=sim_prob,
            market_probability=market_prob,
            category=category,
            confidence_tier=confidence_tier,
        )
