"""
Digital Twin Usage Example

This example demonstrates how to use the complete Digital Twin integration
between MiroFish simulation and the Job Shop Scheduler.

The integration enables:
1. Live factory state tracking
2. Agent-based disruption simulation
3. Predictive rescheduling based on simulation results
"""

import random
from datetime import datetime, timedelta

# Import scheduling components
from backend.app.services.scheduling.models import (
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
from backend.app.services.scheduling.solver import JobShopSolver

# Import Digital Twin components
from backend.app.services.digital_twin import (
    # Phase 1: Entity Mapper
    map_scheduling_problem_to_agents,
    AgentMappingConfig,
    # Phase 2: State Manager
    FactoryStateManager,
    # Phase 3: Disruption Engine
    DisruptionEngine,
    MachineFailureSimulator,
    OperatorAvailabilitySimulator,
    RushOrderSimulator,
    create_default_scenario,
    create_high_stress_scenario,
    # Phase 4: Prediction Bridge
    PredictionBridge,
)


def create_sample_factory():
    """Create a sample factory for demonstration"""

    # Create machines
    machines = [
        Machine(
            machine_id="M1",
            name="Laser Cutter 1",
            machine_type=MachineType.LASER,
            capacity=10.0,
            historical_efficiency=0.92,
            historical_uptime=0.95,
        ),
        Machine(
            machine_id="M2",
            name="Laser Cutter 2",
            machine_type=MachineType.LASER,
            capacity=10.0,
            historical_efficiency=0.88,
            historical_uptime=0.90,
        ),
        Machine(
            machine_id="M3",
            name="Press Brake 1",
            machine_type=MachineType.PRESSBRAKE,
            capacity=8.0,
            historical_efficiency=0.85,
            historical_uptime=0.92,
        ),
        Machine(
            machine_id="M4",
            name="Welding Station 1",
            machine_type=MachineType.WELDING,
            capacity=6.0,
            historical_efficiency=0.90,
            historical_uptime=0.88,
        ),
    ]

    # Create operators
    operators = [
        Operator(
            operator_id="OP1",
            name="Alice Johnson",
            skills=["laser", "cnc"],
            skill_levels={"laser": "advanced", "cnc": "intermediate"},
            shift_start=7,
            shift_end=15,
            efficiency_factor=1.1,
        ),
        Operator(
            operator_id="OP2",
            name="Bob Smith",
            skills=["welding", "assembly"],
            skill_levels={"welding": "expert", "assembly": "advanced"},
            shift_start=7,
            shift_end=15,
            efficiency_factor=1.0,
        ),
        Operator(
            operator_id="OP3",
            name="Carol White",
            skills=["pressbrake", "forming"],
            skill_levels={"pressbrake": "advanced", "forming": "intermediate"},
            shift_start=15,
            shift_end=23,
            efficiency_factor=1.2,
        ),
    ]

    # Create jobs
    jobs = [
        Job(
            job_id="J1",
            name="Order A-2024-001",
            priority=JobPriority.NORMAL,
            due_date=datetime.now() + timedelta(days=2),
            operations=[
                Operation(
                    operation_id="J1-OP1",
                    name="Cutting",
                    machine_type=MachineType.LASER,
                    duration=120,
                ),
                Operation(
                    operation_id="J1-OP2",
                    name="Forming",
                    machine_type=MachineType.PRESSBRAKE,
                    duration=90,
                    predecessors=["J1-OP1"],
                ),
            ],
        ),
        Job(
            job_id="J2",
            name="Order A-2024-002",
            priority=JobPriority.HIGH,
            due_date=datetime.now() + timedelta(days=1),
            operations=[
                Operation(
                    operation_id="J2-OP1",
                    name="Welding",
                    machine_type=MachineType.WELDING,
                    duration=180,
                ),
            ],
        ),
    ]

    return machines, operators, jobs


def example_phase1_entity_mapping():
    """Phase 1: Map scheduling entities to OASIS agent profiles"""
    print("\n" + "=" * 60)
    print("PHASE 1: Entity Mapper")
    print("=" * 60)

    # Get factory entities
    machines, operators, jobs = create_sample_factory()

    # Create mapping configuration
    config = AgentMappingConfig(
        shift_start_hour=7,
        shift_end_hour=23,
        generate_mbti=True,
        generate_personality=True,
    )

    # Map to OASIS agent profiles
    agent_profiles = map_scheduling_problem_to_agents(
        machines=machines,
        operators=operators,
        jobs=jobs,
        config=config,
    )

    print(f"Generated {len(agent_profiles)} agent profiles:")
    print(
        f"  - Machines: {sum(1 for p in agent_profiles if p.source_entity_type == 'Machine')}"
    )
    print(
        f"  - Operators: {sum(1 for p in agent_profiles if p.source_entity_type == 'Operator')}"
    )
    print(
        f"  - Jobs: {sum(1 for p in agent_profiles if p.source_entity_type == 'Job')}"
    )

    # Show sample profiles
    for profile in agent_profiles[:3]:
        print(f"\n  Agent: {profile.name} ({profile.source_entity_type})")
        print(f"    Username: {profile.user_name}")
        print(f"    Bio: {profile.bio[:60]}...")
        if hasattr(profile, "_machine_type"):
            print(f"    Machine Type: {profile._machine_type}")

    return agent_profiles


def example_phase2_state_manager():
    """Phase 2: Track live factory state"""
    print("\n" + "=" * 60)
    print("PHASE 2: State Manager")
    print("=" * 60)

    # Get factory entities
    machines, operators, jobs = create_sample_factory()

    # Create state manager
    state_manager = FactoryStateManager(persistence_path="/tmp/factory_state.json")

    # Register entities
    for machine in machines:
        state_manager.register_machine(machine)

    for operator in operators:
        state_manager.register_operator(operator)

    for job in jobs:
        state_manager.register_job(job)

    # Simulate live updates
    print("\nSimulating live state updates:")

    # Machine goes down
    state_manager.update_machine_status(
        "M2",
        MachineStatus.DOWN,
        metadata={"reason": "overheating", "temperature": 95.5},
    )
    print("  - M2 status: AVAILABLE -> DOWN (overheating)")

    # Operator check-in
    state_manager.operator_check_in("OP1")
    print("  - OP1 checked in")

    # Job progress update
    state_manager.update_job_progress("J1", 0, "M1", "OP1")
    print("  - J1 operation started on M1 by OP1")

    # Create snapshot
    snapshot = state_manager.create_snapshot()
    print(f"\nFactory Snapshot at {snapshot.timestamp}:")
    print(f"  - Machine utilization: {snapshot.total_machine_utilization:.1%}")
    print(f"  - Operator utilization: {snapshot.total_operator_utilization:.1%}")
    print(f"  - Jobs in queue: {snapshot.jobs_in_queue}")
    print(f"  - Jobs in progress: {snapshot.jobs_in_progress}")

    return state_manager


def example_phase3_disruption_simulation():
    """Phase 3: Run agent-based disruption simulation"""
    print("\n" + "=" * 60)
    print("PHASE 3: Disruption Engine")
    print("=" * 60)

    # Get state manager with factory state
    machines, operators, jobs = create_sample_factory()
    state_manager = FactoryStateManager()

    for machine in machines:
        state_manager.register_machine(machine)

    # Create disruption engine
    engine = DisruptionEngine(state_manager)

    # Register simulators
    engine.register_simulator(MachineFailureSimulator(state_manager))
    engine.register_simulator(OperatorAvailabilitySimulator(state_manager))
    engine.register_simulator(RushOrderSimulator(state_manager))

    # Create scenarios
    scenarios = [
        create_default_scenario("Baseline"),
        create_high_stress_scenario("High Stress"),
    ]

    print("\nRunning disruption simulations:")

    all_predictions = []
    for scenario in scenarios:
        print(f"\n  Scenario: {scenario.name}")
        predictions = engine.simulate_scenario(scenario)
        all_predictions.extend(predictions)

        print(f"    Generated {len(predictions)} predictions")
        for pred in predictions[:3]:  # Show first 3
            print(
                f"      - {pred.disruption_type.name}: {pred.entity_id} "
                f"(P={pred.probability:.1%}, delay={pred.estimated_delay_minutes}min)"
            )

    return engine, all_predictions


def example_phase4_prediction_bridge():
    """Phase 4: Connect simulation to scheduler"""
    print("\n" + "=" * 60)
    print("PHASE 4: Prediction Bridge")
    print("=" * 60)

    # Create scheduling problem
    machines, operators, jobs = create_sample_factory()
    problem = SchedulingProblem(
        problem_id="demo_problem",
        name="Factory Floor Demo",
        machines=machines,
        operators=operators,
        jobs=jobs,
    )

    # Create state manager
    state_manager = FactoryStateManager()
    for machine in machines:
        state_manager.register_machine(machine)

    # Create prediction bridge
    bridge = PredictionBridge(state_manager)
    bridge.set_current_problem(problem)

    # Generate sample disruption predictions
    predictions = [
        type(
            "obj",
            (object,),
            {
                "disruption_type": __import__(
                    "disruption_engine", fromlist=["DisruptionType"]
                ).DisruptionType.MACHINE_BREAKDOWN,
                "entity_id": "M1",
                "entity_type": "machine",
                "probability": 0.75,
                "predicted_time": datetime.now() + timedelta(hours=4),
                "confidence": 0.8,
                "affected_jobs": ["J1"],
                "estimated_delay_minutes": 120,
                "estimated_cost_impact": 500.0,
                "recommended_action": "Prepare backup machine",
                "alternative_resources": ["M2"],
            },
        )()
    ]

    print("\nProcessing disruption predictions:")
    print(f"  Input: {len(predictions)} predictions")
    print(f"  Machine M1 breakdown probability: 75%")

    # Process results (auto-reschedule enabled)
    results = bridge.process_simulation_results(predictions, auto_reschedule=True)

    print(f"\nProcessing Results:")
    print(f"  Feedbacks generated: {results['feedbacks_generated']}")
    print(f"  Reschedule triggered: {results['reschedule_triggered']}")
    print(f"  Reschedule reason: {results.get('reschedule_reason', 'N/A')}")
    print(f"  New makespan: {results.get('new_schedule_makespan', 'N/A')}")

    # Show bridge stats
    stats = bridge.get_stats()
    print(f"\nBridge Statistics:")
    print(f"  Predictions received: {stats['predictions_received']}")
    print(f"  Feedbacks applied: {stats['feedbacks_applied']}")
    print(f"  Reschedules triggered: {stats['reschedules_triggered']}")

    return bridge, results


def example_complete_workflow():
    """Complete Digital Twin workflow"""
    print("\n" + "=" * 60)
    print("COMPLETE DIGITAL TWIN WORKFLOW")
    print("=" * 60)

    # Step 1: Create factory and initial schedule
    print("\n1. Creating factory and initial schedule...")
    machines, operators, jobs = create_sample_factory()

    problem = SchedulingProblem(
        problem_id="live_factory",
        name="Live Factory Floor",
        machines=machines,
        operators=operators,
        jobs=jobs,
    )

    # Solve initial schedule
    solver = JobShopSolver()
    initial_schedule = solver.solve(problem)
    print(f"   Initial makespan: {initial_schedule.makespan} minutes")

    # Step 2: Set up Digital Twin
    print("\n2. Setting up Digital Twin...")
    state_manager = FactoryStateManager()
    for machine in machines:
        state_manager.register_machine(machine)
    for operator in operators:
        state_manager.register_operator(operator)
    for job in jobs:
        state_manager.register_job(job)

    # Step 3: Run disruption simulation
    print("\n3. Running disruption simulation...")
    disruption_engine = DisruptionEngine(state_manager)
    disruption_engine.register_simulator(MachineFailureSimulator(state_manager))
    disruption_engine.register_simulator(OperatorAvailabilitySimulator(state_manager))

    scenario = create_high_stress_scenario("Peak Production")
    predictions = disruption_engine.simulate_scenario(scenario)

    high_risk = [p for p in predictions if p.probability >= 0.5]
    print(f"   Generated {len(predictions)} predictions, {len(high_risk)} high-risk")

    # Step 4: Apply predictions to scheduler
    print("\n4. Applying predictions to scheduler...")
    bridge = PredictionBridge(state_manager, solver)
    bridge.set_current_problem(problem)
    bridge.set_current_schedule(initial_schedule)

    results = bridge.process_simulation_results(predictions, auto_reschedule=True)

    # Step 5: Compare schedules
    print("\n5. Schedule Comparison:")
    print(f"   Initial makespan: {initial_schedule.makespan} minutes")
    if results.get("new_schedule_makespan"):
        print(f"   Adjusted makespan: {results['new_schedule_makespan']} minutes")
        improvement = initial_schedule.makespan - results["new_schedule_makespan"]
        print(f"   Improvement: {improvement} minutes")

    print("\n" + "=" * 60)
    print("Digital Twin workflow complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Run individual phase examples
    print("\nDIGITAL TWIN INTEGRATION DEMONSTRATION")
    print("Integrating MiroFish Simulation with Job Shop Scheduling")

    try:
        # Phase 1: Entity Mapping
        profiles = example_phase1_entity_mapping()

        # Phase 2: State Management
        state_manager = example_phase2_state_manager()

        # Phase 3: Disruption Simulation
        engine, predictions = example_phase3_disruption_simulation()

        # Phase 4: Prediction Bridge
        bridge, results = example_phase4_prediction_bridge()

        # Complete Workflow
        example_complete_workflow()

    except Exception as e:
        print(f"\nError running example: {e}")
        import traceback

        traceback.print_exc()
