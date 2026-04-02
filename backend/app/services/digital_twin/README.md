# Digital Twin Integration for MiroFish-Offline

This module provides a complete **Digital Twin** integration between the **MiroFish Agent Simulation** and the **Job Shop Scheduler**, enabling predictive, agent-based rescheduling for manufacturing floors.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     LIVE SHOP FLOOR                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Machine   │  │   Machine   │  │   Operator  │  │    WIP      │    │
│  │  Sensors    │  │  Sensors    │  │  Terminals  │  │   Queue     │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
└─────────┼────────────────┼─────────────────┼────────────────┼────────────┘
          │                │                 │                │
          └────────────────┴─────────────────┴────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DIGITAL TWIN SERVICE                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Phase 1: Entity Mapper                                          │   │
│  │ Maps scheduling entities → OASIS agent profiles                 │   │
│  │ • MachineAgentMapper    • OperatorAgentMapper                  │   │
│  │ • JobAgentMapper         • Customizable mapping config           │   │
│  └────────────────────────┬────────────────────────────────────────┘   │
│                           │                                            │
│  ┌────────────────────────▼────────────────────────────────────────┐   │
│  │ Phase 2: State Manager                                          │   │
│  │ Tracks live factory state with real-time updates                │   │
│  │ • MachineState (OEE, sensor data)                               │   │
│  │ • OperatorState (availability, assignments)                     │   │
│  │ • JobState (progress, WIP tracking)                             │   │
│  │ • Event subscription system                                     │   │
│  └────────────────────────┬────────────────────────────────────────┘   │
│                           │                                            │
│  ┌────────────────────────▼────────────────────────────────────────┐   │
│  │ Phase 3: Disruption Engine                                       │   │
│  │ Agent-based simulation of factory disruptions                   │   │
│  │ • MachineFailureSimulator (MTBF-based failures)                 │   │
│  │ • OperatorAvailabilitySimulator (absenteeism)                   │   │
│  │ • RushOrderSimulator (urgent arrivals)                          │   │
│  │ • Custom scenario configurations                                 │   │
│  └────────────────────────┬────────────────────────────────────────┘   │
│                           │                                            │
│  ┌────────────────────────▼────────────────────────────────────────┐   │
│  │ Phase 4: Prediction Bridge                                       │   │
│  │ Feeds simulation results back to scheduler                       │   │
│  │ • SimulationResultProcessor → Feedback                           │   │
│  │ • ConstraintUpdater → Problem modifications                    │   │
│  │ • ReschedulingTrigger → Adaptive strategies                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     OR-Tools Job Shop Scheduler                          │
│  • CP-SAT Solver (optimal, minutes)                                      │
│  • FastHeuristicScheduler (fast, seconds)                               │
│  • Constraint updates from simulation                                     │
│  • Multi-objective optimization                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Installation

The Digital Twin module is part of the MiroFish-Offline backend. No additional installation required.

```python
from backend.app.services.digital_twin import (
    # Phase 1
    map_scheduling_problem_to_agents,
    AgentMappingConfig,
    
    # Phase 2
    FactoryStateManager,
    
    # Phase 3
    DisruptionEngine,
    MachineFailureSimulator,
    create_default_scenario,
    
    # Phase 4
    PredictionBridge,
)
```

## Quick Start

### 1. Map Factory Entities to Simulation Agents

```python
from backend.app.services.digital_twin import (
    map_scheduling_problem_to_agents,
    AgentMappingConfig,
)
from backend.app.services.scheduling.models import (
    Machine, Operator, Job
)

# Your factory entities
machines = [Machine(...), Machine(...)]
operators = [Operator(...), Operator(...)]
jobs = [Job(...), Job(...)]

# Configure mapping
config = AgentMappingConfig(
    shift_start_hour=7,
    shift_end_hour=19,
    generate_mbti=True,
)

# Map to OASIS agent profiles
agent_profiles = map_scheduling_problem_to_agents(
    machines=machines,
    operators=operators,
    jobs=jobs,
    config=config,
)

print(f"Generated {len(agent_profiles)} agent profiles")
```

### 2. Track Live Factory State

```python
from backend.app.services.digital_twin import FactoryStateManager
from backend.app.services.scheduling.models import MachineStatus

# Create state manager
state_manager = FactoryStateManager()

# Register entities
for machine in machines:
    state_manager.register_machine(machine)

for operator in operators:
    state_manager.register_operator(operator)

# Update in real-time
state_manager.update_machine_status(
    machine_id="M1",
    new_status=MachineStatus.DOWN,
    metadata={"reason": "overheating"}
)

# Get current snapshot
snapshot = state_manager.create_snapshot()
print(f"Machine utilization: {snapshot.total_machine_utilization:.1%}")
```

### 3. Run Disruption Simulation

```python
from backend.app.services.digital_twin import (
    DisruptionEngine,
    MachineFailureSimulator,
    create_high_stress_scenario,
)

# Create engine
engine = DisruptionEngine(state_manager)
engine.register_simulator(MachineFailureSimulator(state_manager))

# Run scenario
scenario = create_high_stress_scenario("Peak Production")
predictions = engine.simulate_scenario(scenario)

for pred in predictions:
    print(f"{pred.disruption_type.name}: {pred.entity_id} "
          f"(probability={pred.probability:.1%})")
```

### 4. Connect to Scheduler

```python
from backend.app.services.digital_twin import PredictionBridge
from backend.app.services.scheduling.solver import JobShopSolver

# Create bridge
solver = JobShopSolver()
bridge = PredictionBridge(state_manager, solver)

# Set current problem
bridge.set_current_problem(problem)
bridge.set_current_schedule(current_schedule)

# Process predictions and auto-reschedule
results = bridge.process_simulation_results(
    predictions,
    auto_reschedule=True
)

print(f"New makespan: {results['new_schedule_makespan']}")
```

## API Reference

### Phase 1: Entity Mapper

**Classes:**
- `SchedulingEntityMapper` - Abstract base class
- `MachineAgentMapper` - Maps machines to agents
- `OperatorAgentMapper` - Maps operators to agents
- `JobAgentMapper` - Maps jobs to agents
- `AgentMappingConfig` - Configuration for mapping

**Functions:**
- `map_scheduling_problem_to_agents(machines, operators, jobs, config)` - Main entry point
- `create_mapper(entity_type, config)` - Factory function

### Phase 2: State Manager

**Classes:**
- `FactoryStateManager` - Main state tracking class
- `MachineState` - Real-time machine data
- `OperatorState` - Real-time operator data
- `JobState` - Real-time job progress
- `FactorySnapshot` - Complete factory state
- `StateChangeEvent` - State change notification

**Key Methods:**
- `register_machine()`, `register_operator()`, `register_job()`
- `update_machine_status()`, `update_machine_metrics()`
- `operator_check_in()`, `operator_check_out()`
- `update_job_progress()`, `complete_job_operation()`
- `create_snapshot()` - Get current state
- `subscribe(callback, event_types, entity_ids)` - Event subscription

### Phase 3: Disruption Engine

**Classes:**
- `DisruptionEngine` - Main simulation orchestrator
- `DisruptionSimulator` - Abstract base for simulators
- `MachineFailureSimulator` - Machine breakdowns
- `OperatorAvailabilitySimulator` - Absenteeism
- `RushOrderSimulator` - Urgent orders
- `DisruptionPrediction` - Prediction result
- `SimulationScenario` - Scenario configuration

**Scenario Presets:**
- `create_default_scenario()` - Baseline operations
- `create_high_stress_scenario()` - Peak production
- `create_optimistic_scenario()` - Best-case

### Phase 4: Prediction Bridge

**Classes:**
- `PredictionBridge` - Main integration point
- `SimulationResultProcessor` - Transforms predictions to feedback
- `ConstraintUpdater` - Applies constraints to problems
- `ReschedulingTrigger` - Decides when to reschedule
- `SimulationFeedback` - Structured feedback for scheduler

**Strategies:**
- `"fast"` - FastHeuristicScheduler (seconds)
- `"optimal"` - CP-SAT (minutes)
- `"adaptive"` - Chooses based on urgency

## Integration with MiroFish Simulation

The Digital Twin integrates with MiroFish's existing simulation infrastructure:

1. **Agent Profiles** feed into `SimulationManager.prepare_simulation()`
2. **State snapshots** populate the knowledge graph via `EntityReader`
3. **Disruption predictions** can be injected as `EntityNode` attributes
4. **Simulation results** are queried via the existing `/api/simulation/interview` API

Example integration:

```python
from backend.app.services.simulation_manager import SimulationManager

# Create simulation with factory agents
manager = SimulationManager()
state = manager.create_simulation(project_id="factory_twin")

# Map and prepare with factory entities
agent_profiles = map_scheduling_problem_to_agents(...)
# ... pass to prepare_simulation via custom entity types
```

## Configuration

### Environment Variables

```bash
# Digital Twin persistence
DIGITAL_TWIN_STATE_PATH=/var/lib/mirofish/twin_state.json

# Simulation thresholds
DISRUPTION_PROBABILITY_THRESHOLD=0.5
MIN_TIME_BETWEEN_RESCHEDULES=300  # seconds

# Default shift hours
DEFAULT_SHIFT_START=7
DEFAULT_SHIFT_END=19
```

### Custom Simulators

Create custom disruption simulators by extending `DisruptionSimulator`:

```python
class CustomDisruptionSimulator(DisruptionSimulator):
    def get_disruption_type(self):
        return DisruptionType.CUSTOM_EVENT
    
    def simulate(self, scenario, current_time):
        predictions = []
        # Your simulation logic
        return predictions
```

## Performance Considerations

| Component | Latency | Use Case |
|-----------|---------|----------|
| Entity Mapper | ~10ms | One-time at simulation start |
| State Manager | ~1ms | Real-time updates |
| Disruption Engine | ~50-200ms | Periodic simulation runs |
| Prediction Bridge | ~100ms - 5min | Depends on rescheduling strategy |

**Recommendations:**
- Run disruption simulation every 5-15 minutes
- Use `"fast"` strategy for frequent rescheduling
- Use `"optimal"` for end-of-shift optimization
- Persist state every minute for recovery

## Troubleshooting

### Common Issues

**Issue:** `No mapper registered for entity type`
- **Solution:** Add your custom entity type to `MAPPER_REGISTRY`

**Issue:** Predictions not triggering rescheduling
- **Solution:** Check `probability_threshold` in `ReschedulingTrigger`

**Issue:** High memory usage
- **Solution:** Limit `event_history` size in `FactoryStateManager`

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('mirofish.digital_twin').setLevel(logging.DEBUG)
```

## Contributing

The Digital Twin module follows MiroFish-Offline's contribution guidelines.

Key areas for extension:
1. Additional disruption simulators (supply chain, quality issues)
2. Custom entity mappers for specialized equipment
3. Integration with external IoT platforms (MTConnect, OPC UA)
4. Machine learning for prediction accuracy

## References

- **MiroFish Simulation**: Based on OASIS framework
- **Scheduling**: Google OR-Tools CP-SAT
- **Digital Twin Patterns**: Inspired by OpenFactoryTwin (OFacT)
- **Industry Standards**: ISA-95, MTConnect, OPC UA

## License

Same as MiroFish-Offline: AGPL-3.0
