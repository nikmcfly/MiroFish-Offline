"""
Shared pytest fixtures for the MiroFish backtesting test suite.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.models.prediction import PredictionMarket


# ---------------------------------------------------------------------------
# SQLite store (in-memory)
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_store(tmp_path):
    """In-memory SQLite store backed by a tmpdir file so WAL works correctly."""
    from app.storage.sqlite_store import SQLiteStore

    db_path = str(tmp_path / "test.db")
    store = SQLiteStore(db_path=db_path)
    return store


# ---------------------------------------------------------------------------
# Flask app / test client
# ---------------------------------------------------------------------------

@pytest.fixture
def app(sqlite_store):
    """Flask test app with mocked Neo4j and in-memory SQLite."""
    with patch("app.storage.Neo4jStorage"):
        with patch("app.services.simulation_runner.SimulationRunner.register_cleanup"):
            from app import create_app

            class TestConfig:
                SECRET_KEY = "test-secret"
                DEBUG = False
                JSON_AS_ASCII = False
                TESTING = True
                NEO4J_URI = "bolt://localhost:7687"
                NEO4J_USER = "neo4j"
                NEO4J_PASSWORD = "test"
                SQLITE_DB_PATH = ":memory:"
                LLM_API_KEY = "test-key"

            test_app = create_app(config_class=TestConfig)

            # Replace the sqlite extension with our fixture store
            test_app.extensions["sqlite"] = sqlite_store

            yield test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns predetermined JSON responses."""
    client = MagicMock()
    client.chat.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"probability": 0.65, "confidence": 0.7, "reasoning": "Test reasoning"}'
                }
            }
        ]
    }
    return client


# ---------------------------------------------------------------------------
# Sample markets
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_market():
    """A PredictionMarket fixture for testing."""
    return PredictionMarket(
        condition_id="cond_abc123",
        title="Will BTC exceed $100k by end of 2025?",
        slug="btc-100k-2025",
        description="Whether Bitcoin will exceed $100,000 USD",
        outcomes=["Yes", "No"],
        prices=[0.60, 0.40],
        volume=500000.0,
        liquidity=100000.0,
        end_date="2025-12-31T23:59:59Z",
        active=True,
    )


@pytest.fixture
def sample_resolved_market():
    """A resolved PredictionMarket with actual_outcome set."""
    return PredictionMarket(
        condition_id="cond_resolved_001",
        title="Will ETH merge complete by 2023?",
        slug="eth-merge-2023",
        description="Whether Ethereum will complete the merge",
        outcomes=["Yes", "No"],
        prices=[0.85, 0.15],
        volume=1000000.0,
        liquidity=250000.0,
        end_date="2023-12-31T23:59:59Z",
        active=False,
        actual_outcome="YES",
    )
