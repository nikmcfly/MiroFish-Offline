"""
Tests for app.storage.sqlite_store.SQLiteStore
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.backtest import BacktestRun, BacktestResult, BacktestRunStatus
from app.models.position import PaperOrder, PaperPosition, PositionStatus
from app.storage.sqlite_store import StorageError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


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


class TestMarketCategories:

    def test_save_and_get_market_category(self, sqlite_store):
        sqlite_store.save_market_category("mkt_cat_001", "politics")
        assert sqlite_store.get_market_category("mkt_cat_001") == "politics"

    def test_get_nonexistent_returns_none(self, sqlite_store):
        assert sqlite_store.get_market_category("nonexistent") is None

    def test_upsert_overwrites(self, sqlite_store):
        sqlite_store.save_market_category("mkt_cat_002", "sports")
        sqlite_store.save_market_category("mkt_cat_002", "entertainment")
        assert sqlite_store.get_market_category("mkt_cat_002") == "entertainment"


class TestCalibrationProfiles:

    def test_save_and_load_profiles(self, sqlite_store):
        run = BacktestRun(id="bt_cp_test")
        sqlite_store.save_backtest_run(run)

        sqlite_store.save_calibration_profile("bt_cp_test", "politics", -0.05, 30)
        sqlite_store.save_calibration_profile("bt_cp_test", "crypto", 0.12, 25)

        profiles = sqlite_store.load_calibration_profiles("bt_cp_test")
        assert len(profiles) == 2
        assert profiles["politics"]["offset"] == -0.05
        assert profiles["politics"]["sample_size"] == 30
        assert profiles["crypto"]["offset"] == 0.12

    def test_empty_profiles(self, sqlite_store):
        profiles = sqlite_store.load_calibration_profiles("nonexistent")
        assert profiles == {}


class TestLatestCompletedRunId:

    def test_returns_latest_completed(self, sqlite_store):
        sqlite_store.save_backtest_run(BacktestRun(
            id="bt_old", started_at="2025-01-01T00:00:00", status="COMPLETED"
        ))
        sqlite_store.save_backtest_run(BacktestRun(
            id="bt_new", started_at="2025-06-01T00:00:00", status="COMPLETED"
        ))
        sqlite_store.save_backtest_run(BacktestRun(
            id="bt_running", started_at="2025-07-01T00:00:00", status="RUNNING"
        ))
        assert sqlite_store.get_latest_completed_run_id() == "bt_new"

    def test_returns_none_when_no_completed(self, sqlite_store):
        sqlite_store.save_backtest_run(BacktestRun(id="bt_pending", status="PENDING"))
        assert sqlite_store.get_latest_completed_run_id() is None


class TestBacktestResultCategoryColumns:

    def test_category_columns_persisted(self, sqlite_store):
        run = BacktestRun(id="bt_cat_col")
        sqlite_store.save_backtest_run(run)

        result = BacktestResult(
            id="btr_cat_001", run_id="bt_cat_col",
            market_id="mkt_x", category="sports", confidence_tier="HIGH",
        )
        sqlite_store.save_backtest_result(result)

        results = sqlite_store.get_results_by_run("bt_cat_col")
        assert len(results) == 1
        assert results[0].category == "sports"
        assert results[0].confidence_tier == "HIGH"


class TestDiskFullErrorHandling:

    def test_disk_full_raises_storage_error(self, sqlite_store):
        """Disk I/O errors during writes raise StorageError."""
        run = BacktestRun(id="bt_disk_test")

        with patch.object(sqlite_store.engine, "connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.side_effect = OperationalError(
                "INSERT", {}, Exception("disk I/O error")
            )
            mock_connect.return_value = mock_conn

            with pytest.raises(StorageError, match="Disk I/O error"):
                sqlite_store.save_backtest_run(run)

    def test_non_disk_error_propagates_as_operational(self, sqlite_store):
        """Non-disk OperationalErrors propagate unchanged."""
        run = BacktestRun(id="bt_other_err")

        with patch.object(sqlite_store.engine, "connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.side_effect = OperationalError(
                "INSERT", {}, Exception("table not found")
            )
            mock_connect.return_value = mock_conn

            with pytest.raises(OperationalError):
                sqlite_store.save_backtest_run(run)


class TestWALMode:

    def test_wal_mode_enabled(self, sqlite_store):
        with sqlite_store.engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result == "wal"
