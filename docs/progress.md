# MiroFish-Offline Migration Progress

## Overview
Migration from Zep Cloud + DashScope (Alibaba Qwen API) to local Neo4j CE + Ollama.

## PHASE 0 — Scaffolding (COMPLETE)
- **TASK-001**: Created `LLMClient` abstraction (`backend/app/llm/client.py`) — Ollama-backed, sync, supports chat + embedding
- **TASK-002**: Created `NERExtractor` (`backend/app/llm/ner_extractor.py`) — local NER/RE via LLM, ontology-guided
- **TASK-003**: Created `EmbeddingService` (`backend/app/llm/embedding.py`) — nomic-embed-text via Ollama, 768d vectors

## PHASE 1 — Storage Layer (COMPLETE)
- **TASK-004**: Created `GraphStorage` abstract interface (`backend/app/storage/graph_storage.py`)
- **TASK-005**: Created `Neo4jStorage` implementation (`backend/app/storage/neo4j_storage.py`) — full CRUD, hybrid search (0.7*vector + 0.3*BM25), vector indexes, fulltext indexes
- **TASK-006**: Created `backend/app/storage/__init__.py` with exports
- **TASK-007**: Config updates for Neo4j + Ollama connection params

## PHASE 2 — Service Layer Rewrite (COMPLETE)
- **TASK-008**: Rewrote `graph_builder.py` — uses `GraphStorage` instead of Zep client
- **TASK-009**: Created `entity_reader.py` (replaces `zep_entity_reader.py`) — `EntityReader(storage: GraphStorage)`, optimized `get_entity_with_context()` with O(1) node lookup
- **TASK-010**: Marked `zep_paging.py` for deletion (only used by old zep files)
- **TASK-011**: Created `graph_tools.py` (replaces `zep_tools.py`, ~900 lines) — `GraphToolsService(storage, llm_client)`, all 7 dataclasses preserved, LLM tools (insight_forge, panorama, interviews) intact
- **TASK-012**: Adapted `report_agent.py` — `ZepToolsService` → `GraphToolsService`, DI constructor
- **TASK-013**: Created `graph_memory_updater.py` (replaces `zep_graph_memory_updater.py`) — `GraphMemoryUpdater(graph_id, storage)`, adapted `simulation_runner.py`
- **TASK-014**: Adapted `oasis_profile_generator.py` — removed `zep_cloud` import, `_search_graph_for_entity()` rewrite
- **TASK-014b**: Adapted `simulation_manager.py`, `simulation_config_generator.py`, `services/__init__.py`, `api/report.py`, `api/simulation.py` — all Zep references replaced with GraphStorage DI via `current_app.extensions`

## PHASE 3 — Flask DI + App Factory (COMPLETE)
- **TASK-015**: Wired `Neo4jStorage` singleton in `create_app()` → `app.extensions['neo4j_storage']`. Updated all API endpoints (`graph.py`, `simulation.py`, `report.py`) to use injected storage. Removed all `ZEP_API_KEY` guards. Added teardown hook to close Neo4j driver.

## PHASE 4 — End-to-End Test (COMPLETE)
- **TASK-016**: Verified full import chain — all storage, service, and API modules import successfully. Flask app factory creates without crash (graceful fallback when Neo4j/Ollama unavailable).

## PHASE 5 — CAMEL-AI + Ollama (COMPLETE — already compatible)
- **TASK-017**: Verified simulation scripts already use `ModelPlatformType.OPENAI` with `OPENAI_API_BASE_URL` mapped from `LLM_BASE_URL`. No DashScope references remain. Ollama's OpenAI-compatible API works out of the box.

## PHASE 6 — Cleanup (COMPLETE)
- **TASK-018**: Deleted 4 dead `zep_*.py` files, deprecated `generate_python_code()` in ontology_generator, fixed Zep docstrings in graph.py, added `requests` to requirements.txt

## PHASE 7 — Publish (TODO)
- **TASK-019**: Rename to MiroFish-Offline, add AGPL-3.0 license, publish to GitHub

## PHASE 8 — Prediction Markets + Backtesting (COMPLETE)
- **Prediction Engine**: Polymarket client, scenario generator, LLM debate simulator, calibrated signal generation
- **Backtesting**: runs pipeline against resolved markets, computes accuracy/Brier/ROI/Sharpe/drawdown/calibration RMSE
- **Paper Trading**: simulated order execution with 1-2% slippage, positions tracked in SQLite
- **Calibration**: Platt scaling via LogisticRegression, HMAC-signed persistence
- **SQLite Storage**: SQLAlchemy Core, WAL mode, FK enforcement, 4 tables (backtest_runs, backtest_results, paper_orders, paper_positions)
- **API**: POST /api/backtest/run, GET /run/:id, GET /runs with DB-level concurrent guard
- **Frontend**: BacktestView (metrics grid, sortable results table, live polling), PredictionView (market browser, signal display)
- **Tests**: 62 tests covering all new code paths
- **Cleanup**: deleted dead sentiment_analyzer.py, translated Chinese comments, extracted calibration config

## Files Created (New)
| File | Replaces | Status |
|------|----------|--------|
| `backend/app/llm/client.py` | DashScope API calls | Done |
| `backend/app/llm/ner_extractor.py` | Zep Cloud NER | Done |
| `backend/app/llm/embedding.py` | Zep Cloud embeddings | Done |
| `backend/app/storage/graph_storage.py` | Zep Cloud SDK interface | Done |
| `backend/app/storage/neo4j_storage.py` | Zep Cloud backend | Done |
| `backend/app/services/entity_reader.py` | `zep_entity_reader.py` | Done |
| `backend/app/services/graph_tools.py` | `zep_tools.py` | Done |
| `backend/app/services/graph_memory_updater.py` | `zep_graph_memory_updater.py` | Done |

## Files Modified
| File | Changes | Status |
|------|---------|--------|
| `backend/app/services/graph_builder.py` | Uses GraphStorage | Done |
| `backend/app/services/report_agent.py` | GraphToolsService DI | Done |
| `backend/app/services/simulation_runner.py` | GraphMemoryManager DI | Done |
| `backend/app/services/oasis_profile_generator.py` | GraphStorage DI | Done |
| `backend/app/services/simulation_manager.py` | EntityReader DI | Done |
| `backend/app/services/simulation_config_generator.py` | Import fix | Done |
| `backend/app/services/__init__.py` | All new exports | Done |
| `backend/app/api/report.py` | GraphToolsService DI, TODO cleaned | Done |
| `backend/app/api/simulation.py` | EntityReader DI, ZEP guards removed | Done |
| `backend/app/__init__.py` | Neo4jStorage singleton init + teardown | Done |

## Files Deleted (PHASE 6 — DONE)
- ~~`backend/app/services/zep_entity_reader.py`~~ — deleted
- ~~`backend/app/services/zep_tools.py`~~ — deleted
- ~~`backend/app/services/zep_graph_memory_updater.py`~~ — deleted
- ~~`backend/app/utils/zep_paging.py`~~ — deleted
