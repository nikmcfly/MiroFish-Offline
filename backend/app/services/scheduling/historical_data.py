"""
Historical Data Integration for Realistic Scheduling

Learns from past job performance to set accurate processing times,
predict bottlenecks, and calibrate constraints.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import statistics
from collections import defaultdict

from .models import (
    Machine,
    MachineType,
    Job,
    Operation,
    Operator,
    LaborSkill,
    SchedulingProblem,
)


@dataclass
class HistoricalJobRecord:
    """Historical record of a completed job"""

    job_id: str
    job_type: str
    material: str
    quantity: int

    # Planned vs actual
    planned_start: datetime
    planned_end: datetime
    actual_start: datetime
    actual_end: datetime

    # Operations
    operations: List[Dict[str, Any]]  # List of operation records

    # Outcome
    on_time: bool
    quality_score: float  # 0-1

    def get_total_duration(self) -> timedelta:
        return self.actual_end - self.actual_start

    def get_tardiness(self) -> timedelta:
        if self.actual_end > self.planned_end:
            return self.actual_end - self.planned_end
        return timedelta(0)


@dataclass
class MachinePerformance:
    """Historical performance metrics for a machine"""

    machine_id: str
    machine_type: MachineType

    # Uptime metrics
    total_hours: float = 0
    uptime_hours: float = 0
    availability_pct: float = 0.95

    # Efficiency
    theoretical_output: float = 0
    actual_output: float = 0
    efficiency_pct: float = 0.85

    # Setup times
    setup_times: List[float] = field(default_factory=list)  # Minutes
    avg_setup_time: float = 15.0
    std_setup_time: float = 5.0

    # Processing times by operation type
    processing_times: Dict[str, List[float]] = field(default_factory=dict)
    avg_processing_time: Dict[str, float] = field(default_factory=dict)

    # Maintenance patterns
    mtbf_hours: float = 1000.0  # Mean time between failures
    mttr_hours: float = 4.0  # Mean time to repair

    def update_statistics(self):
        """Recalculate derived statistics"""
        if self.total_hours > 0:
            self.availability_pct = self.uptime_hours / self.total_hours

        if self.theoretical_output > 0:
            self.efficiency_pct = self.actual_output / self.theoretical_output

        if self.setup_times:
            self.avg_setup_time = statistics.mean(self.setup_times)
            if len(self.setup_times) > 1:
                self.std_setup_time = statistics.stdev(self.setup_times)

        for op_type, times in self.processing_times.items():
            if times:
                self.avg_processing_time[op_type] = statistics.mean(times)


@dataclass
class OperatorPerformance:
    """Historical performance metrics for an operator"""

    operator_id: str

    # Productivity
    jobs_completed: int = 0
    total_hours_worked: float = 0
    output_rate: float = 1.0  # Relative to standard

    # Quality
    defect_rate: float = 0.02
    rework_rate: float = 0.05

    # Skills demonstrated
    demonstrated_skills: Dict[str, float] = field(default_factory=dict)

    def get_efficiency(self) -> float:
        """Get operator efficiency factor"""
        return self.output_rate * (1 - self.defect_rate)


class HistoricalDataLoader:
    """
    Loads and processes historical manufacturing data

    Connects to production database or files to extract
    historical job and machine performance data.
    """

    def __init__(self, data_source: str = "database"):
        self.data_source = data_source
        self.logger = self._get_logger()

        # Cached data
        self.job_history: List[HistoricalJobRecord] = []
        self.machine_performance: Dict[str, MachinePerformance] = {}
        self.operator_performance: Dict[str, OperatorPerformance] = {}

    def _get_logger(self):
        from ....utils.logger import get_logger

        return get_logger("mirofish.scheduling.HistoricalDataLoader")

    def load_from_database(
        self, connection_string: str, date_range: Tuple[datetime, datetime]
    ) -> bool:
        """
        Load historical data from production database

        Args:
            connection_string: Database connection
            date_range: (start_date, end_date) for history

        Returns:
            True if successful
        """
        try:
            import psycopg2

            conn = psycopg2.connect(connection_string)
            cursor = conn.cursor()

            # Load completed jobs
            cursor.execute(
                """
                SELECT 
                    job_id, job_type, material, quantity,
                    planned_start, planned_end, actual_start, actual_end,
                    on_time, quality_score
                FROM jobs 
                WHERE actual_end IS NOT NULL
                AND actual_start BETWEEN %s AND %s
            """,
                date_range,
            )

            for row in cursor.fetchall():
                record = HistoricalJobRecord(
                    job_id=row[0],
                    job_type=row[1],
                    material=row[2],
                    quantity=row[3],
                    planned_start=row[4],
                    planned_end=row[5],
                    actual_start=row[6],
                    actual_end=row[7],
                    on_time=row[8],
                    quality_score=row[9],
                    operations=self._load_operations(cursor, row[0]),
                )
                self.job_history.append(record)

            # Load machine performance
            cursor.execute("""
                SELECT machine_id, machine_type, 
                       total_hours, uptime_hours,
                       theoretical_output, actual_output
                FROM machine_performance
            """)

            for row in cursor.fetchall():
                perf = MachinePerformance(
                    machine_id=row[0],
                    machine_type=MachineType(row[1]),
                    total_hours=row[2],
                    uptime_hours=row[3],
                    theoretical_output=row[4],
                    actual_output=row[5],
                )
                self.machine_performance[row[0]] = perf

            conn.close()
            self.logger.info(f"Loaded {len(self.job_history)} historical jobs")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load historical data: {e}")
            return False

    def load_from_json(self, filepath: str) -> bool:
        """Load historical data from JSON export"""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Load job records
            for job_data in data.get("jobs", []):
                record = HistoricalJobRecord(
                    job_id=job_data["job_id"],
                    job_type=job_data.get("job_type", "unknown"),
                    material=job_data.get("material"),
                    quantity=job_data.get("quantity", 1),
                    planned_start=datetime.fromisoformat(job_data["planned_start"]),
                    planned_end=datetime.fromisoformat(job_data["planned_end"]),
                    actual_start=datetime.fromisoformat(job_data["actual_start"]),
                    actual_end=datetime.fromisoformat(job_data["actual_end"]),
                    on_time=job_data.get("on_time", True),
                    quality_score=job_data.get("quality_score", 1.0),
                    operations=job_data.get("operations", []),
                )
                self.job_history.append(record)

            # Load machine performance
            for machine_id, perf_data in data.get("machines", {}).items():
                perf = MachinePerformance(
                    machine_id=machine_id,
                    machine_type=MachineType(perf_data["machine_type"]),
                    **{k: v for k, v in perf_data.items() if k != "machine_type"},
                )
                self.machine_performance[machine_id] = perf

            self.logger.info(f"Loaded {len(self.job_history)} jobs from JSON")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load JSON: {e}")
            return False

    def _load_operations(self, cursor, job_id: str) -> List[Dict[str, Any]]:
        """Load operation details for a job"""
        cursor.execute(
            """
            SELECT operation_id, machine_id, 
                   planned_duration, actual_duration,
                   setup_time
            FROM job_operations
            WHERE job_id = %s
        """,
            (job_id,),
        )

        operations = []
        for row in cursor.fetchall():
            operations.append(
                {
                    "operation_id": row[0],
                    "machine_id": row[1],
                    "planned_duration": row[2],
                    "actual_duration": row[3],
                    "setup_time": row[4],
                }
            )
        return operations

    def get_average_job_duration(
        self, job_type: str, material: Optional[str] = None
    ) -> Optional[timedelta]:
        """Get average duration for a job type"""
        matching = [
            j.get_total_duration()
            for j in self.job_history
            if j.job_type == job_type and (material is None or j.material == material)
        ]

        if not matching:
            return None

        avg_seconds = statistics.mean([d.total_seconds() for d in matching])
        return timedelta(seconds=avg_seconds)

    def get_on_time_rate(self, job_type: str) -> float:
        """Get historical on-time delivery rate for job type"""
        matching = [j for j in self.job_history if j.job_type == job_type]
        if not matching:
            return 0.8  # Default assumption

        on_time_count = sum(1 for j in matching if j.on_time)
        return on_time_count / len(matching)

    def get_bottleneck_machines(self, top_n: int = 3) -> List[Tuple[str, float]]:
        """Identify machines that are most often the bottleneck"""
        bottleneck_counts = defaultdict(int)

        for job in self.job_history:
            if job.operations:
                # Find operation with longest actual duration
                longest_op = max(
                    job.operations, key=lambda x: x.get("actual_duration", 0)
                )
                machine_id = longest_op.get("machine_id")
                if machine_id:
                    bottleneck_counts[machine_id] += 1

        # Sort by frequency
        sorted_bottlenecks = sorted(
            bottleneck_counts.items(), key=lambda x: x[1], reverse=True
        )

        return sorted_bottlenecks[:top_n]


class ConstraintCalibrator:
    """
    Calibrates scheduling constraints based on historical data

    Uses past performance to set realistic processing times,
    buffer factors, and machine efficiency parameters.
    """

    def __init__(self, loader: HistoricalDataLoader):
        self.loader = loader
        self.logger = self._get_logger()

    def _get_logger(self):
        from ....utils.logger import get_logger

        return get_logger("mirofish.scheduling.ConstraintCalibrator")

    def calibrate_machine(self, machine: Machine) -> Machine:
        """
        Calibrate machine parameters from historical data

        Args:
            machine: Machine to calibrate

        Returns:
            Calibrated machine
        """
        perf = self.loader.machine_performance.get(machine.machine_id)
        if not perf:
            self.logger.warning(f"No historical data for machine {machine.machine_id}")
            return machine

        # Update efficiency
        machine.historical_efficiency = perf.efficiency_pct
        machine.historical_uptime = perf.availability_pct
        machine.avg_setup_time = perf.avg_setup_time

        # Adjust capacity based on efficiency
        effective_capacity = machine.capacity * perf.efficiency_pct

        self.logger.info(
            f"Calibrated {machine.name}: "
            f"efficiency={perf.efficiency_pct:.1%}, "
            f"uptime={perf.availability_pct:.1%}"
        )

        return machine

    def calibrate_operation(
        self, operation: Operation, machine_type: MachineType
    ) -> Operation:
        """
        Calibrate operation duration from historical data

        Uses average actual processing time for similar operations,
        adds buffer based on variability.
        """
        # Find historical records for this operation type on this machine type
        similar_ops = []

        for job in self.loader.job_history:
            for op_record in job.operations:
                if op_record.get("machine_type") == machine_type.value:
                    actual = op_record.get("actual_duration")
                    if actual:
                        similar_ops.append(actual)

        if len(similar_ops) < 3:
            self.logger.warning(
                f"Insufficient historical data for {operation.operation_id}"
            )
            return operation

        # Calculate statistics
        avg_duration = statistics.mean(similar_ops)
        std_duration = statistics.stdev(similar_ops) if len(similar_ops) > 1 else 0

        # Set calibrated duration (mean + 1 std for safety)
        calibrated = avg_duration + std_duration

        operation.historical_avg_duration = avg_duration
        operation.duration = int(calibrated)

        self.logger.info(
            f"Calibrated {operation.operation_id}: "
            f"duration={operation.duration}min "
            f"(avg={avg_duration:.1f}, std={std_duration:.1f})"
        )

        return operation

    def calibrate_problem(self, problem: SchedulingProblem) -> SchedulingProblem:
        """
        Calibrate entire scheduling problem

        Args:
            problem: Scheduling problem to calibrate

        Returns:
            Calibrated problem
        """
        # Calibrate machines
        for machine in problem.machines:
            self.calibrate_machine(machine)

        # Calibrate operations
        for job in problem.jobs:
            for op in job.operations:
                self.calibrate_operation(op, op.machine_type)

            # Calibrate job due dates based on historical performance
            if job.due_date and job.operations:
                historical_duration = self.loader.get_average_job_duration(
                    job.material or "unknown"
                )
                if historical_duration:
                    # Adjust for efficiency
                    job.historical_similar_job_duration = int(
                        historical_duration.total_seconds() / 60
                    )

        self.logger.info("Problem calibration complete")
        return problem

    def estimate_confidence(self, problem: SchedulingProblem) -> float:
        """
        Estimate confidence level for schedule feasibility

        Based on historical on-time rate for similar jobs.
        """
        if not self.loader.job_history:
            return 0.5  # Unknown

        confidences = []
        for job in problem.jobs:
            on_time_rate = self.loader.get_on_time_rate(job.material or "unknown")
            confidences.append(on_time_rate)

        return statistics.mean(confidences) if confidences else 0.5

    def suggest_buffer_factor(self, problem: SchedulingProblem) -> float:
        """
        Suggest time buffer factor based on historical variability

        Returns factor to multiply planned durations by
        to achieve desired service level.
        """
        # Analyze historical tardiness
        tardiness_ratios = []
        for job in self.loader.job_history:
            if not job.on_time and job.planned_end:
                tardiness = job.get_tardiness()
                planned_duration = job.planned_end - job.planned_start
                if planned_duration.total_seconds() > 0:
                    ratio = tardiness.total_seconds() / planned_duration.total_seconds()
                    tardiness_ratios.append(ratio)

        if not tardiness_ratios:
            return 1.1  # 10% buffer default

        # Suggest buffer at 90th percentile of tardiness
        buffer = statistics.quantiles(tardiness_ratios, n=10)[-1]
        return 1.0 + min(buffer, 0.5)  # Cap at 50% buffer


class RealisticConstraintBuilder:
    """
    Builds realistic constraints using historical data

    Creates scheduling constraints that reflect actual
    shop floor performance rather than theoretical values.
    """

    def __init__(self, loader: HistoricalDataLoader):
        self.loader = loader

    def build_setup_time_matrix(
        self, machines: List[Machine]
    ) -> Dict[Tuple[str, str], int]:
        """
        Build sequence-dependent setup time matrix

        Analyzes historical setup times based on:
        - Material changes
        - Tool changes
        - Previous operation type

        Returns dict: (from_op, to_op) -> setup_time_minutes
        """
        setup_matrix = defaultdict(list)

        # Analyze historical job sequences
        for job in self.loader.job_history:
            ops = job.operations
            for i in range(1, len(ops)):
                prev_op = ops[i - 1]
                curr_op = ops[i]

                # Key: (prev_material, curr_material, prev_type, curr_type)
                key = (
                    prev_op.get("material", "unknown"),
                    curr_op.get("material", "unknown"),
                    prev_op.get("operation_type", "unknown"),
                    curr_op.get("operation_type", "unknown"),
                )

                setup_time = curr_op.get("setup_time", 15)
                setup_matrix[key].append(setup_time)

        # Calculate average setup times
        result = {}
        for key, times in setup_matrix.items():
            result[key] = int(statistics.mean(times))

        return result

    def build_machine_eligibility(self, operation: Operation) -> List[MachineType]:
        """
        Build list of eligible machine types based on historical success

        Only includes machine types that have successfully
        completed similar operations in the past.
        """
        eligible = []

        for job in self.loader.job_history:
            for op_record in job.operations:
                if op_record.get("operation_type") == operation.name:
                    machine_type = op_record.get("machine_type")
                    if machine_type:
                        try:
                            mt = MachineType(machine_type)
                            if mt not in eligible:
                                eligible.append(mt)
                        except ValueError:
                            pass

        return eligible if eligible else [operation.machine_type]

    def estimate_quality_yield(self, machine: Machine, operation: Operation) -> float:
        """
        Estimate quality yield for operation on machine

        Based on historical defect rates.
        """
        perf = self.loader.machine_performance.get(machine.machine_id)
        if not perf:
            return 0.95  # Default

        # Could be more sophisticated based on operation type
        return 1.0 - perf.efficiency_pct * 0.1  # Simplified


# Factory function for common calibration workflows


def create_realistic_problem(
    base_problem: SchedulingProblem,
    historical_data_path: Optional[str] = None,
    database_connection: Optional[str] = None,
    date_range: Optional[Tuple[datetime, datetime]] = None,
) -> SchedulingProblem:
    """
    Create a scheduling problem with realistic constraints

    Args:
        base_problem: Base problem definition
        historical_data_path: Path to JSON history file
        database_connection: Database connection string
        date_range: Date range for historical data

    Returns:
        Calibrated scheduling problem
    """
    loader = HistoricalDataLoader()

    # Load historical data
    if historical_data_path:
        loader.load_from_json(historical_data_path)
    elif database_connection and date_range:
        loader.load_from_database(database_connection, date_range)
    else:
        # Use default/synthetic data
        return base_problem

    # Calibrate
    calibrator = ConstraintCalibrator(loader)
    calibrated = calibrator.calibrate_problem(base_problem)

    # Log calibration results
    confidence = calibrator.estimate_confidence(calibrated)
    buffer = calibrator.suggest_buffer_factor(calibrated)

    print(f"Calibration complete:")
    print(f"  - Confidence: {confidence:.1%}")
    print(f"  - Suggested buffer: {buffer:.1%}")

    return calibrated
