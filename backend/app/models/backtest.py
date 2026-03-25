"""
Backtest data models for historical prediction evaluation.

Schema:
    BacktestRun    — one full backtest execution across N markets
    BacktestResult — per-market outcome within a run
    BacktestMetrics — aggregate statistics for a completed run
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class BacktestRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPUTING_METRICS = "COMPUTING_METRICS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class BacktestRun:
    """One full backtest execution across N markets."""

    id: str = field(default_factory=lambda: f"bt_{uuid.uuid4().hex[:12]}")
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = BacktestRunStatus.PENDING.value
    metrics: Optional[Dict[str, Any]] = None
    total_markets: int = 0
    completed_markets: int = 0
    failed_markets: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "config": self.config,
            "status": self.status,
            "metrics": self.metrics,
            "total_markets": self.total_markets,
            "completed_markets": self.completed_markets,
            "failed_markets": self.failed_markets,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestRun":
        return cls(
            id=data["id"],
            started_at=data.get("started_at", ""),
            config=data.get("config", {}),
            status=data.get("status", BacktestRunStatus.PENDING.value),
            metrics=data.get("metrics"),
            total_markets=data.get("total_markets", 0),
            completed_markets=data.get("completed_markets", 0),
            failed_markets=data.get("failed_markets", 0),
        )


@dataclass
class BacktestResult:
    """Per-market outcome within a backtest run."""

    id: str = field(default_factory=lambda: f"btr_{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    market_id: str = ""
    market_title: str = ""
    predicted_prob: float = 0.0
    market_prob: float = 0.0
    actual_outcome: Optional[str] = None
    signal_direction: str = "HOLD"
    edge: float = 0.0
    brier_score: Optional[float] = None
    correct: Optional[int] = None  # 0 or 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "market_id": self.market_id,
            "market_title": self.market_title,
            "predicted_prob": self.predicted_prob,
            "market_prob": self.market_prob,
            "actual_outcome": self.actual_outcome,
            "signal_direction": self.signal_direction,
            "edge": self.edge,
            "brier_score": self.brier_score,
            "correct": self.correct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestResult":
        return cls(
            id=data["id"],
            run_id=data.get("run_id", ""),
            market_id=data.get("market_id", ""),
            market_title=data.get("market_title", ""),
            predicted_prob=data.get("predicted_prob", 0.0),
            market_prob=data.get("market_prob", 0.0),
            actual_outcome=data.get("actual_outcome"),
            signal_direction=data.get("signal_direction", "HOLD"),
            edge=data.get("edge", 0.0),
            brier_score=data.get("brier_score"),
            correct=data.get("correct"),
        )


@dataclass
class BacktestMetrics:
    """Aggregate statistics for a completed backtest run."""

    accuracy: float = 0.0
    brier_score: float = 0.0
    roi: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calibration_rmse: float = 0.0
    markets_tested: int = 0
    avg_edge: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "brier_score": round(self.brier_score, 4),
            "roi": round(self.roi, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "calibration_rmse": round(self.calibration_rmse, 4),
            "markets_tested": self.markets_tested,
            "avg_edge": round(self.avg_edge, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestMetrics":
        return cls(
            accuracy=data.get("accuracy", 0.0),
            brier_score=data.get("brier_score", 0.0),
            roi=data.get("roi", 0.0),
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            calibration_rmse=data.get("calibration_rmse", 0.0),
            markets_tested=data.get("markets_tested", 0),
            avg_edge=data.get("avg_edge", 0.0),
        )
