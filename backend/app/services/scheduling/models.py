"""
Shop Scheduling System for Manufacturing Floor

A comprehensive job shop scheduling system using Google OR-Tools CP-SAT solver.
Supports flexible job shop with parallel machines, sequence-dependent setup times,
labor constraints, and multi-objective optimization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
import json


class MachineType(Enum):
    """Types of machines in the shop floor"""

    LASER = "laser"  # Cutting
    PRESSBRAKE = "pressbrake"  # Forming
    WELDING = "welding"  # Joining
    POLISHING = "polishing"  # Finishing
    ASSEMBLY = "assembly"  # Build
    SHIPPING = "shipping"  # Dispatch


class MachineStatus(Enum):
    """Current status of a machine"""

    AVAILABLE = "available"
    RUNNING = "running"
    SETUP = "setup"
    MAINTENANCE = "maintenance"
    DOWN = "down"
    OFFLINE = "offline"


class JobPriority(Enum):
    """Job priority levels"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    RUSH = 4
    CRITICAL = 5


class OperationStatus(Enum):
    """Status of an operation"""

    PENDING = "pending"
    QUEUED = "queued"
    SETUP = "setup"
    RUNNING = "running"
    COMPLETE = "complete"
    BLOCKED = "blocked"


@dataclass
class Machine:
    """
    Represents a machine/workstation on the shop floor

    Attributes:
        machine_id: Unique identifier
        name: Human-readable name
        machine_type: Type of machine (laser, pressbrake, etc.)
        capabilities: List of operations this machine can perform
        capacity: Units per hour this machine can process
        setup_time: Default setup time in minutes
        status: Current operational status
        maintenance_schedule: List of planned maintenance windows
        operator_required_skill: Skill level required to operate
    """

    machine_id: str
    name: str
    machine_type: MachineType
    capabilities: List[str] = field(default_factory=list)
    capacity: float = 1.0  # Units per hour
    setup_time: int = 15  # Minutes
    status: MachineStatus = MachineStatus.AVAILABLE

    # Resource constraints
    operator_required_skill: str = "basic"
    max_operators: int = 1
    current_operators: List[str] = field(default_factory=list)

    # Historical performance
    historical_efficiency: float = 0.85  # 0-1, actual vs theoretical
    historical_uptime: float = 0.90  # Availability percentage
    avg_setup_time: float = 15.0  # Minutes from historical data

    # Scheduling
    maintenance_windows: List[Tuple[datetime, datetime]] = field(default_factory=list)

    def get_effective_capacity(self) -> float:
        """Calculate effective capacity considering historical efficiency"""
        return self.capacity * self.historical_efficiency

    def is_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if machine is available for a time window"""
        if self.status in [MachineStatus.DOWN, MachineStatus.OFFLINE]:
            return False

        # Check maintenance windows
        for maint_start, maint_end in self.maintenance_windows:
            if not (end_time <= maint_start or start_time >= maint_end):
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "machine_type": self.machine_type.value,
            "capabilities": self.capabilities,
            "capacity": self.capacity,
            "setup_time": self.setup_time,
            "status": self.status.value,
            "historical_efficiency": self.historical_efficiency,
            "historical_uptime": self.historical_uptime,
        }


@dataclass
class LaborSkill:
    """
    Represents a labor skill/certification

    Attributes:
        skill_id: Unique identifier
        name: Skill name (e.g., "CNC Operation", "Welding Certification")
        level: Skill level (basic, intermediate, advanced, expert)
        machine_types: Which machine types this skill applies to
    """

    skill_id: str
    name: str
    level: str = "basic"  # basic, intermediate, advanced, expert
    machine_types: List[MachineType] = field(default_factory=list)

    def can_operate(self, machine_type: MachineType) -> bool:
        """Check if this skill allows operating a machine type"""
        return machine_type in self.machine_types


@dataclass
class Operator:
    """
    Represents a shop floor operator/labor

    Attributes:
        operator_id: Unique identifier
        name: Operator name
        skills: List of skill IDs the operator has
        shift_hours: Working hours (e.g., [7, 15] for 7am-3pm)
        hourly_rate: Cost per hour
        efficiency_factor: Operator efficiency (0-1)
    """

    operator_id: str
    name: str
    skills: List[str] = field(default_factory=list)
    skill_levels: Dict[str, str] = field(default_factory=dict)  # skill_id -> level
    shift_start: int = 7  # Hour of day (0-23)
    shift_end: int = 15  # Hour of day
    hourly_rate: float = 25.0
    efficiency_factor: float = 1.0

    # Historical performance
    historical_output_rate: float = 1.0  # Relative to standard

    def is_available(self, hour: int) -> bool:
        """Check if operator is working at given hour"""
        return self.shift_start <= hour < self.shift_end

    def has_skill(self, skill_id: str, min_level: str = "basic") -> bool:
        """Check if operator has required skill at minimum level"""
        if skill_id not in self.skills:
            return False

        level_order = {"basic": 0, "intermediate": 1, "advanced": 2, "expert": 3}
        operator_level = self.skill_levels.get(skill_id, "basic")
        return level_order.get(operator_level, 0) >= level_order.get(min_level, 0)


@dataclass
class Operation:
    """
    Represents a single operation/step in a job

    Attributes:
        operation_id: Unique identifier
        name: Operation name
        machine_type: Required machine type
        duration: Processing time in minutes
        setup_time: Setup time in minutes (machine-specific)
        required_skill: Skill required to perform operation
        predecessors: Operations that must complete before this one
    """

    operation_id: str
    name: str
    machine_type: MachineType
    duration: int  # Minutes
    setup_time: int = 0  # Minutes (from machine)
    required_skill: Optional[str] = None
    predecessors: List[str] = field(default_factory=list)  # operation_ids

    # Alternative routing
    alternative_machine_types: List[MachineType] = field(default_factory=list)

    # Historical data
    historical_avg_duration: Optional[float] = None
    historical_setup_time: Optional[float] = None

    def get_total_duration(self, machine: Machine) -> int:
        """Calculate total time including setup"""
        setup = self.setup_time or machine.avg_setup_time
        return int(setup + self.duration)


@dataclass
class Job:
    """
    Represents a manufacturing job/order

    Attributes:
        job_id: Unique identifier
        name: Job name/description
        priority: Job priority
        due_date: When job must be completed
        operations: List of operations required
        quantity: Number of units
        customer: Customer name (for rush priorities)
        material: Material type (affects processing)
    """

    job_id: str
    name: str
    priority: JobPriority = JobPriority.NORMAL
    due_date: Optional[datetime] = None
    release_date: datetime = field(default_factory=datetime.now)
    operations: List[Operation] = field(default_factory=list)
    quantity: int = 1
    customer: Optional[str] = None
    material: Optional[str] = None

    # Status
    status: str = "pending"  # pending, released, in_progress, complete

    # Historical data
    historical_similar_job_duration: Optional[int] = None  # Minutes
    past_due_history: float = 0.0  # 0-1, how often similar jobs were late

    def get_critical_path_duration(self) -> int:
        """Estimate minimum possible duration (sum of operations)"""
        return sum(op.duration + op.setup_time for op in self.operations)

    def is_rush(self) -> bool:
        """Check if this is a rush job"""
        return self.priority in [JobPriority.RUSH, JobPriority.CRITICAL]

    def get_tardiness_penalty(self, completion_time: datetime) -> int:
        """Calculate tardiness penalty if job is late"""
        if not self.due_date or completion_time <= self.due_date:
            return 0

        # Penalty based on priority
        penalty_multipliers = {
            JobPriority.LOW: 1,
            JobPriority.NORMAL: 2,
            JobPriority.HIGH: 5,
            JobPriority.RUSH: 10,
            JobPriority.CRITICAL: 50,
        }

        minutes_late = int((completion_time - self.due_date).total_seconds() / 60)
        return minutes_late * penalty_multipliers.get(self.priority, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "quantity": self.quantity,
            "status": self.status,
            "operations_count": len(self.operations),
        }


@dataclass
class ScheduleEntry:
    """
    Represents a single scheduled operation

    This is the output of the scheduler - what operation runs on which
    machine at what time with which operator.
    """

    entry_id: str
    job_id: str
    operation_id: str

    # Assignment
    machine_id: str
    operator_id: Optional[str] = None

    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)
    setup_start: Optional[datetime] = None
    setup_end: Optional[datetime] = None

    # Status
    status: OperationStatus = OperationStatus.PENDING

    # Metadata
    expected_duration: int = 0  # Minutes (for variance tracking)
    actual_duration: Optional[int] = None

    def get_duration(self) -> int:
        """Get scheduled duration in minutes"""
        return int((self.end_time - self.start_time).total_seconds() / 60)

    def is_delayed(self, current_time: Optional[datetime] = None) -> bool:
        """Check if operation is delayed vs expected"""
        if self.status == OperationStatus.COMPLETE:
            return False

        check_time = current_time or datetime.now()
        return check_time > self.end_time and self.status != OperationStatus.COMPLETE


@dataclass
class Schedule:
    """
    Complete schedule output

    Attributes:
        schedule_id: Unique identifier
        entries: List of scheduled operations
        makespan: Total schedule duration
        objectives: Optimization objective values
    """

    schedule_id: str
    entries: List[ScheduleEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    # Objectives
    makespan: int = 0  # Minutes
    total_tardiness: int = 0  # Minutes
    total_cost: float = 0.0
    machine_utilization: Dict[str, float] = field(default_factory=dict)

    # Solver info
    solver_status: str = "unknown"
    solve_time: float = 0.0  # Seconds
    optimality_gap: Optional[float] = None

    def get_job_completion_time(self, job_id: str) -> Optional[datetime]:
        """Get when a job completes"""
        job_entries = [e for e in self.entries if e.job_id == job_id]
        if not job_entries:
            return None
        return max(e.end_time for e in job_entries)

    def get_machine_schedule(self, machine_id: str) -> List[ScheduleEntry]:
        """Get all entries for a specific machine"""
        return sorted(
            [e for e in self.entries if e.machine_id == machine_id],
            key=lambda x: x.start_time,
        )

    def get_utilization(self, machine_id: str, window_hours: int = 24) -> float:
        """Calculate machine utilization percentage"""
        machine_entries = self.get_machine_schedule(machine_id)
        if not machine_entries:
            return 0.0

        total_busy_time = sum(e.get_duration() for e in machine_entries)
        window_minutes = window_hours * 60
        return min(1.0, total_busy_time / window_minutes)

    def to_gantt_data(self) -> List[Dict[str, Any]]:
        """Convert to format suitable for Gantt chart visualization"""
        data = []
        for entry in self.entries:
            data.append(
                {
                    "job_id": entry.job_id,
                    "operation": entry.operation_id,
                    "machine": entry.machine_id,
                    "start": entry.start_time.isoformat(),
                    "end": entry.end_time.isoformat(),
                    "status": entry.status.value,
                }
            )
        return data


@dataclass
class SchedulingProblem:
    """
    Complete scheduling problem definition

    This is the input to the scheduler - everything needed to create
    an optimized schedule.
    """

    problem_id: str
    name: str

    # Resources
    machines: List[Machine] = field(default_factory=list)
    operators: List[Operator] = field(default_factory=list)

    # Jobs
    jobs: List[Job] = field(default_factory=list)

    # Constraints
    start_time: datetime = field(default_factory=datetime.now)
    planning_horizon: int = 7  # Days

    # Objective weights
    objective_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "makespan": 0.3,
            "tardiness": 0.4,
            "cost": 0.2,
            "utilization": 0.1,
        }
    )

    # Historical data integration
    use_historical_durations: bool = True
    use_historical_setup_times: bool = True

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate that problem is solvable"""
        errors = []

        # Check machines exist
        if not self.machines:
            errors.append("No machines defined")

        # Check jobs exist
        if not self.jobs:
            errors.append("No jobs defined")

        # Check operations have valid machine types
        machine_types = {m.machine_type for m in self.machines}
        for job in self.jobs:
            for op in job.operations:
                if op.machine_type not in machine_types:
                    if op.machine_type not in op.alternative_machine_types:
                        errors.append(
                            f"Job {job.job_id} op {op.operation_id}: "
                            f"no machine for {op.machine_type.value}"
                        )

        return len(errors) == 0, errors

    def get_machines_by_type(self, machine_type: MachineType) -> List[Machine]:
        """Get all machines of a specific type"""
        return [m for m in self.machines if m.machine_type == machine_type]

    def estimate_makespan(self) -> int:
        """Rough estimate of minimum possible makespan"""
        total_work = sum(
            op.duration + op.setup_time for job in self.jobs for op in job.operations
        )

        # Divide by number of machines (very rough)
        num_machines = len(self.machines)
        if num_machines == 0:
            return total_work

        return int(total_work / num_machines)
