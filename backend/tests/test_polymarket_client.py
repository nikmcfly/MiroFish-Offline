"""
Tests for app.services.polymarket_client.PolymarketClient (mocked HTTP).
"""

from unittest.mock import patch, MagicMock

import pytest
import requests

from app.services.polymarket_client import PolymarketClient


SAMPLE_MARKET_JSON = {
    "conditionId": "cond_001",
    "question": "Will it rain tomorrow?",
    "slug": "rain-tomorrow",
    "description": "Rain forecast market",
    "tokens": [
        {"outcome": "Yes", "price": "0.65", "winner": False},
        {"outcome": "No", "price": "0.35", "winner": False},
    ],
    "volume": "50000",
    "liquidity": "10000",
    "endDate": "2025-12-31",
    "active": True,
}

SAMPLE_RESOLVED_JSON = {
    "conditionId": "cond_resolved",
    "question": "Did it rain?",
    "slug": "did-it-rain",
    "description": "Resolved rain market",
    "tokens": [
        {"outcome": "Yes", "price": "1.0", "winner": True},
        {"outcome": "No", "price": "0.0", "winner": False},
    ],
    "volume": "80000",
    "liquidity": "20000",
    "endDate": "2025-06-01",
    "active": False,
    "resolved": True,
}


class TestFetchActiveMarketsSuccess:

    @patch("app.services.polymarket_client.requests.get")
    def test_fetch_active_markets_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [SAMPLE_MARKET_JSON]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = PolymarketClient(base_url="http://fake-api")
        markets = client.fetch_active_markets(min_volume=1000, limit=10)

        assert len(markets) == 1
        assert markets[0].condition_id == "cond_001"
        assert markets[0].title == "Will it rain tomorrow?"
        assert markets[0].prices[0] == 0.65


class TestFetchActiveMarketsRetryOnTimeout:

    @patch("app.services.polymarket_client.time.sleep")
    @patch("app.services.polymarket_client.requests.get")
    def test_fetch_active_markets_retry_on_timeout(self, mock_get, mock_sleep):
        """First call times out, second succeeds."""
        mock_resp_ok = MagicMock()
        mock_resp_ok.json.return_value = [SAMPLE_MARKET_JSON]
        mock_resp_ok.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.Timeout("Connection timed out"),
            mock_resp_ok,
        ]

        client = PolymarketClient(base_url="http://fake-api")
        markets = client.fetch_active_markets(min_volume=1000, limit=10)

        assert len(markets) == 1
        assert mock_get.call_count == 2


class TestFetchActiveMarketsMalformedJson:

    @patch("app.services.polymarket_client.requests.get")
    def test_fetch_active_markets_malformed_json(self, mock_get):
        """Non-list response returns empty list."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "bad request"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = PolymarketClient(base_url="http://fake-api")
        markets = client.fetch_active_markets(min_volume=1000, limit=10)

        assert markets == []


class TestFetchActiveMarketsEmpty:

    @patch("app.services.polymarket_client.requests.get")
    def test_fetch_active_markets_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = PolymarketClient(base_url="http://fake-api")
        markets = client.fetch_active_markets(min_volume=1000, limit=10)

        assert markets == []


class TestFetchResolvedMarkets:

    @patch("app.services.polymarket_client.requests.get")
    def test_fetch_resolved_markets(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [SAMPLE_RESOLVED_JSON]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = PolymarketClient(base_url="http://fake-api")
        markets = client.fetch_resolved_markets(limit=10)

        assert len(markets) == 1
        assert markets[0].actual_outcome == "YES"
        assert markets[0].active is False


class TestGetMarketSuccess:

    @patch("app.services.polymarket_client.requests.get")
    def test_get_market_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_MARKET_JSON
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = PolymarketClient(base_url="http://fake-api")
        market = client.get_market("cond_001")

        assert market is not None
        assert market.condition_id == "cond_001"
        mock_get.assert_called_once()
