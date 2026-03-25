"""
Tests for PredictionManager dependency injection of result_store.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.models.prediction import PredictionRunManager


class TestDefaultStoreIsPredictionRunManager:

    @patch("app.services.prediction_manager.DebateSimulator")
    @patch("app.services.prediction_manager.ScenarioGenerator")
    @patch("app.services.prediction_manager.LLMClient")
    def test_default_store_is_prediction_run_manager(
        self, MockLLM, MockScenGen, MockDebate
    ):
        from app.services.prediction_manager import PredictionManager

        mgr = PredictionManager()
        assert mgr.result_store is PredictionRunManager


class TestCustomStoreUsed:

    @patch("app.services.prediction_manager.DebateSimulator")
    @patch("app.services.prediction_manager.ScenarioGenerator")
    @patch("app.services.prediction_manager.LLMClient")
    def test_custom_store_used(self, MockLLM, MockScenGen, MockDebate):
        from app.services.prediction_manager import PredictionManager
        from app.models.prediction import (
            PredictionRun,
            PredictionRunStatus,
            PredictionMarket,
        )

        custom_store = MagicMock()
        mgr = PredictionManager(result_store=custom_store)
        assert mgr.result_store is custom_store

        # Create a market and run prediction — save_run should be called on custom_store
        market = PredictionMarket(
            condition_id="cond_di",
            title="DI test",
            slug="di-test",
            description="test",
            outcomes=["Yes", "No"],
            prices=[0.5, 0.5],
            volume=10000,
            liquidity=5000,
            end_date="2025-12-31",
        )
        run = PredictionRun(
            run_id="pred_di",
            status=PredictionRunStatus.FETCHING_MARKET,
            created_at="2025-01-01",
            updated_at="2025-01-01",
        )

        # Make the scenario generator and debate simulator return mocks
        mock_scenario = MagicMock()
        mock_scenario.to_dict.return_value = {}
        mock_scenario.context_document = "test context"
        MockScenGen.return_value.generate_scenario.return_value = mock_scenario

        mock_sentiment = MagicMock()
        mock_sentiment.to_dict.return_value = {}
        mock_sentiment.simulated_probability = 0.6
        mock_sentiment.confidence = 0.7
        mock_sentiment.total_posts_analyzed = 10
        MockDebate.return_value.simulate_debate.return_value = mock_sentiment

        mgr.run_prediction(market=market, run=run)

        # Verify the custom store's save_run was called (multiple times during pipeline)
        assert custom_store.save_run.call_count >= 1
