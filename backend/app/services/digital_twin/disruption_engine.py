"""
Disruption Engine - Phase 3

Simulates realistic disruptions on the factory floor using agent-based modeling.
Generates disruption predictions that feed into the scheduler for proactive rescheduling.
"""

import random
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Tuple
from collections import defaultdict

from ..scheduling.models import (
    Machine,
    MachineStatus,
    MachineType,
    Operator,
    Job,
    JobPriority,
)
from .state_manager import (
    FactoryStateManager,
    MachineState,
    OperatorState,
    JobState,
    StateChangeEvent,
    StateChangeType,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.digital_twin.disruption_engine")


class DisruptionType(Enum):
    """Types of disruptions that can occur on the factory floor"""

    MACHINE_BREAKDOWN = auto()
    MACHINE_DEGRADATION = auto()
    OPERATOR_ABSENCE = auto()
    OPERATOR_DELAY = auto()
    RUSH_ORDER_ARRIVAL = auto()
    MATERIAL_SHORTAGE = auto()
    QUALITY_ISSUE = auto()
    SUPPLY_CHAIN_DELAY = auto()


@dataclass
class DisruptionPrediction:
    """
    A predicted disruption event from agent-based simulation.

    Contains probability, impact assessment, and recommended mitigation.
    """

    disruption_type: DisruptionType
    entity_id: str
    entity_type: str  # "machine", "operator", "job", "system"

    # Prediction metrics
    probability: float  # 0.0 to 1.0
    predicted_time: datetime
    confidence: float  # Model confidence

    # Impact assessment
    affected_jobs: List[str] = field(default_factory=list)
    estimated_delay_minutes: int = 0
    estimated_cost_impact: float = 0.0

    # Mitigation recommendations
    recommended_action: str = ""
    alternative_resources: List[str] = field(default_factory=list)

    # Metadata
    simulation_run_id: str = ""
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disruption_type": self.disruption_type.name,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "probability": self.probability,
            "predicted_time": self.predicted_time.isoformat(),
            "confidence": self.confidence,
            "affected_jobs": self.affected_jobs,
            "estimated_delay_minutes": self.estimated_delay_minutes,
            "estimated_cost_impact": self.estimated_cost_impact,
            "recommended_action": self.recommended_action,
            "alternative_resources": self.alternative_resources,
            "simulation_run_id": self.simulation_run_id,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class SimulationScenario:
    """
    A simulation scenario configuration for disruption modeling.

    Defines initial conditions, agent behaviors, and simulation parameters.
    """

    scenario_id: str
    name: str
    description: str = ""

    # Time parameters
    simulation_hours: int = 24
    time_step_minutes: int = 15

    # Disruption parameters
    base_failure_rate: float = 0.01  # Per hour
    base_absence_rate: float = 0.02  # Per operator per day
    rush_order_probability: float = 0.1  # Per day

    # Agent behavior modifiers
    machine_aggression: float = 1.0  # 0.5=cautious, 2.0=aggressive
    operator_reliability: float = 1.0  # 0.5=unreliable, 2.0=highly reliable

    # External factors
    weather_impact: float = 0.0  # 0-1, affects absenteeism
    supply_chain_stress: float = 0.0  # 0-1, affects material delays

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "simulation_hours": self.simulation_hours,
            "time_step_minutes": self.time_step_minutes,
            "base_failure_rate": self.base_failure_rate,
            "base_absence_rate": self.base_absence_rate,
            "rush_order_probability": self.rush_order_probability,
            "machine_aggression": self.machine_aggression,
            "operator_reliability": self.operator_reliability,
            "weather_impact": self.weather_impact,
            "supply_chain_stress": self.supply_chain_stress,
        }


class DisruptionSimulator(ABC):
    """
    Abstract base class for disruption simulators.

    Each simulator models a specific type of disruption using agent-based
    behaviors and historical patterns.
    """

    def __init__(self, state_manager: FactoryStateManager):
        self.state_manager = state_manager
        self.rng = random.Random()

    @abstractmethod
    def simulate(
        self,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> List[DisruptionPrediction]:
        """
        Run simulation and return predicted disruptions.

        Args:
            scenario: Simulation configuration
            current_time: Current factory time

        Returns:
            List of predicted disruptions
        """
        pass

    @abstractmethod
    def get_disruption_type(self) -> DisruptionType:
        """Return the type of disruption this simulator models"""
        pass


class MachineFailureSimulator(DisruptionSimulator):
    """
    Simulates machine breakdowns and degradation.

    Models:
    - MTBF (Mean Time Between Failures) based on machine type
    - Degradation curves based on runtime and maintenance
    - Cascading failures from workload stress
    - Historical failure patterns
    """

    # Industry-standard MTBF values (hours)
    MTBF_BY_TYPE = {
        MachineType.LASER: 1000,
        MachineType.PRESSBRAKE: 800,
        MachineType.WELDING: 1200,
        MachineType.POLISHING: 600,
        MachineType.ASSEMBLY: 1500,
        MachineType.SHIPPING: 2000,
    }

    def get_disruption_type(self) -> DisruptionType:
        return DisruptionType.MACHINE_BREAKDOWN

    def simulate(
        self,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> List[DisruptionPrediction]:
        """Simulate machine failures for the scenario period"""
        predictions = []
        machines = self.state_manager.get_all_machine_states()

        for machine_id, machine_state in machines.items():
            # Skip machines already down
            if machine_state.status == MachineStatus.DOWN:
                continue

            # Calculate failure probability
            failure_prob = self._calculate_failure_probability(machine_state, scenario)

            if failure_prob > 0.1:  # Only predict significant risks
                prediction = self._create_prediction(
                    machine_id,
                    machine_state,
                    failure_prob,
                    scenario,
                    current_time,
                )
                predictions.append(prediction)

        return predictions

    def _calculate_failure_probability(
        self,
        machine: MachineState,
        scenario: SimulationScenario,
    ) -> float:
        """Calculate probability of failure in the scenario timeframe"""
        # Base rate from machine type
        mtbf = self.MTBF_BY_TYPE.get(MachineType(machine.machine_type), 1000)

        # Convert MTBF to probability for simulation period
        hours = scenario.simulation_hours
        base_prob = 1 - (0.5 ** (hours / mtbf))

        # Adjust for machine condition
        condition_factor = 1.0

        # Age factor (based on cycle count)
        if machine.cycle_count > 10000:
            condition_factor *= 1.5
        elif machine.cycle_count > 5000:
            condition_factor *= 1.2

        # Temperature stress
        if machine.temperature and machine.temperature > 80:
            condition_factor *= 1.3

        # Maintenance status
        if machine.next_scheduled_maintenance:
            days_to_maintenance = (
                machine.next_scheduled_maintenance - datetime.now()
            ).days
            if days_to_maintenance < 0:
                condition_factor *= 2.0  # Overdue maintenance
            elif days_to_maintenance < 3:
                condition_factor *= 1.5

        # Historical performance
        if machine.availability < 0.8:
            condition_factor *= 1.4

        # Apply scenario modifiers
        aggression = scenario.machine_aggression

        final_prob = min(0.95, base_prob * condition_factor * aggression)
        return final_prob

    def _create_prediction(
        self,
        machine_id: str,
        machine: MachineState,
        probability: float,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> DisruptionPrediction:
        """Create a disruption prediction for a machine"""
        # Predict time based on MTBF distribution
        expected_time = current_time + timedelta(
            hours=random.expovariate(probability / scenario.simulation_hours)
        )

        # Estimate impact
        affected_jobs = self._get_affected_jobs(machine_id)

        # Estimate repair time (2-8 hours typical)
        repair_time = random.randint(2, 8) * 60  # minutes

        # Calculate delay impact
        delay = self._calculate_delay_impact(affected_jobs, repair_time)

        # Find alternative machines
        alternatives = self._find_alternative_machines(machine_id)

        return DisruptionPrediction(
            disruption_type=DisruptionType.MACHINE_BREAKDOWN,
            entity_id=machine_id,
            entity_type="machine",
            probability=probability,
            predicted_time=expected_time,
            confidence=0.7 if machine.availability > 0.9 else 0.5,
            affected_jobs=affected_jobs,
            estimated_delay_minutes=delay,
            estimated_cost_impact=delay * 10,  # $10/minute placeholder
            recommended_action="Schedule preventive maintenance"
            if probability < 0.5
            else "Prepare backup machine",
            alternative_resources=alternatives,
        )

    def _get_affected_jobs(self, machine_id: str) -> List[str]:
        """Get jobs currently using or queued for this machine"""
        affected = []
        active_jobs = self.state_manager.get_active_jobs()
        for job in active_jobs:
            if job.assigned_machine_id == machine_id:
                affected.append(job.job_id)
        return affected

    def _calculate_delay_impact(
        self,
        affected_jobs: List[str],
        repair_time: int,
    ) -> int:
        """Calculate total delay impact"""
        if not affected_jobs:
            return 0

        # Each affected job contributes to delay
        # Plus cascading delays to subsequent operations
        total_delay = repair_time * len(affected_jobs)

        # Add cascading delay (30% of repair time per job in queue)
        total_delay += int(repair_time * 0.3 * len(affected_jobs))

        return total_delay

    def _find_alternative_machines(self, machine_id: str) -> List[str]:
        """Find machines that could handle the same work"""
        machine = self.state_manager.get_machine_state(machine_id)
        if not machine:
            return []

        alternatives = []
        all_machines = self.state_manager.get_all_machine_states()

        for other_id, other in all_machines.items():
            if other_id != machine_id:
                if other.machine_type == machine.machine_type:
                    if other.status == MachineStatus.AVAILABLE:
                        alternatives.append(other_id)

        return alternatives[:3]  # Top 3 alternatives


class OperatorAvailabilitySimulator(DisruptionSimulator):
    """
    Simulates operator absenteeism and delays.

    Models:
    - Historical absence patterns
    - Shift-based availability
    - Skill-based substitution
    - External factors (weather, events)
    """

    def get_disruption_type(self) -> DisruptionType:
        return DisruptionType.OPERATOR_ABSENCE

    def simulate(
        self,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> List[DisruptionPrediction]:
        """Simulate operator availability disruptions"""
        predictions = []

        # Get all operators
        operators = (
            self.state_manager.get_all_machine_states()
        )  # Actually need operators
        # This is a placeholder - in real implementation, get from state_manager

        # Simulate for each operator
        for operator_id in self._get_operator_ids():
            absence_prob = self._calculate_absence_probability(operator_id, scenario)

            if absence_prob > 0.05:  # 5% threshold
                prediction = self._create_absence_prediction(
                    operator_id,
                    absence_prob,
                    scenario,
                    current_time,
                )
                predictions.append(prediction)

        return predictions

    def _get_operator_ids(self) -> List[str]:
        """Get list of tracked operator IDs"""
        # In real implementation, query state_manager
        return []

    def _calculate_absence_probability(
        self,
        operator_id: str,
        scenario: SimulationScenario,
    ) -> float:
        """Calculate probability of operator absence"""
        base_rate = scenario.base_absence_rate

        # Apply reliability factor
        reliability = scenario.operator_reliability
        adjusted_rate = base_rate / reliability

        # Apply weather impact
        weather_factor = 1.0 + (scenario.weather_impact * 0.5)

        # Day of week factor (higher on Mondays/Fridays)
        day_factor = 1.0
        weekday = datetime.now().weekday()
        if weekday in [0, 4]:  # Monday or Friday
            day_factor = 1.3

        final_prob = min(0.5, adjusted_rate * weather_factor * day_factor)
        return final_prob

    def _create_absence_prediction(
        self,
        operator_id: str,
        probability: float,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> DisruptionPrediction:
        """Create absence prediction"""
        # Predict absence in next 24 hours
        expected_time = current_time + timedelta(
            hours=random.gauss(12, 6)  # Centered around midday
        )

        # Find substitute operators with same skills
        substitutes = self._find_substitutes(operator_id)

        return DisruptionPrediction(
            disruption_type=DisruptionType.OPERATOR_ABSENCE,
            entity_id=operator_id,
            entity_type="operator",
            probability=probability,
            predicted_time=expected_time,
            confidence=0.6,
            affected_jobs=[],  # Would populate from actual assignments
            estimated_delay_minutes=30,  # Time to find substitute
            recommended_action="Cross-train backup operators"
            if not substitutes
            else "Use substitute",
            alternative_resources=substitutes,
        )

    def _find_substitutes(self, operator_id: str) -> List[str]:
        """Find operators who could substitute"""
        # Implementation would check skill compatibility
        return []


class RushOrderSimulator(DisruptionSimulator):
    """
    Simulates rush order arrivals and their impact.

    Models:
    - Customer urgency patterns
    - Market demand fluctuations
    - Contractual obligations
    - Queuing impact on existing orders
    """

    def get_disruption_type(self) -> DisruptionType:
        return DisruptionType.RUSH_ORDER_ARRIVAL

    def simulate(
        self,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> List[DisruptionPrediction]:
        """Simulate rush order arrivals"""
        predictions = []

        # Probability of rush order in scenario period
        prob = scenario.rush_order_probability

        if self.rng.random() < prob:
            prediction = self._create_rush_order_prediction(scenario, current_time)
            predictions.append(prediction)

        return predictions

    def _create_rush_order_prediction(
        self,
        scenario: SimulationScenario,
        current_time: datetime,
    ) -> DisruptionPrediction:
        """Create rush order prediction"""
        # Random arrival time in scenario period
        arrival_offset = random.randint(0, scenario.simulation_hours * 60)
        arrival_time = current_time + timedelta(minutes=arrival_offset)

        # Estimate impact on existing queue
        pending_jobs = len(self.state_manager.get_pending_jobs())
        active_jobs = len(self.state_manager.get_active_jobs())

        # Rush order typically delays others
        delay_per_job = 15  # minutes
        total_delay = delay_per_job * (pending_jobs + active_jobs) // 2

        return DisruptionPrediction(
            disruption_type=DisruptionType.RUSH_ORDER_ARRIVAL,
            entity_id=f"RUSH_{random.randint(1000, 9999)}",
            entity_type="job",
            probability=scenario.rush_order_probability,
            predicted_time=arrival_time,
            confidence=0.5,  # Market uncertainty
            affected_jobs=[],  # All jobs could be affected
            estimated_delay_minutes=total_delay,
            estimated_cost_impact=500,  # Rush fees
            recommended_action="Pre-position flexible capacity",
            alternative_resources=[],
        )


class DisruptionEngine:
    """
    Central engine for agent-based disruption simulation.

    Coordinates multiple simulators to generate comprehensive
    disruption predictions for proactive scheduling.

    Usage:
        engine = DisruptionEngine(state_manager)
        engine.register_simulator(MachineFailureSimulator())
        engine.register_simulator(OperatorAvailabilitySimulator())

        predictions = engine.simulate_scenario(scenario)
    """

    def __init__(self, state_manager: FactoryStateManager):
        """
        Initialize disruption engine.

        Args:
            state_manager: Factory state manager for current conditions
        """
        self.state_manager = state_manager
        self._simulators: Dict[DisruptionType, DisruptionSimulator] = {}
        self._prediction_history: List[DisruptionPrediction] = []

        logger.info("DisruptionEngine initialized")

    def register_simulator(self, simulator: DisruptionSimulator) -> None:
        """Register a disruption simulator"""
        disruption_type = simulator.get_disruption_type()
        self._simulators[disruption_type] = simulator
        logger.debug(f"Registered simulator: {disruption_type.name}")

    def simulate_scenario(
        self,
        scenario: SimulationScenario,
        aggregation: str = "union",
    ) -> List[DisruptionPrediction]:
        """
        Run simulation scenario across all registered simulators.

        Args:
            scenario: Simulation configuration
            aggregation: How to combine predictions ("union" or "priority")

        Returns:
            List of predicted disruptions
        """
        all_predictions = []
        current_time = datetime.now()

        logger.info(f"Running simulation scenario: {scenario.name}")

        for disruption_type, simulator in self._simulators.items():
            try:
                predictions = simulator.simulate(scenario, current_time)
                all_predictions.extend(predictions)
                logger.debug(
                    f"Simulator {disruption_type.name}: {len(predictions)} predictions"
                )
            except Exception as e:
                logger.error(f"Simulator {disruption_type.name} failed: {e}")

        # Aggregate predictions
        if aggregation == "priority":
            final_predictions = self._prioritize_predictions(all_predictions)
        else:
            final_predictions = all_predictions

        # Sort by probability
        final_predictions.sort(key=lambda p: p.probability, reverse=True)

        # Store history
        self._prediction_history.extend(final_predictions)

        logger.info(
            f"Simulation complete: {len(final_predictions)} predictions generated"
        )
        return final_predictions

    def _prioritize_predictions(
        self,
        predictions: List[DisruptionPrediction],
    ) -> List[DisruptionPrediction]:
        """
        Prioritize and deduplicate predictions.

        Keeps highest probability prediction per entity.
        """
        by_entity: Dict[str, DisruptionPrediction] = {}

        for pred in predictions:
            key = f"{pred.entity_type}:{pred.entity_id}"
            if key not in by_entity or pred.probability > by_entity[key].probability:
                by_entity[key] = pred

        return list(by_entity.values())

    def get_high_risk_predictions(
        self,
        probability_threshold: float = 0.5,
        hours_ahead: int = 24,
    ) -> List[DisruptionPrediction]:
        """Get high-risk predictions for immediate attention"""
        cutoff_time = datetime.now() + timedelta(hours=hours_ahead)

        return [
            p
            for p in self._prediction_history
            if p.probability >= probability_threshold
            and p.predicted_time <= cutoff_time
            and p.predicted_time > datetime.now()
        ]

    def get_prediction_statistics(self) -> Dict[str, Any]:
        """Get statistics on prediction accuracy and coverage"""
        if not self._prediction_history:
            return {"error": "No predictions recorded"}

        by_type = defaultdict(list)
        for p in self._prediction_history:
            by_type[p.disruption_type.name].append(p.probability)

        stats = {
            "total_predictions": len(self._prediction_history),
            "by_type": {
                t: {
                    "count": len(probs),
                    "avg_probability": statistics.mean(probs),
                    "max_probability": max(probs),
                }
                for t, probs in by_type.items()
            },
        }

        return stats

    def export_predictions(
        self,
        predictions: List[DisruptionPrediction],
        format: str = "json",
    ) -> str:
        """Export predictions to string format"""
        if format == "json":
            import json

            return json.dumps(
                [p.to_dict() for p in predictions],
                indent=2,
                default=str,
            )
        elif format == "csv":
            # Simple CSV format
            lines = ["type,entity_id,probability,predicted_time,delay_minutes"]
            for p in predictions:
                lines.append(
                    f"{p.disruption_type.name},{p.entity_id},{p.probability},"
                    f"{p.predicted_time.isoformat()},{p.estimated_delay_minutes}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")


def create_default_scenario(name: str = "Default") -> SimulationScenario:
    """Create a default simulation scenario"""
    return SimulationScenario(
        scenario_id=f"SCEN_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name=name,
        description="Standard factory operations with baseline disruption rates",
        simulation_hours=24,
        time_step_minutes=15,
        base_failure_rate=0.01,
        base_absence_rate=0.02,
        rush_order_probability=0.1,
        machine_aggression=1.0,
        operator_reliability=1.0,
        weather_impact=0.0,
        supply_chain_stress=0.0,
    )


def create_high_stress_scenario(name: str = "High Stress") -> SimulationScenario:
    """Create a high-stress simulation scenario"""
    return SimulationScenario(
        scenario_id=f"SCEN_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name=name,
        description="High-demand period with elevated disruption risks",
        simulation_hours=24,
        time_step_minutes=15,
        base_failure_rate=0.02,  # 2x failure rate
        base_absence_rate=0.05,  # 2.5x absence rate
        rush_order_probability=0.25,  # 2.5x rush orders
        machine_aggression=1.5,
        operator_reliability=0.8,
        weather_impact=0.3,  # Bad weather
        supply_chain_stress=0.4,  # Supply issues
    )


def create_optimistic_scenario(name: str = "Optimistic") -> SimulationScenario:
    """Create an optimistic simulation scenario"""
    return SimulationScenario(
        scenario_id=f"SCEN_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name=name,
        description="Best-case scenario with minimal disruptions",
        simulation_hours=24,
        time_step_minutes=15,
        base_failure_rate=0.005,  # 50% of baseline
        base_absence_rate=0.01,  # 50% of baseline
        rush_order_probability=0.05,
        machine_aggression=0.8,  # Conservative operation
        operator_reliability=1.3,  # Highly reliable
        weather_impact=0.0,
        supply_chain_stress=0.0,
    )
