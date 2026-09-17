<div align="center">

<img src="./static/image/mirofish-offline-banner.png" alt="MiroFish Offline" width="100%"/>

# MiroFish-Offline

**Fully local fork of [MiroFish](https://github.com/666ghj/MiroFish) — no cloud APIs required. English UI.**

*A multi-agent swarm intelligence engine that simulates public opinion, market sentiment, and social dynamics. Entirely on your hardware.*

[![GitHub Stars](https://img.shields.io/github/stars/nikmcfly/MiroFish-Offline?style=flat-square&color=DAA520)](https://github.com/nikmcfly/MiroFish-Offline/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/nikmcfly/MiroFish-Offline?style=flat-square)](https://github.com/nikmcfly/MiroFish-Offline/network)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](./LICENSE)

</div>

## What is this?

MiroFish is a multi-agent simulation engine: upload any document (press release, policy draft, financial report), and it generates hundreds of AI agents with unique personalities that simulate the public reaction on social media. Posts, arguments, opinion shifts — hour by hour.

The [original MiroFish](https://github.com/666ghj/MiroFish) was built for the Chinese market (Chinese UI, Zep Cloud for knowledge graphs, DashScope API). This fork makes it **fully local and fully English**:

| Original MiroFish | MiroFish-Offline |
|---|---|
| Chinese UI | **English UI** (1,000+ strings translated) |
| Zep Cloud (graph memory) | **Neo4j Community Edition 5.15** |
| DashScope / OpenAI API (LLM) | **Ollama** or **llama.cpp** (qwen2.5, llama3, etc.) |
| Zep Cloud embeddings | **nomic-embed-text**, served locally |
| Cloud API keys required | **Zero cloud dependencies** |

## Workflow

1. **Graph Build** — Extracts entities (people, companies, events) and relationships from your document. Builds a knowledge graph with individual and group memory via Neo4j.
2. **Env Setup** — Generates hundreds of agent personas, each with unique personality, opinion bias, reaction speed, influence level, and memory of past events.
3. **Simulation** — Agents interact on simulated social platforms: posting, replying, arguing, shifting opinions. The system tracks sentiment evolution, topic propagation, and influence dynamics in real time.
4. **Report** — A ReportAgent analyzes the post-simulation environment, interviews a focus group of agents, searches the knowledge graph for evidence, and generates a structured analysis.
5. **Interaction** — Chat with any agent from the simulated world. Ask them why they posted what they posted. Full memory and personality persists.

## Screenshot

<div align="center">
<img src="./static/image/mirofish-offline-screenshot.jpg" alt="MiroFish Offline — English UI" width="100%"/>
</div>

## Quick Start

### Prerequisites

- Docker & Docker Compose (recommended), **or**
- Python 3.11+, Node.js 18+, Neo4j 5.15+, and an LLM backend: **Ollama** or **llama.cpp**

### Option A: Docker (easiest)

```bash
git clone https://github.com/nikmcfly/MiroFish-Offline.git
cd MiroFish-Offline
cp .env.example .env

# Start all services (Neo4j, Ollama, MiroFish)
docker compose --profile ollama up -d

# Pull the required models into Ollama
docker exec mirofish-ollama ollama pull qwen2.5:32b
docker exec mirofish-ollama ollama pull nomic-embed-text
```

Or with llama.cpp instead of Ollama. Uncomment the llama.cpp and Docker-override
blocks in `.env` first, then:

```bash
docker compose --profile llamacpp up -d
```

No pull step is needed — the servers fetch their models from Hugging Face on first
start into the `llamacpp_models` volume, which takes a while. Watch progress with
`docker compose logs -f llamacpp-chat`.

> The profile flag is required. Plain `docker compose up -d` starts Neo4j and
> MiroFish but no LLM backend, since the two backends are mutually exclusive.

Open `http://localhost:3000` — that's it.

### Option B: Manual

**1. Start Neo4j**

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/mirofish \
  neo4j:5.15-community
```

**2. Start an LLM backend & get models**

Either Ollama:

```bash
ollama serve &
ollama pull qwen2.5:32b      # LLM (or qwen2.5:14b for less VRAM)
ollama pull nomic-embed-text  # Embeddings (768d)
```

...or llama.cpp. Chat and embeddings need separate servers, because `--embeddings`
restricts a server to embedding use only:

```bash
# chat
llama-server -hf bartowski/Qwen2.5-32B-Instruct-GGUF:Q4_K_M \
  --host 127.0.0.1 --port 8080 \
  --alias qwen2.5-32b-instruct \
  --jinja -np 4 --kv-unified-per-slot 16384

# embeddings
llama-server -hf nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0 \
  --host 127.0.0.1 --port 8081 \
  --alias nomic-embed-text \
  --embeddings --pooling mean
```

The embedding model caps at 2048 tokens under llama.cpp. Ollama exposes 8192 for the
same model, but MiroFish chunks text at 500 characters, so the limit is not reached
in practice. The context-extension flags on the Nomic model card
(`--rope-scaling yarn --rope-freq-scale .75`) only stretch it to 2730, not 8192, so
they are left out.

Then switch `.env` to the llama.cpp profile. Three things that are easy to get wrong:

1. **Context is a launch flag, not a request parameter.** `OLLAMA_NUM_CTX` has no
   effect. `-np N --kv-unified-per-slot M` gives each of the N slots M tokens. If
   prompts appear truncated, check those, not the env var.
   **Do not go below 16384 per slot.** The report agent accumulates tool-call
   history across its retrieval rounds; at 8192 it fails mid-report with
   `request (8280 tokens) exceeds the available context size (8192 tokens)`.
   Ollama silently truncates instead of failing, so a size that appears to work
   there will hard-error here.
2. **`--jinja` is required** on the chat server for tool-calling support.
3. **Do not set `--sleep-idle-seconds`.** It unloads the model after idleness, which
   turns a bursty embedding call mid-simulation into a reload stall.

VRAM is the same either way — llama.cpp is not more efficient, it just makes the
budget explicit. At `-np 4 --kv-unified-per-slot 16384` the KV cache holds 65536
tokens, which costs roughly 3.5GB for 7B, 12GB for 14B and 16GB for 32B, on top of
the weights. So 32B needs about 36GB in total and will not fit a 24GB card; use
`Qwen2.5-14B-Instruct-GGUF` (~21GB) there, or lower `-np` to 2.

**3. Configure & run backend**

```bash
cp .env.example .env
# Edit .env if your Neo4j or LLM backend are on non-default ports,
# or to switch from the Ollama profile to the llama.cpp one

cd backend
pip install -r requirements.txt
python run.py
```

**4. Run frontend**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration

All settings are in `.env` (copy from `.env.example`):

```bash
# LLM — points to local Ollama (OpenAI-compatible API)
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b
LLM_API_STYLE=ollama

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish

# Embeddings
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_API_STYLE=ollama
```

Works with any OpenAI-compatible API — swap Ollama for llama.cpp, Claude, GPT or any
other provider by changing `LLM_BASE_URL`, `LLM_API_KEY` and the two `*_API_STYLE`
settings. Use `openai` for everything except Ollama itself; `.env.example` carries a
ready-made llama.cpp profile.

## Architecture

This fork introduces a clean abstraction layer between the application and the graph database:

```
┌─────────────────────────────────────────┐
│              Flask API                   │
│  graph.py  simulation.py  report.py     │
└──────────────┬──────────────────────────┘
               │ app.extensions['neo4j_storage']
┌──────────────▼──────────────────────────┐
│           Service Layer                  │
│  EntityReader  GraphToolsService         │
│  GraphMemoryUpdater  ReportAgent         │
└──────────────┬──────────────────────────┘
               │ storage: GraphStorage
┌──────────────▼──────────────────────────┐
│         GraphStorage (abstract)          │
│              │                            │
│    ┌─────────▼─────────┐                │
│    │   Neo4jStorage     │                │
│    │  ┌───────────────┐ │                │
│    │  │ EmbeddingService│ ← embed server │
│    │  │ NERExtractor   │ ← chat server  │
│    │  │ SearchService  │ ← Hybrid search │
│    │  └───────────────┘ │                │
│    └───────────────────┘                │
└─────────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Neo4j CE   │
        │  5.15       │
        └─────────────┘
```

**Key design decisions:**

- `GraphStorage` is an abstract interface — swap Neo4j for any other graph DB by implementing one class
- Dependency injection via Flask `app.extensions` — no global singletons
- Hybrid search: 0.7 × vector similarity + 0.3 × BM25 keyword search
- Synchronous NER/RE extraction via local LLM (replaces Zep's async episodes)
- All original dataclasses and LLM tools (InsightForge, Panorama, Agent Interviews) preserved

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| VRAM (GPU) | 10 GB (14b model) | 24 GB (32b model) |
| Disk | 20 GB | 50 GB |
| CPU | 4 cores | 8+ cores |

CPU-only mode works but is significantly slower for LLM inference. For lighter setups, use `qwen2.5:14b` or `qwen2.5:7b`.

## Use Cases

- **PR crisis testing** — simulate the public reaction to a press release before publishing
- **Trading signal generation** — feed financial news and observe simulated market sentiment
- **Policy impact analysis** — test draft regulations against simulated public response
- **Creative experiments** — someone fed it a classical Chinese novel with a lost ending; the agents wrote a narratively consistent conclusion

## License

AGPL-3.0 — same as the original MiroFish project. See [LICENSE](./LICENSE).

## Credits & Attribution

This is a modified fork of [MiroFish](https://github.com/666ghj/MiroFish) by [666ghj](https://github.com/666ghj), originally supported by [Shanda Group](https://www.shanda.com/). The simulation engine is powered by [OASIS](https://github.com/camel-ai/oasis) from the CAMEL-AI team.

**Modifications in this fork:**
- Backend migrated from Zep Cloud to local Neo4j CE 5.15 + Ollama
- Entire frontend translated from Chinese to English (20 files, 1,000+ strings)
- All Zep references replaced with Neo4j across the UI
- Rebranded to MiroFish Offline
