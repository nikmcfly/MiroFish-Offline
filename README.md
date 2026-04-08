<div align="center">

<img src="./static/image/mirofish-offline-banner.png" alt="MiroFish Offline" width="100%"/>

# MiroFish-Offline

**Vollständig lokaler Fork von [MiroFish](https://github.com/666ghj/MiroFish) — keine Cloud-APIs erforderlich. Deutsche Benutzeroberfläche.**

*Eine Multi-Agenten-Schwarm-Intelligenz-Engine, die öffentliche Meinung, Marktstimmung und soziale Dynamiken simuliert. Vollständig auf deiner eigenen Hardware.*

[![GitHub Stars](https://img.shields.io/github/stars/nikmcfly/MiroFish-Offline?style=flat-square&color=DAA520)](https://github.com/nikmcfly/MiroFish-Offline/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/nikmcfly/MiroFish-Offline?style=flat-square)](https://github.com/nikmcfly/MiroFish-Offline/network)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](./LICENSE)

</div>

## Was ist das?

MiroFish ist eine Multi-Agenten-Simulations-Engine: Lade ein beliebiges Dokument hoch (Pressemitteilung, Richtlinienentwurf, Finanzbericht) und es generiert Hunderte von KI-Agenten mit einzigartigen Persönlichkeiten, die die öffentliche Reaktion in sozialen Medien simulieren. Beiträge, Argumente, Meinungsverschiebungen — Stunde für Stunde.

Das [originale MiroFish](https://github.com/666ghj/MiroFish) wurde für den chinesischen Markt entwickelt (chinesische Benutzeroberfläche, Zep Cloud für Wissensgraphen, DashScope API). Dieser Fork macht es **vollständig lokal und vollständig auf Deutsch**:

| Originales MiroFish | MiroFish-Offline |
|---|---|
| Chinesische Benutzeroberfläche | **Deutsche Benutzeroberfläche** (1.000+ Strings übersetzt) |
| Zep Cloud (Graph-Speicher) | **Neo4j Community Edition 5.15** |
| DashScope / OpenAI API (LLM) | **Ollama** (qwen2.5, llama3, usw.) |
| Zep Cloud Einbettungen | **nomic-embed-text** über Ollama |
| Cloud-API-Schlüssel erforderlich | **Keine Cloud-Abhängigkeiten** |

## Arbeitsablauf

1. **Graphaufbau** — Extrahiert Entitäten (Personen, Unternehmen, Ereignisse) und Beziehungen aus deinem Dokument. Erstellt einen Wissensgraphen mit individuellem und Gruppengedächtnis über Neo4j.
2. **Umgebung einrichten** — Generiert Hunderte von Agenten-Personas, jede mit einzigartiger Persönlichkeit, Meinungsverzerrung, Reaktionsgeschwindigkeit, Einflussniveau und Erinnerung an vergangene Ereignisse.
3. **Simulation** — Agenten interagieren auf simulierten sozialen Plattformen: Beiträge verfassen, antworten, streiten, Meinungen verschieben. Das System verfolgt Sentimententwicklung, Themenverbreitung und Einfluss-Dynamiken in Echtzeit.
4. **Bericht** — Ein ReportAgent analysiert das Post-Simulations-Umfeld, interviewt eine Fokusgruppe von Agenten, durchsucht den Wissensgraphen nach Beweisen und erstellt eine strukturierte Analyse.
5. **Interaktion** — Chatte mit beliebigen Agenten der simulierten Welt. Frage sie, warum sie gepostet haben, was sie gepostet haben. Vollständiges Gedächtnis und Persönlichkeit bleibt erhalten.

## Screenshot

<div align="center">
<img src="./static/image/mirofish-offline-screenshot.jpg" alt="MiroFish Offline — Deutsche Benutzeroberfläche" width="100%"/>
</div>

## Schnellstart

### Voraussetzungen

- Docker & Docker Compose (empfohlen), **oder**
- Python 3.11+, Node.js 18+, Neo4j 5.15+, Ollama

### Option A: Docker (einfachste Methode)

```bash
git clone https://github.com/nikmcfly/MiroFish-Offline.git
cd MiroFish-Offline
cp .env.example .env

# Alle Dienste starten (Neo4j, Ollama, MiroFish)
docker compose up -d

# Benötigte Modelle in Ollama laden
docker exec mirofish-ollama ollama pull qwen2.5:32b
docker exec mirofish-ollama ollama pull nomic-embed-text
```

`http://localhost:3000` öffnen — fertig.

### Option B: Manuell

**1. Neo4j starten**

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/mirofish \
  neo4j:5.15-community
```

**2. Ollama starten & Modelle laden**

```bash
ollama serve &
ollama pull qwen2.5:32b      # LLM (oder qwen2.5:14b für weniger VRAM)
ollama pull nomic-embed-text  # Einbettungen (768d)
```

**3. Backend konfigurieren & starten**

```bash
cp .env.example .env
# .env bearbeiten, falls Neo4j/Ollama auf anderen Ports laufen

cd backend
pip install -r requirements.txt
python run.py
```

**4. Frontend starten**

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000` öffnen.

## Konfiguration

Alle Einstellungen befinden sich in `.env` (kopiere von `.env.example`):

```bash
# LLM — zeigt auf lokales Ollama (OpenAI-kompatible API)
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish

# Einbettungen
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
```

Funktioniert mit jeder OpenAI-kompatiblen API — ersetze Ollama durch Claude, GPT oder einen anderen Anbieter, indem du `LLM_BASE_URL` und `LLM_API_KEY` änderst.

## Architektur

Dieser Fork führt eine saubere Abstraktionsschicht zwischen der Anwendung und der Graphdatenbank ein:

```
┌─────────────────────────────────────────┐
│              Flask API                   │
│  graph.py  simulation.py  report.py     │
└──────────────┬──────────────────────────┘
               │ app.extensions['neo4j_storage']
┌──────────────▼──────────────────────────┐
│           Dienst-Schicht                 │
│  EntityReader  GraphToolsService         │
│  GraphMemoryUpdater  ReportAgent         │
└──────────────┬──────────────────────────┘
               │ storage: GraphStorage
┌──────────────▼──────────────────────────┐
│         GraphStorage (abstrakt)          │
│              │                            │
│    ┌─────────▼─────────┐                │
│    │   Neo4jStorage     │                │
│    │  ┌───────────────┐ │                │
│    │  │ EmbeddingService│ ← Ollama       │
│    │  │ NERExtractor   │ ← Ollama LLM   │
│    │  │ SearchService  │ ← Hybrid-Suche │
│    │  └───────────────┘ │                │
│    └───────────────────┘                │
└─────────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Neo4j CE   │
        │  5.15       │
        └─────────────┘
```

**Wichtige Design-Entscheidungen:**

- `GraphStorage` ist eine abstrakte Schnittstelle — tausche Neo4j gegen eine andere Graph-Datenbank aus, indem du eine Klasse implementierst
- Dependency Injection über Flask `app.extensions` — keine globalen Singletons
- Hybridsuche: 0,7 × Vektorähnlichkeit + 0,3 × BM25-Schlüsselwortsuche
- Synchrone NER/RE-Extraktion über lokales LLM (ersetzt Zeps asynchrone Episoden)
- Alle originalen Datenklassen und LLM-Tools (InsightForge, Panorama, Agenten-Interviews) erhalten

## Hardware-Anforderungen

| Komponente | Minimum | Empfohlen |
|---|---|---|
| RAM | 16 GB | 32 GB |
| VRAM (GPU) | 10 GB (14b-Modell) | 24 GB (32b-Modell) |
| Festplatte | 20 GB | 50 GB |
| CPU | 4 Kerne | 8+ Kerne |

Nur-CPU-Modus funktioniert, ist aber für LLM-Inferenz deutlich langsamer. Für leichtere Setups verwende `qwen2.5:14b` oder `qwen2.5:7b`.

## Anwendungsfälle

- **PR-Krisentests** — Simuliere die öffentliche Reaktion auf eine Pressemitteilung, bevor sie veröffentlicht wird
- **Handelssignal-Generierung** — Füttere Finanznachrichten ein und beobachte die simulierte Marktstimmung
- **Politikfolgenabschätzung** — Teste Regulierungsentwürfe gegen eine simulierte öffentliche Reaktion
- **Kreative Experimente** — Jemand hat einen klassischen chinesischen Roman mit einem verlorenen Ende eingegeben; die Agenten schrieben einen narrativ konsistenten Abschluss

## Lizenz

AGPL-3.0 — identisch mit dem originalen MiroFish-Projekt. Siehe [LICENSE](./LICENSE).

## Danksagungen & Urheberschaft

Dies ist ein modifizierter Fork von [MiroFish](https://github.com/666ghj/MiroFish) von [666ghj](https://github.com/666ghj), ursprünglich unterstützt von [Shanda Group](https://www.shanda.com/). Die Simulations-Engine basiert auf [OASIS](https://github.com/camel-ai/oasis) vom CAMEL-AI Team.

**Änderungen in diesem Fork:**
- Backend von Zep Cloud auf lokales Neo4j CE 5.15 + Ollama migriert
- Gesamtes Frontend von Chinesisch auf Englisch übersetzt (20 Dateien, 1.000+ Strings)
- Deutsche Übersetzung der gesamten Benutzeroberfläche
- Alle Zep-Referenzen durch Neo4j in der gesamten UI ersetzt
- Umbenannt zu MiroFish Offline
