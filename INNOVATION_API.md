# Innovation Features API Documentation

## 🎯 Quick Start

Access the interactive dashboard at: `http://localhost:8000/dashboard`

API documentation: `http://localhost:8000/docs`

---

## 🗣️ Multi-NPC Conversations

### Start a Conversation
```http
POST /api/v1/conversation/start
Content-Type: application/json

{
  "npc_ids": ["npc_1", "npc_2"],
  "topic": "gossip_about_theft",
  "max_turns": 6
}
```

**Response:**
```json
{
  "participants": ["Aldric the Merchant", "Guard Captain"],
  "topic": "gossip_about_theft",
  "turns": [
    {
      "speaker_id": "npc_1",
      "speaker_name": "Aldric",
      "dialogue": "Did you hear about the theft at the market?",
      "action": "leans in conspiratorially",
      "emotion_after": {...},
      "internal_thought": "I hope the guard can help"
    }
  ],
  "total_turns": 6
}
```

### Check Conversation Likelihood
```http
GET /api/v1/conversation/should-talk/{npc1_id}/{npc2_id}
```

---

## 😱 Emotional Contagion

### Simulate Panic Spread
```http
POST /api/v1/emotion/contagion/panic
Content-Type: application/json

{
  "location": "Market Square",
  "panic_source": "Dragon attack!",
  "intensity": 0.9
}
```

**Response:**
```json
{
  "location": "Market Square",
  "panic_source": "Dragon attack!",
  "total_npcs": 25,
  "affected_npcs": 22,
  "penetration_rate": "88.0%"
}
```

### Get Crowd Mood
```http
GET /api/v1/emotion/crowd-mood/{location}
```

**Response:**
```json
{
  "location": "Market Square",
  "dominant_emotion": "fear",
  "average_valence": -0.45,
  "average_arousal": 0.78,
  "emotion_distribution": {
    "joy": 0.12,
    "fear": 0.82,
    "anger": 0.35,
    ...
  },
  "crowd_size": 25
}
```

---

## ⚔️ Dynamic Quests

### Get Available Quests
```http
GET /api/v1/quests/available?location=Market&quest_type=bounty&limit=10
```

**Response:**
```json
{
  "total": 5,
  "quests": [
    {
      "quest_id": "quest_123",
      "quest_type": "bounty",
      "title": "Bounty: player_456",
      "description": "Aldric is offering a bounty for player_456, wanted for theft",
      "quest_giver_name": "Aldric the Merchant",
      "difficulty": "moderate",
      "rewards": {
        "gold": 600,
        "reputation": {"Traders Guild": 75},
        "experience": 180
      },
      "urgency": 0.7,
      "expires_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### Get Quest Details
```http
GET /api/v1/quests/{quest_id}
```

---

## ⚡ Causality Chains

### Trace Causality Back to Root
```http
GET /api/v1/causality/trace/{node_id}
```

**Response:**
```json
{
  "node_id": "node_789",
  "chain_length": 5,
  "root_cause": "Player stole from merchant",
  "path": [
    {
      "node_id": "node_001",
      "description": "Player stole from merchant",
      "event_type": "crime",
      "severity": 0.6,
      "chain_depth": 0
    },
    {
      "node_id": "node_002",
      "description": "Merchant posted bounty quest",
      "event_type": "quest_creation",
      "severity": 0.5,
      "chain_depth": 1
    },
    ...
  ]
}
```

### Get Butterfly Effects
```http
GET /api/v1/causality/butterfly-effects?min_amplification=5.0&limit=10
```

**Response:**
```json
{
  "total": 3,
  "examples": [
    {
      "chain_id": "chain_456",
      "title": "Chain: Player stole from merchant",
      "root_cause": "Player stole 50 gold from merchant",
      "root_severity": 0.6,
      "root_scope": 2,
      "final_effects": [
        "Town-wide panic about crime wave",
        "Guards increased patrols",
        "Merchants raised prices"
      ],
      "total_actors_affected": 45,
      "chain_depth": 7,
      "butterfly_score": 15.8,
      "amplification": 22.5
    }
  ]
}
```

### Get Actor Impact
```http
GET /api/v1/causality/actor-impact/{actor_id}
```

### Predict Consequences
```http
POST /api/v1/causality/predict
Content-Type: application/json

{
  "event_type": "theft",
  "actor_id": "player_123",
  "severity": 0.7
}
```

**Response:**
```json
{
  "hypothetical_event": {...},
  "predictions": [
    {
      "consequence_type": "bounty_quest",
      "probability": 0.75,
      "expected_severity": 0.65,
      "example": "Merchant posts bounty",
      "confidence": 0.82
    },
    {
      "consequence_type": "reputation_loss",
      "probability": 0.90,
      "expected_severity": 0.55,
      "confidence": 0.88
    }
  ]
}
```

---

## 📜 Cultural Legends

### Get Legends
```http
GET /api/v1/legends?location=Market&faction=Traders&min_spread=5
```

**Response:**
```json
{
  "total": 8,
  "legends": [
    {
      "legend_id": "legend_123",
      "title": "The Great Heist of Shadow Thief",
      "type": "great_heist",
      "status": "folklore",
      "protagonist": "Shadow Thief",
      "reputation": -0.75,
      "spread": 45,
      "fidelity": 0.65,
      "embellishment": 0.35,
      "current_version": "Shadow Thief stole the Crown Jewels...",
      "age_days": 14
    }
  ]
}
```

### Get Protagonist Reputation
```http
GET /api/v1/legends/reputation/{protagonist_id}
```

**Response:**
```json
{
  "protagonist_id": "player_123",
  "reputation_score": -0.68,
  "category": "villain",
  "legend_count": 3,
  "most_famous_legend": "The Great Heist of Shadow Thief",
  "total_spread": 87,
  "legends": [...]
}
```

### Tell a Legend
```http
POST /api/v1/legends/{legend_id}/tell
Content-Type: application/json

{
  "teller_id": "npc_1",
  "listener_id": "npc_2",
  "embellish": true
}
```

---

## 💭 Dreams

### Generate Dream for NPC
```http
POST /api/v1/dreams/generate/{npc_id}
```

**Response:**
```json
{
  "dream_id": "dream_789",
  "npc_id": "npc_1",
  "npc_name": "Aldric",
  "dream_type": "nightmare",
  "content": "Aldric dreams of darkness and being chased...",
  "symbolism": ["darkness", "being chased"],
  "triggered_by_memories": ["mem_123"],
  "emotion_impact": {
    "fear": -0.1,
    "sadness": 0.05
  },
  "behavior_impact": "cautious and jumpy in the morning",
  "vividness": 0.8,
  "interpretation": "Processing deep fears"
}
```

---

## 📊 Analytics

### Get World State Analytics
```http
GET /api/v1/analytics/world-state
```

**Response:**
```json
{
  "total_npcs": 50,
  "average_emotions": {
    "joy": 0.45,
    "trust": 0.52,
    "fear": 0.28,
    ...
  },
  "dominant_world_emotion": "trust",
  "total_causal_events": 234,
  "total_causal_chains": 45,
  "total_legends": 12,
  "active_quests": 8,
  "locations": ["Market Square", "Castle", "Forest"]
}
```

---

## 🎮 Example Workflow: The Butterfly Effect Demo

1. **Commit a Crime**
```http
POST /api/v1/world/crime
{
  "perpetrator_id": "player_1",
  "victim_id": "npc_merchant",
  "crime_type": "theft",
  "description": "Stole 50 gold coins",
  "severity": 0.6,
  "witnesses": ["npc_guard", "npc_bystander"]
}
```

2. **Watch Panic Spread**
```http
POST /api/v1/emotion/contagion/panic
{
  "location": "Market Square",
  "panic_source": "Crime wave!",
  "intensity": 0.7
}
```

3. **Check Generated Quests**
```http
GET /api/v1/quests/available
```

4. **View Causality Chain**
```http
GET /api/v1/causality/butterfly-effects
```

5. **See Legend Formation**
```http
GET /api/v1/legends
```

6. **Check Your Reputation**
```http
GET /api/v1/legends/reputation/player_1
```

---

## 🚀 Advanced Features

### Gossip Cascade
When NPCs learn about crimes, they automatically gossip with nearby NPCs, spreading information through the social network.

### Emotional Contagion in Crowds
Emotions spread based on:
- Social relationships (trust amplifies contagion)
- Personality (empathy increases susceptibility)
- Distance (emotions decay with distance)
- Crowd size (larger crowds amplify emotions)

### Quest Generation Triggers
Quests are automatically generated when:
- NPCs are victims of crimes
- NPCs witness crimes (if lawful personality)
- NPCs have blocked goals
- NPCs experience strong emotions

### Legend Evolution
Legends evolve through:
- Retelling (each telling may add embellishments)
- Time (old legends become myths)
- Spread (widely known stories become folklore)
- Fidelity decay (details become fuzzy over time)

---

## 📈 Metrics & Monitoring

All systems include comprehensive logging and metrics:
- Conversation turn counts
- Emotion contagion penetration rates
- Quest generation rates
- Causality chain depths
- Legend spread metrics
- Dream frequency and types

Access Prometheus metrics at: `http://localhost:8000/metrics`

---

## 🎨 Visualization Dashboard

The interactive dashboard provides real-time visualization of:
- World emotional state (emotion bars)
- Active quests
- Cultural legends
- Butterfly effects
- Causality chains
- NPC statistics

Access at: `http://localhost:8000/dashboard`

Features:
- Auto-refresh every 30 seconds
- One-click panic simulation
- Butterfly effect explorer
- Legend tracker
- Quest monitor
