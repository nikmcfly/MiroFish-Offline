"""
Tests for SQLite-backed prediction run storage.
"""

from app.models.prediction import PredictionRun, PredictionRunStatus
from app.storage.prediction_store import SQLitePredictionStore


class TestSQLitePredictionStore:

    def test_create_and_get_run(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        run = store.create_run()

        assert run.run_id.startswith("pred_")
        assert run.status == PredictionRunStatus.FETCHING_MARKET

        loaded = store.get_run(run.run_id)
        assert loaded is not None
        assert loaded.run_id == run.run_id

    def test_save_and_get_with_nested_data(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        run = store.create_run()

        run.market = {"title": "Test market", "prices": [0.5, 0.5]}
        run.signal = {"direction": "BUY_YES", "edge": 0.15}
        run.sentiment = {"confidence": 0.8, "stance_counts": {"for": 10}}
        run.scenario = {"context_document": "Test context"}
        run.status = PredictionRunStatus.COMPLETED
        store.save_run(run)

        loaded = store.get_run(run.run_id)
        assert loaded.market["title"] == "Test market"
        assert loaded.signal["direction"] == "BUY_YES"
        assert loaded.sentiment["confidence"] == 0.8
        assert loaded.scenario["context_document"] == "Test context"
        assert loaded.status == PredictionRunStatus.COMPLETED

    def test_list_runs_ordered(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)

        runs = []
        for _ in range(3):
            runs.append(store.create_run())

        listed = store.list_runs()
        assert len(listed) == 3
        # Most recent first
        assert listed[0].run_id == runs[-1].run_id

    def test_list_runs_with_limit(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        for _ in range(5):
            store.create_run()

        listed = store.list_runs(limit=2)
        assert len(listed) == 2

    def test_delete_run(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        run = store.create_run()

        assert store.delete_run(run.run_id) is True
        assert store.get_run(run.run_id) is None

    def test_delete_nonexistent(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        assert store.delete_run("nonexistent") is False

    def test_get_nonexistent(self, sqlite_store):
        store = SQLitePredictionStore(sqlite_store)
        assert store.get_run("nonexistent") is None

    def test_update_preserves_data(self, sqlite_store):
        """save_run updates existing run without losing fields."""
        store = SQLitePredictionStore(sqlite_store)
        run = store.create_run()
        run.market = {"title": "Test"}
        store.save_run(run)

        run.status = PredictionRunStatus.COMPLETED
        run.error = "something failed"
        store.save_run(run)

        loaded = store.get_run(run.run_id)
        assert loaded.market["title"] == "Test"
        assert loaded.error == "something failed"
