# MiroFish — Future Features (Proprietary)

Internal roadmap for simulation capabilities beyond the open-source base.
Do NOT push this file to nikmcfly/MiroFish-Offline.

---

## 1. Mid-Simulation Event Injection

**Goal**: Drop breaking news or new narratives into a running simulation and watch agents react in real-time.

**Why**: The current system only injects seed posts at round 0 via `event_config.initial_posts`. Once the simulation starts, you can't introduce new variables. This makes it impossible to test "what if X happens on day 3?"

**Architecture**:

```
Frontend (button)
    → POST /api/simulation/:id/inject-event
        → SimulationIPCClient writes to ipc_commands/
            → run_parallel_simulation.py polls and picks it up
                → ManualAction(CREATE_POST, content=...) for target agent
                    → Other agents react via LLM in subsequent rounds
```

**Changes needed**:

| File | Change |
|------|--------|
| `backend/app/services/simulation_ipc.py` | Add `INJECT_EVENT` to `CommandType` enum |
| `backend/scripts/run_parallel_simulation.py` | Handle `INJECT_EVENT` in `process_commands()` — create a `ManualAction(CREATE_POST)` for the specified agent and inject it into the next round |
| `backend/app/services/simulation_runner.py` | Add `inject_event()` classmethod that writes the IPC command |
| `backend/app/api/simulation.py` | Add `POST /api/simulation/<id>/inject-event` endpoint accepting `{ agent_id, content, platform }` |
| `frontend/src/components/Step3Simulation.vue` | Add "Inject Event" button/modal in the simulation control panel |

**IPC command format**:
```json
{
  "command_id": "evt_xxxx",
  "command_type": "inject_event",
  "args": {
    "platform": "twitter",
    "agent_id": 0,
    "content": "BREAKING: Iran launches second wave of missile strikes...",
    "round_delay": 0
  }
}
```

**Considerations**:
- Agent selection: which agent posts the breaking news? Could be a "Reality Seed" agent (narrator) or any agent
- Multiple events: support queuing multiple injections for different rounds
- Graph impact: injected events should flow through GraphMemoryUpdater like normal actions
- Could support `round_delay: N` to schedule injection N rounds from now

---

## 2. Simulation Resume / Continue

**Goal**: Pick up a completed simulation and keep running more rounds, preserving all existing state.

**Why**: A 7-day simulation might reveal early trends, but you want to see what happens at 30 or 90 days without re-running from scratch. Currently, starting a simulation always resets to round 0.

**Architecture**:

```
POST /api/simulation/:id/start { resume: true, additional_rounds: 200 }
    → SimulationRunner checks for existing SQLite DBs and actions.jsonl
    → Passes --resume flag to run_parallel_simulation.py
    → Script skips environment init, loads existing DB state
    → Starts from last_round + 1, appends to existing action logs
```

**Changes needed**:

| File | Change |
|------|--------|
| `backend/scripts/run_parallel_simulation.py` | Add `--resume` CLI flag. When set: skip `env.reset()`, load existing SQLite DB, read last round number from actions.jsonl, start loop from `last_round + 1` |
| `backend/app/services/simulation_runner.py` | In `start_simulation()`: if `resume=True`, don't clean files, pass `--resume` and `--start-round N` to subprocess. Update `total_rounds` to old + additional |
| `backend/app/api/simulation.py` | In `/start` endpoint: accept `resume: true` and `additional_rounds` params. Skip cleanup when resuming |
| `frontend/src/components/Step3Simulation.vue` | After simulation completes, show "Continue Simulation" button with rounds input |

**Key challenges**:
- OASIS environment state lives in SQLite — need to verify it can be loaded without `env.reset()`
- Agent memory/context from previous rounds must persist (stored in DB, should work)
- `run_state.json` needs to reflect cumulative totals, not reset
- Action log must append, not overwrite

---

## 3. Narrative Stacking (Multi-Document Scenarios)

**Goal**: Add a second (or third) document mid-simulation to layer new narratives on top of the existing one.

**Why**: Real-world scenarios don't happen in isolation. You might start with "Iran conflict impact on Dubai real estate" and then want to add "Saudi Arabia announces Vision 2030 mega-project" to see compound effects.

**Architecture**:

```
POST /api/simulation/:id/add-narrative
    → Upload new document (PDF/MD/TXT)
    → Run through existing NER/graph pipeline → new entities + relations added to same graph_id
    → Generate new seed posts from the document
    → Inject those posts via Event Injection (feature #1)
    → Agents now have both the original + new context in their graph memory
```

**Changes needed**:

| File | Change |
|------|--------|
| `backend/app/api/simulation.py` | Add `POST /api/simulation/<id>/add-narrative` endpoint |
| `backend/app/storage/neo4j_storage.py` | `add_text()` already supports appending to existing graph — no change needed |
| `backend/app/services/graph_memory_updater.py` | No change — new entities merge into existing graph |
| New: narrative injection service | Orchestrates: ingest doc → extract entities → generate seed posts → inject via IPC |
| Frontend | "Add Narrative" button in simulation panel, file upload + preview |

**This builds on features #1 and #2**: you need event injection to post the new narrative's seed content, and ideally resume so the simulation continues with the new context.

---

## 4. Comparative Simulation Runs

**Goal**: Run the same scenario with different variables (e.g., "with sanctions" vs "without sanctions") and compare outcomes side-by-side.

**Why**: The real value of simulation is counterfactual analysis. "What would have happened if Iran didn't retaliate?" requires running two parallel worlds from the same starting point.

**Architecture**:
- Fork a simulation at a specific round (copy SQLite DBs + action logs up to round N)
- Run variant B from that fork point with a different injected event (or no event)
- Dashboard shows both runs side-by-side with divergence metrics

**Changes needed**:
- `POST /api/simulation/:id/fork` — copies sim data to a new sim_id
- Resume (feature #2) from the fork point
- Dashboard comparison view — two simulations' timelines aligned by round
- Divergence metrics: sentiment drift, agent behavior changes, topic distribution shifts

---

## 5. Real-Time Agent Memory Inspection

**Goal**: During a running simulation, query what any agent "knows" and "believes" based on their accumulated graph memory.

**Why**: Understanding WHY an agent posts what it posts. Currently you can interview agents, but you can't see their internal knowledge state.

**Architecture**:
- Query Neo4j for all episodes involving a specific agent
- Show the entity/relation subgraph connected to that agent
- Display the agent's "worldview" — what facts they've been exposed to, who they've interacted with

**Partially exists**: The interview IPC command already works. This is more about visualization than new backend logic.

---

## Implementation Priority

| # | Feature | Complexity | Value | Dependencies |
|---|---------|-----------|-------|-------------|
| 1 | Event Injection | Medium | High | None — IPC infra exists |
| 2 | Simulation Resume | Medium | High | None |
| 3 | Narrative Stacking | Medium | Very High | Requires #1 + #2 |
| 4 | Comparative Runs | High | Very High | Requires #2 |
| 5 | Agent Memory Inspection | Low | Medium | None |

Recommended order: **1 → 2 → 5 → 3 → 4**

Event injection is the quickest win and unlocks the most interesting scenarios. Resume is essential for longer simulations and enables narrative stacking and comparative runs.
