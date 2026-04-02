# MiroFish Platform - Architecture Options

Two approaches for repurposing MiroFish beyond social simulations.

---

## Option 1: Job Shop MVP (Focused)

**Scope**: Job shop scheduling with disruption prediction only.
**Timeline**: 2-3 weeks to production.
**Complexity**: Low.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR SHOP SYSTEM                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   ERP DB    │  │   MES DB    │  │  SCADA DB   │         │
│  │  PostgreSQL │  │  PostgreSQL │  │  PostgreSQL │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
└─────────┼────────────────┼────────────────┼───────────────┘
          │                │                │
          └────────────────┴────────────────┘
                         │
                         ▼ Pull via SQL
┌─────────────────────────────────────────────────────────────┐
│              MIROFISH JOB SHOP SIMULATION                   │
│                     (Port 5001)                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Data Layer (SQLAlchemy)                             │  │
│  │ • Polls ERP/MES/SCADA every 60s                     │  │
│  │ • Caches current factory state                    │  │
│  └─────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼──────────────────────────┐  │
│  │ State Manager                                       │  │
│  │ • MachineState (OEE, status, metrics)               │  │
│  │ • OperatorState (availability, assignments)         │  │
│  │ • JobState (progress, priority)                     │  │
│  └─────────────────────────┬──────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼──────────────────────────┐  │
│  │ Agent Mapper                                        │  │
│  │ • Machine → Agent (low activity, high influence)    │  │
│  │ • Operator → Agent (shift-based, skill-driven)      │  │
│  │ • Job → Agent (priority-based, lifecycle)          │  │
│  └─────────────────────────┬──────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼──────────────────────────┐  │
│  │ Disruption Simulator (OASIS)                        │  │
│  │ • MachineFailureSimulator (MTBF-based)              │  │
│  │ • OperatorAbsenceSimulator (shift patterns)       │  │
│  │ • RushOrderSimulator (priority injection)          │  │
│  └─────────────────────────┬──────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼──────────────────────────┐  │
│  │ Prediction Output                                   │  │
│  │ • Disruption predictions JSON                       │  │
│  │ • Confidence scores                                 │  │
│  │ • Recommended actions                               │  │
│  └─────────────────────────────────────────────────────┘  │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼ HTTP/JSON
┌─────────────────────────────────────────────────────────────┐
│              YOUR EXISTING SCHEDULER                        │
│  • Receives disruption predictions                          │
│  • Adjusts schedule based on risk                           │
│  • Executes on shop floor                                    │
└─────────────────────────────────────────────────────────────┘
```

### Components (Minimal)

```
mirofish-jobshop/
├── core/
│   ├── __init__.py
│   ├── db_connector.py          # Polls your PostgreSQL
│   ├── state_manager.py         # Tracks live factory state
│   ├── agent_mapper.py          # Maps entities to OASIS agents
│   └── disruption_simulator.py  # Runs OASIS simulations
│
├── api/
│   ├── __init__.py
│   └── routes.py                # Flask REST endpoints
│       POST /api/v1/simulate
│       GET  /api/v1/predictions
│       GET  /api/v1/state
│
├── config/
│   └── database.yml             # Your DB connection strings
│
└── run.py                       # Flask app entry point
```

### API Surface (3 Endpoints)

```python
# POST /api/v1/simulate
# Run disruption simulation, return predictions
{
  "scenario": "default" | "high_stress",
  "lookahead_hours": 24
}

# Response
{
  "predictions": [
    {
      "type": "MACHINE_BREAKDOWN",
      "entity_id": "LASER_001",
      "probability": 0.75,
      "predicted_time": "2024-01-15T14:30:00Z",
      "impact_minutes": 120,
      "confidence": 0.8
    }
  ]
}

# GET /api/v1/predictions
# Get cached high-risk predictions

# GET /api/v1/state
# Get current factory snapshot
```

### Data Flow

1. **MiroFish polls your DBs** every 60 seconds
2. **Builds agent representations** of machines/operators/jobs
3. **Runs simulation** every 10 minutes (or on demand)
4. **Returns predictions** to your scheduler via REST
5. **Your scheduler** decides what to do with predictions

### What You Build

- Database connection config (YAML)
- SQL queries to map your tables to entities
- REST client in your scheduler to consume predictions

### What You DON'T Build

- Generic scenario framework
- Database persistence for MiroFish
- Complex optimization
- Multi-tenant support

---

## Option 2: Generic Simulation Platform (Extensible)

**Scope**: Pluggable simulation platform for any company scenario.
**Timeline**: 6-8 weeks to production.
**Complexity**: Medium-High.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      YOUR COMPANY SYSTEMS                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │   ERP    │  │   MES    │  │   WMS    │  │   HR     │  │  SCADA   │ │
│  │   DB     │  │   DB     │  │   DB     │  │   DB     │  │   DB     │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
└───────┼────────────┼────────────┼────────────┼────────────┼──────────┘
        │            │            │            │            │
        └────────────┴────────────┴────────────┴────────────┘
                                   │
                                   ▼ Pull via SQL
┌─────────────────────────────────────────────────────────────────────────┐
│                    MIROFISH SIMULATION PLATFORM                         │
│                              (Port 5001)                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Universal Data Adapter                                          │   │
│  │ • Polls multiple databases                                      │   │
│  │ • Schema mapping per source                                     │   │
│  │ • Entity normalization                                          │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼───────────────────────────────────┐   │
│  │ Scenario Registry                                               │   │
│  │ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │   │
│  │ │  Job Shop   │  │ Supply Chain│  │   Social    │  │   HR    │ │   │
│  │ │   Plugin    │  │   Plugin    │  │   Plugin    │  │  Plugin │ │   │
│  │ │             │  │             │  │             │  │         │ │   │
│  │ │ Entities:   │  │ Entities:   │  │ Entities:   │  │Entities:│ │   │
│  │ │ - Machines  │  │ - Trucks    │  │ - Users     │  │-Employee│ │   │
│  │ │ - Operators │  │ - Warehouses│  │ - Brands    │  │-Team    │ │   │
│  │ │ - Jobs      │  │ - Orders    │  │ - Products  │  │-Project │ │   │
│  │ └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼───────────────────────────────────┐   │
│  │ Simulation Engine (OASIS)                                       │   │
│  │ • Generic agent behaviors (not social-specific)                 │   │
│  │ • Pluggable interaction rules                                   │   │
│  │ • Metric extraction                                             │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                         │
│  ┌─────────────────────────────▼───────────────────────────────────┐   │
│  │ Results Store                                                   │   │
│  │ • PostgreSQL (predictions, snapshots)                         │   │
│  │ • Time-series metrics                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Universal REST API
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONSUMER SYSTEMS                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Scheduler   │  │   TMS/WMS    │  │   Marketing  │  │    HR      │  │
│  │   System     │  │   System     │  │   Platform │  │   Platform │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Components (Extensible)

```
mirofish-platform/
├── core/                              # Shared across all scenarios
│   ├── __init__.py
│   ├── simulation_engine.py           # OASIS wrapper
│   ├── agent_factory.py               # Generic agent creation
│   ├── config_generator.py            # LLM-driven config
│   └── database_adapter.py            # Universal DB connector
│
├── scenarios/                         # Pluggable scenarios
│   ├── __init__.py
│   ├── base.py                        # Scenario interface
│   │
│   ├── job_shop/                      # Job shop simulation
│   │   ├── __init__.py
│   │   ├── entities.py                # Machine, Operator, Job
│   │   ├── behaviors.py               # How agents interact
│   │   ├── metrics.py                 # OEE, utilization, etc.
│   │   └── api.py                     # Job shop specific endpoints
│   │
│   ├── supply_chain/                  # Supply chain simulation
│   │   ├── __init__.py
│   │   ├── entities.py                # Truck, Warehouse, Order
│   │   ├── behaviors.py               # Routing, delays
│   │   ├── metrics.py                 # Lead time, fill rate
│   │   └── api.py                     # SC specific endpoints
│   │
│   └── social/                        # Original MiroFish (optional)
│       ├── __init__.py
│       └── ...
│
├── api/                               # Universal REST API
│   ├── __init__.py
│   ├── routes.py                      # /scenarios/{id}/simulate
│   └── middleware.py                  # Auth, rate limiting
│
├── persistence/                       # Data storage
│   ├── __init__.py
│   ├── models.py                      # SQLAlchemy models
│   └── repository.py                  # Data access layer
│
└── run.py
```

### Scenario Interface

```python
# scenarios/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Scenario(ABC):
    """Base class for all simulation scenarios"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Scenario name"""
        pass
    
    @abstractmethod
    def load_entities(self) -> List[Any]:
        """Load entities from database"""
        pass
    
    @abstractmethod
    def map_to_agents(self, entities: List[Any]) -> List[Dict]:
        """Map entities to OASIS agent profiles"""
        pass
    
    @abstractmethod
    def define_behaviors(self) -> Dict:
        """Define agent interaction rules"""
        pass
    
    @abstractmethod
    def extract_metrics(self, simulation_result: Any) -> Dict:
        """Extract relevant metrics from simulation"""
        pass

# scenarios/job_shop/entities.py
class JobShopScenario(Scenario):
    name = "job_shop"
    
    def load_entities(self):
        # Query ERP for machines, operators, jobs
        return {
            'machines': fetch_machines(),
            'operators': fetch_operators(),
            'jobs': fetch_jobs()
        }
    
    def map_to_agents(self, entities):
        # Map to OASIS profiles
        return [
            *map_machines_to_agents(entities['machines']),
            *map_operators_to_agents(entities['operators']),
            *map_jobs_to_agents(entities['jobs'])
        ]
    
    def define_behaviors(self):
        return {
            'machine_failure': MachineFailureBehavior(),
            'operator_absence': OperatorAbsenceBehavior(),
        }
    
    def extract_metrics(self, result):
        return {
            'disruption_predictions': extract_disruptions(result),
            'utilization_forecast': extract_utilization(result),
        }
```

### API Surface (Universal)

```python
# POST /api/v1/scenarios/{scenario_id}/simulate
{
  "scenario": "job_shop",
  "config": {
    "lookahead_hours": 24,
    "stress_level": "high"
  }
}

# Response (universal format)
{
  "scenario": "job_shop",
  "simulation_id": "sim_abc123",
  "metrics": {
    "disruptions": [...],
    "utilization": [...],
    "custom": {...}
  }
}

# GET /api/v1/scenarios
# List available scenarios

# GET /api/v1/scenarios/{id}/state
# Get current state for scenario
```

### Data Flow

1. **Register scenarios** at startup (job_shop, supply_chain, etc.)
2. **API receives request** for specific scenario
3. **Scenario loads entities** from appropriate database(s)
4. **Maps to agents** using scenario-specific logic
5. **Runs OASIS simulation** with scenario behaviors
6. **Extracts metrics** using scenario-specific logic
7. **Returns results** in universal format

### What You Build

- Core platform (simulation engine, REST API)
- Job Shop scenario (first plugin)
- Database adapter for your systems
- Universal REST client

### What You DON'T Build Initially

- Additional scenarios (supply chain, HR, etc.)
- Multi-tenant support
- Complex persistence
- WebSocket streaming

---

## Comparison

| Aspect | Job Shop MVP | Generic Platform |
|--------|--------------|------------------|
| **Time to production** | 2-3 weeks | 6-8 weeks |
| **Initial scenarios** | 1 (job shop) | 1 (job shop) + framework |
| **Add new scenario** | Refactor code | Write plugin (1 week) |
| **Code complexity** | Low (~2K lines) | Medium (~5K lines) |
| **Extensibility** | Limited | High |
| **Risk** | Low | Medium |
| **Future-proof** | Can refactor later | Built for extension |

---

## Recommendation

**Start with Job Shop MVP**, but architect it so you can refactor to Generic Platform later:

```python
# MVP approach that allows future refactoring

# 1. Build core simulation as functions, not classes
# 2. Keep scenario logic in one module
# 3. Use clear interfaces (even if not formal ABC)
# 4. Document where to add abstraction later

# Later: Extract scenario into formal plugin
# Later: Add scenario registry
# Later: Universalize API
```

This gives you:
- ✅ Working solution in 2-3 weeks
- ✅ Clean code that's refactorable
- ✅ Path to platform later
- ❌ No premature abstraction

---

## Decision Questions

1. **Do you need other scenarios within 6 months?**
   - Yes → Generic Platform
   - No → Job Shop MVP

2. **Is job shop the proving ground?**
   - Yes → MVP, expand later
   - No → Platform from start

3. **Team size?**
   - 1-2 devs → MVP
   - 3+ devs → Platform

4. **Need to demo to stakeholders soon?**
   - Yes → MVP
   - No → Platform

**My strong recommendation**: Build MVP, prove value with job shop, then refactor to platform. You'll have real requirements and avoid building abstractions for scenarios that never materialize.

**Want me to proceed with:**
- A. Job Shop MVP architecture (clean, minimal)
- B. Generic Platform architecture (with job shop as first plugin)
- C. Hybrid approach (MVP that can evolve)