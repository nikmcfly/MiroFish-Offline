"""
Digital Twin Service for Manufacturing Floor

Integrates live shop floor data with MiroFish simulation and OR-Tools scheduling.
Provides agent-based disruption modeling and predictive rescheduling.

Architecture:
- Entity Mapper: Converts scheduling entities to OASIS agent profiles
- State Manager: Tracks real-time factory state
- Disruption Engine: Simulates realistic disruptions via agents
- Prediction Bridge: Feeds simulation results back to solver
- Database Integration: Connects to live ERP and sensor databases
"""

from .entity_mapper import (
    SchedulingEntityMapper,
    MachineAgentMapper,
    OperatorAgentMapper,
    JobAgentMapper,
    create_mapper,
)

from .state_manager import (
    FactoryStateManager,
    MachineState,
    OperatorState,
    JobState,
    FactorySnapshot,
)

from .disruption_engine import (
    DisruptionEngine,
    MachineFailureSimulator,
    OperatorAvailabilitySimulator,
    RushOrderSimulator,
    DisruptionPrediction,
)

from .prediction_bridge import (
    PredictionBridge,
    SimulationResultProcessor,
    ConstraintUpdater,
    ReschedulingTrigger,
)

from .db_integration import (
    # Database Configuration
    DatabaseConfig,
    TableMapping,
    # Connection Management
    DatabaseConnectionManager,
    # Adapters
    ERPAdapter,
    SensorDataAdapter,
    DigitalTwinRepository,
    # Factory Functions
    create_db_manager,
)

__all__ = [
    # Entity Mapper
    "SchedulingEntityMapper",
    "MachineAgentMapper",
    "OperatorAgentMapper",
    "JobAgentMapper",
    "create_mapper",
    # State Manager
    "FactoryStateManager",
    "MachineState",
    "OperatorState",
    "JobState",
    "FactorySnapshot",
    # Disruption Engine
    "DisruptionEngine",
    "MachineFailureSimulator",
    "OperatorAvailabilitySimulator",
    "RushOrderSimulator",
    "DisruptionPrediction",
    # Prediction Bridge
    "PredictionBridge",
    "SimulationResultProcessor",
    "ConstraintUpdater",
    "ReschedulingTrigger",
    # Database Integration
    "DatabaseConfig",
    "TableMapping",
    "DatabaseConnectionManager",
    "ERPAdapter",
    "SensorDataAdapter",
    "DigitalTwinRepository",
    "create_db_manager",
]
