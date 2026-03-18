"""
Tests for category offset integration in PredictionManager._generate_signal().
"""

from unittest.mock import MagicMock, patch

from app.models.backtest import BacktestRun
from app.models.prediction import PredictionMarket, SentimentResult
from app.services.prediction_manager import PredictionManager


def _make_market(prices=None):
    return PredictionMarket(
        condition_id="cond_test",
        title="Test market",
        slug="test",
        description="Test",
        outcomes=["Yes", "No"],
        prices=prices or [0.50, 0.50],
        volume=100000.0,
        liquidity=50000.0,
        end_date="2027-12-31T23:59:59Z",
        active=True,
    )


def _make_sentiment(simulated_probability=0.70, confidence=0.8, total_posts=20):
    return SentimentResult(
        simulated_probability=simulated_probability,
        confidence=confidence,
        stance_counts={"for": 12, "against": 6, "neutral": 2},
        key_arguments_for=["arg1"],
        key_arguments_against=["arg2"],
        total_posts_analyzed=total_posts,
    )


class TestCategoryOffsetAppliedInSignal:

    @patch("app.services.prediction_manager.LLMClient")
    def test_category_offset_adjusts_probability(self, MockLLM, sqlite_store):
        """When category profiles exist, _generate_signal applies the offset."""
        # Setup: completed run with calibration profile
        run = BacktestRun(id="bt_pm_test", status="COMPLETED", started_at="2025-06-01T00:00:00")
        sqlite_store.save_backtest_run(run)
        sqlite_store.save_calibration_profile("bt_pm_test", "politics", 0.10, 30)

        manager = PredictionManager(sqlite_store=sqlite_store)

        # Verify profiles were loaded
        assert "politics" in manager.category_profiles
        assert manager.category_profiles["politics"]["offset"] == 0.10

        market = _make_market(prices=[0.50, 0.50])
        sentiment = _make_sentiment(simulated_probability=0.70)

        # Without category offset
        signal_no_cat = manager._generate_signal(market, sentiment, category=None)

        # With category offset (politics offset = +0.10 → subtract from sim_prob)
        signal_with_cat = manager._generate_signal(market, sentiment, category="politics")

        # The sim_prob should be lower with category offset applied
        assert signal_with_cat.simulated_probability < signal_no_cat.simulated_probability
        assert signal_with_cat.category == "politics"
        assert signal_with_cat.confidence_tier is not None
        assert "Category 'politics' offset" in signal_with_cat.reasoning

    @patch("app.services.prediction_manager.LLMClient")
    def test_no_profiles_no_adjustment(self, MockLLM, sqlite_store):
        """When no completed backtest exists, no offset is applied."""
        manager = PredictionManager(sqlite_store=sqlite_store)
        assert manager.category_profiles == {}

        market = _make_market(prices=[0.50, 0.50])
        sentiment = _make_sentiment(simulated_probability=0.70)

        signal = manager._generate_signal(market, sentiment, category="politics")
        assert "offset" not in signal.reasoning.lower()

    @patch("app.services.prediction_manager.LLMClient")
    def test_unknown_category_no_adjustment(self, MockLLM, sqlite_store):
        """Category not in profiles passes through without adjustment."""
        run = BacktestRun(id="bt_pm_unk", status="COMPLETED", started_at="2025-06-01T00:00:00")
        sqlite_store.save_backtest_run(run)
        sqlite_store.save_calibration_profile("bt_pm_unk", "politics", 0.10, 30)

        manager = PredictionManager(sqlite_store=sqlite_store)

        market = _make_market(prices=[0.50, 0.50])
        sentiment = _make_sentiment(simulated_probability=0.70)

        signal = manager._generate_signal(market, sentiment, category="sports")
        assert "offset" not in signal.reasoning.lower()
