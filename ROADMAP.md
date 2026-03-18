# MiroFish-Offline Roadmap

## Current State (v0.2.0+)

Fully local fork running on Neo4j CE + Ollama. All Zep Cloud dependencies removed. Core pipeline works: upload text → build knowledge graph → entity extraction → simulation → report generation. Prediction market signal engine with backtesting, paper trading, and SQLite storage. 62-test suite.

---

## Near Term

### v0.3.0 — Stability & Python Compatibility
- [ ] Fix `camel-oasis` / `camel-ai` compatibility with Python 3.12+ (currently requires <3.12)
- [ ] Add Docker Compose GPU auto-detection (fallback to CPU-only Ollama)
- [ ] Connection resilience: auto-reconnect to Neo4j on transient failures
- [ ] Add `/api/status` endpoint showing Neo4j connection state, Ollama model availability, and disk usage
- [ ] Structured logging with JSON output option

### v0.4.0 — Search & Retrieval Improvements
- [ ] Tune hybrid search weights (currently 0.7 vector / 0.3 BM25) — make configurable per graph
- [ ] Add graph-aware reranking: boost results connected to the query entity
- [ ] Support multiple embedding models (e.g., mxbai-embed-large, bge-m3 for multilingual)
- [ ] Implement edge-weight decay for temporal relevance in simulations

---

## Mid Term

### v0.5.0 — Multi-Model Support
- [ ] Model router: assign different Ollama models to different tasks (fast model for NER, large model for reports)
- [ ] Support vLLM and llama.cpp as alternative backends alongside Ollama
- [ ] Add model benchmarking tool: compare NER/RE quality across models on the same seed text
- [ ] Quantization-aware config: auto-select context window based on available VRAM

### v0.6.0 — Enhanced Simulation
- [ ] Real-time simulation dashboard with WebSocket updates
- [ ] Agent memory persistence across simulation rounds (currently in-memory)
- [ ] Custom agent archetypes: define personality templates beyond OASIS defaults
- [ ] Multi-language simulation support (agents can interact in different languages)
- [ ] Export simulation transcripts as structured JSON for external analysis

### v0.7.0 — Graph Intelligence
- [ ] Community detection (Louvain/Leiden) to auto-identify entity clusters
- [ ] Graph visualization improvements: force-directed layout, filtering by entity type
- [ ] Temporal graph: track how entity relationships evolve across simulation rounds
- [ ] Graph diff: compare two simulation runs side-by-side

---

## Long Term

### v1.0.0 — Production Ready
- [ ] Authentication & multi-user support
- [ ] Graph versioning: snapshot and restore graph states
- [ ] Plugin system for custom NER extractors, search strategies, and report templates
- [x] Comprehensive test suite — 62 tests (unit + integration) for prediction/backtest system
- [ ] Performance benchmarks: document throughput (texts/min) and latency per hardware tier
- [ ] Helm chart for Kubernetes deployment

### Beyond v1.0
- [ ] Federation: connect multiple MiroFish instances to share entity knowledge
- [ ] Fine-tuned local models specifically trained for NER/RE on social simulation data
- [ ] Voice-driven interaction: talk to simulation agents via local Whisper + TTS
- [ ] Mobile companion app for monitoring running simulations

---

## Hardware Tiers

| Tier | RAM | GPU VRAM | Recommended Model | Expected Performance |
|------|-----|----------|-------------------|---------------------|
| Minimal | 8 GB | — (CPU only) | qwen2.5:3b | Slow, basic NER quality |
| Light | 16 GB | 6-8 GB | qwen2.5:7b | Usable for small graphs |
| Standard | 32 GB | 12-16 GB | qwen2.5:14b | Good for most use cases |
| Power | 64 GB | 24+ GB | qwen2.5:32b | Full quality, fast |

---

## Contributing

This project is AGPL-3.0 licensed. Contributions welcome — especially around:
- Python 3.12+ compatibility for CAMEL-AI / OASIS
- Additional embedding model support
- Simulation quality improvements
- Documentation and tutorials in English

See [GitHub Issues](https://github.com/nikmcfly/MiroFish-Offline/issues) for current tasks.
