<div align="center">

<img src="./static/image/mirofish-offline-banner.png" alt="MiroFish Offline" width="100%"/>

# MiroFish-Offline

**Fully local fork of [MiroFish](https://github.com/666ghj/MiroFish) — no cloud APIs required (Cloud optional for offloading inference). English UI.**

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
| DashScope / OpenAI API (LLM) | **Ollama** (qwen2.5, llama3, etc.) **OR any OpenAI-compatible API** |
| Zep Cloud embeddings | **nomic-embed-text** via Ollama **OR any OpenAI-compatible embeddings** |
| Cloud API keys required | **Zero cloud dependencies (Cloud optional)** |

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
- Python 3.11+, Node.js 18+, Neo4j 5.15+, Ollama

### Option A: Docker (easiest)

```bash
git clone https://github.com/nikmcfly/MiroFish-Offline.git
cd MiroFish-Offline
cp .env.example .env

# Start all services (Neo4j, Ollama, MiroFish)
docker compose up -d

# Pull the required models into Ollama
docker exec mirofish-ollama ollama pull qwen2.5:32b
docker exec mirofish-ollama ollama pull nomic-embed-text
```

Open `http://localhost:3000` — that's it.

### Option B: Cloud Mode (OpenRouter / OpenAI)

If you have limited local hardware, you can run the simulation using cloud APIs (like OpenRouter or OpenAI) while keeping the graph memory local.

1. **Configure `.env`**:
   Uncomment the Cloud section in your `.env` and add your API keys:
   ```bash
   LLM_API_KEY=your_openrouter_key
   LLM_BASE_URL=https://openrouter.ai/api/v1
   LLM_MODEL_NAME=moonshotai/kimi-k2.6
   EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
   EMBEDDING_MODEL=qwen/qwen3-embedding-8b
   ```

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d
   ```

### Option C: Hybrid Routing (Performance & Cost Optimized)

This is the recommended setup for serious research. It splits the workload between two models:
1. **Agent Reasoning** (Smart): Frontier model for complex behavior (e.g., Kimi K2.6, GPT-4o).
2. **Graph Extraction** (Cheap): High-throughput model for entity parsing (e.g., Gemini Flash).

**Configure in `.env`**:
```bash
# Agent Reasoning (Kimi)
LLM_MODEL_NAME=moonshotai/kimi-k2.6

# Background Extraction (Flash)
GRAPH_LLM_MODEL_NAME=google/gemini-3-flash-preview
GRAPH_LLM_API_KEY=your_key
GRAPH_LLM_BASE_URL=https://openrouter.ai/api/v1
```

### Option D: Manual Installation

If you prefer to run services individually:

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/mirofish \
  neo4j:5.15-community
```

**2. Start Ollama & pull models**

```bash
ollama serve &
ollama pull qwen2.5:32b      # LLM (or qwen2.5:14b for less VRAM)
ollama pull nomic-embed-text  # Embeddings (768d)
```

**3. Configure & run backend**

```bash
cp .env.example .env
# Edit .env if your Neo4j/Ollama are on non-default ports

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

## Configuration Reference

MiroFish uses a tiered configuration system. Copy `.env.example` to `.env` to get started.

### 1. Agent Reasoning (The "Brains")
These variables control the primary LLM used by agents for behavior, reports, and simulated interactions.

| Variable | Default (Local) | Recommended (Cloud) |
|---|---|---|
| `LLM_MODEL_NAME` | `qwen2.5:32b` | `moonshotai/kimi-k2.6` |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | `https://openrouter.ai/api/v1` |
| `LLM_API_KEY` | `ollama` | `sk-or-v1-...` |

### 2. Graph Extraction (The "Worker")
Optional. Controls the background process that parses documents into the knowledge graph. **If not set, it defaults to the Agent Reasoning settings above.**

| Variable | Use Case | Recommended |
|---|---|---|
| `GRAPH_LLM_MODEL_NAME` | NER / Ontology | `google/gemini-3-flash-preview` |
| `GRAPH_LLM_API_KEY` | API Auth | (Your OpenRouter Key) |
| `GRAPH_LLM_BASE_URL` | API Endpoint | `https://openrouter.ai/api/v1` |

### 3. Embeddings
Used for vector search and long-term memory retrieval.

| Variable | Local | Cloud |
|---|---|---|
| `EMBEDDING_MODEL` | `nomic-embed-text` | `qwen/qwen3-embedding-8b` |
| `EMBEDDING_BASE_URL`| `http://localhost:11434`| `https://openrouter.ai/api/v1`|

### 4. Database (Neo4j)
| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Use `bolt://neo4j:7687` for Docker |
| `NEO4J_USER` | `neo4j` | Default user |
| `NEO4J_PASSWORD` | `mirofish` | Set during initialization |

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
│    │  │ EmbeddingService│ ← Ollama       │
│    │  │ NERExtractor   │ ← Extraction LLM│
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

| Component | Minimum (Local) | Recommended (Local) | Cloud Mode |
|---|---|---|---|
| **RAM** | 16 GB | 32 GB | 8 GB |
| **VRAM (GPU)** | 10 GB (14b model) | 24 GB (32b model) | **0 GB** |
| **Disk** | 20 GB | 50 GB | 10 GB |
| **CPU** | 4 cores | 8+ cores | 2+ cores |

> [!NOTE]
> **Cloud Mode** offloads all LLM inference and embeddings to external providers. This is the recommended way to run MiroFish on laptops or hardware without a dedicated NVIDIA GPU. **Hybrid Routing** still benefits from 0 GB VRAM requirements as long as both Reasoning and Extraction models are offloaded.

CPU-only mode for local LLMs is possible but not recommended for simulations with >50 agents due to extreme latency.

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
