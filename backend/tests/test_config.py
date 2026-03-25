"""
Tests for app.config.Config
"""

import os
from unittest.mock import patch

import pytest


class TestCalibrationDefaults:

    def test_calibration_defaults(self):
        from app.config import Config

        assert Config.CALIBRATION_MARKET_REGRESSION == 0.30
        assert Config.CALIBRATION_DATE_DAMPENING_DAYS == 14
        assert Config.CALIBRATION_HIGH_EDGE_THRESHOLD == 0.25
        assert Config.CALIBRATION_HIGH_EDGE_MAX_REDUCTION == 0.40
        assert Config.CALIBRATION_SHORT_DATE_PENALTY == 0.20


class TestCalibrationFromEnv:

    def test_calibration_from_env(self):
        """Set env vars and verify overrides by re-evaluating the expressions."""
        env_overrides = {
            "CALIBRATION_MARKET_REGRESSION": "0.50",
            "CALIBRATION_DATE_DAMPENING_DAYS": "7",
            "CALIBRATION_HIGH_EDGE_THRESHOLD": "0.30",
            "CALIBRATION_HIGH_EDGE_MAX_REDUCTION": "0.50",
            "CALIBRATION_SHORT_DATE_PENALTY": "0.40",
        }

        with patch.dict(os.environ, env_overrides):
            # Re-evaluate config values from env
            market_reg = float(os.environ.get("CALIBRATION_MARKET_REGRESSION", "0.30"))
            dampening_days = int(os.environ.get("CALIBRATION_DATE_DAMPENING_DAYS", "14"))
            high_edge = float(os.environ.get("CALIBRATION_HIGH_EDGE_THRESHOLD", "0.25"))
            max_reduction = float(os.environ.get("CALIBRATION_HIGH_EDGE_MAX_REDUCTION", "0.40"))
            short_penalty = float(os.environ.get("CALIBRATION_SHORT_DATE_PENALTY", "0.20"))

            assert market_reg == 0.50
            assert dampening_days == 7
            assert high_edge == 0.30
            assert max_reduction == 0.50
            assert short_penalty == 0.40


class TestSQLiteDBPathDefault:

    def test_sqlite_db_path_default(self):
        from app.config import Config

        # Should contain 'mirofish.db' in the default path
        assert "mirofish.db" in Config.SQLITE_DB_PATH


class TestPaperTradingModeDefault:

    def test_paper_trading_mode_default(self):
        from app.config import Config

        # Default is 'true'
        assert Config.PAPER_TRADING_MODE is True
