"""
Tests for category-specific calibration in calibrator.
"""

from app.models.backtest import BacktestRun, BacktestResult
from app.services.calibrator import Calibrator


def _make_results(category, n, predicted_prob, actual_outcome):
    """Helper to create n BacktestResult instances."""
    return [
        BacktestResult(
            id=f"btr_{category}_{i}",
            run_id="bt_cal",
            market_id=f"mkt_{category}_{i}",
            predicted_prob=predicted_prob,
            actual_outcome=actual_outcome,
            category=category,
        )
        for i in range(n)
    ]


class TestFitCategoryOffsets:

    def test_computes_offsets(self, sqlite_store):
        """fit_category_offsets computes mean(pred) - mean(actual) per category."""
        # Politics: predicted=0.7, actual=YES (1.0) → offset = 0.7 - 1.0 = -0.3
        results = _make_results("politics", 25, 0.7, "YES")
        # Crypto: predicted=0.8, actual=NO (0.0) → offset = 0.8 - 0.0 = 0.8
        results += _make_results("crypto", 25, 0.8, "NO")

        calibrator = Calibrator(store=sqlite_store)
        offsets = calibrator.fit_category_offsets(results)

        assert "politics" in offsets
        assert "crypto" in offsets
        assert abs(offsets["politics"] - (-0.3)) < 0.001
        assert abs(offsets["crypto"] - 0.8) < 0.001

    def test_skips_small_categories(self, sqlite_store):
        """Categories with < 20 results are skipped."""
        results = _make_results("politics", 25, 0.7, "YES")
        results += _make_results("sports", 5, 0.6, "NO")  # Too few

        calibrator = Calibrator(store=sqlite_store)
        offsets = calibrator.fit_category_offsets(results)

        assert "politics" in offsets
        assert "sports" not in offsets

    def test_empty_results(self, sqlite_store):
        """Empty results produce empty offsets."""
        calibrator = Calibrator(store=sqlite_store)
        offsets = calibrator.fit_category_offsets([])
        assert offsets == {}


class TestSaveAndLoadProfiles:

    def test_save_and_load_profiles(self, sqlite_store):
        """Profiles round-trip through SQLite."""
        run = BacktestRun(id="bt_cal_prof")
        sqlite_store.save_backtest_run(run)

        results = _make_results("politics", 25, 0.7, "YES")
        calibrator = Calibrator(store=sqlite_store)
        offsets = {"politics": -0.3, "crypto": 0.8}

        calibrator.save_profiles("bt_cal_prof", offsets, results)

        loaded = calibrator.load_profiles("bt_cal_prof")
        assert "politics" in loaded
        assert "crypto" in loaded
        assert abs(loaded["politics"]["offset"] - (-0.3)) < 0.001
        assert abs(loaded["crypto"]["offset"] - 0.8) < 0.001


class TestTransformWithCategory:

    def test_applies_offset(self, sqlite_store):
        """transform_with_category subtracts the category offset."""
        calibrator = Calibrator(store=sqlite_store)
        profiles = {"politics": {"offset": 0.1, "sample_size": 30}}

        # prob=0.7, offset=0.1 → adjusted = 0.7 - 0.1 = 0.6
        result = calibrator.transform_with_category(0.7, "politics", profiles)
        assert abs(result - 0.6) < 0.001

    def test_clamps_to_valid_range(self, sqlite_store):
        """Adjusted probability is clamped to [0.01, 0.99]."""
        calibrator = Calibrator(store=sqlite_store)
        profiles = {"crypto": {"offset": 0.95, "sample_size": 30}}

        result = calibrator.transform_with_category(0.1, "crypto", profiles)
        assert result == 0.01  # 0.1 - 0.95 = -0.85 → clamped to 0.01

    def test_unknown_category_passthrough(self, sqlite_store):
        """Unknown category returns probability unchanged."""
        calibrator = Calibrator(store=sqlite_store)
        profiles = {"politics": {"offset": 0.1, "sample_size": 30}}

        result = calibrator.transform_with_category(0.7, "sports", profiles)
        assert result == 0.7
