"""
Calibration service — fits Platt scaling or isotonic regression on backtest results
to improve probability estimates.
"""

import base64
import hashlib
import hmac
import pickle
from typing import Optional, List

import numpy as np
from sklearn.linear_model import LogisticRegression

from ..config import Config
from ..models.backtest import BacktestResult
from ..storage.sqlite_store import SQLiteStore
from ..utils.logger import get_logger

logger = get_logger('mirofish.calibrator')

MIN_DATAPOINTS = 20

# HMAC key derived from the app secret — used to sign/verify pickle blobs
_HMAC_KEY = hashlib.sha256(Config.SECRET_KEY.encode()).digest()


def _sign_blob(blob: bytes) -> str:
    """Serialize blob + HMAC signature as base64."""
    sig = hmac.new(_HMAC_KEY, blob, hashlib.sha256).digest()
    # Format: base64(signature + blob)
    return base64.b64encode(sig + blob).decode('ascii')


def _verify_and_load(data: str) -> bytes:
    """Verify HMAC signature and return raw blob. Raises ValueError on tampering."""
    raw = base64.b64decode(data)
    if len(raw) < 32:
        raise ValueError("Calibration model data too short — corrupt or tampered")
    sig = raw[:32]
    blob = raw[32:]
    expected = hmac.new(_HMAC_KEY, blob, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Calibration model HMAC verification failed — data may be tampered")
    return blob


class Calibrator:
    """Probability calibration via Platt scaling (logistic regression)."""

    def __init__(self, store: Optional[SQLiteStore] = None):
        self.store = store
        self.model: Optional[LogisticRegression] = None

    def fit(self, results: List[BacktestResult]) -> bool:
        """
        Fit calibration model on backtest results.

        Args:
            results: List of BacktestResult with predicted_prob and actual_outcome

        Returns:
            True if model was fitted, False if insufficient data
        """
        # Filter to results with valid data
        valid = [
            r for r in results
            if r.predicted_prob is not None and r.actual_outcome is not None
        ]

        if len(valid) < MIN_DATAPOINTS:
            logger.warning(
                f"Insufficient data for calibration: {len(valid)} < {MIN_DATAPOINTS}. Skipping."
            )
            return False

        X = np.array([r.predicted_prob for r in valid]).reshape(-1, 1)
        y = np.array([1.0 if r.actual_outcome == 'YES' else 0.0 for r in valid])

        # Check for degenerate data (all same class)
        if len(np.unique(y)) < 2:
            logger.warning("Degenerate data: all outcomes are the same class. Skipping calibration.")
            return False

        self.model = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000)
        self.model.fit(X, y)

        logger.info(f"Calibration model fitted on {len(valid)} data points")
        return True

    def transform(self, probability: float) -> float:
        """
        Apply fitted calibration model to a raw probability.

        Args:
            probability: Raw probability from the pipeline

        Returns:
            Calibrated probability (or original if no model fitted)
        """
        if self.model is None:
            return probability

        X = np.array([[probability]])
        calibrated = self.model.predict_proba(X)[0, 1]
        return float(calibrated)

    def save(self, run_id: str) -> None:
        """Persist fitted model to SQLite as an HMAC-signed pickle blob."""
        if self.model is None or self.store is None:
            return

        blob = pickle.dumps(self.model)
        model_data = _sign_blob(blob)

        run = self.store.get_backtest_run(run_id)
        if run:
            config = run.config or {}
            config['calibration_model'] = model_data
            self.store.update_backtest_run(run_id, config=config)
            logger.info(f"Calibration model saved for run {run_id}")

    def load(self, run_id: str) -> bool:
        """Load a previously fitted model from SQLite, verifying HMAC signature."""
        if self.store is None:
            return False

        run = self.store.get_backtest_run(run_id)
        if not run or not run.config:
            return False

        model_data = run.config.get('calibration_model')
        if not model_data:
            return False

        try:
            blob = _verify_and_load(model_data)
        except ValueError as e:
            logger.error(f"Calibration model verification failed for run {run_id}: {e}")
            return False

        self.model = pickle.loads(blob)
        logger.info(f"Calibration model loaded from run {run_id}")
        return True
