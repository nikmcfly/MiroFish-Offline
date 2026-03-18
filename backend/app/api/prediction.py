"""
Prediction Market API routes
"""

import traceback
import threading
from flask import request, jsonify, current_app

from . import prediction_bp
from ..config import Config
from ..models.prediction import PredictionMarket, PredictionRunManager, PredictionRunStatus
from ..services.polymarket_client import PolymarketClient
from ..services.prediction_manager import PredictionManager
from ..storage.prediction_store import SQLitePredictionStore
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.prediction')


def _get_pred_store():
    """Get the prediction store — SQLite if available, JSON fallback."""
    sqlite_store = current_app.extensions.get('sqlite')
    if sqlite_store:
        return SQLitePredictionStore(sqlite_store)
    return PredictionRunManager


def _find_run(run_id: str):
    """Find a prediction run in SQLite first, then JSON fallback."""
    store = _get_pred_store()
    if isinstance(store, SQLitePredictionStore):
        run = store.get_run(run_id)
        if run:
            return run
        # Fall back to JSON for pre-migration runs
        return PredictionRunManager.get_run(run_id)
    return store.get_run(run_id)


# ============== Market Browsing ==============

@prediction_bp.route('/markets', methods=['GET'])
def get_markets():
    """
    Fetch active markets from Polymarket.

    Query params:
        min_volume: Minimum volume filter (default 10000)
        limit: Max results (default 50)
        search: Search query (optional)
    """
    try:
        min_volume = request.args.get('min_volume', 10000, type=float)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', None)

        client = PolymarketClient()
        markets = client.fetch_active_markets(
            min_volume=min_volume,
            limit=limit,
            search=search,
        )

        return jsonify({
            "success": True,
            "data": [m.to_dict() for m in markets],
            "count": len(markets),
        })

    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============== Prediction Runs ==============

@prediction_bp.route('/run', methods=['POST'])
def start_prediction_run():
    """
    Start a prediction run for a market.

    Request JSON:
        {
            "market": { ... PredictionMarket dict ... }
        }

    Returns run_id + task_id for polling.
    """
    try:
        data = request.get_json() or {}
        market_data = data.get('market')

        if not market_data:
            return jsonify({"success": False, "error": "market data required"}), 400

        market = PredictionMarket.from_dict(market_data)

        if not market.title:
            return jsonify({"success": False, "error": "market must have a title"}), 400

        # Capture store in request context (before thread starts)
        sqlite_store = current_app.extensions.get('sqlite')

        # Create run — use SQLite store if available, fall back to JSON files
        if sqlite_store:
            pred_store = SQLitePredictionStore(sqlite_store)
            run = pred_store.create_run()
        else:
            pred_store = PredictionRunManager
            run = PredictionRunManager.create_run()

        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="prediction_run",
            metadata={"run_id": run.run_id, "market_title": market.title},
        )

        def run_pipeline():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Starting prediction pipeline...",
                )

                def progress_callback(stage, message):
                    stage_progress = {
                        "fetching_market": 5,
                        "generating_scenario": 25,
                        "running_simulation": 60,
                        "analyzing": 85,
                        "completed": 100,
                    }
                    progress = stage_progress.get(stage, 50)
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=message,
                    )

                manager = PredictionManager(result_store=pred_store, sqlite_store=sqlite_store)
                result = manager.run_prediction(
                    market=market,
                    run=run,
                    progress_callback=progress_callback,
                )

                if result.status == PredictionRunStatus.COMPLETED:
                    task_manager.complete_task(task_id, result={
                        "run_id": result.run_id,
                        "status": "completed",
                        "signal": result.signal,
                    })
                else:
                    task_manager.fail_task(task_id, result.error or "Pipeline failed")

            except Exception as e:
                logger.error(f"Prediction pipeline failed: {e}", exc_info=True)
                task_manager.fail_task(task_id, str(e))

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "run_id": run.run_id,
                "task_id": task_id,
                "status": "started",
                "message": "Prediction pipeline started",
            },
        })

    except Exception as e:
        logger.error(f"Failed to start prediction run: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@prediction_bp.route('/run/<run_id>/status', methods=['GET'])
def get_run_status(run_id: str):
    """Get prediction run status"""
    try:
        run = _find_run(run_id)
        if not run:
            return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

        return jsonify({
            "success": True,
            "data": {
                "run_id": run.run_id,
                "status": run.status.value,
                "progress_message": run.progress_message,
                "error": run.error,
            },
        })

    except Exception as e:
        logger.error(f"Failed to get run status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@prediction_bp.route('/run/<run_id>', methods=['GET'])
def get_run(run_id: str):
    """Get full prediction run details"""
    try:
        run = _find_run(run_id)
        if not run:
            return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

        return jsonify({
            "success": True,
            "data": run.to_dict(),
        })

    except Exception as e:
        logger.error(f"Failed to get run: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@prediction_bp.route('/runs', methods=['GET'])
def list_runs():
    """List all prediction runs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        store = _get_pred_store()
        if isinstance(store, SQLitePredictionStore):
            runs = store.list_runs(limit=limit)
            # Also include any pre-migration JSON runs not yet in SQLite
            json_runs = PredictionRunManager.list_runs(limit=limit)
            sqlite_ids = {r.run_id for r in runs}
            for jr in json_runs:
                if jr.run_id not in sqlite_ids:
                    runs.append(jr)
            runs.sort(key=lambda r: r.created_at, reverse=True)
            runs = runs[:limit]
        else:
            runs = store.list_runs(limit=limit)

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in runs],
            "count": len(runs),
        })

    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@prediction_bp.route('/run/<run_id>', methods=['DELETE'])
def delete_run(run_id: str):
    """Delete a prediction run"""
    try:
        store = _get_pred_store()
        if isinstance(store, SQLitePredictionStore):
            success = store.delete_run(run_id) or PredictionRunManager.delete_run(run_id)
        else:
            success = PredictionRunManager.delete_run(run_id)
        if not success:
            return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

        return jsonify({"success": True, "message": f"Run deleted: {run_id}"})

    except Exception as e:
        logger.error(f"Failed to delete run: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
