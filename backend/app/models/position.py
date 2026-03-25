"""
Paper trading models for simulated order execution and position tracking.

Schema:
    PaperOrder    — a simulated order placed against a prediction market
    PaperPosition — the resulting position from a filled order
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class PaperOrder:
    """A simulated order placed against a prediction market."""

    id: str = field(default_factory=lambda: f"ord_{uuid.uuid4().hex[:12]}")
    market_id: str = ""
    signal_id: str = ""
    side: str = ""  # BUY_YES, BUY_NO
    outcome: str = ""
    size: float = 0.0
    fill_price: float = 0.0
    slippage: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "signal_id": self.signal_id,
            "side": self.side,
            "outcome": self.outcome,
            "size": self.size,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperOrder":
        return cls(
            id=data["id"],
            market_id=data.get("market_id", ""),
            signal_id=data.get("signal_id", ""),
            side=data.get("side", ""),
            outcome=data.get("outcome", ""),
            size=data.get("size", 0.0),
            fill_price=data.get("fill_price", 0.0),
            slippage=data.get("slippage", 0.0),
            created_at=data.get("created_at", ""),
        )


@dataclass
class PaperPosition:
    """The resulting position from a filled paper order."""

    id: str = field(default_factory=lambda: f"pos_{uuid.uuid4().hex[:12]}")
    order_id: str = ""
    market_id: str = ""
    outcome: str = ""
    entry_price: float = 0.0
    cost_basis: float = 0.0
    status: str = PositionStatus.OPEN.value
    resolved_pnl: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "market_id": self.market_id,
            "outcome": self.outcome,
            "entry_price": self.entry_price,
            "cost_basis": self.cost_basis,
            "status": self.status,
            "resolved_pnl": self.resolved_pnl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperPosition":
        return cls(
            id=data["id"],
            order_id=data.get("order_id", ""),
            market_id=data.get("market_id", ""),
            outcome=data.get("outcome", ""),
            entry_price=data.get("entry_price", 0.0),
            cost_basis=data.get("cost_basis", 0.0),
            status=data.get("status", PositionStatus.OPEN.value),
            resolved_pnl=data.get("resolved_pnl"),
        )
