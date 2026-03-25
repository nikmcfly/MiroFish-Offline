"""
Paper trading service — simulates order execution for prediction market signals.
"""

import random
from typing import Optional

from ..models.prediction import PredictionMarket, TradingSignal
from ..models.position import PaperOrder, PaperPosition, PositionStatus
from ..storage.sqlite_store import SQLiteStore
from ..utils.logger import get_logger

logger = get_logger('mirofish.paper_trader')

DEFAULT_BET_SIZE = 10.0  # $10 per trade


class PaperTrader:
    """Simulates order execution with slippage for paper trading."""

    def __init__(self, store: SQLiteStore, bet_size: float = DEFAULT_BET_SIZE):
        self.store = store
        self.bet_size = bet_size

    def execute(
        self,
        signal: TradingSignal,
        market: PredictionMarket,
        signal_id: str = "",
    ) -> Optional[PaperOrder]:
        """
        Execute a paper trade based on a signal.

        Args:
            signal: Trading signal from prediction pipeline
            market: Market data
            signal_id: Optional reference to the prediction run

        Returns:
            PaperOrder if trade was executed, None for HOLD signals
        """
        if signal.direction == "HOLD":
            return None

        # Simulate 1-2% slippage
        slippage = random.uniform(0.01, 0.02)

        if signal.direction == "BUY_YES":
            base_price = market.prices[0] if market.prices else 0.5
            fill_price = min(base_price * (1 + slippage), 0.99)
            outcome = "Yes"
        else:  # BUY_NO
            base_price = market.prices[1] if len(market.prices) > 1 else 0.5
            fill_price = min(base_price * (1 + slippage), 0.99)
            outcome = "No"

        order = PaperOrder(
            market_id=market.condition_id,
            signal_id=signal_id,
            side=signal.direction,
            outcome=outcome,
            size=self.bet_size,
            fill_price=fill_price,
            slippage=slippage,
        )
        self.store.save_paper_order(order)

        position = PaperPosition(
            order_id=order.id,
            market_id=market.condition_id,
            outcome=outcome,
            entry_price=fill_price,
            cost_basis=self.bet_size * fill_price,
            status=PositionStatus.OPEN.value,
        )
        self.store.save_paper_position(position)

        logger.info(
            f"Paper trade: {signal.direction} {outcome} @ {fill_price:.4f} "
            f"(slippage {slippage:.2%}) for {market.title}"
        )
        return order
