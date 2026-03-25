"""
Tests for app.services.market_classifier — LLM classification with SQLite caching.
"""

from unittest.mock import MagicMock, patch

from app.models.prediction import PredictionMarket
from app.services.market_classifier import MarketClassifier, compute_confidence_tier, CATEGORIES


class TestComputeConfidenceTier:

    def test_high_tier(self):
        assert compute_confidence_tier(0.20) == "HIGH"
        assert compute_confidence_tier(-0.15) == "HIGH"

    def test_medium_tier(self):
        assert compute_confidence_tier(0.10) == "MEDIUM"
        assert compute_confidence_tier(-0.08) == "MEDIUM"

    def test_low_tier(self):
        assert compute_confidence_tier(0.05) == "LOW"
        assert compute_confidence_tier(0.0) == "LOW"


class TestMarketClassifierCaching:

    def test_returns_cached_category(self, sqlite_store):
        """classify() returns cached result without calling LLM."""
        sqlite_store.save_market_category("mkt_cached", "sports")

        mock_llm = MagicMock()
        classifier = MarketClassifier(store=sqlite_store, llm_client=mock_llm)

        result = classifier.classify("mkt_cached", "Will team X win?", "")
        assert result == "sports"
        mock_llm.chat_json.assert_not_called()

    def test_llm_called_on_cache_miss(self, sqlite_store):
        """classify() calls LLM and caches result on miss."""
        mock_llm = MagicMock()
        mock_llm.chat_json.return_value = {"category": "politics"}

        classifier = MarketClassifier(store=sqlite_store, llm_client=mock_llm)
        result = classifier.classify("mkt_new", "Will candidate X win?", "Election question")

        assert result == "politics"
        mock_llm.chat_json.assert_called_once()

        # Verify it was cached
        cached = sqlite_store.get_market_category("mkt_new")
        assert cached == "politics"

    def test_unknown_category_defaults_to_other(self, sqlite_store):
        """LLM returning unknown category falls back to 'other'."""
        mock_llm = MagicMock()
        mock_llm.chat_json.return_value = {"category": "weather"}

        classifier = MarketClassifier(store=sqlite_store, llm_client=mock_llm)
        result = classifier.classify("mkt_unknown", "Will it rain?", "")

        assert result == "other"

    def test_llm_error_defaults_to_other(self, sqlite_store):
        """LLM error falls back to 'other'."""
        mock_llm = MagicMock()
        mock_llm.chat_json.side_effect = RuntimeError("LLM down")

        classifier = MarketClassifier(store=sqlite_store, llm_client=mock_llm)
        result = classifier.classify("mkt_err", "Will X happen?", "")

        assert result == "other"


class TestBatchClassification:

    def test_classify_batch(self, sqlite_store):
        """classify_batch classifies multiple markets, using cache where available."""
        sqlite_store.save_market_category("mkt_a", "crypto")

        mock_llm = MagicMock()
        mock_llm.chat_json.return_value = {"category": "sports"}

        classifier = MarketClassifier(store=sqlite_store, llm_client=mock_llm)

        markets = [
            PredictionMarket(
                condition_id="mkt_a", title="BTC price", slug="btc",
                description="", outcomes=["Yes", "No"], prices=[0.5, 0.5],
                volume=1000.0, liquidity=500.0, end_date="2025-12-31",
            ),
            PredictionMarket(
                condition_id="mkt_b", title="Team wins", slug="team",
                description="", outcomes=["Yes", "No"], prices=[0.5, 0.5],
                volume=1000.0, liquidity=500.0, end_date="2025-12-31",
            ),
        ]

        results = classifier.classify_batch(markets)
        assert results == {"mkt_a": "crypto", "mkt_b": "sports"}
        # Only mkt_b should trigger LLM call
        assert mock_llm.chat_json.call_count == 1
