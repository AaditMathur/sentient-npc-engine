"""
World Event System — Event-driven NPC reactions via Redis Streams.

Architecture:
  Game Engine → POST /world/event → Event Producer → Redis Stream
                                                    → NPC Reaction Workers (async consumers)
                                                    → Rumor Propagation

Events are broadcast to affected NPCs based on:
  - Location proximity (radius)
  - Faction membership
  - Social graph distance (for rumor propagation)
"""
from __future__ import annotations

import json
from typing import List, Dict
from datetime import datetime, timezone

from app.models import WorldEvent, EventType
from app.database import get_redis
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


# ─────────────────────────────────────────────
# EVENT PRODUCER
# ─────────────────────────────────────────────

class WorldEventProducer:
    """
    Publishes world events to Redis Streams.
    Called by the API server when a game event occurs.
    """

    async def publish(self, event: WorldEvent) -> str:
        """
        Serialize and push event to Redis stream.
        Returns stream entry ID.
        """
        redis = await get_redis()

        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "description": event.description,
            "location": event.location or "",
            "affected_factions": json.dumps(event.affected_factions),
            "affected_npcs": json.dumps(event.affected_npcs),
            "radius": str(event.radius),
            "severity": str(event.severity),
            "timestamp": event.timestamp.isoformat(),
            "metadata": json.dumps(event.metadata),
            "propagates_as_rumor": str(event.propagates_as_rumor),
        }

        entry_id = await redis.xadd(
            settings.redis_stream_world_events,
            payload,
            maxlen=10000,  # keep last 10k events
        )

        logger.info(
            "world_event_published",
            event_id=event.event_id,
            event_type=event.event_type.value,
            severity=event.severity,
            entry_id=entry_id,
        )

        return entry_id

    async def publish_npc_reaction(
        self,
        npc_id: str,
        event_id: str,
        reaction: str,
        emotion_delta: Dict[str, float],
    ) -> None:
        """Publish an NPC's reaction back to the reaction stream."""
        redis = await get_redis()
        await redis.xadd(
            settings.redis_stream_npc_reactions,
            {
                "npc_id": npc_id,
                "event_id": event_id,
                "reaction": reaction,
                "emotion_delta": json.dumps(emotion_delta),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            maxlen=50000,
        )


# ─────────────────────────────────────────────
# EVENT CONSUMER / DISPATCHER
# ─────────────────────────────────────────────

class WorldEventConsumer:
    """
    Reads from Redis stream and dispatches events to NPC brain workers.
    Runs as a background process.
    """

    def __init__(
        self,
        consumer_group: str = "npc_reaction_workers",
        consumer_name: str = "worker_1",
    ):
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.stream = settings.redis_stream_world_events

    async def ensure_group(self) -> None:
        redis = await get_redis()
        try:
            await redis.xgroup_create(
                self.stream,
                self.consumer_group,
                id="0",
                mkstream=True,
            )
        except Exception:
            pass  # Group already exists

    async def read_events(
        self,
        batch_size: int = 10,
        block_ms: int = 1000,
    ) -> List[WorldEvent]:
        """
        Read a batch of unprocessed events from the stream.
        Uses consumer groups for at-least-once delivery.
        """
        redis = await get_redis()
        raw = await redis.xreadgroup(
            groupname=self.consumer_group,
            consumername=self.consumer_name,
            streams={self.stream: ">"},
            count=batch_size,
            block=block_ms,
        )

        events = []
        if not raw:
            return events

        for stream_name, messages in raw:
            for entry_id, data in messages:
                try:
                    event = self._deserialize(data)
                    events.append((entry_id, event))
                except Exception as e:
                    logger.error("event_deserialize_error", error=str(e), data=data)

        return events

    async def ack(self, entry_id: str) -> None:
        redis = await get_redis()
        await redis.xack(self.stream, self.consumer_group, entry_id)

    def _deserialize(self, data: Dict[str, str]) -> WorldEvent:
        return WorldEvent(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            description=data["description"],
            location=data.get("location") or None,
            affected_factions=json.loads(data.get("affected_factions", "[]")),
            affected_npcs=json.loads(data.get("affected_npcs", "[]")),
            radius=float(data.get("radius", 100.0)),
            severity=float(data.get("severity", 0.5)),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=json.loads(data.get("metadata", "{}")),
            propagates_as_rumor=data.get("propagates_as_rumor", "True") == "True",
        )


# ─────────────────────────────────────────────
# RUMOR PROPAGATION ENGINE
# ─────────────────────────────────────────────

class RumorPropagator:
    """
    Spreads events as rumors through the social graph.

    Rumor fidelity decreases with each hop:
    - Direct witness: 100% accurate
    - 1 hop away: ~70% accurate, severity dampened
    - 2 hops: ~50% accurate, severity further dampened
    - 3+ hops: ~30% accuracy, often distorted
    """

    FIDELITY_BY_HOP = {0: 1.0, 1: 0.7, 2: 0.5, 3: 0.3}
    SEVERITY_DAMPEN_PER_HOP = 0.3

    def create_rumor_variant(
        self,
        original: WorldEvent,
        hop: int,
        spreader_name: str,
    ) -> WorldEvent:
        """Create a rumor version of an event with reduced severity and fidelity."""
        fidelity = self.FIDELITY_BY_HOP.get(min(hop, 3), 0.3)
        severity = max(0.1, original.severity - hop * self.SEVERITY_DAMPEN_PER_HOP)

        description = self._distort_description(
            original.description,
            fidelity,
            spreader_name,
        )

        return WorldEvent(
            event_id=original.event_id,
            event_type=EventType.RUMOR,
            description=description,
            location=original.location,
            affected_factions=original.affected_factions,
            radius=original.radius * 0.5,
            severity=severity,
            metadata={
                **original.metadata,
                "original_event_id": original.event_id,
                "rumor_hop": hop,
                "spreader": spreader_name,
                "fidelity": fidelity,
            },
            propagates_as_rumor=hop < 3,
        )

    def _distort_description(
        self,
        original: str,
        fidelity: float,
        spreader: str,
    ) -> str:
        """
        At low fidelity, distort the rumor description.
        In production, this could also call the LLM to paraphrase.
        """
        if fidelity >= 0.7:
            return f"{spreader} says: '{original}'"
        elif fidelity >= 0.5:
            return f"Word is spreading that {original.lower()} (heard from {spreader})"
        else:
            return f"There are unconfirmed rumors that something terrible happened near {spreader}"


# ─────────────────────────────────────────────
# EVENT TYPE → REACTION TEMPLATES
# For quick reaction generation without LLM call
# ─────────────────────────────────────────────

QUICK_REACTIONS: Dict[str, List[str]] = {
    EventType.DRAGON_KILLED: [
        "The dragon is finally dead! We are saved!",
        "I can hardly believe it. The beast is slain.",
        "The heroes have done it! Time to celebrate!",
    ],
    EventType.MARKET_FIRE: [
        "The market is burning! We must evacuate!",
        "My goods! Everything will be lost!",
        "Someone set the market on fire. This is no accident.",
    ],
    EventType.PLAYER_ATTACK: [
        "They attacked me! Guards! Help!",
        "How dare they raise a hand against me!",
        "I must flee before they come back!",
    ],
    EventType.PLAGUE: [
        "The sickness spreads. Keep your distance from me.",
        "Gods protect us. Half the village is coughing.",
        "We must quarantine the infected areas.",
    ],
    EventType.FESTIVAL: [
        "Finally, a reason to be merry! Let us celebrate!",
        "I've been looking forward to the festival all season.",
        "Put your worries aside — tonight we dance!",
    ],
    EventType.CRIME_COMMITTED: [
        "A crime?! Here?! What is this world coming to!",
        "I knew something terrible would happen. I felt it in my bones.",
        "Lock your doors tonight. There's a criminal about!",
        "How can anyone feel safe with such villainy happening?",
        "Someone must put a stop to this lawlessness!",
    ],
    EventType.RUMOR_HEARD: [
        "Have you heard? They say terrible things happened...",
        "Word is spreading about some dreadful business.",
        "I don't know if it's true, but people are talking about a crime.",
        "Keep your eyes open. I've heard troubling rumors.",
        "They whisper of crimes in the shadows. Be careful.",
    ],
}


def get_quick_reaction(event_type: str) -> str:
    import random
    reactions = QUICK_REACTIONS.get(event_type, ["Something has happened."])
    return random.choice(reactions)


# Singletons
event_producer = WorldEventProducer()
event_consumer = WorldEventConsumer()
rumor_propagator = RumorPropagator()
