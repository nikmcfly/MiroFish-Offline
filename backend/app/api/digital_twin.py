"""
Digital Twin API for Shop System Integration

Provides REST API endpoints for the shop system to:
1. Push live factory data (machines, operators, jobs, sensor readings)
2. Trigger simulations
3. Get disruption predictions
4. Receive optimized schedules

Architecture:
┌─────────────────┐      HTTP/REST       ┌─────────────────────┐
│   Shop System   │ ◄──────────────────► │  MiroFish Digital   │
│   (Your ERP)    │   POST /api/twin/... │  Twin Service       │
│                 │                      │  (This API)           │
│ - Pushes data   │                      │  - Runs simulations   │
│ - Triggers sims │                      │  - Returns insights   │
│ - Gets results  │                      │  - Optimizes schedule │
└─────────────────┘                      └─────────────────────┘
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Blueprint, request, jsonify, current_app
import threading
import uuid

from ...services.digital_twin import (
    # Core components
    FactoryStateManager,
    DisruptionEngine,
    MachineFailureSimulator,
    OperatorAvailabilitySimulator,
    RushOrderSimulator,
    PredictionBridge,
    # Database integration
    DatabaseConfig,
    DatabaseConnectionManager,
    ERPAdapter,
    SensorDataAdapter,
    DigitalTwinRepository,
    create_db_manager,
    TableMapping,
    # Scenarios
    create_default_scenario,
    create_high_stress_scenario,
)

from ...services.scheduling.models import (
    Machine,
    MachineType,
    MachineStatus,
    Operator,
    LaborSkill,
    Job,
    JobPriority,
    Operation,
    SchedulingProblem,
)

from ...services.scheduling.solver import JobShopSolver, FastHeuristicScheduler

from ...utils.logger import get_logger

logger = get_logger("mirofish.api.digital_twin")

# Blueprint for Digital Twin API
digital_twin_bp = Blueprint("digital_twin", __name__, url_prefix="/api/twin")

# =============================================================================
# Global State (managed per app context)
# =============================================================================


class DigitalTwinService:
    """Singleton service holding Digital Twin components"""

    def __init__(self):
        self.db_manager: Optional[DatabaseConnectionManager] = None
        self.state_manager: Optional[FactoryStateManager] = None
        self.disruption_engine: Optional[DisruptionEngine] = None
        self.prediction_bridge: Optional[PredictionBridge] = None
        self.initialized = False

        # Track active simulations
        self.active_simulations: Dict[str, Dict] = {}

    def initialize(
        self, db_configs: Dict[str, DatabaseConfig], table_mapping: TableMapping
    ):
        """Initialize with database connections"""
        if self.initialized:
            return

        # Setup database connections
        self.db_manager = create_db_manager(**db_configs)

        # Initialize components
        self.state_manager = FactoryStateManager()
        self.disruption_engine = DisruptionEngine(self.state_manager)
        self.disruption_engine.register_simulator(
            MachineFailureSimulator(self.state_manager)
        )
        self.disruption_engine.register_simulator(
            OperatorAvailabilitySimulator(self.state_manager)
        )
        self.disruption_engine.register_simulator(
            RushOrderSimulator(self.state_manager)
        )

        # Setup prediction bridge
        solver = JobShopSolver()
        self.prediction_bridge = PredictionBridge(self.state_manager, solver)

        self.initialized = True
        logger.info("Digital Twin Service initialized")

    def load_from_erp(self, table_mapping: TableMapping):
        """Load current factory state from ERP"""
        if not self.db_manager:
            raise ValueError("Service not initialized")

        erp = ERPAdapter(self.db_manager, table_mapping)

        # Load machines
        for machine in erp.get_machines():
            self.state_manager.register_machine(machine)

        # Load operators
        for operator in erp.get_operators():
            self.state_manager.register_operator(operator)

        # Load jobs
        for job in erp.get_jobs():
            self.state_manager.register_job(job)

        logger.info("Factory state loaded from ERP")


# Global instance
digital_twin_service = DigitalTwinService()

# =============================================================================
# API Endpoints
# =============================================================================


@digital_twin_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.

    Returns service status and database connectivity.
    """
    status = {
        "status": "healthy" if digital_twin_service.initialized else "initializing",
        "timestamp": datetime.now().isoformat(),
        "initialized": digital_twin_service.initialized,
    }

    if digital_twin_service.db_manager:
        # Test connections
        db_status = {}
        for db_name in ["erp", "sensor", "dt"]:
            try:
                db_status[db_name] = (
                    "connected"
                    if digital_twin_service.db_manager.test_connection(db_name)
                    else "error"
                )
            except:
                db_status[db_name] = "not_configured"
        status["databases"] = db_status

    return jsonify({"success": True, "data": status})


@digital_twin_bp.route("/initialize", methods=["POST"])
def initialize_service():
    """
    Initialize Digital Twin with database configurations.

    Request Body:
        {
            "databases": {
                "erp": {"host": "...", "port": 5432, "database": "...", "username": "...", "password": "..."},
                "sensor": {...},
                "dt": {...}
            },
            "table_mapping": {
                "machines_table": "equipment",
                "machine_id_column": "asset_id",
                ...
            }
        }

    Returns:
        {"success": true, "data": {"initialized": true}}
    """
    try:
        data = request.get_json() or {}

        # Parse database configs
        db_configs = {}
        for db_name, config in data.get("databases", {}).items():
            db_configs[f"{db_name}_config"] = DatabaseConfig(name=db_name, **config)

        # Parse table mapping
        mapping = TableMapping(**data.get("table_mapping", {}))

        # Initialize service
        digital_twin_service.initialize(db_configs, mapping)
        digital_twin_service.load_from_erp(mapping)

        return jsonify(
            {
                "success": True,
                "data": {
                    "initialized": True,
                    "machines_tracked": len(
                        digital_twin_service.state_manager.get_all_machine_states()
                    ),
                    "operators_tracked": len(
                        digital_twin_service.state_manager._operators
                    ),
                    "jobs_tracked": len(digital_twin_service.state_manager._jobs),
                },
            }
        )

    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Data Ingestion Endpoints
# =============================================================================


@digital_twin_bp.route("/data/machines", methods=["POST"])
def push_machine_data():
    """
    Push live machine data from shop floor.

    Request Body:
        {
            "machines": [
                {
                    "machine_id": "M1",
                    "status": "RUNNING",
                    "oee": 0.85,
                    "temperature": 75.5,
                    "vibration": 2.1,
                    "current_job_id": "J123",
                    "timestamp": "2024-01-15T10:30:00Z"
                }
            ]
        }

    Returns:
        {"success": true, "data": {"updated": 1}}
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        data = request.get_json() or {}
        machines_data = data.get("machines", [])

        updated = 0
        for machine_data in machines_data:
            machine_id = machine_data.get("machine_id")

            # Update status
            if "status" in machine_data:
                digital_twin_service.state_manager.update_machine_status(
                    machine_id,
                    MachineStatus[machine_data["status"]],
                    metadata=machine_data.get("metadata", {}),
                )

            # Update metrics
            digital_twin_service.state_manager.update_machine_metrics(
                machine_id,
                oee=machine_data.get("oee"),
                temperature=machine_data.get("temperature"),
                vibration=machine_data.get("vibration"),
                power_consumption=machine_data.get("power_consumption"),
                cycle_count=machine_data.get("cycle_count"),
            )
            updated += 1

        return jsonify({"success": True, "data": {"updated": updated}})

    except Exception as e:
        logger.error(f"Failed to push machine data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@digital_twin_bp.route("/data/operators", methods=["POST"])
def push_operator_data():
    """
    Push operator attendance/assignment data.

    Request Body:
        {
            "operators": [
                {
                    "operator_id": "OP1",
                    "event": "check_in",  // or "check_out", "assignment"
                    "current_assignment": "M1",
                    "timestamp": "2024-01-15T10:30:00Z"
                }
            ]
        }
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        data = request.get_json() or {}
        operators_data = data.get("operators", [])

        for op_data in operators_data:
            operator_id = op_data.get("operator_id")
            event = op_data.get("event")

            if event == "check_in":
                digital_twin_service.state_manager.operator_check_in(operator_id)
            elif event == "check_out":
                digital_twin_service.state_manager.operator_check_out(operator_id)
            elif event == "assignment":
                digital_twin_service.state_manager.assign_operator(
                    operator_id, op_data.get("current_assignment")
                )

        return jsonify({"success": True, "data": {"processed": len(operators_data)}})

    except Exception as e:
        logger.error(f"Failed to push operator data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@digital_twin_bp.route("/data/jobs", methods=["POST"])
def push_job_data():
    """
    Push job updates from shop floor.

    Request Body:
        {
            "jobs": [
                {
                    "job_id": "J123",
                    "status": "in_progress",
                    "current_operation_idx": 2,
                    "percent_complete": 45.5,
                    "assigned_machine_id": "M1",
                    "assigned_operator_id": "OP1"
                }
            ]
        }
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        data = request.get_json() or {}
        jobs_data = data.get("jobs", [])

        for job_data in jobs_data:
            job_id = job_data.get("job_id")

            # Update progress
            if "current_operation_idx" in job_data:
                digital_twin_service.state_manager.update_job_progress(
                    job_id,
                    job_data["current_operation_idx"],
                    job_data.get("assigned_machine_id"),
                    job_data.get("assigned_operator_id"),
                )

            # Complete operation
            if job_data.get("operation_completed"):
                digital_twin_service.state_manager.complete_job_operation(job_id)

        return jsonify({"success": True, "data": {"processed": len(jobs_data)}})

    except Exception as e:
        logger.error(f"Failed to push job data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Simulation Endpoints
# =============================================================================


@digital_twin_bp.route("/simulate", methods=["POST"])
def run_simulation():
    """
    Run disruption simulation and return predictions.

    Request Body:
        {
            "scenario": "default" | "high_stress" | "custom",
            "scenario_config": {  // optional custom config
                "simulation_hours": 24,
                "base_failure_rate": 0.01,
                ...
            },
            "callback_url": "https://shop-system/webhook"  // optional async callback
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_abc123",
                "predictions": [
                    {
                        "disruption_type": "MACHINE_BREAKDOWN",
                        "entity_id": "M1",
                        "probability": 0.75,
                        "predicted_time": "2024-01-15T14:30:00Z",
                        "estimated_delay_minutes": 120,
                        "recommended_action": "Prepare backup machine"
                    }
                ]
            }
        }
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        data = request.get_json() or {}
        scenario_type = data.get("scenario", "default")

        # Create scenario
        if scenario_type == "high_stress":
            scenario = create_high_stress_scenario()
        elif scenario_type == "custom":
            from ...services.digital_twin.disruption_engine import SimulationScenario

            scenario = SimulationScenario(**data.get("scenario_config", {}))
        else:
            scenario = create_default_scenario()

        simulation_id = f"sim_{uuid.uuid4().hex[:8]}"

        # Check for async callback
        callback_url = data.get("callback_url")

        if callback_url:
            # Run async
            def run_async():
                try:
                    predictions = (
                        digital_twin_service.disruption_engine.simulate_scenario(
                            scenario
                        )
                    )

                    # Send callback
                    import requests

                    requests.post(
                        callback_url,
                        json={
                            "simulation_id": simulation_id,
                            "status": "completed",
                            "predictions": [p.to_dict() for p in predictions],
                        },
                    )
                except Exception as e:
                    logger.error(f"Async simulation failed: {e}")

            thread = threading.Thread(target=run_async)
            thread.start()

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "running",
                        "message": "Simulation started asynchronously",
                    },
                }
            )

        else:
            # Run sync
            predictions = digital_twin_service.disruption_engine.simulate_scenario(
                scenario
            )

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "completed",
                        "predictions": [p.to_dict() for p in predictions],
                    },
                }
            )

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@digital_twin_bp.route("/simulate/schedule", methods=["POST"])
def simulate_and_reschedule():
    """
    Run simulation, get predictions, and return optimized schedule.

    This is the main integration endpoint - full pipeline in one call.

    Request Body:
        {
            "scenario": "default",
            "reschedule_strategy": "adaptive" | "fast" | "optimal",
            "current_problem": {  // optional - use current state if not provided
                "machines": [...],
                "operators": [...],
                "jobs": [...]
            }
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation": {...},
                "predictions": [...],
                "reschedule_triggered": true,
                "schedule": {
                    "makespan": 1200,
                    "entries": [...]
                },
                "recommendations": [...]
            }
        }
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        data = request.get_json() or {}

        # Step 1: Run simulation
        scenario = create_default_scenario()
        predictions = digital_twin_service.disruption_engine.simulate_scenario(scenario)

        # Step 2: Build scheduling problem from current state
        snapshot = digital_twin_service.state_manager.create_snapshot()

        # Convert to SchedulingProblem
        problem = SchedulingProblem(
            problem_id=f"twin_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name="Digital Twin Optimized",
            machines=[...],  # Convert from snapshot
            operators=[...],
            jobs=[...],
        )

        # Step 3: Process through prediction bridge
        digital_twin_service.prediction_bridge.set_current_problem(problem)
        results = digital_twin_service.prediction_bridge.process_simulation_results(
            predictions, auto_reschedule=True
        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "predictions": [p.to_dict() for p in predictions],
                    "reschedule_triggered": results.get("reschedule_triggered"),
                    "new_makespan": results.get("new_schedule_makespan"),
                    "recommendations": results.get("recommendations", []),
                },
            }
        )

    except Exception as e:
        logger.error(f"Simulate-and-reschedule failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Query Endpoints
# =============================================================================


@digital_twin_bp.route("/state", methods=["GET"])
def get_current_state():
    """Get current factory state snapshot"""
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        snapshot = digital_twin_service.state_manager.create_snapshot()

        return jsonify({"success": True, "data": snapshot.to_dict()})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@digital_twin_bp.route("/predictions", methods=["GET"])
def get_predictions():
    """
    Get recent disruption predictions.

    Query Parameters:
        - min_probability: float (default 0.0)
        - hours_ahead: int (default 24)
    """
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        min_prob = request.args.get("min_probability", 0.0, type=float)
        hours_ahead = request.args.get("hours_ahead", 24, type=int)

        predictions = digital_twin_service.disruption_engine.get_high_risk_predictions(
            probability_threshold=min_prob, hours_ahead=hours_ahead
        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "count": len(predictions),
                    "predictions": [p.to_dict() for p in predictions],
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@digital_twin_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get Digital Twin service statistics"""
    try:
        if not digital_twin_service.initialized:
            return jsonify({"success": False, "error": "Service not initialized"}), 400

        stats = {
            "state_manager": digital_twin_service.state_manager.get_metrics(),
            "prediction_bridge": digital_twin_service.prediction_bridge.get_stats(),
            "disruption_engine": digital_twin_service.disruption_engine.get_prediction_statistics(),
        }

        return jsonify({"success": True, "data": stats})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# WebSocket Support (for real-time streaming)
# =============================================================================

# Optional: Add SocketIO for real-time updates
# This would allow the shop system to subscribe to live events


def register_digital_twin_api(app):
    """Register Digital Twin blueprint with Flask app"""
    app.register_blueprint(digital_twin_bp)
    logger.info("Digital Twin API registered")
