"""
Tests for Backtester.compute_metrics — isolated metric calculations.
"""

import math

import pytest

from app.models.backtest import BacktestResult, BacktestRun
from app.services.backtester import Backtester


def _result(
    run_id: str,
    idx: int,
    predicted: float,
    market: float,
    actual: str,
    direction: str,
    correct: int = None,
    edge: float = 0.0,
) -> BacktestResult:
    actual_prob = 1.0 if actual == "YES" else 0.0
    brier = (predicted - actual_prob) ** 2
    return BacktestResult(
        id=f"btr_{idx}",
        run_id=run_id,
        market_id=f"mkt_{idx}",
        market_title=f"Market {idx}",
        predicted_prob=predicted,
        market_prob=market,
        actual_outcome=actual,
        signal_direction=direction,
        edge=edge,
        brier_score=brier,
        correct=correct,
    )


class TestAccuracyPerfect:

    def test_accuracy_perfect(self, sqlite_store):
        run = BacktestRun(id="bt_perf")
        sqlite_store.save_backtest_run(run)

        for i in range(5):
            r = _result("bt_perf", i, 0.80, 0.55, "YES", "BUY_YES", correct=1, edge=0.25)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_perf")
        assert metrics.accuracy == 1.0


class TestAccuracyWorst:

    def test_accuracy_worst(self, sqlite_store):
        run = BacktestRun(id="bt_worst")
        sqlite_store.save_backtest_run(run)

        for i in range(5):
            r = _result("bt_worst", i, 0.80, 0.55, "NO", "BUY_YES", correct=0, edge=0.25)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_worst")
        assert metrics.accuracy == 0.0


class TestAccuracyAllHold:

    def test_accuracy_all_hold(self, sqlite_store):
        run = BacktestRun(id="bt_hold")
        sqlite_store.save_backtest_run(run)

        for i in range(5):
            r = _result("bt_hold", i, 0.50, 0.50, "YES", "HOLD", correct=None, edge=0.0)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_hold")
        # No actionable signals — accuracy should be 0
        assert metrics.accuracy == 0.0


class TestBrierScoreCalculation:

    def test_brier_score_calculation(self, sqlite_store):
        run = BacktestRun(id="bt_brier")
        sqlite_store.save_backtest_run(run)

        # predicted=0.8, actual=YES => brier = (0.8-1.0)^2 = 0.04
        r1 = _result("bt_brier", 0, 0.80, 0.55, "YES", "BUY_YES", correct=1)
        # predicted=0.3, actual=NO  => brier = (0.3-0.0)^2 = 0.09
        r2 = _result("bt_brier", 1, 0.30, 0.55, "NO", "BUY_NO", correct=1)
        sqlite_store.save_backtest_result(r1)
        sqlite_store.save_backtest_result(r2)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_brier")
        expected_brier = (0.04 + 0.09) / 2
        assert abs(metrics.brier_score - expected_brier) < 1e-6


class TestROICalculation:

    def test_roi_calculation(self, sqlite_store):
        run = BacktestRun(id="bt_roi")
        sqlite_store.save_backtest_run(run)

        # Win at market_prob=0.60, payout = 1/0.60 = 1.667, profit = 0.667
        r1 = _result("bt_roi", 0, 0.80, 0.60, "YES", "BUY_YES", correct=1)
        # Loss, profit = -1.0
        r2 = _result("bt_roi", 1, 0.80, 0.60, "NO", "BUY_YES", correct=0)
        sqlite_store.save_backtest_result(r1)
        sqlite_store.save_backtest_result(r2)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_roi")

        # total_invested=2, total_return = 0.667 + (-1.0) = -0.333
        expected_roi = ((1 / 0.60 - 1) + (-1.0)) / 2.0
        assert abs(metrics.roi - expected_roi) < 1e-4


class TestSharpeRatioZeroVariance:

    def test_sharpe_ratio_zero_variance(self, sqlite_store):
        """All same return should give sharpe=0 (zero std dev)."""
        run = BacktestRun(id="bt_sharpe0")
        sqlite_store.save_backtest_run(run)

        # All wins at same market_prob => same return
        for i in range(5):
            r = _result("bt_sharpe0", i, 0.80, 0.60, "YES", "BUY_YES", correct=1)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_sharpe0")
        assert metrics.sharpe_ratio == 0.0


class TestSharpeRatioNormal:

    def test_sharpe_ratio_normal(self, sqlite_store):
        """Mixed wins/losses should produce non-zero sharpe."""
        run = BacktestRun(id="bt_sharpe_n")
        sqlite_store.save_backtest_run(run)

        # Win
        r1 = _result("bt_sharpe_n", 0, 0.80, 0.60, "YES", "BUY_YES", correct=1)
        # Loss
        r2 = _result("bt_sharpe_n", 1, 0.80, 0.60, "NO", "BUY_YES", correct=0)
        # Win
        r3 = _result("bt_sharpe_n", 2, 0.80, 0.60, "YES", "BUY_YES", correct=1)
        sqlite_store.save_backtest_result(r1)
        sqlite_store.save_backtest_result(r2)
        sqlite_store.save_backtest_result(r3)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_sharpe_n")
        # Should be a real number, not zero or infinity
        assert metrics.sharpe_ratio != 0.0
        assert math.isfinite(metrics.sharpe_ratio)


class TestMaxDrawdown:

    def test_max_drawdown(self, sqlite_store):
        run = BacktestRun(id="bt_dd")
        sqlite_store.save_backtest_run(run)

        # Win, Win, Loss, Loss — drawdown = 2 losses from peak
        for i, (actual, correct) in enumerate([
            ("YES", 1), ("YES", 1), ("NO", 0), ("NO", 0)
        ]):
            r = _result("bt_dd", i, 0.80, 0.60, actual, "BUY_YES", correct=correct)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_dd")
        assert metrics.max_drawdown > 0.0


class TestCalibrationRMSE:

    def test_calibration_rmse(self, sqlite_store):
        run = BacktestRun(id="bt_cal")
        sqlite_store.save_backtest_run(run)

        # Well-calibrated: predicted ~0.8 and 80% resolve YES
        for i in range(10):
            actual = "YES" if i < 8 else "NO"
            r = _result("bt_cal", i, 0.80, 0.55, actual, "BUY_YES", correct=1 if actual == "YES" else 0)
            sqlite_store.save_backtest_result(r)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_cal")
        # Should be reasonably small for well-calibrated predictions
        assert metrics.calibration_rmse < 0.5


class TestEmptyResults:

    def test_empty_results(self, sqlite_store):
        run = BacktestRun(id="bt_empty")
        sqlite_store.save_backtest_run(run)

        bt = Backtester(sqlite_store)
        metrics = bt.compute_metrics("bt_empty")
        assert metrics.markets_tested == 0
        assert metrics.accuracy == 0.0
        assert metrics.brier_score == 0.0
        assert metrics.roi == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
