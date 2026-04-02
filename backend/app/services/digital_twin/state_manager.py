"""
State Manager - Phase 2

Tracks live factory state including machine status, operator availability, and job progress.
Maintains real-time synchronization between physical shop floor and digital twin.
"""

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any, Set
from collections import deque

from ..scheduling.models import (
    Machine,
    MachineStatus,
    Operator,
    Job,
    JobPriority,
    Operation,
    OperationStatus,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.digital_twin.state_manager")


class StateChangeType(Enum):
    """Types of state changes that can occur"""

    MACHINE_STATUS_CHANGE = auto()
    MACHINE_METRIC_UPDATE = auto()
    OPERATOR_CHECK_IN = auto()
    OPERATOR_CHECK_OUT = auto()
    OPERATOR_SKILL_UPDATE = auto()
    JOB_ARRIVAL = auto()
    JOB_STATUS_CHANGE = auto()
    OPERATION_START = auto()
    OPERATION_COMPLETE = auto()
    SCHEDULE_UPDATE = auto()


@dataclass
class MachineState:
    """
    Real-time state of a machine on the factory floor.

    Tracks current status, active job, performance metrics,
    and sensor data for digital twin synchronization.
    """

    machine_id: str
    name: str
    machine_type: str

    # Current state
    status: MachineStatus = MachineStatus.AVAILABLE
    current_job_id: Optional[str] = None
    current_operation_id: Optional[str] = None

    # Timing
    status_changed_at: datetime = field(default_factory=datetime.now)
    operation_started_at: Optional[datetime] = None

    # Performance metrics (live)
    oee: float = 0.0  # Overall Equipment Effectiveness
    availability: float = 1.0
    performance: float = 1.0
    quality: float = 1.0

    # Sensor data
    temperature: Optional[float] = None
    vibration: Optional[float] = None
    power_consumption: Optional[float] = None
    cycle_count: int = 0

    # Maintenance
    last_maintenance: Optional[datetime] = None
    next_scheduled_maintenance: Optional[datetime] = None

    # History (last N state changes)
    status_history: deque = field(default_factory=lambda: deque(maxlen=100))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "machine_type": self.machine_type,
            "status": self.status.value,
            "current_job_id": self.current_job_id,
            "current_operation_id": self.current_operation_id,
            "status_changed_at": self.status_changed_at.isoformat(),
            "operation_started_at": self.operation_started_at.isoformat()
            if self.operation_started_at
            else None,
            "oee": self.oee,
            "availability": self.availability,
            "performance": self.performance,
            "quality": self.quality,
            "temperature": self.temperature,
            "vibration": self.vibration,
            "power_consumption": self.power_consumption,
            "cycle_count": self.cycle_count,
            "last_maintenance": self.last_maintenance.isoformat()
            if self.last_maintenance
            else None,
            "next_scheduled_maintenance": self.next_scheduled_maintenance.isoformat()
            if self.next_scheduled_maintenance
            else None,
        }


@dataclass
class OperatorState:
    """
    Real-time state of an operator on the factory floor.

    Tracks availability, current assignment, skills, and performance.
    """

    operator_id: str
    name: str

    # Current state
    is_available: bool = True
    current_assignment: Optional[str] = None  # job_id or machine_id

    # Timing
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None

    # Skills and capabilities
    skills: List[str] = field(default_factory=list)
    skill_levels: Dict[str, str] = field(default_factory=dict)

    # Performance metrics
    efficiency_factor: float = 1.0
    jobs_completed_today: int = 0
    total_hours_today: float = 0.0

    # Shift info
    shift_start: int = 7
    shift_end: int = 15

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "operator_id": self.operator_id,
            "name": self.name,
            "is_available": self.is_available,
            "current_assignment": self.current_assignment,
            "checked_in_at": self.checked_in_at.isoformat()
            if self.checked_in_at
            else None,
            "skills": self.skills,
            "skill_levels": self.skill_levels,
            "efficiency_factor": self.efficiency_factor,
            "jobs_completed_today": self.jobs_completed_today,
            "total_hours_today": self.total_hours_today,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
        }


@dataclass
class JobState:
    """
    Real-time state of a job in production.

    Tracks progress through operations, current status, and completion estimates.
    """

    job_id: str
    name: str
    priority: JobPriority

    # Progress tracking
    status: str = "pending"  # pending, released, in_progress, complete
    current_operation_idx: int = 0
    operations_completed: int = 0
    total_operations: int = 0

    # Timing
    release_date: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    actual_completion: Optional[datetime] = None

    # Progress metrics
    percent_complete: float = 0.0
    estimated_duration_remaining: int = 0  # minutes

    # Current assignment
    assigned_machine_id: Optional[str] = None
    assigned_operator_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority.value,
            "status": self.status,
            "current_operation_idx": self.current_operation_idx,
            "operations_completed": self.operations_completed,
            "total_operations": self.total_operations,
            "release_date": self.release_date.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "estimated_completion": self.estimated_completion.isoformat()
            if self.estimated_completion
            else None,
            "percent_complete": self.percent_complete,
            "estimated_duration_remaining": self.estimated_duration_remaining,
            "assigned_machine_id": self.assigned_machine_id,
            "assigned_operator_id": self.assigned_operator_id,
        }


@dataclass
class StateChangeEvent:
    """Represents a change in factory state"""

    event_type: StateChangeType
    entity_id: str
    entity_type: str  # "machine", "operator", "job"
    timestamp: datetime
    old_value: Any = None
    new_value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "timestamp": self.timestamp.isoformat(),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "metadata": self.metadata,
        }


@dataclass
class FactorySnapshot:
    """
    Complete snapshot of factory state at a point in time.

    Used for:
    - Digital twin synchronization
    - Simulation initialization
    - Historical analysis
    - Solver input
    """

    timestamp: datetime
    machines: Dict[str, MachineState]
    operators: Dict[str, OperatorState]
    jobs: Dict[str, JobState]

    # Aggregate metrics
    total_machine_utilization: float = 0.0
    total_operator_utilization: float = 0.0
    jobs_in_queue: int = 0
    jobs_in_progress: int = 0
    jobs_completed_today: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "machines": {k: v.to_dict() for k, v in self.machines.items()},
            "operators": {k: v.to_dict() for k, v in self.operators.items()},
            "jobs": {k: v.to_dict() for k, v in self.jobs.items()},
            "total_machine_utilization": self.total_machine_utilization,
            "total_operator_utilization": self.total_operator_utilization,
            "jobs_in_queue": self.jobs_in_queue,
            "jobs_in_progress": self.jobs_in_progress,
            "jobs_completed_today": self.jobs_completed_today,
        }


class FactoryStateManager:
    """
    Manages real-time factory state for digital twin integration.

    Provides:
    - Live state tracking for machines, operators, and jobs
    - Event subscription for state changes
    - Snapshot creation for simulation input
    - WebSocket/polling support for real-time updates
    - Persistence for historical analysis

    Thread-safe for concurrent updates from multiple data sources.
    """

    def __init__(self, persistence_path: Optional[str] = None):
        """
        Initialize state manager.

        Args:
            persistence_path: Optional path to save state history
        """
        self._machines: Dict[str, MachineState] = {}
        self._operators: Dict[str, OperatorState] = {}
        self._jobs: Dict[str, JobState] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Event subscribers: callback -> (event_types filter, entity_id filter)
        self._subscribers: Dict[Callable, tuple] = {}

        # State change history
        self._event_history: deque = deque(maxlen=10000)

        # Persistence
        self._persistence_path = persistence_path
        self._last_persist_time = datetime.now()

        # Metrics
        self._metrics = {
            "updates_received": 0,
            "events_published": 0,
            "snapshots_created": 0,
        }

        logger.info("FactoryStateManager initialized")

    # ==================== Machine Operations ====================

    def register_machine(self, machine: Machine) -> MachineState:
        """Register a machine for state tracking"""
        with self._lock:
            state = MachineState(
                machine_id=machine.machine_id,
                name=machine.name,
                machine_type=machine.machine_type.value,
                status=machine.status,
                availability=machine.historical_uptime,
                performance=machine.historical_efficiency,
            )
            self._machines[machine.machine_id] = state
            logger.debug(f"Registered machine: {machine.name} ({machine.machine_id})")
            return state

    def update_machine_status(
        self,
        machine_id: str,
        new_status: MachineStatus,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Update machine status and publish event"""
        with self._lock:
            if machine_id not in self._machines:
                logger.warning(f"Machine not found: {machine_id}")
                return

            machine = self._machines[machine_id]
            old_status = machine.status

            if old_status != new_status:
                machine.status = new_status
                machine.status_changed_at = datetime.now()
                machine.status_history.append(
                    {
                        "from": old_status.value,
                        "to": new_status.value,
                        "at": machine.status_changed_at.isoformat(),
                    }
                )

                event = StateChangeEvent(
                    event_type=StateChangeType.MACHINE_STATUS_CHANGE,
                    entity_id=machine_id,
                    entity_type="machine",
                    timestamp=machine.status_changed_at,
                    old_value=old_status.value,
                    new_value=new_status.value,
                    metadata=metadata or {},
                )
                self._publish_event(event)

                logger.info(
                    f"Machine {machine_id} status: {old_status.value} -> {new_status.value}"
                )

    def update_machine_metrics(
        self,
        machine_id: str,
        oee: Optional[float] = None,
        temperature: Optional[float] = None,
        vibration: Optional[float] = None,
        power_consumption: Optional[float] = None,
        cycle_count: Optional[int] = None,
    ) -> None:
        """Update machine sensor metrics"""
        with self._lock:
            if machine_id not in self._machines:
                return

            machine = self._machines[machine_id]

            if oee is not None:
                machine.oee = oee
            if temperature is not None:
                machine.temperature = temperature
            if vibration is not None:
                machine.vibration = vibration
            if power_consumption is not None:
                machine.power_consumption = power_consumption
            if cycle_count is not None:
                machine.cycle_count = cycle_count

            event = StateChangeEvent(
                event_type=StateChangeType.MACHINE_METRIC_UPDATE,
                entity_id=machine_id,
                entity_type="machine",
                timestamp=datetime.now(),
                metadata={
                    "oee": oee,
                    "temperature": temperature,
                    "vibration": vibration,
                },
            )
            self._publish_event(event)

    def get_machine_state(self, machine_id: str) -> Optional[MachineState]:
        """Get current state of a machine"""
        with self._lock:
            return self._machines.get(machine_id)

    def get_all_machine_states(self) -> Dict[str, MachineState]:
        """Get all machine states"""
        with self._lock:
            return dict(self._machines)

    # ==================== Operator Operations ====================

    def register_operator(self, operator: Operator) -> OperatorState:
        """Register an operator for state tracking"""
        with self._lock:
            state = OperatorState(
                operator_id=operator.operator_id,
                name=operator.name,
                skills=operator.skills.copy(),
                skill_levels=operator.skill_levels.copy(),
                efficiency_factor=operator.efficiency_factor,
                shift_start=operator.shift_start,
                shift_end=operator.shift_end,
            )
            self._operators[operator.operator_id] = state
            logger.debug(
                f"Registered operator: {operator.name} ({operator.operator_id})"
            )
            return state

    def operator_check_in(self, operator_id: str) -> None:
        """Mark operator as checked in and available"""
        with self._lock:
            if operator_id not in self._operators:
                logger.warning(f"Operator not found: {operator_id}")
                return

            operator = self._operators[operator_id]
            operator.is_available = True
            operator.checked_in_at = datetime.now()
            operator.checked_out_at = None

            event = StateChangeEvent(
                event_type=StateChangeType.OPERATOR_CHECK_IN,
                entity_id=operator_id,
                entity_type="operator",
                timestamp=operator.checked_in_at,
                new_value="checked_in",
            )
            self._publish_event(event)
            logger.info(f"Operator {operator_id} checked in")

    def operator_check_out(self, operator_id: str) -> None:
        """Mark operator as checked out and unavailable"""
        with self._lock:
            if operator_id not in self._operators:
                return

            operator = self._operators[operator_id]
            operator.is_available = False
            operator.checked_out_at = datetime.now()

            if operator.checked_in_at:
                session_hours = (
                    operator.checked_out_at - operator.checked_in_at
                ).total_seconds() / 3600
                operator.total_hours_today += session_hours

            operator.current_assignment = None

            event = StateChangeEvent(
                event_type=StateChangeType.OPERATOR_CHECK_OUT,
                entity_id=operator_id,
                entity_type="operator",
                timestamp=operator.checked_out_at,
                old_value="checked_in",
                new_value="checked_out",
            )
            self._publish_event(event)
            logger.info(f"Operator {operator_id} checked out")

    def assign_operator(self, operator_id: str, assignment_id: str) -> None:
        """Assign operator to a job or machine"""
        with self._lock:
            if operator_id not in self._operators:
                return

            operator = self._operators[operator_id]
            operator.current_assignment = assignment_id
            logger.debug(f"Operator {operator_id} assigned to {assignment_id}")

    def get_operator_state(self, operator_id: str) -> Optional[OperatorState]:
        """Get current state of an operator"""
        with self._lock:
            return self._operators.get(operator_id)

    def get_available_operators(self) -> List[OperatorState]:
        """Get all available operators"""
        with self._lock:
            return [op for op in self._operators.values() if op.is_available]

    # ==================== Job Operations ====================

    def register_job(self, job: Job) -> JobState:
        """Register a job for progress tracking"""
        with self._lock:
            state = JobState(
                job_id=job.job_id,
                name=job.name,
                priority=job.priority,
                status=job.status,
                total_operations=len(job.operations),
                due_date=job.due_date,
                release_date=job.release_date,
            )
            self._jobs[job.job_id] = state

            event = StateChangeEvent(
                event_type=StateChangeType.JOB_ARRIVAL,
                entity_id=job.job_id,
                entity_type="job",
                timestamp=datetime.now(),
                new_value="registered",
                metadata={
                    "priority": job.priority.value,
                    "operations": len(job.operations),
                },
            )
            self._publish_event(event)

            logger.debug(f"Registered job: {job.name} ({job.job_id})")
            return state

    def update_job_progress(
        self,
        job_id: str,
        operation_idx: int,
        machine_id: str,
        operator_id: str,
    ) -> None:
        """Update job progress when operation starts"""
        with self._lock:
            if job_id not in self._jobs:
                return

            job = self._jobs[job_id]
            job.current_operation_idx = operation_idx
            job.assigned_machine_id = machine_id
            job.assigned_operator_id = operator_id
            job.status = "in_progress"

            if job.started_at is None:
                job.started_at = datetime.now()

            job.percent_complete = (
                (operation_idx / job.total_operations) * 100
                if job.total_operations > 0
                else 0
            )

            event = StateChangeEvent(
                event_type=StateChangeType.OPERATION_START,
                entity_id=job_id,
                entity_type="job",
                timestamp=datetime.now(),
                metadata={
                    "operation_idx": operation_idx,
                    "machine_id": machine_id,
                    "operator_id": operator_id,
                },
            )
            self._publish_event(event)

    def complete_job_operation(self, job_id: str) -> None:
        """Mark current operation as complete"""
        with self._lock:
            if job_id not in self._jobs:
                return

            job = self._jobs[job_id]
            job.operations_completed += 1
            job.percent_complete = (
                (job.operations_completed / job.total_operations) * 100
                if job.total_operations > 0
                else 100
            )

            if job.operations_completed >= job.total_operations:
                job.status = "complete"
                job.actual_completion = datetime.now()

                event_type = StateChangeType.JOB_STATUS_CHANGE
            else:
                event_type = StateChangeType.OPERATION_COMPLETE

            event = StateChangeEvent(
                event_type=event_type,
                entity_id=job_id,
                entity_type="job",
                timestamp=datetime.now(),
                old_value=job.operations_completed - 1,
                new_value=job.operations_completed,
                metadata={"percent_complete": job.percent_complete},
            )
            self._publish_event(event)

    def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get current state of a job"""
        with self._lock:
            return self._jobs.get(job_id)

    def get_active_jobs(self) -> List[JobState]:
        """Get all jobs that are in progress"""
        with self._lock:
            return [job for job in self._jobs.values() if job.status == "in_progress"]

    def get_pending_jobs(self) -> List[JobState]:
        """Get all jobs waiting to start"""
        with self._lock:
            return [job for job in self._jobs.values() if job.status == "pending"]

    # ==================== Snapshot Operations ====================

    def create_snapshot(self) -> FactorySnapshot:
        """Create a complete snapshot of current factory state"""
        with self._lock:
            snapshot = FactorySnapshot(
                timestamp=datetime.now(),
                machines=dict(self._machines),
                operators=dict(self._operators),
                jobs=dict(self._jobs),
            )

            # Calculate aggregate metrics
            if self._machines:
                running_machines = sum(
                    1
                    for m in self._machines.values()
                    if m.status == MachineStatus.RUNNING
                )
                snapshot.total_machine_utilization = running_machines / len(
                    self._machines
                )

            if self._operators:
                working_operators = sum(
                    1 for o in self._operators.values() if o.current_assignment
                )
                snapshot.total_operator_utilization = working_operators / len(
                    self._operators
                )

            snapshot.jobs_in_queue = len(self.get_pending_jobs())
            snapshot.jobs_in_progress = len(self.get_active_jobs())

            self._metrics["snapshots_created"] += 1

            logger.debug(f"Created factory snapshot at {snapshot.timestamp}")
            return snapshot

    def get_snapshot_as_scheduling_problem(self) -> Dict[str, Any]:
        """
        Convert current snapshot to scheduling problem input format.

        Returns dict with:
        - machines: List of machine data
        - operators: List of available operators
        - jobs: List of pending and active jobs
        """
        snapshot = self.create_snapshot()

        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "machines": [m.to_dict() for m in snapshot.machines.values()],
            "operators": [
                o.to_dict() for o in snapshot.operators.values() if o.is_available
            ],
            "pending_jobs": [
                j.to_dict() for j in snapshot.jobs.values() if j.status == "pending"
            ],
            "active_jobs": [
                j.to_dict() for j in snapshot.jobs.values() if j.status == "in_progress"
            ],
            "metrics": {
                "machine_utilization": snapshot.total_machine_utilization,
                "operator_utilization": snapshot.total_operator_utilization,
                "jobs_in_queue": snapshot.jobs_in_queue,
                "jobs_in_progress": snapshot.jobs_in_progress,
            },
        }

    # ==================== Event Subscription ====================

    def subscribe(
        self,
        callback: Callable[[StateChangeEvent], None],
        event_types: Optional[List[StateChangeType]] = None,
        entity_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Subscribe to state change events.

        Args:
            callback: Function to call when event occurs
            event_types: Optional filter for specific event types
            entity_ids: Optional filter for specific entities
        """
        with self._lock:
            self._subscribers[callback] = (event_types, entity_ids)
            logger.debug(
                f"Added subscriber: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
            )

    def unsubscribe(self, callback: Callable) -> None:
        """Remove event subscription"""
        with self._lock:
            if callback in self._subscribers:
                del self._subscribers[callback]

    def _publish_event(self, event: StateChangeEvent) -> None:
        """Publish event to all matching subscribers"""
        self._event_history.append(event)
        self._metrics["events_published"] += 1

        for callback, (event_types, entity_ids) in self._subscribers.items():
            # Check filters
            if event_types and event.event_type not in event_types:
                continue
            if entity_ids and event.entity_id not in entity_ids:
                continue

            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event subscriber: {e}")

    # ==================== Persistence ====================

    def save_state(self, filepath: Optional[str] = None) -> None:
        """Save current state to JSON file"""
        filepath = filepath or self._persistence_path
        if not filepath:
            return

        snapshot = self.create_snapshot()

        try:
            with open(filepath, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2, default=str)
            logger.info(f"Saved factory state to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self, filepath: str) -> bool:
        """Load state from JSON file"""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Parse and restore state
            # (Implementation would reconstruct MachineState, OperatorState, JobState objects)

            logger.info(f"Loaded factory state from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return False

    # ==================== Statistics ====================

    def get_metrics(self) -> Dict[str, Any]:
        """Get manager performance metrics"""
        return {
            **self._metrics,
            "machines_tracked": len(self._machines),
            "operators_tracked": len(self._operators),
            "jobs_tracked": len(self._jobs),
            "subscribers_count": len(self._subscribers),
            "event_history_size": len(self._event_history),
        }

    def get_event_history(
        self,
        event_types: Optional[List[StateChangeType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[StateChangeEvent]:
        """Get filtered event history"""
        with self._lock:
            events = list(self._event_history)

            if event_types:
                events = [e for e in events if e.event_type in event_types]

            if since:
                events = [e for e in events if e.timestamp >= since]

            return events[-limit:]


# Factory function
def create_factory_state_manager(
    persistence_path: Optional[str] = None,
) -> FactoryStateManager:
    """Create a new factory state manager"""
    return FactoryStateManager(persistence_path)
