"""
Tests for app.services.paper_trader.PaperTrader
"""

from unittest.mock import patch

import pytest

from app.models.prediction import PredictionMarket, TradingSignal
from app.services.paper_trader import PaperTrader


def _make_signal(direction: str) -> TradingSignal:
    return TradingSignal(
        direction=direction,
        edge=0.15,
        confidence=0.80,
        reasoning="Test signal",
        simulated_probability=0.70,
        market_probability=0.55,
    )


class TestExecuteBuyYes:

    def test_execute_buy_yes(self, sqlite_store, sample_market):
        trader = PaperTrader(sqlite_store)
        signal = _make_signal("BUY_YES")

        with patch("app.services.paper_trader.random.uniform", return_value=0.015):
            order = trader.execute(signal, sample_market, signal_id="sig_001")

        assert order is not None
        assert order.side == "BUY_YES"
        assert order.outcome == "Yes"
        assert order.size == 10.0
        assert order.slippage == 0.015

        # Verify persisted
        orders = sqlite_store.get_orders()
        assert len(orders) == 1

        positions = sqlite_store.get_positions()
        assert len(positions) == 1
        assert positions[0].order_id == order.id
        assert positions[0].outcome == "Yes"


class TestExecuteBuyNo:

    def test_execute_buy_no(self, sqlite_store, sample_market):
        trader = PaperTrader(sqlite_store)
        signal = _make_signal("BUY_NO")

        with patch("app.services.paper_trader.random.uniform", return_value=0.015):
            order = trader.execute(signal, sample_market, signal_id="sig_002")

        assert order is not None
        assert order.side == "BUY_NO"
        assert order.outcome == "No"


class TestExecuteHold:

    def test_execute_hold(self, sqlite_store, sample_market):
        trader = PaperTrader(sqlite_store)
        signal = _make_signal("HOLD")

        order = trader.execute(signal, sample_market)
        assert order is None

        assert sqlite_store.get_orders() == []
        assert sqlite_store.get_positions() == []


class TestSlippageRange:

    def test_slippage_range(self, sqlite_store, sample_market):
        """Verify slippage is in the 1-2% range."""
        trader = PaperTrader(sqlite_store)
        signal = _make_signal("BUY_YES")

        slippages = []
        for _ in range(50):
            order = trader.execute(signal, sample_market, signal_id="sig_slip")
            slippages.append(order.slippage)

        assert all(0.01 <= s <= 0.02 for s in slippages)


class TestSQLiteWrite:

    def test_sqlite_write(self, sqlite_store, sample_market):
        """Verify records are actually persisted in SQLite."""
        trader = PaperTrader(sqlite_store)
        signal = _make_signal("BUY_YES")

        with patch("app.services.paper_trader.random.uniform", return_value=0.015):
            order = trader.execute(signal, sample_market, signal_id="sig_write")

        orders = sqlite_store.get_orders()
        assert len(orders) == 1
        assert orders[0].market_id == sample_market.condition_id
        assert orders[0].signal_id == "sig_write"

        positions = sqlite_store.get_positions()
        assert len(positions) == 1
        assert positions[0].market_id == sample_market.condition_id
        assert positions[0].status == "OPEN"
        assert positions[0].cost_basis == pytest.approx(10.0 * order.fill_price)
