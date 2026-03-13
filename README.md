# Sentient NPC Engine 3.0

Production-grade AI middleware that turns game NPCs into autonomous cognitive agents with memory, emotions, personality, goals, and dynamic LLM-powered dialogue.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GAME CLIENT / SDK                         │
│              (Unity C# SDK  /  REST API  /  WebSocket)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Gateway                              │
│         /npc/create   /npc/interact   /world/event               │
└──────┬──────────────────────┬───────────────────────┬───────────┘
       │                      │                       │
┌──────▼───────┐  ┌───────────▼──────────┐  ┌────────▼──────────┐
│  NPC Brain   │  │   World Event Bus    │  │  Background Sim   │
│  Pipeline    │  │   (Redis Streams)    │  │  Worker Pool      │
│              │  │                      │  │                   │
│ Perception   │  │  dragon_killed       │  │  emotion decay    │
│ Memory Ret.  │  │  market_fire         │  │  memory decay     │
│ Emotion Upd  │  │  player_attack       │  │  goal eval        │
│ Personality  │  │  rumor_spread        │  │  rumor propagate  │
│ Goal Planner │  └──────────────────────┘  └───────────────────┘
│ Dialogue Gen │
│ Action Exec  │
└──────┬───────┘
       │
┌──────▼────────────────────────────────────────────────────────┐
│                     Data Layer                                 │
│                                                               │
│  PostgreSQL (NPC state)    Neo4j (Social graph)               │
│  Qdrant (Vector memory)    Redis (Cache + Streams)            │
└───────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start infrastructure
docker-compose up -d

# 3. Run migrations
python scripts/migrate.py

# 4. Start API server
uvicorn app.main:app --reload --port 8000

# 5. Start background worker
python workers/simulation_worker.py
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Server | FastAPI + Uvicorn |
| LLM Backend | Anthropic Claude (claude-sonnet-4-20250514) |
| Vector Memory | Qdrant |
| NPC State | PostgreSQL + SQLAlchemy |
| Social Graph | Neo4j |
| Cache | Redis |
| Event Streaming | Redis Streams |
| Background Jobs | Celery + Redis |
| Embeddings | sentence-transformers |

## Key Features

- **Cognitive Pipeline**: Perception → Memory → Emotion → Personality → Goals → Dialogue → Action
- **Hybrid Memory**: Episodic + Semantic + Emotional memory with vector similarity search
- **Emotion Engine**: 6-dimensional emotion vector with decay and stimulus response
- **GOAP Planner**: Goal-Oriented Action Planning with personality/emotion modifiers
- **Social Graph**: NPC-to-NPC relationship tracking with trust, fear, friendship
- **World Events**: Event-driven reactions via Redis Streams
- **Background Sim**: NPCs evolve even when players are offline
