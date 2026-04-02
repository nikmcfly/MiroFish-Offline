"""
Entity Mapper - Phase 1

Maps scheduling system entities (Machines, Operators, Jobs) to OASIS agent profiles
for MiroFish simulation. Each factory entity becomes an agent with realistic behaviors.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, TypeVar, Generic, Type
import uuid

from ..scheduling.models import (
    Machine,
    MachineType,
    MachineStatus,
    Operator,
    LaborSkill,
    Job,
    JobPriority,
    Operation,
)
from ..oasis_profile_generator import OasisAgentProfile


@dataclass
class AgentMappingConfig:
    """Configuration for entity-to-agent mapping"""

    # Activity levels by entity type
    machine_activity_base: float = 0.3
    operator_activity_base: float = 0.7
    job_activity_base: float = 0.5

    # Influence weights (for agent interactions)
    machine_influence: float = 2.5  # Machines are central
    operator_influence: float = 1.5
    job_influence: float = 1.0

    # Response delays (simulation minutes)
    machine_response_delay: int = 30
    operator_response_delay: int = 5
    job_response_delay: int = 10

    # Shift hours for factory floor
    shift_start_hour: int = 7
    shift_end_hour: int = 19

    # Personality generation
    generate_mbti: bool = True
    generate_personality: bool = True


class SchedulingEntityMapper(ABC):
    """
    Abstract base class for mapping scheduling entities to OASIS agent profiles.

    Each mapper handles one entity type and creates agent profiles with:
    - Realistic factory floor behaviors
    - Appropriate activity patterns (shift hours, breaks)
    - Entity-specific attributes (skills, capacities, etc.)
    """

    def __init__(self, config: AgentMappingConfig = None):
        self.config = config or AgentMappingConfig()

    @abstractmethod
    def map_to_agent(self, entity: Any, user_id: int) -> OasisAgentProfile:
        """Map a scheduling entity to an OASIS agent profile"""
        pass

    @abstractmethod
    def get_entity_type(self) -> str:
        """Return the entity type this mapper handles"""
        pass

    def _generate_username(self, name: str) -> str:
        """Generate a clean username from entity name"""
        clean = name.lower().replace(" ", "_").replace("-", "_")
        clean = "".join(c for c in clean if c.isalnum() or c == "_")
        suffix = random.randint(100, 999)
        return f"{clean}_{suffix}"

    def _get_factory_active_hours(self) -> List[int]:
        """Get active hours based on shift schedule"""
        return list(range(self.config.shift_start_hour, self.config.shift_end_hour))

    def _generate_mbti(self) -> str:
        """Generate random MBTI type for personality"""
        types = [
            "ISTJ",
            "ISFJ",
            "INFJ",
            "INTJ",
            "ISTP",
            "ISFP",
            "INFP",
            "INTP",
            "ESTP",
            "ESFP",
            "ENFP",
            "ENTP",
            "ESTJ",
            "ESFJ",
            "ENFJ",
            "ENTJ",
        ]
        return random.choice(types)


class MachineAgentMapper(SchedulingEntityMapper):
    """
    Maps Machine entities to agent profiles representing factory equipment.

    Machine agents have:
    - Low activity but high influence (when they act, it matters)
    - Strict shift-based active hours
    - Personas reflecting their function and reliability
    """

    def get_entity_type(self) -> str:
        return "Machine"

    def map_to_agent(self, machine: Machine, user_id: int) -> OasisAgentProfile:
        """Convert a Machine to an OASIS agent profile"""
        username = self._generate_username(machine.name)

        # Generate persona based on machine type
        persona = self._generate_machine_persona(machine)
        bio = self._generate_machine_bio(machine)

        # Active hours: machines run during shifts
        active_hours = self._get_factory_active_hours()

        # Activity level based on machine reliability
        activity = self.config.machine_activity_base
        if machine.status == MachineStatus.DOWN:
            activity = 0.05  # Minimal activity when down
        elif machine.historical_uptime < 0.8:
            activity = 0.2  # Lower activity for unreliable machines

        # Influence: machines are central to operations
        influence = self.config.machine_influence

        # Generate profile
        profile = OasisAgentProfile(
            user_id=user_id,
            user_name=username,
            name=machine.name,
            bio=bio,
            persona=persona,
            karma=random.randint(2000, 5000),  # High karma for importance
            friend_count=random.randint(50, 150),
            follower_count=random.randint(200, 800),
            statuses_count=random.randint(500, 2000),
            age=None,  # Machines don't have age
            gender=None,
            mbti="ISTJ"
            if self.config.generate_mbti
            else None,  # Machines are systematic
            country="US",
            profession=self._get_machine_profession(machine),
            interested_topics=self._get_machine_topics(machine),
            source_entity_uuid=machine.machine_id,
            source_entity_type="Machine",
        )

        # Store additional machine metadata for simulation use
        profile._machine_type = machine.machine_type.value
        profile._machine_status = machine.status.value
        profile._capacity = machine.capacity
        profile._historical_efficiency = machine.historical_efficiency
        profile._historical_uptime = machine.historical_uptime

        return profile

    def _generate_machine_persona(self, machine: Machine) -> str:
        """Generate a detailed persona for a machine"""
        type_desc = {
            MachineType.LASER: "precision cutting equipment",
            MachineType.PRESSBRAKE: "metal forming press",
            MachineType.WELDING: "welding station",
            MachineType.POLISHING: "surface finishing equipment",
            MachineType.ASSEMBLY: "assembly workstation",
            MachineType.SHIPPING: "dispatch and logistics station",
        }

        machine_desc = type_desc.get(machine.machine_type, "industrial equipment")

        reliability = (
            "highly reliable"
            if machine.historical_uptime > 0.9
            else "moderately reliable"
            if machine.historical_uptime > 0.75
            else "frequently needs attention"
        )

        efficiency = (
            "operates at peak efficiency"
            if machine.historical_efficiency > 0.9
            else "maintains good throughput"
            if machine.historical_efficiency > 0.75
            else "runs below optimal capacity"
        )

        persona = f"""I am {machine.name}, a {machine_desc} on the factory floor. {efficiency} with {machine.capacity} units per hour capacity. Known to be {reliability} with {machine.historical_uptime:.0%} uptime historically. I operate during shift hours and respond to maintenance needs and production demands. When I'm down, the whole line feels it. I have strong relationships with the operators who run me and the maintenance team that keeps me running. My personality is systematic and dependable - I communicate status changes clearly and don't like surprises."""

        return persona

    def _generate_machine_bio(self, machine: Machine) -> str:
        """Generate a short bio for the machine"""
        return f"{machine.machine_type.value.title()} equipment | Capacity: {machine.capacity}/hr | Efficiency: {machine.historical_efficiency:.0%}"

    def _get_machine_profession(self, machine: Machine) -> str:
        """Get profession description for machine"""
        professions = {
            MachineType.LASER: "Precision Cutting Equipment",
            MachineType.PRESSBRAKE: "Metal Forming Press",
            MachineType.WELDING: "Welding Station",
            MachineType.POLISHING: "Surface Finishing",
            MachineType.ASSEMBLY: "Assembly Workstation",
            MachineType.SHIPPING: "Logistics Station",
        }
        return professions.get(machine.machine_type, "Industrial Equipment")

    def _get_machine_topics(self, machine: Machine) -> List[str]:
        """Get interested topics for machine agent"""
        base_topics = ["Maintenance", "Production Schedule", "Quality Control"]

        type_topics = {
            MachineType.LASER: ["Precision", "Cutting Parameters", "Material Types"],
            MachineType.PRESSBRAKE: ["Bend Angles", "Die Selection", "Forming"],
            MachineType.WELDING: ["Weld Quality", "Joint Preparation", "Consumables"],
            MachineType.POLISHING: ["Surface Finish", "Abrasive Selection"],
            MachineType.ASSEMBLY: ["Build Quality", "Component Fit", "Testing"],
            MachineType.SHIPPING: ["Logistics", "Packaging", "Delivery Windows"],
        }

        return base_topics + type_topics.get(machine.machine_type, [])


class OperatorAgentMapper(SchedulingEntityMapper):
    """
    Maps Operator entities to agent profiles representing factory workers.

    Operator agents have:
    - High activity during shifts
    - Skills-based influence and interactions
    - Realistic shift patterns and break times
    """

    def get_entity_type(self) -> str:
        return "Operator"

    def map_to_agent(self, operator: Operator, user_id: int) -> OasisAgentProfile:
        """Convert an Operator to an OASIS agent profile"""
        username = self._generate_username(operator.name)

        # Generate persona based on operator characteristics
        persona = self._generate_operator_persona(operator)
        bio = self._generate_operator_bio(operator)

        # Active hours: operator's shift
        active_hours = list(range(operator.shift_start, operator.shift_end))

        # Activity level based on efficiency
        activity = self.config.operator_activity_base * operator.efficiency_factor

        # Influence based on skill level and experience
        influence = self.config.operator_influence
        if len(operator.skills) > 3:
            influence += 0.5  # Skilled operators have more influence

        # Generate profile
        profile = OasisAgentProfile(
            user_id=user_id,
            user_name=username,
            name=operator.name,
            bio=bio,
            persona=persona,
            karma=random.randint(800, 2500),
            friend_count=random.randint(100, 300),
            follower_count=random.randint(150, 500),
            statuses_count=random.randint(800, 3000),
            age=random.randint(22, 55),
            gender=random.choice(["male", "female"]),
            mbti=self._generate_mbti() if self.config.generate_mbti else None,
            country="US",
            profession=self._get_operator_profession(operator),
            interested_topics=self._get_operator_topics(operator),
            source_entity_uuid=operator.operator_id,
            source_entity_type="Operator",
        )

        # Store operator metadata
        profile._skills = operator.skills
        profile._skill_levels = operator.skill_levels
        profile._shift_start = operator.shift_start
        profile._shift_end = operator.shift_end
        profile._hourly_rate = operator.hourly_rate
        profile._efficiency_factor = operator.efficiency_factor

        return profile

    def _generate_operator_persona(self, operator: Operator) -> str:
        """Generate a detailed persona for an operator"""
        skills_str = (
            ", ".join(operator.skills[:5]) if operator.skills else "general operations"
        )

        experience_level = (
            "experienced"
            if len(operator.skills) > 3
            else "skilled"
            if len(operator.skills) > 1
            else "newer"
        )

        efficiency_desc = (
            "highly efficient"
            if operator.efficiency_factor > 1.0
            else "consistently productive"
            if operator.efficiency_factor > 0.9
            else "building efficiency"
        )

        persona = f"""I am {operator.name}, a factory floor operator working the {operator.shift_start}:00 to {operator.shift_end}:00 shift. I am {experience_level} with expertise in {skills_str}. I'm {efficiency_desc} at my work with an efficiency rating of {operator.efficiency_factor:.2f}. I care deeply about quality and safety. I communicate frequently with my team and supervisors about production status, equipment issues, and job progress. I'm proactive about reporting problems and suggesting improvements. My personality is practical and hands-on - I believe in doing the job right the first time. I value clear communication and reliable equipment."""

        return persona

    def _generate_operator_bio(self, operator: Operator) -> str:
        """Generate a short bio for the operator"""
        top_skill = operator.skills[0] if operator.skills else "Operations"
        return f"Factory Operator | {top_skill} Specialist | Shift: {operator.shift_start}:00-{operator.shift_end}:00"

    def _get_operator_profession(self, operator: Operator) -> str:
        """Get profession description for operator"""
        if not operator.skills:
            return "Factory Operator"

        # Use primary skill for profession
        skill_to_profession = {
            "welding": "Certified Welder",
            "cnc": "CNC Machinist",
            "assembly": "Assembly Technician",
            "quality": "Quality Inspector",
            "maintenance": "Maintenance Technician",
            "laser": "Laser Operator",
            "forming": "Forming Specialist",
        }

        primary_skill = operator.skills[0].lower()
        return skill_to_profession.get(primary_skill, "Factory Operator")

    def _get_operator_topics(self, operator: Operator) -> List[str]:
        """Get interested topics for operator agent"""
        base_topics = ["Workplace Safety", "Production Targets", "Team Communication"]

        skill_topics = []
        for skill in operator.skills[:3]:
            skill_lower = skill.lower()
            if "weld" in skill_lower:
                skill_topics.extend(["Welding Techniques", "Joint Quality"])
            elif "cnc" in skill_lower or "machin" in skill_lower:
                skill_topics.extend(["Programming", "Tooling"])
            elif "quality" in skill_lower:
                skill_topics.extend(["Inspection", "Defect Prevention"])
            elif "maint" in skill_lower:
                skill_topics.extend(["Preventive Maintenance", "Troubleshooting"])
            else:
                skill_topics.append(skill)

        return base_topics + skill_topics


class JobAgentMapper(SchedulingEntityMapper):
    """
    Maps Job entities to agent profiles representing production orders.

    Job agents have:
    - Activity based on job urgency (priority)
    - Lifecycle-based active periods (from release to completion)
    - Stakeholder communication patterns
    """

    def get_entity_type(self) -> str:
        return "Job"

    def map_to_agent(self, job: Job, user_id: int) -> OasisAgentProfile:
        """Convert a Job to an OASIS agent profile"""
        username = self._generate_username(job.name)

        # Generate persona based on job characteristics
        persona = self._generate_job_persona(job)
        bio = self._generate_job_bio(job)

        # Activity based on priority
        priority_activity = {
            JobPriority.LOW: 0.3,
            JobPriority.NORMAL: 0.5,
            JobPriority.HIGH: 0.7,
            JobPriority.RUSH: 0.9,
            JobPriority.CRITICAL: 1.0,
        }
        activity = priority_activity.get(job.priority, 0.5)

        # Influence based on priority
        priority_influence = {
            JobPriority.LOW: 0.8,
            JobPriority.NORMAL: 1.0,
            JobPriority.HIGH: 1.5,
            JobPriority.RUSH: 2.0,
            JobPriority.CRITICAL: 3.0,
        }
        influence = priority_influence.get(job.priority, 1.0)

        # Generate profile
        profile = OasisAgentProfile(
            user_id=user_id,
            user_name=username,
            name=job.name,
            bio=bio,
            persona=persona,
            karma=random.randint(500, 1500),
            friend_count=random.randint(30, 100),
            follower_count=random.randint(50, 200),
            statuses_count=random.randint(200, 1000),
            age=None,  # Jobs don't have age
            gender=None,
            mbti="ESTJ"
            if self.config.generate_mbti
            else None,  # Jobs are task-oriented
            country="US",
            profession=f"Production Order ({job.priority.name})",
            interested_topics=self._get_job_topics(job),
            source_entity_uuid=job.job_id,
            source_entity_type="Job",
        )

        # Store job metadata
        profile._job_priority = job.priority.value
        profile._quantity = job.quantity
        profile._material = job.material
        profile._customer = job.customer
        profile._operations_count = len(job.operations)

        return profile

    def _generate_job_persona(self, job: Job) -> str:
        """Generate a detailed persona for a job"""
        priority_desc = {
            JobPriority.LOW: "a standard",
            JobPriority.NORMAL: "a regular",
            JobPriority.HIGH: "a high-priority",
            JobPriority.RUSH: "an urgent",
            JobPriority.CRITICAL: "a critical",
        }

        priority_str = priority_desc.get(job.priority, "a standard")

        due_date_str = ""
        if job.due_date:
            due_date_str = f" My deadline is {job.due_date.strftime('%Y-%m-%d %H:%M')}."

        material_str = f" Made from {job.material}." if job.material else ""

        customer_str = f" For customer: {job.customer}." if job.customer else ""

        persona = f"""I am {job.name}, {priority_str} production order for {job.quantity} units.{material_str}{customer_str}{due_date_str} I require {len(job.operations)} operations to complete. I communicate my status and needs to schedulers, operators, and supervisors. I'm demanding when I'm critical or rush priority - I need attention and resources. I'm patient when I'm normal priority - I wait my turn. My personality is goal-oriented and persistent - I'm not complete until all my operations are done and I'm delivered on time. I track my progress through the shop and escalate when I'm at risk of being late."""

        return persona

    def _generate_job_bio(self, job: Job) -> str:
        """Generate a short bio for the job"""
        return f"{job.priority.name} Priority | Qty: {job.quantity} | Ops: {len(job.operations)} | Material: {job.material or 'N/A'}"

    def _get_job_topics(self, job: Job) -> List[str]:
        """Get interested topics for job agent"""
        topics = ["Production Schedule", "On-Time Delivery", "Quality Requirements"]

        if job.material:
            topics.append(f"{job.material} Processing")

        if job.priority in [JobPriority.RUSH, JobPriority.CRITICAL]:
            topics.extend(["Expediting", "Resource Allocation"])

        return topics


# Factory function for creating mappers
MAPPER_REGISTRY = {
    "Machine": MachineAgentMapper,
    "Operator": OperatorAgentMapper,
    "Job": JobAgentMapper,
}


def create_mapper(
    entity_type: str, config: AgentMappingConfig = None
) -> SchedulingEntityMapper:
    """Factory function to create appropriate mapper for entity type"""
    mapper_class = MAPPER_REGISTRY.get(entity_type)
    if not mapper_class:
        raise ValueError(
            f"No mapper registered for entity type: {entity_type}. "
            f"Available: {list(MAPPER_REGISTRY.keys())}"
        )
    return mapper_class(config)


def map_scheduling_problem_to_agents(
    machines: List[Machine],
    operators: List[Operator],
    jobs: List[Job],
    config: AgentMappingConfig = None,
) -> List[OasisAgentProfile]:
    """
    Map an entire scheduling problem to OASIS agent profiles.

    This is the main entry point for Phase 1 - converts all factory entities
    to agents that can participate in MiroFish simulation.

    Args:
        machines: List of Machine entities
        operators: List of Operator entities
        jobs: List of Job entities
        config: Optional mapping configuration

    Returns:
        List of OasisAgentProfile objects ready for simulation
    """
    profiles = []
    user_id = 0

    # Map machines
    machine_mapper = MachineAgentMapper(config)
    for machine in machines:
        profile = machine_mapper.map_to_agent(machine, user_id)
        profiles.append(profile)
        user_id += 1

    # Map operators
    operator_mapper = OperatorAgentMapper(config)
    for operator in operators:
        profile = operator_mapper.map_to_agent(operator, user_id)
        profiles.append(profile)
        user_id += 1

    # Map jobs
    job_mapper = JobAgentMapper(config)
    for job in jobs:
        profile = job_mapper.map_to_agent(job, user_id)
        profiles.append(profile)
        user_id += 1

    return profiles
