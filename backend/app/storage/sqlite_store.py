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
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine

from ..models.backtest import BacktestResult, BacktestRun
from ..models.position import PaperOrder, PaperPosition

logger = logging.getLogger(__name__)

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
        logger.info("SQLiteStore initialized: %s (WAL mode)", db_path)

    # ── Backtest Runs ────────────────────────────────────────────────

    def save_backtest_run(self, run: BacktestRun) -> None:
        d = run.to_dict()
        d["config"] = json.dumps(d["config"]) if d["config"] else None
        d["metrics"] = json.dumps(d["metrics"]) if d["metrics"] else None
        with self.engine.connect() as conn:
            conn.execute(
                backtest_runs.insert().prefix_with("OR REPLACE"),
                d,
            )
            conn.commit()

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
        with self.engine.connect() as conn:
            conn.execute(
                backtest_runs.update().where(backtest_runs.c.id == run_id).values(**updates)
            )
            conn.commit()

    @staticmethod
    def _row_to_backtest_run(row: Any) -> BacktestRun:
        d = dict(row)
        d["config"] = json.loads(d["config"]) if d.get("config") else {}
        d["metrics"] = json.loads(d["metrics"]) if d.get("metrics") else None
        return BacktestRun.from_dict(d)

    # ── Backtest Results ─────────────────────────────────────────────

    def save_backtest_result(self, result: BacktestResult) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                backtest_results.insert().prefix_with("OR REPLACE"),
                result.to_dict(),
            )
            conn.commit()

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
        with self.engine.connect() as conn:
            conn.execute(
                paper_orders.insert().prefix_with("OR REPLACE"),
                order.to_dict(),
            )
            conn.commit()

    def get_orders(self) -> List[PaperOrder]:
        with self.engine.connect() as conn:
            rows = conn.execute(paper_orders.select()).mappings().all()
        return [PaperOrder.from_dict(dict(r)) for r in rows]

    # ── Paper Positions ──────────────────────────────────────────────

    def save_paper_position(self, position: PaperPosition) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                paper_positions.insert().prefix_with("OR REPLACE"),
                position.to_dict(),
            )
            conn.commit()

    def get_positions(self) -> List[PaperPosition]:
        with self.engine.connect() as conn:
            rows = conn.execute(paper_positions.select()).mappings().all()
        return [PaperPosition.from_dict(dict(r)) for r in rows]
