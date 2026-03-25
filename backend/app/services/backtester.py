"""
Backtesting engine — runs the prediction pipeline against resolved markets
and computes accuracy metrics.

State machine:
    PENDING → RUNNING → COMPUTING_METRICS → COMPLETED
                 ↓                              ↓
              FAILED                          FAILED
"""

import math
from typing import Optional, Callable, Dict, Any, List

from collections import defaultdict

from ..config import Config
from ..models.backtest import BacktestRun, BacktestRunStatus, BacktestResult, BacktestMetrics
from ..models.prediction import PredictionMarket, PredictionRun, PredictionRunStatus, PredictionRunManager
from ..services.calibrator import Calibrator
from ..services.market_classifier import MarketClassifier, compute_confidence_tier
from ..services.polymarket_client import PolymarketClient
from ..services.prediction_manager import PredictionManager
from ..storage.sqlite_store import SQLiteStore
from ..utils.logger import get_logger

logger = get_logger('mirofish.backtester')


class Backtester:
    """Runs the prediction pipeline against resolved markets for validation."""

    def __init__(self, store: SQLiteStore, classifier: Optional[MarketClassifier] = None):
        self.store = store
        self.polymarket = PolymarketClient()
        self.classifier = classifier or MarketClassifier(store)

    def run(
        self,
        num_markets: int = 50,
        config_overrides: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        bt_run: Optional[BacktestRun] = None,
    ) -> BacktestRun:
        """
        Execute a full backtest.

        Args:
            num_markets: Number of resolved markets to test
            config_overrides: Optional config overrides for calibration params
            progress_callback: Called with (market_index, total, title, success_count, fail_count)
            bt_run: Optional pre-created BacktestRun (for API use — allows returning the ID before the thread starts)

        Returns:
            Completed BacktestRun with metrics
        """
        if bt_run is None:
            bt_run = BacktestRun(
                config=config_overrides or {},
                total_markets=num_markets,
            )
            self.store.save_backtest_run(bt_run)

        try:
            # Transition to RUNNING
            bt_run.status = BacktestRunStatus.RUNNING.value
            self.store.save_backtest_run(bt_run)

            # Fetch resolved markets
            logger.info(f"Fetching {num_markets} resolved markets...")
            markets = self.polymarket.fetch_resolved_markets(limit=num_markets)
            bt_run.total_markets = len(markets)
            self.store.save_backtest_run(bt_run)

            if not markets:
                logger.warning("No resolved markets found")
                bt_run.status = BacktestRunStatus.COMPLETED.value
                bt_run.metrics = BacktestMetrics(markets_tested=0).to_dict()
                self.store.save_backtest_run(bt_run)
                return bt_run

            # Check which markets are already completed (for resume)
            completed_ids = set(self.store.get_completed_market_ids(bt_run.id))

            # Process each market
            manager = PredictionManager()
            success_count = len(completed_ids)
            fail_count = 0

            for i, market in enumerate(markets):
                if market.condition_id in completed_ids:
                    logger.info(f"Skipping already-completed market: {market.title}")
                    continue

                try:
                    logger.info(f"[{i+1}/{len(markets)}] Processing: {market.title}")

                    if progress_callback:
                        progress_callback(i + 1, len(markets), market.title, success_count, fail_count)

                    # Run prediction pipeline
                    run = PredictionRunManager.create_run()
                    result_run = manager.run_prediction(market=market, run=run)

                    if result_run.status == PredictionRunStatus.COMPLETED and result_run.signal:
                        # Compare prediction vs actual
                        bt_result = self._evaluate_result(bt_run.id, market, result_run)
                        self.store.save_backtest_result(bt_result)
                        success_count += 1
                    else:
                        fail_count += 1
                        logger.warning(f"Pipeline failed for {market.title}: {result_run.error}")

                except Exception as e:
                    fail_count += 1
                    logger.error(f"Error processing market {market.title}: {e}")

                # Update progress
                bt_run.completed_markets = success_count
                bt_run.failed_markets = fail_count
                self.store.save_backtest_run(bt_run)

            # Compute metrics
            bt_run.status = BacktestRunStatus.COMPUTING_METRICS.value
            self.store.save_backtest_run(bt_run)

            metrics = self.compute_metrics(bt_run.id)
            bt_run.metrics = metrics.to_dict()

            # Fit and save category calibration offsets
            all_results = self.store.get_results_by_run(bt_run.id)
            calibrator = Calibrator(store=self.store)
            offsets = calibrator.fit_category_offsets(all_results)
            if offsets:
                calibrator.save_profiles(bt_run.id, offsets, all_results)

            bt_run.status = BacktestRunStatus.COMPLETED.value
            self.store.save_backtest_run(bt_run)

            logger.info(f"Backtest completed: {success_count} success, {fail_count} failed")
            return bt_run

        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            bt_run.status = BacktestRunStatus.FAILED.value
            self.store.save_backtest_run(bt_run)
            raise

    def _evaluate_result(
        self,
        run_id: str,
        market: PredictionMarket,
        prediction: PredictionRun,
    ) -> BacktestResult:
        """Compare a prediction against the actual market resolution."""
        signal = prediction.signal
        predicted_prob = signal['simulated_probability']
        market_prob = signal['market_probability']
        direction = signal['direction']
        edge = signal['edge']

        actual_outcome = (market.actual_outcome or '').upper()

        # Determine if signal was correct
        # YES resolved = probability was 1.0, NO resolved = probability was 0.0
        actual_prob = 1.0 if actual_outcome == 'YES' else 0.0

        # Signal is correct if direction matches resolution
        if direction == 'BUY_YES':
            correct = 1 if actual_outcome == 'YES' else 0
        elif direction == 'BUY_NO':
            correct = 1 if actual_outcome == 'NO' else 0
        else:
            correct = None  # HOLD — not evaluated

        # Brier score: (predicted_prob - actual_binary)^2
        brier = (predicted_prob - actual_prob) ** 2

        # Classify market category and confidence tier
        category = self.classifier.classify(
            market.condition_id, market.title, market.description or ""
        )
        confidence_tier = compute_confidence_tier(edge)

        return BacktestResult(
            run_id=run_id,
            market_id=market.condition_id,
            market_title=market.title,
            predicted_prob=predicted_prob,
            market_prob=market_prob,
            actual_outcome=actual_outcome,
            signal_direction=direction,
            edge=edge,
            brier_score=brier,
            correct=correct,
            category=category,
            confidence_tier=confidence_tier,
        )

    def compute_metrics(self, run_id: str) -> BacktestMetrics:
        """Compute aggregate metrics from backtest results."""
        results = self.store.get_results_by_run(run_id)

        if not results:
            return BacktestMetrics(markets_tested=0)

        # Filter to actionable signals (non-HOLD) for accuracy
        actionable = [r for r in results if r.correct is not None]
        all_brier = [r.brier_score for r in results if r.brier_score is not None]
        all_edges = [r.edge for r in results]

        # Accuracy
        if actionable:
            accuracy = sum(r.correct for r in actionable) / len(actionable)
        else:
            accuracy = 0.0

        # Brier score (mean)
        brier_score = sum(all_brier) / len(all_brier) if all_brier else 0.0

        # ROI: simple model — bet $1 on each signal, win pays 1/market_prob, lose pays 0
        total_invested = 0.0
        total_return = 0.0
        returns_list = []

        for r in actionable:
            bet = 1.0
            total_invested += bet
            if r.correct:
                payout = bet / max(r.market_prob if r.signal_direction == 'BUY_YES' else (1 - r.market_prob), 0.01)
                profit = payout - bet
            else:
                profit = -bet
            total_return += profit
            returns_list.append(profit / bet)

        roi = total_return / total_invested if total_invested > 0 else 0.0

        # Sharpe ratio (annualized, assuming daily bets)
        if len(returns_list) >= 2:
            mean_return = sum(returns_list) / len(returns_list)
            variance = sum((r - mean_return) ** 2 for r in returns_list) / (len(returns_list) - 1)
            std_return = math.sqrt(variance) if variance > 0 else 0.0
            sharpe_ratio = (mean_return / std_return) * math.sqrt(252) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for ret in returns_list:
            cumulative += ret
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_drawdown:
                max_drawdown = dd

        # Calibration RMSE — bin predictions into 10 buckets, compare predicted vs actual
        calibration_rmse = self._compute_calibration_rmse(results)

        # Average edge
        avg_edge = sum(all_edges) / len(all_edges) if all_edges else 0.0

        # Per-category metrics
        category_metrics = self._compute_group_metrics(results, key_fn=lambda r: r.category or "other")

        # Per-confidence-tier metrics
        tier_metrics = self._compute_group_metrics(results, key_fn=lambda r: r.confidence_tier or "LOW")

        return BacktestMetrics(
            accuracy=accuracy,
            brier_score=brier_score,
            roi=roi,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            calibration_rmse=calibration_rmse,
            markets_tested=len(results),
            avg_edge=avg_edge,
            category_metrics=category_metrics,
            confidence_tier_metrics=tier_metrics,
        )

    def _compute_group_metrics(
        self, results: List[BacktestResult], key_fn
    ) -> Dict[str, Any]:
        """Compute mini-metrics grouped by an arbitrary key function."""
        groups: Dict[str, List[BacktestResult]] = defaultdict(list)
        for r in results:
            groups[key_fn(r)].append(r)

        out = {}
        for group_name, group_results in sorted(groups.items()):
            actionable = [r for r in group_results if r.correct is not None]
            briers = [r.brier_score for r in group_results if r.brier_score is not None]
            edges = [r.edge for r in group_results]

            acc = sum(r.correct for r in actionable) / len(actionable) if actionable else 0.0

            # ROI per group
            invested = 0.0
            returns = 0.0
            for r in actionable:
                invested += 1.0
                if r.correct:
                    payout = 1.0 / max(
                        r.market_prob if r.signal_direction == 'BUY_YES' else (1 - r.market_prob),
                        0.01,
                    )
                    returns += payout - 1.0
                else:
                    returns -= 1.0
            group_roi = returns / invested if invested > 0 else 0.0

            out[group_name] = {
                "accuracy": round(acc, 4),
                "brier_score": round(sum(briers) / len(briers), 4) if briers else 0.0,
                "roi": round(group_roi, 4),
                "markets_tested": len(group_results),
                "avg_edge": round(sum(edges) / len(edges), 4) if edges else 0.0,
            }
        return out

    def _compute_calibration_rmse(self, results: List[BacktestResult]) -> float:
        """Compute calibration RMSE by binning predictions."""
        if not results:
            return 0.0

        # Bin predictions into 10 buckets
        bins: Dict[int, List[tuple]] = {i: [] for i in range(10)}
        for r in results:
            if r.predicted_prob is not None and r.actual_outcome is not None:
                bucket = min(int(r.predicted_prob * 10), 9)
                actual = 1.0 if r.actual_outcome == 'YES' else 0.0
                bins[bucket].append((r.predicted_prob, actual))

        # RMSE across non-empty bins
        squared_errors = []
        for bucket_items in bins.values():
            if bucket_items:
                mean_pred = sum(p for p, _ in bucket_items) / len(bucket_items)
                mean_actual = sum(a for _, a in bucket_items) / len(bucket_items)
                squared_errors.append((mean_pred - mean_actual) ** 2)

        if not squared_errors:
            return 0.0
        return math.sqrt(sum(squared_errors) / len(squared_errors))
