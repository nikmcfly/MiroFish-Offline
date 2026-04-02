"""
Prediction Bridge - Phase 4

Feeds simulation results back to the job shop scheduler.
Processes disruption predictions, updates solver constraints, and triggers rescheduling.
"""

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Tuple
from collections import defaultdict

from ..scheduling.models import (
    SchedulingProblem,
    Schedule,
    ScheduleEntry,
    Machine,
    MachineStatus,
    MachineType,
    Operator,
    Job,
    JobPriority,
    Operation,
    OperationStatus,
)
from ..scheduling.solver import (
    JobShopSolver,
    FastHeuristicScheduler,
    SolverConfig,
)
from ..scheduling.historical_data import (
    ConstraintCalibrator,
    HistoricalDataLoader,
)
from .state_manager import FactoryStateManager
from .disruption_engine import DisruptionPrediction, DisruptionType
from ..utils.logger import get_logger

logger = get_logger("mirofish.digital_twin.prediction_bridge")


class BridgeEventType(Enum):
    """Types of events that can flow through the prediction bridge"""

    DISRUPTION_PREDICTED = auto()
    CONSTRAINT_UPDATED = auto()
    RESCHEDULE_TRIGGERED = auto()
    SCHEDULE_OPTIMIZED = auto()
    SIMULATION_FEEDBACK = auto()


@dataclass
class BridgeEvent:
    """An event flowing through the prediction bridge"""

    event_type: BridgeEventType
    timestamp: datetime
    source: str  # Component that generated the event
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more urgent


@dataclass
class SimulationFeedback:
    """
    Processed feedback from simulation to scheduler.

    Contains actionable recommendations for constraint updates,
    schedule adjustments, and parameter tuning.
    """

    feedback_type: str  # "disruption", "pattern", "constraint"
    source_prediction: Optional[DisruptionPrediction]

    # Recommendations
    recommended_constraints: Dict[str, Any] = field(default_factory=dict)
    parameter_adjustments: Dict[str, float] = field(default_factory=dict)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)

    # Confidence
    confidence: float = 0.5
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_type": self.feedback_type,
            "source_prediction": self.source_prediction.to_dict()
            if self.source_prediction
            else None,
            "recommended_constraints": self.recommended_constraints,
            "parameter_adjustments": self.parameter_adjustments,
            "risk_assessment": self.risk_assessment,
            "confidence": self.confidence,
            "generated_at": self.generated_at.isoformat(),
        }


class SimulationResultProcessor:
    """
    Processes raw simulation results into structured feedback.

    Transforms disruption predictions into:
    - Constraint updates (machine availability windows)
    - Parameter adjustments (buffer times, priority weights)
    - Risk assessments (schedule feasibility, tardiness risk)
    """

    def __init__(self):
        self._processing_stats = {
            "predictions_processed": 0,
            "feedbacks_generated": 0,
            "constraints_suggested": 0,
        }

    def process_predictions(
        self,
        predictions: List[DisruptionPrediction],
        current_problem: SchedulingProblem,
    ) -> List[SimulationFeedback]:
        """
        Process disruption predictions into scheduler feedback.

        Args:
            predictions: Disruption predictions from simulation
            current_problem: Current scheduling problem context

        Returns:
            List of actionable feedback items
        """
        feedbacks = []

        for prediction in predictions:
            try:
                feedback = self._process_single_prediction(prediction, current_problem)
                if feedback:
                    feedbacks.append(feedback)
                    self._processing_stats["feedbacks_generated"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to process prediction {prediction.entity_id}: {e}"
                )

            self._processing_stats["predictions_processed"] += 1

        logger.info(
            f"Processed {len(predictions)} predictions into {len(feedbacks)} feedback items"
        )
        return feedbacks

    def _process_single_prediction(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> Optional[SimulationFeedback]:
        """Process a single disruption prediction"""

        if prediction.disruption_type == DisruptionType.MACHINE_BREAKDOWN:
            return self._process_machine_breakdown(prediction, problem)

        elif prediction.disruption_type == DisruptionType.OPERATOR_ABSENCE:
            return self._process_operator_absence(prediction, problem)

        elif prediction.disruption_type == DisruptionType.MACHINE_DEGRADATION:
            return self._process_machine_degradation(prediction, problem)

        elif prediction.disruption_type == DisruptionType.RUSH_ORDER_ARRIVAL:
            return self._process_rush_order(prediction, problem)

        else:
            # Generic processing for other disruption types
            return self._process_generic_disruption(prediction, problem)

    def _process_machine_breakdown(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> SimulationFeedback:
        """Process machine breakdown prediction"""
        machine_id = prediction.entity_id

        # Calculate when machine will be unavailable
        downtime_start = prediction.predicted_time
        downtime_duration = timedelta(minutes=prediction.estimated_delay_minutes)
        downtime_end = downtime_start + downtime_duration

        # Find jobs affected
        affected_jobs = prediction.affected_jobs

        return SimulationFeedback(
            feedback_type="disruption",
            source_prediction=prediction,
            recommended_constraints={
                "machine_unavailable": {
                    "machine_id": machine_id,
                    "unavailable_from": downtime_start.isoformat(),
                    "unavailable_until": downtime_end.isoformat(),
                },
                "job_reassignment_candidates": affected_jobs,
            },
            parameter_adjustments={
                "buffer_factor": 1.2,  # Add 20% buffer
                "alternative_machine_weight": 1.5,  # Favor alternatives
            },
            risk_assessment={
                "schedule_feasibility": 1.0 - prediction.probability,
                "tardiness_risk": prediction.probability,
                "affected_job_count": len(affected_jobs),
                "estimated_total_delay": prediction.estimated_delay_minutes,
            },
            confidence=prediction.confidence,
        )

    def _process_operator_absence(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> SimulationFeedback:
        """Process operator absence prediction"""
        operator_id = prediction.entity_id

        return SimulationFeedback(
            feedback_type="disruption",
            source_prediction=prediction,
            recommended_constraints={
                "operator_unavailable": {
                    "operator_id": operator_id,
                    "absence_time": prediction.predicted_time.isoformat(),
                    "duration_minutes": prediction.estimated_delay_minutes,
                },
            },
            parameter_adjustments={
                "cross_training_priority": 1.3,
                "skill_constraint_relaxation": 0.8
                if prediction.alternative_resources
                else 1.0,
            },
            risk_assessment={
                "skill_shortage_risk": prediction.probability,
                "substitute_availability": len(prediction.alternative_resources),
            },
            confidence=prediction.confidence * 0.8,  # Operator predictions less certain
        )

    def _process_machine_degradation(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> SimulationFeedback:
        """Process machine degradation prediction"""
        machine_id = prediction.entity_id

        return SimulationFeedback(
            feedback_type="constraint",
            source_prediction=prediction,
            recommended_constraints={
                "machine_efficiency_reduction": {
                    "machine_id": machine_id,
                    "efficiency_factor": 0.85,  # 15% reduction
                    "from_time": prediction.predicted_time.isoformat(),
                },
            },
            parameter_adjustments={
                "processing_time_buffer": 1.15,  # 15% longer processing
                "maintenance_priority": 2.0,
            },
            risk_assessment={
                "quality_risk": prediction.probability * 0.5,
                "throughput_impact": prediction.probability * 0.3,
            },
            confidence=prediction.confidence,
        )

    def _process_rush_order(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> SimulationFeedback:
        """Process rush order arrival prediction"""
        return SimulationFeedback(
            feedback_type="constraint",
            source_prediction=prediction,
            recommended_constraints={
                "capacity_reservation": {
                    "time": prediction.predicted_time.isoformat(),
                    "flexible_capacity_percent": 20,
                },
                "preemption_rules": {
                    "allow_priority_bumping": True,
                    "max_bumped_jobs": 3,
                },
            },
            parameter_adjustments={
                "rush_order_priority_weight": 2.0,
                "existing_job_buffer": 1.1,
            },
            risk_assessment={
                "queue_disruption": prediction.probability,
                "cascading_delay_risk": prediction.probability * 0.5,
            },
            confidence=prediction.confidence * 0.6,  # Rush orders very uncertain
        )

    def _process_generic_disruption(
        self,
        prediction: DisruptionPrediction,
        problem: SchedulingProblem,
    ) -> SimulationFeedback:
        """Process generic disruption"""
        return SimulationFeedback(
            feedback_type="pattern",
            source_prediction=prediction,
            recommended_constraints={
                "general_buffer": {
                    "applies_to": prediction.entity_type,
                    "buffer_minutes": prediction.estimated_delay_minutes // 2,
                },
            },
            parameter_adjustments={
                "uncertainty_factor": 1.0 + (prediction.probability * 0.5),
            },
            risk_assessment={
                "general_risk": prediction.probability,
            },
            confidence=prediction.confidence * 0.7,
        )

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics"""
        return dict(self._processing_stats)


class ConstraintUpdater:
    """
    Updates scheduling problem constraints based on simulation feedback.

    Applies disruption predictions to:
    - Machine availability windows
    - Operator assignments
    - Job due dates and priorities
    - Processing time estimates
    """

    def __init__(self):
        self._update_history: List[Dict] = []
        self._applied_constraints: Dict[str, Any] = {}

    def apply_feedback(
        self,
        problem: SchedulingProblem,
        feedback: SimulationFeedback,
    ) -> SchedulingProblem:
        """
        Apply simulation feedback to scheduling problem.

        Returns a modified problem with updated constraints.
        """
        updated_problem = self._copy_problem(problem)

        # Apply constraint updates
        for (
            constraint_type,
            constraint_data,
        ) in feedback.recommended_constraints.items():
            try:
                if constraint_type == "machine_unavailable":
                    self._apply_machine_unavailability(updated_problem, constraint_data)

                elif constraint_type == "operator_unavailable":
                    self._apply_operator_unavailability(
                        updated_problem, constraint_data
                    )

                elif constraint_type == "machine_efficiency_reduction":
                    self._apply_efficiency_reduction(updated_problem, constraint_data)

                elif constraint_type == "capacity_reservation":
                    self._apply_capacity_reservation(updated_problem, constraint_data)

                elif constraint_type == "job_reassignment_candidates":
                    self._mark_reassignment_candidates(updated_problem, constraint_data)

                # Log the update
                self._update_history.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "constraint_type": constraint_type,
                        "data": constraint_data,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to apply constraint {constraint_type}: {e}")

        # Apply parameter adjustments
        self._apply_parameter_adjustments(
            updated_problem, feedback.parameter_adjustments
        )

        return updated_problem

    def _copy_problem(self, problem: SchedulingProblem) -> SchedulingProblem:
        """Create a copy of the scheduling problem"""
        # Shallow copy - sufficient for constraint updates
        import copy

        return copy.copy(problem)

    def _apply_machine_unavailability(
        self,
        problem: SchedulingProblem,
        constraint: Dict,
    ) -> None:
        """Mark machine as unavailable during predicted downtime"""
        machine_id = constraint["machine_id"]
        unavailable_from = datetime.fromisoformat(constraint["unavailable_from"])
        unavailable_until = datetime.fromisoformat(constraint["unavailable_until"])

        for machine in problem.machines:
            if machine.machine_id == machine_id:
                # Add maintenance window
                machine.maintenance_windows.append(
                    (unavailable_from, unavailable_until)
                )
                logger.info(
                    f"Added maintenance window for {machine_id}: "
                    f"{unavailable_from} to {unavailable_until}"
                )
                break

    def _apply_operator_unavailability(
        self,
        problem: SchedulingProblem,
        constraint: Dict,
    ) -> None:
        """Mark operator as unavailable"""
        operator_id = constraint["operator_id"]

        for operator in problem.operators:
            if operator.operator_id == operator_id:
                # Temporarily set shift to zero (unavailable)
                operator.shift_start = 0
                operator.shift_end = 0
                logger.info(f"Marked operator {operator_id} as unavailable")
                break

    def _apply_efficiency_reduction(
        self,
        problem: SchedulingProblem,
        constraint: Dict,
    ) -> None:
        """Reduce machine efficiency"""
        machine_id = constraint["machine_id"]
        efficiency_factor = constraint["efficiency_factor"]

        for machine in problem.machines:
            if machine.machine_id == machine_id:
                machine.historical_efficiency *= efficiency_factor
                logger.info(
                    f"Reduced efficiency for {machine_id} to {machine.historical_efficiency:.2%}"
                )
                break

    def _apply_capacity_reservation(
        self,
        problem: SchedulingProblem,
        constraint: Dict,
    ) -> None:
        """Reserve capacity for rush orders"""
        # Implementation would adjust available capacity
        # This is a placeholder
        logger.info("Capacity reservation applied")

    def _mark_reassignment_candidates(
        self,
        problem: SchedulingProblem,
        job_ids: List[str],
    ) -> None:
        """Mark jobs as candidates for reassignment"""
        for job in problem.jobs:
            if job.job_id in job_ids:
                # Increase alternative machine priority
                for op in job.operations:
                    # Add more alternative machine types
                    if not op.alternative_machine_types:
                        op.alternative_machine_types = []
                    # This would need actual logic based on shop layout
                logger.debug(f"Marked job {job.job_id} for reassignment consideration")

    def _apply_parameter_adjustments(
        self,
        problem: SchedulingProblem,
        adjustments: Dict[str, float],
    ) -> None:
        """Apply parameter adjustments to problem"""
        # Store adjustments for solver to use
        problem._twin_adjustments = adjustments

        # Apply buffer factor to operations
        buffer = adjustments.get("buffer_factor", 1.0)
        if buffer != 1.0:
            for job in problem.jobs:
                for op in job.operations:
                    # Scale operation durations
                    if hasattr(op, "_original_duration"):
                        op.duration = int(op._original_duration * buffer)
                    else:
                        op._original_duration = op.duration
                        op.duration = int(op.duration * buffer)

        logger.info(f"Applied parameter adjustments: {adjustments}")

    def get_update_history(self, limit: int = 100) -> List[Dict]:
        """Get history of constraint updates"""
        return self._update_history[-limit:]


class ReschedulingTrigger:
    """
    Decides when and how to trigger rescheduling based on feedback.

    Implements intelligent triggering strategies:
    - Threshold-based: Trigger when disruption probability exceeds threshold
    - Periodic: Trigger on schedule
    - Event-driven: Trigger on critical events
    - Cost-benefit: Trigger when benefit exceeds cost
    """

    def __init__(
        self,
        solver: Optional[JobShopSolver] = None,
        fast_scheduler: Optional[FastHeuristicScheduler] = None,
    ):
        self.solver = solver or JobShopSolver()
        self.fast_scheduler = fast_scheduler or FastHeuristicScheduler(
            dispatch_rule="priority"
        )

        self._trigger_history: List[Dict] = []
        self._reschedule_count = 0
        self._last_reschedule_time: Optional[datetime] = None

        # Thresholds
        self.probability_threshold = 0.5
        self.delay_threshold_minutes = 30
        self.min_time_between_reschedules = timedelta(minutes=5)

    def should_reschedule(
        self,
        feedbacks: List[SimulationFeedback],
        current_schedule: Optional[Schedule],
    ) -> Tuple[bool, str]:
        """
        Determine if rescheduling should be triggered.

        Returns:
            (should_trigger, reason)
        """
        if not feedbacks:
            return False, "No feedback to process"

        # Check time since last reschedule
        if self._last_reschedule_time:
            time_since = datetime.now() - self._last_reschedule_time
            if time_since < self.min_time_between_reschedules:
                return False, f"Too soon since last reschedule ({time_since})"

        # Check probability threshold
        max_probability = max(
            f.source_prediction.probability for f in feedbacks if f.source_prediction
        )
        if max_probability >= self.probability_threshold:
            return True, f"High disruption probability: {max_probability:.1%}"

        # Check total delay impact
        total_delay = sum(
            f.source_prediction.estimated_delay_minutes
            for f in feedbacks
            if f.source_prediction
        )
        if total_delay >= self.delay_threshold_minutes:
            return True, f"Total delay impact: {total_delay} minutes"

        # Check schedule feasibility
        high_risk_feedbacks = [
            f
            for f in feedbacks
            if f.risk_assessment.get("schedule_feasibility", 1.0) < 0.7
        ]
        if len(high_risk_feedbacks) >= 2:
            return True, f"Multiple high-risk predictions ({len(high_risk_feedbacks)})"

        return False, "No rescheduling criteria met"

    def execute_reschedule(
        self,
        problem: SchedulingProblem,
        strategy: str = "adaptive",
        progress_callback: Optional[Callable] = None,
    ) -> Optional[Schedule]:
        """
        Execute rescheduling with chosen strategy.

        Strategies:
        - "fast": Use FastHeuristicScheduler (seconds)
        - "optimal": Use JobShopSolver with CP-SAT (minutes)
        - "adaptive": Choose based on urgency
        """
        self._reschedule_count += 1
        start_time = datetime.now()

        logger.info(
            f"Starting rescheduling (strategy={strategy}, run={self._reschedule_count})"
        )

        try:
            if strategy == "fast":
                schedule = self.fast_scheduler.solve(problem)

            elif strategy == "optimal":
                schedule = self.solver.solve(problem, progress_callback)

            elif strategy == "adaptive":
                # Choose based on problem urgency
                has_critical = any(
                    job.priority in [JobPriority.RUSH, JobPriority.CRITICAL]
                    for job in problem.jobs
                )

                if has_critical:
                    schedule = self.solver.solve(problem, progress_callback)
                else:
                    schedule = self.fast_scheduler.solve(problem)

            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            elapsed = (datetime.now() - start_time).total_seconds()

            self._last_reschedule_time = datetime.now()
            self._trigger_history.append(
                {
                    "timestamp": self._last_reschedule_time.isoformat(),
                    "strategy": strategy,
                    "elapsed_seconds": elapsed,
                    "makespan": schedule.makespan if schedule else None,
                }
            )

            logger.info(
                f"Rescheduling complete in {elapsed:.1f}s, makespan={schedule.makespan if schedule else 'N/A'}"
            )
            return schedule

        except Exception as e:
            logger.error(f"Rescheduling failed: {e}")
            return None

    def get_trigger_history(self, limit: int = 50) -> List[Dict]:
        """Get history of reschedule triggers"""
        return self._trigger_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get rescheduling statistics"""
        return {
            "total_reschedules": self._reschedule_count,
            "last_reschedule": self._last_reschedule_time.isoformat()
            if self._last_reschedule_time
            else None,
            "avg_time_between_reschedules": self._calculate_avg_interval(),
        }

    def _calculate_avg_interval(self) -> Optional[float]:
        """Calculate average time between reschedules (minutes)"""
        if len(self._trigger_history) < 2:
            return None

        timestamps = [
            datetime.fromisoformat(h["timestamp"]) for h in self._trigger_history
        ]
        intervals = [
            (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
            for i in range(1, len(timestamps))
        ]

        return sum(intervals) / len(intervals)


class PredictionBridge:
    """
    Central bridge connecting simulation results to scheduler.

    Orchestrates the flow:
    1. Receive disruption predictions from simulation
    2. Process into structured feedback
    3. Update scheduling problem constraints
    4. Trigger rescheduling when appropriate
    5. Track feedback loop performance

    This is the main entry point for Phase 4 integration.
    """

    def __init__(
        self,
        state_manager: FactoryStateManager,
        solver: Optional[JobShopSolver] = None,
    ):
        """
        Initialize prediction bridge.

        Args:
            state_manager: Factory state manager for current conditions
            solver: Optional custom solver instance
        """
        self.state_manager = state_manager

        # Components
        self.result_processor = SimulationResultProcessor()
        self.constraint_updater = ConstraintUpdater()
        self.rescheduling_trigger = ReschedulingTrigger(solver=solver)

        # State
        self._current_problem: Optional[SchedulingProblem] = None
        self._current_schedule: Optional[Schedule] = None
        self._bridge_events: List[BridgeEvent] = []
        self._subscribers: List[Callable[[BridgeEvent], None]] = []

        # Performance tracking
        self._stats = {
            "predictions_received": 0,
            "feedbacks_applied": 0,
            "reschedules_triggered": 0,
            "total_delay_prevented": 0,
        }

        logger.info("PredictionBridge initialized")

    def set_current_problem(self, problem: SchedulingProblem) -> None:
        """Set the current scheduling problem context"""
        self._current_problem = problem
        logger.debug("Current scheduling problem updated")

    def set_current_schedule(self, schedule: Schedule) -> None:
        """Set the current schedule"""
        self._current_schedule = schedule
        logger.debug("Current schedule updated")

    def process_simulation_results(
        self,
        predictions: List[DisruptionPrediction],
        auto_reschedule: bool = True,
    ) -> Dict[str, Any]:
        """
        Process simulation results and optionally trigger rescheduling.

        This is the main entry point for the prediction bridge.

        Args:
            predictions: Disruption predictions from simulation
            auto_reschedule: Whether to automatically trigger rescheduling

        Returns:
            Processing results summary
        """
        if not self._current_problem:
            raise ValueError(
                "No current problem set. Call set_current_problem() first."
            )

        self._stats["predictions_received"] += len(predictions)

        # Step 1: Process predictions into feedback
        feedbacks = self.result_processor.process_predictions(
            predictions, self._current_problem
        )

        self._publish_event(
            BridgeEvent(
                event_type=BridgeEventType.SIMULATION_FEEDBACK,
                timestamp=datetime.now(),
                source="PredictionBridge",
                data={"feedbacks_generated": len(feedbacks)},
            )
        )

        # Step 2: Apply feedback to problem constraints
        updated_problem = self._current_problem
        for feedback in feedbacks:
            updated_problem = self.constraint_updater.apply_feedback(
                updated_problem, feedback
            )
            self._stats["feedbacks_applied"] += 1

        self._publish_event(
            BridgeEvent(
                event_type=BridgeEventType.CONSTRAINT_UPDATED,
                timestamp=datetime.now(),
                source="ConstraintUpdater",
                data={"constraints_applied": len(feedbacks)},
            )
        )

        # Step 3: Check if rescheduling needed
        should_reschedule, reason = self.rescheduling_trigger.should_reschedule(
            feedbacks, self._current_schedule
        )

        new_schedule = None
        if should_reschedule and auto_reschedule:
            new_schedule = self.rescheduling_trigger.execute_reschedule(updated_problem)

            if new_schedule:
                self._current_schedule = new_schedule
                self._current_problem = updated_problem
                self._stats["reschedules_triggered"] += 1

                self._publish_event(
                    BridgeEvent(
                        event_type=BridgeEventType.RESCHEDULE_TRIGGERED,
                        timestamp=datetime.now(),
                        source="ReschedulingTrigger",
                        data={
                            "reason": reason,
                            "new_makespan": new_schedule.makespan,
                        },
                    )
                )

        # Prepare results
        results = {
            "predictions_processed": len(predictions),
            "feedbacks_generated": len(feedbacks),
            "reschedule_triggered": should_reschedule and auto_reschedule,
            "reschedule_reason": reason if should_reschedule else None,
            "new_schedule_makespan": new_schedule.makespan if new_schedule else None,
            "updated_problem": updated_problem,
        }

        logger.info(
            f"Simulation results processed: {len(feedbacks)} feedbacks, "
            f"reschedule={'yes' if should_reschedule else 'no'}"
        )

        return results

    def subscribe(self, callback: Callable[[BridgeEvent], None]) -> None:
        """Subscribe to bridge events"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[BridgeEvent], None]) -> None:
        """Unsubscribe from bridge events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _publish_event(self, event: BridgeEvent) -> None:
        """Publish event to subscribers"""
        self._bridge_events.append(event)
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"Error in bridge event subscriber: {e}")

    def get_current_state(self) -> Dict[str, Any]:
        """Get current bridge state"""
        return {
            "has_problem": self._current_problem is not None,
            "has_schedule": self._current_schedule is not None,
            "makespan": self._current_schedule.makespan
            if self._current_schedule
            else None,
            "stats": dict(self._stats),
            "recent_events": len(self._bridge_events),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics"""
        return {
            **self._stats,
            "processor_stats": self.result_processor.get_stats(),
            "trigger_stats": self.rescheduling_trigger.get_stats(),
        }


def create_prediction_bridge(
    state_manager: FactoryStateManager,
    solver: Optional[JobShopSolver] = None,
) -> PredictionBridge:
    """Factory function to create a prediction bridge"""
    return PredictionBridge(state_manager, solver)
