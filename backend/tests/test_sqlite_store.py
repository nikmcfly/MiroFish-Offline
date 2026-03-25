"""
Tests for app.storage.sqlite_store.SQLiteStore
"""

from app.models.backtest import BacktestRun, BacktestResult, BacktestRunStatus
from app.models.position import PaperOrder, PaperPosition, PositionStatus
from sqlalchemy import text


class TestSaveAndGetBacktestRun:

    def test_save_and_get_backtest_run(self, sqlite_store):
        run = BacktestRun(
            id="bt_test001",
            status=BacktestRunStatus.RUNNING.value,
            config={"num_markets": 10},
            total_markets=10,
        )
        sqlite_store.save_backtest_run(run)

        loaded = sqlite_store.get_backtest_run("bt_test001")
        assert loaded is not None
        assert loaded.id == "bt_test001"
        assert loaded.status == BacktestRunStatus.RUNNING.value
        assert loaded.config == {"num_markets": 10}
        assert loaded.total_markets == 10

    def test_get_nonexistent_run_returns_none(self, sqlite_store):
        assert sqlite_store.get_backtest_run("nonexistent") is None


class TestListBacktestRunsOrdered:

    def test_list_backtest_runs_ordered(self, sqlite_store):
        run_a = BacktestRun(id="bt_a", started_at="2025-01-01T00:00:00")
        run_b = BacktestRun(id="bt_b", started_at="2025-06-01T00:00:00")
        run_c = BacktestRun(id="bt_c", started_at="2025-03-01T00:00:00")

        sqlite_store.save_backtest_run(run_a)
        sqlite_store.save_backtest_run(run_b)
        sqlite_store.save_backtest_run(run_c)

        runs = sqlite_store.list_backtest_runs()
        assert len(runs) == 3
        # Should be ordered by started_at descending
        assert runs[0].id == "bt_b"
        assert runs[1].id == "bt_c"
        assert runs[2].id == "bt_a"


class TestUpdateBacktestRun:

    def test_update_backtest_run(self, sqlite_store):
        run = BacktestRun(id="bt_upd", status=BacktestRunStatus.PENDING.value)
        sqlite_store.save_backtest_run(run)

        sqlite_store.update_backtest_run(
            "bt_upd",
            status=BacktestRunStatus.COMPLETED.value,
            metrics={"accuracy": 0.75},
            completed_markets=5,
        )

        loaded = sqlite_store.get_backtest_run("bt_upd")
        assert loaded.status == BacktestRunStatus.COMPLETED.value
        assert loaded.metrics == {"accuracy": 0.75}
        assert loaded.completed_markets == 5


class TestBacktestResults:

    def test_save_and_get_backtest_result(self, sqlite_store):
        # Need a parent run first
        run = BacktestRun(id="bt_res_run")
        sqlite_store.save_backtest_run(run)

        result = BacktestResult(
            id="btr_001",
            run_id="bt_res_run",
            market_id="mkt_abc",
            market_title="Test Market",
            predicted_prob=0.70,
            market_prob=0.55,
            actual_outcome="YES",
            signal_direction="BUY_YES",
            edge=0.15,
            brier_score=0.09,
            correct=1,
        )
        sqlite_store.save_backtest_result(result)

        results = sqlite_store.get_results_by_run("bt_res_run")
        assert len(results) == 1
        r = results[0]
        assert r.id == "btr_001"
        assert r.market_id == "mkt_abc"
        assert r.predicted_prob == 0.70
        assert r.correct == 1

    def test_get_results_by_run(self, sqlite_store):
        run = BacktestRun(id="bt_multi")
        sqlite_store.save_backtest_run(run)

        for i in range(5):
            result = BacktestResult(
                id=f"btr_m{i}",
                run_id="bt_multi",
                market_id=f"mkt_{i}",
            )
            sqlite_store.save_backtest_result(result)

        results = sqlite_store.get_results_by_run("bt_multi")
        assert len(results) == 5

        # Different run should return empty
        assert sqlite_store.get_results_by_run("bt_other") == []

    def test_get_completed_market_ids(self, sqlite_store):
        run = BacktestRun(id="bt_cids")
        sqlite_store.save_backtest_run(run)

        for mid in ["mkt_a", "mkt_b", "mkt_c"]:
            result = BacktestResult(
                id=f"btr_{mid}",
                run_id="bt_cids",
                market_id=mid,
            )
            sqlite_store.save_backtest_result(result)

        ids = sqlite_store.get_completed_market_ids("bt_cids")
        assert set(ids) == {"mkt_a", "mkt_b", "mkt_c"}


class TestHasActiveBacktest:

    def test_no_active_backtest(self, sqlite_store):
        assert sqlite_store.has_active_backtest() is None

    def test_running_backtest_detected(self, sqlite_store):
        run = BacktestRun(id="bt_active", status="RUNNING")
        sqlite_store.save_backtest_run(run)
        assert sqlite_store.has_active_backtest() == "bt_active"

    def test_completed_not_detected(self, sqlite_store):
        run = BacktestRun(id="bt_done", status="COMPLETED")
        sqlite_store.save_backtest_run(run)
        assert sqlite_store.has_active_backtest() is None


class TestPaperOrders:

    def test_save_and_get_paper_order(self, sqlite_store):
        order = PaperOrder(
            id="ord_test001",
            market_id="mkt_xyz",
            signal_id="sig_001",
            side="BUY_YES",
            outcome="Yes",
            size=10.0,
            fill_price=0.62,
            slippage=0.015,
        )
        sqlite_store.save_paper_order(order)

        orders = sqlite_store.get_orders()
        assert len(orders) == 1
        o = orders[0]
        assert o.id == "ord_test001"
        assert o.side == "BUY_YES"
        assert o.fill_price == 0.62


class TestPaperPositions:

    def test_save_and_get_paper_position(self, sqlite_store):
        # Save the order first (FK dependency)
        order = PaperOrder(id="ord_pos_test", market_id="mkt_pos")
        sqlite_store.save_paper_order(order)

        position = PaperPosition(
            id="pos_test001",
            order_id="ord_pos_test",
            market_id="mkt_pos",
            outcome="Yes",
            entry_price=0.60,
            cost_basis=6.0,
            status=PositionStatus.OPEN.value,
        )
        sqlite_store.save_paper_position(position)

        positions = sqlite_store.get_positions()
        assert len(positions) == 1
        p = positions[0]
        assert p.id == "pos_test001"
        assert p.entry_price == 0.60
        assert p.status == "OPEN"


class TestWALMode:

    def test_wal_mode_enabled(self, sqlite_store):
        with sqlite_store.engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result == "wal"
