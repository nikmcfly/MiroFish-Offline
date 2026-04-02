"""
Shop Scheduling Module for MiroFish-Offline

A complete job shop scheduling system with OR-Tools integration.
"""

from .models import (
    Machine,
    MachineType,
    MachineStatus,
    Operator,
    LaborSkill,
    Job,
    JobPriority,
    Operation,
    OperationStatus,
    Schedule,
    ScheduleEntry,
    SchedulingProblem,
)

from .solver import (
    JobShopSolver,
    FastHeuristicScheduler,
    HybridScheduler,
    SolverConfig,
    create_scheduler,
)

from .historical_data import (
    HistoricalDataLoader,
    MachinePerformance,
    OperatorPerformance,
    ConstraintCalibrator,
    RealisticConstraintBuilder,
    create_realistic_problem,
)

from .visualization import (
    ScheduleVisualizer,
    ScheduleReporter,
    GanttData,
    visualize_schedule,
)

__all__ = [
    # Models
    "Machine",
    "MachineType",
    "MachineStatus",
    "Operator",
    "LaborSkill",
    "Job",
    "JobPriority",
    "Operation",
    "OperationStatus",
    "Schedule",
    "ScheduleEntry",
    "SchedulingProblem",
    # Solvers
    "JobShopSolver",
    "FastHeuristicScheduler",
    "HybridScheduler",
    "SolverConfig",
    "create_scheduler",
    # Historical Data
    "HistoricalDataLoader",
    "MachinePerformance",
    "OperatorPerformance",
    "ConstraintCalibrator",
    "RealisticConstraintBuilder",
    "create_realistic_problem",
    # Visualization
    "ScheduleVisualizer",
    "ScheduleReporter",
    "GanttData",
    "visualize_schedule",
]
