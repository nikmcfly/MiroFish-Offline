"""
SQLAlchemy Core-based SQLite storage for backtesting and paper trading.

Schema diagram:

    backtest_runs
    ┌──────────────────────┐
    │ id           TEXT PK │
    │ started_at   TEXT    │
    │ config       TEXT    │  ← JSON
    │ status       TEXT    │
    │ metrics      TEXT    │  ← JSON
    │ total_markets    INT │
    │ completed_markets INT│
    │ failed_markets   INT │
    └──────────┬───────────┘
               │ 1:N
    backtest_results
    ┌──────────────────────┐
    │ id           TEXT PK │
    │ run_id       TEXT FK │──→ backtest_runs.id
    │ market_id    TEXT    │
    │ market_title TEXT    │
    │ predicted_prob REAL  │
    │ market_prob    REAL  │
    │ actual_outcome TEXT  │
    │ signal_direction TEXT│
    │ edge           REAL  │
    │ brier_score    REAL  │
    │ correct        INT   │
    │ category       TEXT  │
    │ confidence_tier TEXT │
    └──────────────────────┘

    market_categories
    ┌──────────────────────┐
    │ market_id    TEXT PK │
    │ category     TEXT    │
    │ classified_at TEXT   │
    └──────────────────────┘

    calibration_profiles
    ┌──────────────────────┐
    │ id           TEXT PK │
    │ run_id       TEXT FK │──→ backtest_runs.id
    │ category     TEXT    │
    │ offset       REAL    │
    │ sample_size  INT     │
    │ created_at   TEXT    │
    │ UNIQUE(run_id, category) │
    └──────────────────────┘

    paper_orders
    ┌──────────────────────┐
    │ id           TEXT PK │
    │ market_id    TEXT    │
    │ signal_id    TEXT    │
    │ side         TEXT    │
    │ outcome      TEXT    │
    │ size         REAL    │
    │ fill_price   REAL    │
    │ slippage     REAL    │
    │ created_at   TEXT    │
    └──────────┬───────────┘
               │ 1:N
    paper_positions
    ┌──────────────────────┐
    │ id           TEXT PK │
    │ order_id     TEXT FK │──→ paper_orders.id
    │ market_id    TEXT    │
    │ outcome      TEXT    │
    │ entry_price  REAL    │
    │ cost_basis   REAL    │
    │ status       TEXT    │
    │ resolved_pnl REAL    │
    └──────────────────────┘
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import OperationalError

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine

from ..models.backtest import BacktestResult, BacktestRun
from ..models.prediction import PredictionRun, PredictionRunStatus
from ..models.position import PaperOrder, PaperPosition

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when a storage operation fails (disk full, I/O error, etc.)."""
    pass

metadata = MetaData()

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("started_at", String),
    Column("config", String),  # JSON
    Column("status", String),
    Column("metrics", String),  # JSON
    Column("total_markets", Integer, default=0),
    Column("completed_markets", Integer, default=0),
    Column("failed_markets", Integer, default=0),
)

backtest_results = Table(
    "backtest_results",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("backtest_runs.id")),
    Column("market_id", String),
    Column("market_title", String),
    Column("predicted_prob", Float),
    Column("market_prob", Float),
    Column("actual_outcome", String),
    Column("signal_direction", String),
    Column("edge", Float),
    Column("brier_score", Float),
    Column("correct", Integer),
    Column("category", String),
    Column("confidence_tier", String),
)

market_categories = Table(
    "market_categories",
    metadata,
    Column("market_id", String, primary_key=True),
    Column("category", String, nullable=False),
    Column("classified_at", String),
)

calibration_profiles = Table(
    "calibration_profiles",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("backtest_runs.id")),
    Column("category", String, nullable=False),
    Column("offset", Float, nullable=False),
    Column("sample_size", Integer),
    Column("created_at", String),
    UniqueConstraint("run_id", "category", name="uq_run_category"),
)

prediction_runs = Table(
    "prediction_runs",
    metadata,
    Column("run_id", String, primary_key=True),
    Column("status", String),
    Column("created_at", String),
    Column("updated_at", String),
    Column("market", String),  # JSON
    Column("project_id", String),
    Column("graph_id", String),
    Column("simulation_id", String),
    Column("scenario", String),  # JSON
    Column("sentiment", String),  # JSON
    Column("signal", String),  # JSON
    Column("error", String),
    Column("progress_message", String),
)

paper_orders = Table(
    "paper_orders",
    metadata,
    Column("id", String, primary_key=True),
    Column("market_id", String),
    Column("signal_id", String),
    Column("side", String),
    Column("outcome", String),
    Column("size", Float),
    Column("fill_price", Float),
    Column("slippage", Float),
    Column("created_at", String),
)

paper_positions = Table(
    "paper_positions",
    metadata,
    Column("id", String, primary_key=True),
    Column("order_id", String, ForeignKey("paper_orders.id")),
    Column("market_id", String),
    Column("outcome", String),
    Column("entry_price", Float),
    Column("cost_basis", Float),
    Column("status", String),
    Column("resolved_pnl", Float),
)


class SQLiteStore:
    """SQLite repository for backtest runs, results, and paper trading."""

    def __init__(self, db_path: str = "data/mirofish.db"):
        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.engine: Engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        metadata.create_all(self.engine)
        # Enable WAL mode for concurrent reads + enforce foreign keys
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        self._migrate_add_columns()
        logger.info("SQLiteStore initialized: %s (WAL mode)", db_path)

    def _safe_write(self, operation: str, fn):
        """Execute a write operation with disk-full error handling.

        Args:
            operation: Human-readable description for error messages
            fn: Callable that receives a connection and performs the write
        """
        try:
            with self.engine.connect() as conn:
                fn(conn)
                conn.commit()
        except OperationalError as e:
            err_msg = str(e).lower()
            if "disk" in err_msg or "i/o" in err_msg or "full" in err_msg or "readonly" in err_msg:
                logger.error(f"Storage I/O error during {operation}: {e}")
                raise StorageError(f"Disk I/O error during {operation}: {e}") from e
            raise

    def _migrate_add_columns(self):
        """Add new columns to existing tables (idempotent)."""
        migrations = [
            "ALTER TABLE backtest_results ADD COLUMN category TEXT",
            "ALTER TABLE backtest_results ADD COLUMN confidence_tier TEXT",
        ]
        with self.engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass  # Column already exists
            conn.commit()

    # ── Backtest Runs ────────────────────────────────────────────────

    def save_backtest_run(self, run: BacktestRun) -> None:
        d = run.to_dict()
        d["config"] = json.dumps(d["config"]) if d["config"] else None
        d["metrics"] = json.dumps(d["metrics"]) if d["metrics"] else None
        self._safe_write("save_backtest_run", lambda conn: conn.execute(
            backtest_runs.insert().prefix_with("OR REPLACE"), d,
        ))

    def get_backtest_run(self, run_id: str) -> Optional[BacktestRun]:
        with self.engine.connect() as conn:
            row = conn.execute(
                backtest_runs.select().where(backtest_runs.c.id == run_id)
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_backtest_run(row)

    def list_backtest_runs(self) -> List[BacktestRun]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                backtest_runs.select().order_by(backtest_runs.c.started_at.desc())
            ).mappings().all()
        return [self._row_to_backtest_run(r) for r in rows]

    def has_active_backtest(self) -> Optional[str]:
        """Return the ID of any PENDING/RUNNING backtest, or None."""
        with self.engine.connect() as conn:
            row = conn.execute(
                backtest_runs.select()
                .where(backtest_runs.c.status.in_(["PENDING", "RUNNING", "COMPUTING_METRICS"]))
                .limit(1)
            ).mappings().first()
        return row["id"] if row else None

    def update_backtest_run(self, run_id: str, **kwargs: Any) -> None:
        updates: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if key in ("config", "metrics") and value is not None:
                updates[key] = json.dumps(value)
            else:
                updates[key] = value
        self._safe_write("update_backtest_run", lambda conn: conn.execute(
            backtest_runs.update().where(backtest_runs.c.id == run_id).values(**updates)
        ))

    @staticmethod
    def _row_to_backtest_run(row: Any) -> BacktestRun:
        d = dict(row)
        d["config"] = json.loads(d["config"]) if d.get("config") else {}
        d["metrics"] = json.loads(d["metrics"]) if d.get("metrics") else None
        return BacktestRun.from_dict(d)

    # ── Backtest Results ─────────────────────────────────────────────

    def save_backtest_result(self, result: BacktestResult) -> None:
        d = result.to_dict()
        self._safe_write("save_backtest_result", lambda conn: conn.execute(
            backtest_results.insert().prefix_with("OR REPLACE"), d,
        ))

    def get_results_by_run(self, run_id: str) -> List[BacktestResult]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                backtest_results.select().where(backtest_results.c.run_id == run_id)
            ).mappings().all()
        return [BacktestResult.from_dict(dict(r)) for r in rows]

    def get_completed_market_ids(self, run_id: str) -> List[str]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                backtest_results.select()
                .with_only_columns(backtest_results.c.market_id)
                .where(backtest_results.c.run_id == run_id)
            ).all()
        return [r[0] for r in rows]

    # ── Paper Orders ─────────────────────────────────────────────────

    def save_paper_order(self, order: PaperOrder) -> None:
        d = order.to_dict()
        self._safe_write("save_paper_order", lambda conn: conn.execute(
            paper_orders.insert().prefix_with("OR REPLACE"), d,
        ))

    def get_orders(self) -> List[PaperOrder]:
        with self.engine.connect() as conn:
            rows = conn.execute(paper_orders.select()).mappings().all()
        return [PaperOrder.from_dict(dict(r)) for r in rows]

    # ── Paper Positions ──────────────────────────────────────────────

    def save_paper_position(self, position: PaperPosition) -> None:
        d = position.to_dict()
        self._safe_write("save_paper_position", lambda conn: conn.execute(
            paper_positions.insert().prefix_with("OR REPLACE"), d,
        ))

    def get_positions(self) -> List[PaperPosition]:
        with self.engine.connect() as conn:
            rows = conn.execute(paper_positions.select()).mappings().all()
        return [PaperPosition.from_dict(dict(r)) for r in rows]

    # ── Market Categories ─────────────────────────────────────────

    def get_market_category(self, market_id: str) -> Optional[str]:
        """Return cached category for a market, or None."""
        with self.engine.connect() as conn:
            row = conn.execute(
                market_categories.select().where(market_categories.c.market_id == market_id)
            ).mappings().first()
        return row["category"] if row else None

    def save_market_category(self, market_id: str, category: str) -> None:
        """Cache a market's category classification."""
        row = {
            "market_id": market_id,
            "category": category,
            "classified_at": datetime.now().isoformat(),
        }
        self._safe_write("save_market_category", lambda conn: conn.execute(
            market_categories.insert().prefix_with("OR REPLACE"), row,
        ))

    # ── Calibration Profiles ──────────────────────────────────────

    def save_calibration_profile(
        self, run_id: str, category: str, offset: float, sample_size: int
    ) -> None:
        """Save a per-category calibration offset for a backtest run."""
        row = {
            "id": f"cp_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "category": category,
            "offset": offset,
            "sample_size": sample_size,
            "created_at": datetime.now().isoformat(),
        }
        self._safe_write("save_calibration_profile", lambda conn: conn.execute(
            calibration_profiles.insert().prefix_with("OR REPLACE"), row,
        ))

    def load_calibration_profiles(self, run_id: str) -> Dict[str, Dict[str, Any]]:
        """Load all category offsets for a run. Returns {category: {offset, sample_size}}."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                calibration_profiles.select().where(calibration_profiles.c.run_id == run_id)
            ).mappings().all()
        return {
            row["category"]: {"offset": row["offset"], "sample_size": row["sample_size"]}
            for row in rows
        }

    def get_latest_completed_run_id(self) -> Optional[str]:
        """Return the ID of the most recent COMPLETED backtest run, or None."""
        with self.engine.connect() as conn:
            row = conn.execute(
                backtest_runs.select()
                .where(backtest_runs.c.status == "COMPLETED")
                .order_by(backtest_runs.c.started_at.desc())
                .limit(1)
            ).mappings().first()
        return row["id"] if row else None

    # ── Prediction Runs ───────────────────────────────────────────

    def save_prediction_run(self, run: PredictionRun) -> None:
        """Save or update a prediction run."""
        d = run.to_dict()
        # Serialize nested dicts as JSON
        for key in ("market", "scenario", "sentiment", "signal"):
            if d.get(key) is not None:
                d[key] = json.dumps(d[key])
        self._safe_write("save_prediction_run", lambda conn: conn.execute(
            prediction_runs.insert().prefix_with("OR REPLACE"), d,
        ))

    def get_prediction_run(self, run_id: str) -> Optional[PredictionRun]:
        """Get a prediction run by ID."""
        with self.engine.connect() as conn:
            row = conn.execute(
                prediction_runs.select().where(prediction_runs.c.run_id == run_id)
            ).mappings().first()
        if row is None:
            return None
        return self._row_to_prediction_run(row)

    def list_prediction_runs(self, limit: int = 50) -> List[PredictionRun]:
        """List prediction runs, most recent first."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                prediction_runs.select()
                .order_by(prediction_runs.c.created_at.desc())
                .limit(limit)
            ).mappings().all()
        return [self._row_to_prediction_run(r) for r in rows]

    def delete_prediction_run(self, run_id: str) -> bool:
        """Delete a prediction run. Returns True if deleted."""
        deleted = []
        def _do_delete(conn):
            result = conn.execute(
                prediction_runs.delete().where(prediction_runs.c.run_id == run_id)
            )
            deleted.append(result.rowcount > 0)
        self._safe_write("delete_prediction_run", _do_delete)
        return deleted[0] if deleted else False

    @staticmethod
    def _row_to_prediction_run(row: Any) -> PredictionRun:
        d = dict(row)
        for key in ("market", "scenario", "sentiment", "signal"):
            if d.get(key):
                d[key] = json.loads(d[key])
        return PredictionRun.from_dict(d)
