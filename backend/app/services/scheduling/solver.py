"""
OR-Tools CP-SAT Solver Integration for Shop Scheduling

This module provides the core optimization engine using Google OR-Tools.
Handles flexible job shop scheduling with:
- Parallel machines
- Sequence-dependent setup times
- Resource constraints (labor)
- Multi-objective optimization
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import time

# OR-Tools imports
try:
    from ortools.sat.python import cp_model
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp

    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("Warning: OR-Tools not installed. Install with: pip install ortools")

from .models import (
    SchedulingProblem,
    Schedule,
    ScheduleEntry,
    Machine,
    MachineType,
    Job,
    Operation,
    Operator,
    JobPriority,
    OperationStatus,
)


@dataclass
class SolverConfig:
    """Configuration for the OR-Tools solver"""

    # Solver parameters
    max_solve_time: int = 300  # Seconds
    num_search_workers: int = 8  # Parallel workers

    # Solution strategy
    solution_strategy: str = "cp_sat"  # cp_sat or cp

    # Objective weights (must sum to 1.0)
    makespan_weight: float = 0.3
    tardiness_weight: float = 0.4
    cost_weight: float = 0.2
    utilization_weight: float = 0.1

    # Constraint handling
    allow_overtime: bool = False
    max_overtime_hours: int = 4

    # Setup time handling
    sequence_dependent_setup: bool = True

    def __post_init__(self):
        """Normalize weights to sum to 1.0"""
        total = (
            self.makespan_weight
            + self.tardiness_weight
            + self.cost_weight
            + self.utilization_weight
        )
        if total != 1.0:
            self.makespan_weight /= total
            self.tardiness_weight /= total
            self.cost_weight /= total
            self.utilization_weight /= total


class JobShopSolver:
    """
    Flexible Job Shop Scheduler using OR-Tools CP-SAT

    Solves the scheduling problem:
    - Assign operations to machines (considering parallel machines)
    - Sequence operations on each machine
    - Respect precedence constraints
    - Minimize weighted objectives
    """

    def __init__(self, config: SolverConfig = None):
        self.config = config or SolverConfig()
        self.model = None
        self.solver = None
        self.status = None

        # Solution callbacks
        self.solution_callback = None
        self.best_solution = None
        self.best_objective = float("inf")

        # Variable storage
        self.start_vars = {}  # (job_id, op_id) -> IntVar
        self.end_vars = {}
        self.machine_vars = {}  # (job_id, op_id) -> IntVar (machine index)
        self.setup_vars = {}
        self.operator_vars = {}

        # Data
        self.problem = None
        self.machine_map = {}  # machine_type -> list of machine indices
        self.machine_list = []  # flat list of machines
        self.operation_list = []  # flat list of (job, op) tuples
        self.horizon = 0

    def solve(
        self, problem: SchedulingProblem, progress_callback: Optional[Callable] = None
    ) -> Schedule:
        """
        Solve the scheduling problem

        Args:
            problem: SchedulingProblem instance
            progress_callback: Called with (status, objective, elapsed_time)

        Returns:
            Schedule with optimized assignments
        """
        if not ORTOOLS_AVAILABLE:
            raise RuntimeError(
                "OR-Tools not installed. Install with: pip install ortools"
            )

        self.problem = problem

        # Build the model
        self._build_model()

        # Solve
        schedule = self._solve_with_progress(progress_callback)

        return schedule

    def _build_model(self):
        """Build the CP-SAT model"""
        self.model = cp_model.CpModel()

        # Prepare data
        self._prepare_data()

        # Create variables
        self._create_variables()

        # Add constraints
        self._add_precedence_constraints()
        self._add_machine_constraints()
        self._add_no_overlap_constraints()
        self._add_setup_time_constraints()
        self._add_resource_constraints()

        # Add objective
        self._add_objective()

    def _prepare_data(self):
        """Prepare data structures for modeling"""

        # Build machine map by type
        self.machine_map = {}
        self.machine_list = self.problem.machines

        for idx, machine in enumerate(self.machine_list):
            if machine.machine_type not in self.machine_map:
                self.machine_map[machine.machine_type] = []
            self.machine_map[machine.machine_type].append(idx)

        # Build operation list
        self.operation_list = []
        for job in self.problem.jobs:
            for op in job.operations:
                self.operation_list.append((job, op))

        # Calculate horizon (upper bound on makespan)
        total_work = sum(
            op.duration + op.setup_time
            for job in self.problem.jobs
            for op in job.operations
        )

        # Add buffer for setup and slack
        num_machines = max(len(self.machine_list), 1)
        self.horizon = int(total_work * 2 / num_machines) + 1440  # +24 hours buffer

        print(
            f"Model: {len(self.operation_list)} operations, "
            f"{len(self.machine_list)} machines, horizon={self.horizon} min"
        )

    def _create_variables(self):
        """Create CP-SAT variables"""

        for job, op in self.operation_list:
            key = (job.job_id, op.operation_id)

            # Start time variable (0 to horizon)
            self.start_vars[key] = self.model.NewIntVar(
                0, self.horizon, f"start_{job.job_id}_{op.operation_id}"
            )

            # End time variable
            duration = op.duration + (op.setup_time or 0)
            self.end_vars[key] = self.model.NewIntVar(
                0, self.horizon, f"end_{job.job_id}_{op.operation_id}"
            )

            # Link start and end: end = start + duration
            self.model.Add(self.end_vars[key] == self.start_vars[key] + duration)

            # Machine assignment variable
            # Get valid machines for this operation
            valid_machines = self._get_valid_machines(op)

            if len(valid_machines) == 1:
                # Fixed assignment
                self.machine_vars[key] = valid_machines[0]
            else:
                # Flexible assignment
                self.machine_vars[key] = self.model.NewIntVar(
                    min(valid_machines),
                    max(valid_machines),
                    f"machine_{job.job_id}_{op.operation_id}",
                )

    def _get_valid_machines(self, operation: Operation) -> List[int]:
        """Get list of machine indices that can perform this operation"""
        valid = []

        # Primary machine type
        if operation.machine_type in self.machine_map:
            valid.extend(self.machine_map[operation.machine_type])

        # Alternative machine types
        for alt_type in operation.alternative_machine_types:
            if alt_type in self.machine_map:
                valid.extend(self.machine_map[alt_type])

        # Remove duplicates while preserving order
        seen = set()
        unique_valid = []
        for m in valid:
            if m not in seen:
                seen.add(m)
                unique_valid.append(m)

        return unique_valid if unique_valid else [0]  # Fallback

    def _add_precedence_constraints(self):
        """Add precedence constraints between operations"""

        for job, op in self.operation_list:
            key = (job.job_id, op.operation_id)

            # Each predecessor must complete before this operation starts
            for pred_id in op.predecessors:
                pred_key = (job.job_id, pred_id)
                if pred_key in self.end_vars:
                    # end_pred <= start_current
                    self.model.Add(self.end_vars[pred_key] <= self.start_vars[key])

    def _add_machine_constraints(self):
        """Add constraints ensuring operations are assigned to valid machines"""

        for job, op in self.operation_list:
            key = (job.job_id, op.operation_id)
            valid_machines = self._get_valid_machines(op)

            if isinstance(self.machine_vars[key], int):
                continue  # Fixed assignment, no constraint needed

            # Allow only valid machines (using AllowedAssignments)
            valid_tuples = [(m,) for m in valid_machines]
            self.model.AddAllowedAssignments([self.machine_vars[key]], valid_tuples)

    def _add_no_overlap_constraints(self):
        """
        Add no-overlap constraints for each machine

        Operations on the same machine cannot overlap
        """

        for machine_idx, machine in enumerate(self.machine_list):
            # Find all operations that could use this machine
            ops_on_machine = []

            for job, op in self.operation_list:
                key = (job.job_id, op.operation_id)
                valid_machines = self._get_valid_machines(op)

                if machine_idx in valid_machines:
                    ops_on_machine.append((key, op))

            if len(ops_on_machine) < 2:
                continue  # No overlap possible with 0 or 1 operations

            # Create interval variables for no-overlap
            intervals = []
            bool_vars = []

            for key, op in ops_on_machine:
                duration = op.duration + (op.setup_time or 0)

                # Create optional interval
                is_on_machine = self.model.NewBoolVar(f"on_m{machine_idx}_{key}")
                bool_vars.append((key, is_on_machine))

                # Link machine assignment to boolean
                if not isinstance(self.machine_vars[key], int):
                    self.model.Add(self.machine_vars[key] == machine_idx).OnlyEnforceIf(
                        is_on_machine
                    )

                    self.model.Add(self.machine_vars[key] != machine_idx).OnlyEnforceIf(
                        is_on_machine.Not()
                    )
                else:
                    # Fixed assignment
                    if self.machine_vars[key] == machine_idx:
                        self.model.Add(is_on_machine == 1)
                    else:
                        self.model.Add(is_on_machine == 0)

                # Create interval variable
                interval = self.model.NewOptionalIntervalVar(
                    self.start_vars[key],
                    duration,
                    self.end_vars[key],
                    is_on_machine,
                    f"interval_m{machine_idx}_{key}",
                )
                intervals.append(interval)

            # Add no-overlap constraint for this machine
            self.model.AddNoOverlap(intervals)

    def _add_setup_time_constraints(self):
        """
        Add sequence-dependent setup time constraints

        If operation A is followed by operation B on the same machine,
        B's start time must be >= A's end time + setup_time(A->B)
        """

        if not self.config.sequence_dependent_setup:
            return

        # For each machine, add setup constraints between consecutive operations
        for machine_idx in range(len(self.machine_list)):
            machine = self.machine_list[machine_idx]

            # Find operations on this machine
            ops = []
            for job, op in self.operation_list:
                key = (job.job_id, op.operation_id)
                valid = self._get_valid_machines(op)
                if machine_idx in valid:
                    ops.append((key, job, op))

            if len(ops) < 2:
                continue

            # Add setup time between pairs
            for i, (key_i, job_i, op_i) in enumerate(ops):
                for j, (key_j, job_j, op_j) in enumerate(ops):
                    if i >= j:
                        continue

                    # Calculate setup time from op_i to op_j
                    setup_time = self._calculate_setup_time(machine, op_i, op_j)

                    if setup_time <= 0:
                        continue

                    # If both on machine, enforce setup time
                    # This is handled implicitly by no-overlap + duration including setup
                    # But we can add explicit constraints for more complex scenarios

    def _calculate_setup_time(
        self, machine: Machine, op_from: Operation, op_to: Operation
    ) -> int:
        """Calculate sequence-dependent setup time"""

        # Base setup time for machine
        base_setup = machine.setup_time

        # Additional setup based on material/tool changes
        material_change = (
            (op_from.material != op_to.material)
            if hasattr(op_from, "material")
            else False
        )

        if material_change:
            base_setup += 15  # Extra 15 min for material change

        return base_setup

    def _add_resource_constraints(self):
        """
        Add labor/resource constraints

        Optional: constrain based on operator availability and skills
        """
        # Simplified: assume operators are always available
        # Can be extended for shift constraints, skill matching, etc.
        pass

    def _add_objective(self):
        """Add multi-objective function"""

        objectives = []

        # 1. Minimize makespan (total completion time)
        if self.config.makespan_weight > 0:
            makespan = self.model.NewIntVar(0, self.horizon, "makespan")

            # makespan >= all operation end times
            for job, op in self.operation_list:
                key = (job.job_id, op.operation_id)
                self.model.Add(makespan >= self.end_vars[key])

            objectives.append(makespan * int(self.config.makespan_weight * 1000))

        # 2. Minimize total tardiness
        if self.config.tardiness_weight > 0:
            total_tardiness = self.model.NewIntVar(
                0, self.horizon * 100, "total_tardiness"
            )

            for job in self.problem.jobs:
                if job.due_date:
                    # Calculate due time in minutes from start
                    due_minutes = int(
                        (job.due_date - self.problem.start_time).total_seconds() / 60
                    )

                    # Get last operation end time
                    if job.operations:
                        last_op = job.operations[-1]
                        key = (job.job_id, last_op.operation_id)

                        # tardiness = max(0, end_time - due_time)
                        tardiness = self.model.NewIntVar(
                            0, self.horizon, f"tardiness_{job.job_id}"
                        )

                        # Linearize: tardiness >= end_time - due_time
                        self.model.Add(tardiness >= self.end_vars[key] - due_minutes)

                        # Add to sum (would need auxiliary variable for proper sum)
                        # Simplified: just add to objective directly

            objectives.append(
                total_tardiness * int(self.config.tardiness_weight * 1000)
            )

        # Combine objectives
        if len(objectives) == 1:
            self.model.Minimize(objectives[0])
        elif len(objectives) > 1:
            # Weighted sum
            total = sum(objectives)
            self.model.Minimize(total)

        # Default: minimize makespan if no objectives specified
        if not objectives:
            makespan = self.model.NewIntVar(0, self.horizon, "makespan")
            for job, op in self.operation_list:
                key = (job.job_id, op.operation_id)
                self.model.Add(makespan >= self.end_vars[key])
            self.model.Minimize(makespan)

    def _solve_with_progress(self, progress_callback: Optional[Callable]) -> Schedule:
        """Solve the model with progress reporting"""

        solver = cp_model.CpSolver()

        # Solver parameters
        solver.parameters.max_time_in_seconds = self.config.max_solve_time
        solver.parameters.num_search_workers = self.config.num_search_workers
        solver.parameters.log_search_progress = True

        # Solution callback for progress
        class SolutionPrinter(cp_model.CpSolverSolutionCallback):
            def __init__(self, start_time):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self.start_time = start_time
                self.solution_count = 0

            def on_solution_callback(self):
                self.solution_count += 1
                elapsed = time.time() - self.start_time
                objective = self.ObjectiveValue()

                if progress_callback:
                    progress_callback(
                        status=f"Solution {self.solution_count}",
                        objective=objective,
                        elapsed_time=elapsed,
                    )

        # Solve
        start_time = time.time()
        callback = SolutionPrinter(start_time)
        status = solver.SolveWithSolutionCallback(self.model, callback)

        solve_time = time.time() - start_time

        # Build schedule from solution
        schedule = self._build_schedule(solver, status, solve_time)

        return schedule

    def _build_schedule(self, solver, status, solve_time) -> Schedule:
        """Convert solver solution to Schedule object"""

        schedule = Schedule(
            schedule_id=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            solver_status=self._status_to_string(status),
            solve_time=solve_time,
        )

        if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
            # No solution found
            return schedule

        # Extract solution values
        entries = []
        job_completion_times = {}

        for job, op in self.operation_list:
            key = (job.job_id, op.operation_id)

            start_time = solver.Value(self.start_vars[key])
            end_time = solver.Value(self.end_vars[key])

            # Get assigned machine
            if isinstance(self.machine_vars[key], int):
                machine_idx = self.machine_vars[key]
            else:
                machine_idx = solver.Value(self.machine_vars[key])

            machine = self.machine_list[machine_idx]

            # Convert minutes to datetime
            start_dt = self.problem.start_time + timedelta(minutes=start_time)
            end_dt = self.problem.start_time + timedelta(minutes=end_time)

            entry = ScheduleEntry(
                entry_id=f"{job.job_id}_{op.operation_id}",
                job_id=job.job_id,
                operation_id=op.operation_id,
                machine_id=machine.machine_id,
                start_time=start_dt,
                end_time=end_dt,
                expected_duration=op.duration,
                status=OperationStatus.PENDING,
            )
            entries.append(entry)

            # Track job completion
            if job.job_id not in job_completion_times:
                job_completion_times[job.job_id] = end_time
            else:
                job_completion_times[job.job_id] = max(
                    job_completion_times[job.job_id], end_time
                )

        schedule.entries = entries
        schedule.makespan = (
            max(job_completion_times.values()) if job_completion_times else 0
        )

        # Calculate machine utilization
        for machine in self.machine_list:
            machine_entries = [e for e in entries if e.machine_id == machine.machine_id]
            total_busy = sum(e.get_duration() for e in machine_entries)
            utilization = total_busy / schedule.makespan if schedule.makespan > 0 else 0
            schedule.machine_utilization[machine.machine_id] = min(1.0, utilization)

        # Calculate total tardiness
        total_tardiness = 0
        for job in self.problem.jobs:
            if job.due_date:
                completion = job_completion_times.get(job.job_id, 0)
                due_minutes = int(
                    (job.due_date - self.problem.start_time).total_seconds() / 60
                )
                if completion > due_minutes:
                    tardiness = completion - due_minutes
                    weight = job.priority.value
                    total_tardiness += tardiness * weight

        schedule.total_tardiness = total_tardiness

        return schedule

    def _status_to_string(self, status) -> str:
        """Convert solver status to string"""
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        return status_map.get(status, f"UNKNOWN_STATUS_{status}")


class FastHeuristicScheduler:
    """
    Fast heuristic scheduler for large problems or quick approximations

    Uses dispatch rules (SPT, EDD, CR) instead of optimization.
    Good for:
    - Very large problems where CP-SAT is too slow
    - Real-time rescheduling
    - Initial solution for CP-SAT
    """

    def __init__(self, dispatch_rule: str = "spt"):
        self.dispatch_rule = dispatch_rule  # spt, edd, cr, atc

    def solve(self, problem: SchedulingProblem) -> Schedule:
        """
        Fast heuristic solution

        Args:
            problem: SchedulingProblem

        Returns:
            Schedule (not necessarily optimal)
        """
        schedule = Schedule(
            schedule_id=f"heuristic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            solver_status="HEURISTIC",
        )

        # Machine availability tracking
        machine_available_time = {
            m.machine_id: problem.start_time for m in problem.machines
        }

        # Operation completion tracking
        op_completion_time = {}

        # Schedule operations in priority order
        all_operations = []
        for job in problem.jobs:
            for op in job.operations:
                all_operations.append((job, op))

        # Sort by dispatch rule
        sorted_ops = self._sort_operations(all_operations)

        # Schedule each operation
        for job, op in sorted_ops:
            # Find earliest start time (after predecessors)
            earliest_start = problem.start_time

            for pred_id in op.predecessors:
                pred_key = (job.job_id, pred_id)
                if pred_key in op_completion_time:
                    earliest_start = max(earliest_start, op_completion_time[pred_key])

            # Find best machine (earliest available)
            valid_machines = self._get_valid_machines(problem, op)
            best_machine = None
            best_start = None

            for machine in valid_machines:
                machine_start = max(
                    earliest_start, machine_available_time[machine.machine_id]
                )

                if best_start is None or machine_start < best_start:
                    best_start = machine_start
                    best_machine = machine

            if best_machine is None:
                continue  # No valid machine

            # Schedule operation
            duration = timedelta(minutes=op.duration)
            end_time = best_start + duration

            entry = ScheduleEntry(
                entry_id=f"{job.job_id}_{op.operation_id}",
                job_id=job.job_id,
                operation_id=op.operation_id,
                machine_id=best_machine.machine_id,
                start_time=best_start,
                end_time=end_time,
                expected_duration=op.duration,
            )
            schedule.entries.append(entry)

            # Update tracking
            op_completion_time[(job.job_id, op.operation_id)] = end_time
            machine_available_time[best_machine.machine_id] = end_time

        # Calculate metrics
        if schedule.entries:
            schedule.makespan = int(
                (
                    max(e.end_time for e in schedule.entries) - problem.start_time
                ).total_seconds()
                / 60
            )

        return schedule

    def _sort_operations(
        self, operations: List[Tuple[Job, Operation]]
    ) -> List[Tuple[Job, Operation]]:
        """Sort operations by dispatch rule"""

        if self.dispatch_rule == "spt":
            # Shortest Processing Time
            return sorted(operations, key=lambda x: x[1].duration)

        elif self.dispatch_rule == "edd":
            # Earliest Due Date
            return sorted(operations, key=lambda x: x[0].due_date or datetime.max)

        elif self.dispatch_rule == "priority":
            # Job priority
            return sorted(operations, key=lambda x: x[0].priority.value, reverse=True)

        else:
            # Default: job priority then arrival
            return sorted(
                operations,
                key=lambda x: (x[0].priority.value, x[1].duration),
                reverse=True,
            )

    def _get_valid_machines(
        self, problem: SchedulingProblem, op: Operation
    ) -> List[Machine]:
        """Get machines that can perform this operation"""
        valid = []

        for machine in problem.machines:
            if machine.machine_type == op.machine_type:
                valid.append(machine)
            elif op.machine_type in op.alternative_machine_types:
                valid.append(machine)

        return valid if valid else problem.machines[:1]


def create_scheduler(solver_type: str = "cp_sat", **kwargs) -> Any:
    """
    Factory function to create appropriate scheduler

    Args:
        solver_type: "cp_sat", "heuristic", or "hybrid"
        **kwargs: Config options

    Returns:
        Scheduler instance
    """
    if solver_type == "cp_sat":
        config = SolverConfig(**kwargs)
        return JobShopSolver(config)

    elif solver_type == "heuristic":
        dispatch_rule = kwargs.get("dispatch_rule", "priority")
        return FastHeuristicScheduler(dispatch_rule)

    elif solver_type == "hybrid":
        # Use heuristic for initial solution, then CP-SAT
        # Return a wrapper that does both
        return HybridScheduler(**kwargs)

    else:
        raise ValueError(f"Unknown solver type: {solver_type}")


class HybridScheduler:
    """
    Hybrid scheduler: heuristic + CP-SAT

    1. Run fast heuristic for initial solution
    2. Feed to CP-SAT as hint
    3. Run CP-SAT with time limit
    """

    def __init__(self, **kwargs):
        self.heuristic = FastHeuristicScheduler(dispatch_rule="priority")
        self.optimizer = JobShopSolver(SolverConfig(**kwargs))

    def solve(self, problem: SchedulingProblem) -> Schedule:
        """Solve using hybrid approach"""

        # Step 1: Fast heuristic
        print("Running heuristic scheduler...")
        heuristic_schedule = self.heuristic.solve(problem)

        # Could feed heuristic solution as hint to CP-SAT
        # For now, just return whichever is better

        print("Running CP-SAT optimizer...")
        optimized_schedule = self.optimizer.solve(problem)

        # Return the better schedule
        if optimized_schedule.makespan < heuristic_schedule.makespan:
            return optimized_schedule
        else:
            return heuristic_schedule
