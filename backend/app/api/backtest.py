"""
Backtest API routes
"""

import threading
from flask import request, jsonify, current_app

from . import backtest_bp
from ..models.backtest import BacktestRun
from ..services.backtester import Backtester
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.backtest')

# Track running backtests to prevent concurrent starts
_running_backtests = {}
_lock = threading.Lock()

MAX_MARKETS = 500


@backtest_bp.route('/run', methods=['POST'])
def start_backtest():
    """
    Start a backtest run.

    Request JSON:
        {
            "num_markets": 50,
            "config_overrides": {}  (optional)
        }
    """
    try:
        store = current_app.extensions.get('sqlite')
        if store is None:
            return jsonify({"success": False, "error": "SQLite store not initialized"}), 503

        data = request.get_json() or {}
        num_markets = data.get('num_markets', 50)
        config_overrides = data.get('config_overrides', {})

        # Validate input
        if not isinstance(num_markets, int) or num_markets < 1:
            return jsonify({"success": False, "error": "num_markets must be a positive integer"}), 400
        num_markets = min(num_markets, MAX_MARKETS)

        # DB-level guard: works across processes (gunicorn)
        active_id = store.has_active_backtest()
        if active_id:
            return jsonify({
                "success": False,
                "error": "A backtest is already running",
                "active_run_id": active_id,
            }), 409

        with _lock:

            # Create run + register thread atomically inside the lock
            bt_run = BacktestRun(
                config=config_overrides,
                total_markets=num_markets,
            )
            store.save_backtest_run(bt_run)

            backtester = Backtester(store)

            def run_backtest():
                try:
                    backtester.run(
                        num_markets=num_markets,
                        config_overrides=config_overrides,
                        bt_run=bt_run,
                    )
                except Exception as e:
                    logger.error(f"Backtest thread failed: {e}", exc_info=True)
                finally:
                    with _lock:
                        _running_backtests.pop(bt_run.id, None)

            thread = threading.Thread(target=run_backtest, daemon=True)
            _running_backtests[bt_run.id] = thread
            thread.start()

        return jsonify({
            "success": True,
            "data": {
                "run_id": bt_run.id,
                "status": "started",
                "message": f"Backtest started with {num_markets} markets",
            },
        })

    except Exception as e:
        logger.error(f"Failed to start backtest: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@backtest_bp.route('/run/<run_id>', methods=['GET'])
def get_backtest_run(run_id: str):
    """Get backtest run status, results, and metrics."""
    try:
        store = current_app.extensions.get('sqlite')
        if store is None:
            return jsonify({"success": False, "error": "SQLite store not initialized"}), 503

        bt_run = store.get_backtest_run(run_id)
        if not bt_run:
            return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

        results = store.get_results_by_run(run_id)

        return jsonify({
            "success": True,
            "data": {
                **bt_run.to_dict(),
                "results": [r.to_dict() for r in results],
            },
        })

    except Exception as e:
        logger.error(f"Failed to get backtest run: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@backtest_bp.route('/runs', methods=['GET'])
def list_backtest_runs():
    """List all backtest runs."""
    try:
        store = current_app.extensions.get('sqlite')
        if store is None:
            return jsonify({"success": False, "error": "SQLite store not initialized"}), 503

        runs = store.list_backtest_runs()

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in runs],
            "count": len(runs),
        })

    except Exception as e:
        logger.error(f"Failed to list backtest runs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
