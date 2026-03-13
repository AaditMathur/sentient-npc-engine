# Sentient NPC Engine 3.0 🧠✨

Production-grade AI middleware that turns game NPCs into autonomous cognitive agents with memory, emotions, personality, goals, and dynamic LLM-powered dialogue.

## 🏆 Hackathon Innovation Features

This engine includes cutting-edge features that create emergent, living game worlds:

### 🗣️ Multi-NPC Conversations
- NPCs autonomously talk to each other based on relationships, proximity, and shared knowledge
- Gossip spreads naturally through social networks
- Emergent storylines form without player involvement
- Conversations influenced by personality, emotions, and recent events

### 😱 Emotional Contagion
- Emotions spread through crowds like real social contagion
- Panic cascades during attacks, joy spreads at festivals
- Crowd amplification effects (emotions intensify in groups)
- Personality-based resistance and susceptibility

### ⚔️ Dynamic Quest Generation
- NPCs autonomously create quests based on their goals and experiences
- Crime victims generate revenge/bounty quests
- Merchants create retrieval quests for stolen goods
- Guards post bounties for criminals
- Quest rewards scale with emotional intensity and severity

### ⚡ Temporal Causality Chains
- Track cause-and-effect relationships across the entire world
- Visualize butterfly effects: small actions → massive consequences
- Predict future consequences of hypothetical events
- Trace any event back to its root cause
- Measure player impact on the world

### 📜 Cultural Memory & Legends
- Events become stories, stories become folklore, folklore becomes legend
- Player reputation evolves into legendary status (hero or villain)
- Legends spread through retelling, gaining embellishments
- NPCs reference legends in conversations
- Cultural narratives shape NPC behavior

### 💭 Dream & Subconscious System
- NPCs dream based on memories, emotions, and goals
- Nightmares process trauma and reduce fear
- Prophetic dreams hint at future events
- Wish-fulfillment dreams increase motivation
- Dreams influence next-day behavior and can inspire new goals

### 📊 Real-Time Analytics Dashboard
- Live visualization of world emotional state
- Causality chain explorer
- Legend tracker with spread metrics
- Active quest monitor
- Butterfly effect showcase

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

# 6. Run innovation demo
python demo_innovations.py

# 7. Open dashboard
# Visit http://localhost:8000/dashboard
```

## 🎮 Try the Innovation Features

### Interactive Dashboard
```bash
# Open in browser
http://localhost:8000/dashboard
```

Features:
- Real-time world emotion visualization
- Butterfly effect explorer
- Legend tracker
- Quest monitor
- One-click panic simulation

### Run the Demo
```bash
python demo_innovations.py
```

This will showcase:
- Multi-NPC conversations
- Emotional contagion spreading
- Dynamic quest generation
- Causality chain tracking
- Legend formation
- Dream generation

### API Documentation
```bash
# Interactive API docs
http://localhost:8000/docs

# Innovation API guide
See INNOVATION_API.md for detailed examples
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

### Core Cognitive Architecture
- **Cognitive Pipeline**: Perception → Memory → Emotion → Personality → Goals → Dialogue → Action
- **Hybrid Memory**: Episodic + Semantic + Emotional memory with vector similarity search
- **Emotion Engine**: 8-dimensional emotion vector with decay and stimulus response
- **GOAP Planner**: Goal-Oriented Action Planning with personality/emotion modifiers
- **Social Graph**: NPC-to-NPC relationship tracking with trust, fear, friendship
- **World Events**: Event-driven reactions via Redis Streams
- **Background Sim**: NPCs evolve even when players are offline

### Innovation Features (Hackathon Special)
- **Multi-NPC Conversations**: Autonomous NPC-to-NPC dialogue with emergent storylines
- **Emotional Contagion**: Emotions spread through crowds with social physics
- **Dynamic Quests**: NPCs generate quests based on goals, crimes, and events
- **Causality Chains**: Track butterfly effects and predict consequences
- **Cultural Legends**: Events become folklore, player reputation becomes legendary
- **Dream System**: NPCs dream and process memories, influencing behavior
- **Real-Time Dashboard**: Visualize world state, emotions, and causality
