"""
Tests for app.api.backtest — Flask API endpoints.
"""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from app.models.backtest import BacktestRun, BacktestRunStatus


class TestStartBacktest:

    def test_start_backtest(self, client, sqlite_store):
        with patch("app.api.backtest.Backtester") as MockBT:
            mock_bt = MagicMock()
            MockBT.return_value = mock_bt

            resp = client.post(
                "/api/backtest/run",
                json={"num_markets": 5},
            )

        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["data"]["status"] == "started"
        assert "run_id" in data["data"]

        # Clean up: clear running backtests
        import app.api.backtest as bt_mod
        with bt_mod._lock:
            bt_mod._running_backtests.clear()


class TestGetBacktestStatus:

    def test_get_backtest_status(self, client, sqlite_store):
        run = BacktestRun(
            id="bt_api_status",
            status=BacktestRunStatus.COMPLETED.value,
            metrics={"accuracy": 0.75},
        )
        sqlite_store.save_backtest_run(run)

        resp = client.get("/api/backtest/run/bt_api_status")
        data = resp.get_json()

        assert resp.status_code == 200
        assert data["success"] is True
        assert data["data"]["id"] == "bt_api_status"
        assert data["data"]["status"] == "COMPLETED"


class TestGetBacktestNotFound:

    def test_get_backtest_not_found(self, client, sqlite_store):
        resp = client.get("/api/backtest/run/nonexistent_id")
        data = resp.get_json()

        assert resp.status_code == 404
        assert data["success"] is False


class TestListBacktestsEmpty:

    def test_list_backtests_empty(self, client, sqlite_store):
        resp = client.get("/api/backtest/runs")
        data = resp.get_json()

        assert resp.status_code == 200
        assert data["success"] is True
        assert data["count"] == 0
        assert data["data"] == []


class TestConcurrentBacktestRejected:

    def test_concurrent_backtest_rejected(self, client, sqlite_store):
        """Second backtest should be rejected with 409 via DB-level guard."""
        # Insert a RUNNING backtest into the DB
        run = BacktestRun(id="bt_already_running", status="RUNNING")
        sqlite_store.save_backtest_run(run)

        resp = client.post(
            "/api/backtest/run",
            json={"num_markets": 5},
        )
        data = resp.get_json()

        assert resp.status_code == 409
        assert data["success"] is False
        assert "already running" in data["error"]

        # Clean up
        sqlite_store.update_backtest_run("bt_already_running", status="COMPLETED")
