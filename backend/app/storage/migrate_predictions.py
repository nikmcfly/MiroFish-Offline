"""
One-time migration: move prediction runs from JSON files to SQLite.

Usage:
    cd backend && uv run python -m app.storage.migrate_predictions
"""

import json
import os

from ..config import Config
from ..models.prediction import PredictionRun
from ..storage.sqlite_store import SQLiteStore


def migrate(db_path: str = None, predictions_dir: str = None):
    """Migrate JSON prediction runs to SQLite."""
    db_path = db_path or Config.SQLITE_DB_PATH
    predictions_dir = predictions_dir or Config.PREDICTION_DATA_DIR

    if not os.path.isdir(predictions_dir):
        print(f"No predictions directory found at {predictions_dir}")
        return 0

    store = SQLiteStore(db_path=db_path)
    migrated = 0
    skipped = 0
    errors = 0

    for name in sorted(os.listdir(predictions_dir)):
        run_path = os.path.join(predictions_dir, name, "run.json")
        if not os.path.isfile(run_path):
            continue

        try:
            with open(run_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            run = PredictionRun.from_dict(data)

            # Check if already migrated
            existing = store.get_prediction_run(run.run_id)
            if existing:
                skipped += 1
                continue

            store.save_prediction_run(run)
            migrated += 1
            print(f"  Migrated: {run.run_id} ({run.market.get('title', '?')[:50] if run.market else '?'})")

        except Exception as e:
            errors += 1
            print(f"  Error migrating {name}: {e}")

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
    return migrated


if __name__ == "__main__":
    migrate()
