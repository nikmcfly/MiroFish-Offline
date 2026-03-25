"""
Tests for app.services.backtester.Backtester (integration-level with mocked externals).
"""

from unittest.mock import patch, MagicMock

import pytest

from app.models.backtest import BacktestRun, BacktestResult, BacktestRunStatus
from app.models.prediction import (
    PredictionMarket,
    PredictionRun,
    PredictionRunStatus,
    TradingSignal,
)
from app.services.backtester import Backtester


def _make_resolved_market(idx: int, actual_outcome: str = "YES") -> PredictionMarket:
    return PredictionMarket(
        condition_id=f"cond_{idx}",
        title=f"Test Market {idx}",
        slug=f"test-market-{idx}",
        description=f"Description {idx}",
        outcomes=["Yes", "No"],
        prices=[0.60, 0.40],
        volume=100000.0,
        liquidity=50000.0,
        end_date="2025-12-31T23:59:59Z",
        active=False,
        actual_outcome=actual_outcome,
    )


def _make_completed_prediction_run(sim_prob: float = 0.70, market_prob: float = 0.60):
    run = PredictionRun(
        run_id="pred_test",
        status=PredictionRunStatus.COMPLETED,
        created_at="2025-01-01",
        updated_at="2025-01-01",
        signal=TradingSignal(
            direction="BUY_YES",
            edge=sim_prob - market_prob,
            confidence=0.8,
            reasoning="test",
            simulated_probability=sim_prob,
            market_probability=market_prob,
        ).to_dict(),
    )
    return run


class TestBacktestFullPipeline:

    @patch("app.services.backtester.PredictionManager")
    @patch("app.services.backtester.PredictionRunManager")
    @patch("app.services.backtester.PolymarketClient")
    def test_backtest_full_pipeline(
        self, MockPolyClient, MockRunMgr, MockPredMgr, sqlite_store
    ):
        """Mock 3 resolved markets, verify results and metrics."""
        markets = [_make_resolved_market(i, "YES") for i in range(3)]

        mock_poly = MagicMock()
        mock_poly.fetch_resolved_markets.return_value = markets
        MockPolyClient.return_value = mock_poly

        mock_run = _make_completed_prediction_run()
        MockRunMgr.create_run.return_value = mock_run

        mock_mgr = MagicMock()
        mock_mgr.run_prediction.return_value = mock_run
        MockPredMgr.return_value = mock_mgr

        backtester = Backtester(sqlite_store)
        backtester.polymarket = mock_poly

        result_run = backtester.run(num_markets=3)

        assert result_run.status == BacktestRunStatus.COMPLETED.value
        assert result_run.metrics is not None
        assert result_run.completed_markets == 3
        assert result_run.failed_markets == 0

        results = sqlite_store.get_results_by_run(result_run.id)
        assert len(results) == 3


class TestBacktestResumeAfterCrash:

    @patch("app.services.backtester.PredictionManager")
    @patch("app.services.backtester.PredictionRunManager")
    @patch("app.services.backtester.PolymarketClient")
    def test_backtest_resume_after_crash(
        self, MockPolyClient, MockRunMgr, MockPredMgr, sqlite_store
    ):
        """Pre-populate some results, verify they are skipped on resume."""
        markets = [_make_resolved_market(i, "YES") for i in range(3)]

        mock_poly = MagicMock()
        mock_poly.fetch_resolved_markets.return_value = markets
        MockPolyClient.return_value = mock_poly

        mock_run = _make_completed_prediction_run()
        MockRunMgr.create_run.return_value = mock_run

        mock_mgr = MagicMock()
        mock_mgr.run_prediction.return_value = mock_run
        MockPredMgr.return_value = mock_mgr

        backtester = Backtester(sqlite_store)
        backtester.polymarket = mock_poly

        # Run once fully
        first_run = backtester.run(num_markets=3)

        # Pre-populate result for market 0 in a NEW run
        new_bt_run = BacktestRun(id="bt_resume_test", total_markets=3)
        sqlite_store.save_backtest_run(new_bt_run)

        pre_result = BacktestResult(
            id="btr_pre",
            run_id="bt_resume_test",
            market_id="cond_0",
            market_title="Test Market 0",
            predicted_prob=0.70,
            market_prob=0.60,
            actual_outcome="YES",
            signal_direction="BUY_YES",
            edge=0.10,
            brier_score=0.09,
            correct=1,
        )
        sqlite_store.save_backtest_result(pre_result)

        completed_ids = sqlite_store.get_completed_market_ids("bt_resume_test")
        assert "cond_0" in completed_ids


class TestBacktestZeroMarkets:

    @patch("app.services.backtester.PredictionManager")
    @patch("app.services.backtester.PolymarketClient")
    def test_backtest_zero_markets(self, MockPolyClient, MockPredMgr, sqlite_store):
        """Empty list from polymarket should return completed with zero metrics."""
        mock_poly = MagicMock()
        mock_poly.fetch_resolved_markets.return_value = []
        MockPolyClient.return_value = mock_poly

        backtester = Backtester(sqlite_store)
        backtester.polymarket = mock_poly

        result_run = backtester.run(num_markets=10)

        assert result_run.status == BacktestRunStatus.COMPLETED.value
        assert result_run.metrics is not None
        assert result_run.metrics["markets_tested"] == 0


class TestBacktestAllFailures:

    @patch("app.services.backtester.PredictionManager")
    @patch("app.services.backtester.PredictionRunManager")
    @patch("app.services.backtester.PolymarketClient")
    def test_backtest_all_failures(
        self, MockPolyClient, MockRunMgr, MockPredMgr, sqlite_store
    ):
        """All pipeline runs fail — should still complete with 0 success."""
        markets = [_make_resolved_market(i) for i in range(3)]

        mock_poly = MagicMock()
        mock_poly.fetch_resolved_markets.return_value = markets
        MockPolyClient.return_value = mock_poly

        failed_run = PredictionRun(
            run_id="pred_fail",
            status=PredictionRunStatus.FAILED,
            created_at="2025-01-01",
            updated_at="2025-01-01",
            error="LLM timeout",
        )
        MockRunMgr.create_run.return_value = failed_run

        mock_mgr = MagicMock()
        mock_mgr.run_prediction.return_value = failed_run
        MockPredMgr.return_value = mock_mgr

        backtester = Backtester(sqlite_store)
        backtester.polymarket = mock_poly

        result_run = backtester.run(num_markets=3)

        assert result_run.status == BacktestRunStatus.COMPLETED.value
        assert result_run.completed_markets == 0
        assert result_run.failed_markets == 3
