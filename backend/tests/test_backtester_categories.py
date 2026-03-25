"""
Tests for per-category and per-tier metrics in backtester.
"""

from app.models.backtest import BacktestRun, BacktestResult, BacktestMetrics
from app.services.backtester import Backtester


class TestPerCategoryMetrics:

    def test_category_metrics_computed(self, sqlite_store):
        """compute_metrics returns per-category breakdown."""
        run = BacktestRun(id="bt_cat_test")
        sqlite_store.save_backtest_run(run)

        # Create results across two categories
        for i in range(5):
            sqlite_store.save_backtest_result(BacktestResult(
                id=f"btr_pol_{i}", run_id="bt_cat_test",
                market_id=f"mkt_pol_{i}", market_title=f"Politics {i}",
                predicted_prob=0.7, market_prob=0.5,
                actual_outcome="YES", signal_direction="BUY_YES",
                edge=0.2, brier_score=0.09, correct=1,
                category="politics", confidence_tier="HIGH",
            ))

        for i in range(3):
            sqlite_store.save_backtest_result(BacktestResult(
                id=f"btr_spt_{i}", run_id="bt_cat_test",
                market_id=f"mkt_spt_{i}", market_title=f"Sports {i}",
                predicted_prob=0.6, market_prob=0.5,
                actual_outcome="NO", signal_direction="BUY_YES",
                edge=0.1, brier_score=0.36, correct=0,
                category="sports", confidence_tier="MEDIUM",
            ))

        backtester = Backtester(store=sqlite_store)
        metrics = backtester.compute_metrics("bt_cat_test")

        assert metrics.category_metrics is not None
        assert "politics" in metrics.category_metrics
        assert "sports" in metrics.category_metrics

        pol = metrics.category_metrics["politics"]
        assert pol["accuracy"] == 1.0
        assert pol["markets_tested"] == 5

        spt = metrics.category_metrics["sports"]
        assert spt["accuracy"] == 0.0
        assert spt["markets_tested"] == 3

    def test_confidence_tier_metrics_computed(self, sqlite_store):
        """compute_metrics returns per-tier breakdown."""
        run = BacktestRun(id="bt_tier_test")
        sqlite_store.save_backtest_run(run)

        # HIGH tier
        for i in range(4):
            sqlite_store.save_backtest_result(BacktestResult(
                id=f"btr_h_{i}", run_id="bt_tier_test",
                market_id=f"mkt_h_{i}", predicted_prob=0.8, market_prob=0.5,
                actual_outcome="YES", signal_direction="BUY_YES",
                edge=0.3, brier_score=0.04, correct=1,
                category="crypto", confidence_tier="HIGH",
            ))

        # LOW tier
        for i in range(2):
            sqlite_store.save_backtest_result(BacktestResult(
                id=f"btr_l_{i}", run_id="bt_tier_test",
                market_id=f"mkt_l_{i}", predicted_prob=0.52, market_prob=0.5,
                actual_outcome="NO", signal_direction="HOLD",
                edge=0.02, brier_score=0.27, correct=None,
                category="other", confidence_tier="LOW",
            ))

        backtester = Backtester(store=sqlite_store)
        metrics = backtester.compute_metrics("bt_tier_test")

        assert metrics.confidence_tier_metrics is not None
        assert "HIGH" in metrics.confidence_tier_metrics
        assert "LOW" in metrics.confidence_tier_metrics
        assert metrics.confidence_tier_metrics["HIGH"]["markets_tested"] == 4

    def test_empty_results_no_category_metrics(self, sqlite_store):
        """compute_metrics with no results returns None category_metrics."""
        run = BacktestRun(id="bt_empty_cat")
        sqlite_store.save_backtest_run(run)

        backtester = Backtester(store=sqlite_store)
        metrics = backtester.compute_metrics("bt_empty_cat")

        assert metrics.markets_tested == 0
        # Empty results return default None for category/tier metrics
        assert metrics.category_metrics is None
        assert metrics.confidence_tier_metrics is None


class TestCategoryInResults:

    def test_result_has_category_fields(self):
        """BacktestResult serializes category and confidence_tier."""
        result = BacktestResult(
            id="btr_x", run_id="bt_x", market_id="mkt_x",
            category="crypto", confidence_tier="HIGH",
        )
        d = result.to_dict()
        assert d["category"] == "crypto"
        assert d["confidence_tier"] == "HIGH"

        restored = BacktestResult.from_dict(d)
        assert restored.category == "crypto"
        assert restored.confidence_tier == "HIGH"
