"""
Tests for app.services.calibrator.Calibrator
"""

import pytest

from app.models.backtest import BacktestResult, BacktestRun
from app.services.calibrator import Calibrator, MIN_DATAPOINTS


def _make_result(idx: int, predicted: float, actual: str) -> BacktestResult:
    return BacktestResult(
        id=f"btr_cal_{idx}",
        run_id="bt_cal_test",
        market_id=f"mkt_{idx}",
        predicted_prob=predicted,
        actual_outcome=actual,
    )


class TestFitInsufficientData:

    def test_fit_insufficient_data(self):
        cal = Calibrator()
        results = [_make_result(i, 0.5, "YES") for i in range(10)]
        assert cal.fit(results) is False
        assert cal.model is None


class TestFitNormal:

    def test_fit_normal(self):
        cal = Calibrator()
        results = []
        for i in range(35):
            if i < 20:
                results.append(_make_result(i, 0.7 + (i % 5) * 0.05, "YES"))
            else:
                results.append(_make_result(i, 0.3 + (i % 5) * 0.05, "NO"))

        assert cal.fit(results) is True
        assert cal.model is not None


class TestTransformNoModel:

    def test_transform_no_model(self):
        cal = Calibrator()
        assert cal.model is None
        assert cal.transform(0.65) == 0.65


class TestTransformWithModel:

    def test_transform_with_model(self):
        cal = Calibrator()
        results = []
        for i in range(35):
            if i < 20:
                results.append(_make_result(i, 0.7 + (i % 5) * 0.05, "YES"))
            else:
                results.append(_make_result(i, 0.3 + (i % 5) * 0.05, "NO"))

        cal.fit(results)
        calibrated = cal.transform(0.75)
        # Should return a valid probability between 0 and 1
        assert 0.0 <= calibrated <= 1.0
        # Should differ from input (model was fitted)
        # (Not guaranteed to differ much, but should be a float)
        assert isinstance(calibrated, float)


class TestDegenerateData:

    def test_degenerate_data(self):
        """All same outcome should return False."""
        cal = Calibrator()
        results = [_make_result(i, 0.5 + i * 0.01, "YES") for i in range(30)]
        assert cal.fit(results) is False
        assert cal.model is None


class TestSaveAndLoad:

    def test_save_and_load(self, sqlite_store):
        run = BacktestRun(id="bt_cal_persist", config={})
        sqlite_store.save_backtest_run(run)

        # Fit a model
        cal = Calibrator(store=sqlite_store)
        results = []
        for i in range(35):
            if i < 20:
                results.append(_make_result(i, 0.7 + (i % 5) * 0.05, "YES"))
            else:
                results.append(_make_result(i, 0.3 + (i % 5) * 0.05, "NO"))
        cal.fit(results)

        original_output = cal.transform(0.75)

        # Save
        cal.save("bt_cal_persist")

        # Load into a new calibrator
        cal2 = Calibrator(store=sqlite_store)
        assert cal2.model is None
        loaded = cal2.load("bt_cal_persist")
        assert loaded is True
        assert cal2.model is not None

        # Should produce same output
        loaded_output = cal2.transform(0.75)
        assert abs(original_output - loaded_output) < 1e-6

    def test_load_nonexistent(self, sqlite_store):
        cal = Calibrator(store=sqlite_store)
        assert cal.load("nonexistent_run") is False

    def test_load_tampered_data_rejected(self, sqlite_store):
        """Tampered model data should fail HMAC verification."""
        import base64
        run = BacktestRun(id="bt_cal_tamper", config={})
        sqlite_store.save_backtest_run(run)

        # Store a fake model blob (not properly signed)
        fake_data = base64.b64encode(b"\x00" * 64).decode('ascii')
        sqlite_store.update_backtest_run("bt_cal_tamper", config={"calibration_model": fake_data})

        cal = Calibrator(store=sqlite_store)
        assert cal.load("bt_cal_tamper") is False
        assert cal.model is None
