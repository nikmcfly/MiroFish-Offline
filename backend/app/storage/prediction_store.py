"""
SQLite-backed prediction run store — drop-in replacement for PredictionRunManager.

Implements the same classmethod-style interface (create_run, save_run, get_run,
list_runs, delete_run) but persists to SQLite instead of JSON files.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from ..models.prediction import PredictionRun, PredictionRunStatus
from ..storage.sqlite_store import SQLiteStore


class SQLitePredictionStore:
    """SQLite-backed prediction run persistence.

    Drop-in replacement for PredictionRunManager. Unlike the classmethod-based
    original, this requires a store instance — matching PredictionManager's DI pattern.
    """

    def __init__(self, store: SQLiteStore):
        self.store = store

    def create_run(self) -> PredictionRun:
        run_id = f"pred_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        run = PredictionRun(
            run_id=run_id,
            status=PredictionRunStatus.FETCHING_MARKET,
            created_at=now,
            updated_at=now,
        )
        self.store.save_prediction_run(run)
        return run

    def save_run(self, run: PredictionRun) -> None:
        run.updated_at = datetime.now().isoformat()
        self.store.save_prediction_run(run)

    def get_run(self, run_id: str) -> Optional[PredictionRun]:
        return self.store.get_prediction_run(run_id)

    def list_runs(self, limit: int = 50) -> List[PredictionRun]:
        return self.store.list_prediction_runs(limit=limit)

    def delete_run(self, run_id: str) -> bool:
        return self.store.delete_prediction_run(run_id)
