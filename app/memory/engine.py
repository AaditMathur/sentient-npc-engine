"""
Memory Engine — Hybrid Episodic / Semantic / Emotional Memory
with Qdrant vector similarity search.

Retrieval Score = semantic_similarity × importance × recency
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    ScoredPoint,
)
from sentence_transformers import SentenceTransformer

from app.models import Memory, MemoryType, MemoryQuery, EmotionVector
from app.database import get_qdrant
from app.config import get_settings

settings = get_settings()

# ─────────────────────────────────────────────
# Embedding Model (runs locally, no API cost)
# Produces 384-dim vectors matching QDRANT config
# ─────────────────────────────────────────────
_embed_model: Optional[SentenceTransformer] = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def embed_text(text: str) -> List[float]:
    model = get_embed_model()
    return model.encode(text, normalize_embeddings=True).tolist()


# ─────────────────────────────────────────────
# MEMORY ENGINE
# ─────────────────────────────────────────────

class MemoryEngine:
    """
    Manages NPC memory storage and retrieval.

    Memory is stored in Qdrant as vector embeddings.
    Payload stores all metadata for filtering and scoring.

    Retrieval uses a compound score:
        score = α × semantic_sim + β × importance + γ × recency + δ × emotional_salience
    """

    def __init__(
        self,
        recency_weight: float = 0.25,
        importance_weight: float = 0.35,
        similarity_weight: float = 0.30,
        emotional_weight: float = 0.10,
    ):
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight
        self.similarity_weight = similarity_weight
        self.emotional_weight = emotional_weight
        self.collection = settings.qdrant_collection_memories

    async def store(self, memory: Memory) -> str:
        """Embed and store a memory in Qdrant."""
        client = await get_qdrant()

        # Embed the event text
        memory_text = self._memory_to_text(memory)
        embedding = embed_text(memory_text)
        memory.embedding = embedding

        # Build payload
        payload = {
            "npc_id": memory.npc_id,
            "memory_id": memory.memory_id,
            "memory_type": memory.memory_type.value,
            "event": memory.event,
            "participants": memory.participants,
            "location": memory.location,
            "emotion_at_time": memory.emotion_at_time.model_dump(),
            "importance": memory.importance,
            "emotional_intensity": memory.emotional_intensity,
            "timestamp": memory.timestamp.isoformat(),
            "tags": memory.tags,
            "access_count": 0,
            "last_accessed": None,
            "salience": memory.salience,
        }

        point = PointStruct(
            id=memory.memory_id,
            vector=embedding,
            payload=payload,
        )

        await client.upsert(
            collection_name=self.collection,
            points=[point],
        )

        return memory.memory_id

    async def retrieve(
        self,
        query: MemoryQuery,
        current_emotion: Optional[EmotionVector] = None,
    ) -> List[Tuple[Memory, float]]:
        """
        Retrieve top-k most relevant memories for a given context.

        Uses compound scoring:
          score = similarity_weight × cos_sim
                + importance_weight × importance
                + recency_weight × recency
                + emotional_weight × emotional_resonance
        """
        client = await get_qdrant()

        # Embed the query
        query_embedding = embed_text(query.query_text)

        # Build filter
        must_conditions = [
            FieldCondition(
                key="npc_id",
                match=MatchValue(value=query.npc_id),
            )
        ]
        if query.memory_type:
            must_conditions.append(
                FieldCondition(
                    key="memory_type",
                    match=MatchValue(value=query.memory_type.value),
                )
            )

        qdrant_filter = Filter(must=must_conditions)

        # Fetch candidates (more than top_k to allow re-ranking)
        candidates = await client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=query.top_k * 4,
            with_payload=True,
        )

        if not candidates:
            return []

        # Re-rank with compound score
        scored: List[Tuple[Memory, float]] = []
        now = datetime.now(timezone.utc)

        for point in candidates:
            memory = self._point_to_memory(point)
            compound_score = self._compound_score(
                semantic_similarity=point.score,
                importance=memory.importance,
                timestamp=memory.timestamp,
                now=now,
                emotional_intensity=memory.emotional_intensity,
                current_emotion=current_emotion,
            )
            scored.append((memory, compound_score))

        # Sort by compound score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:query.top_k]

    def _compound_score(
        self,
        semantic_similarity: float,
        importance: float,
        timestamp: datetime,
        now: datetime,
        emotional_intensity: float = 0.5,
        current_emotion: Optional[EmotionVector] = None,
    ) -> float:
        """
        Compound retrieval score formula.
        Recency uses exponential decay over days.
        """
        # Recency: 1.0 today → ~0.5 at 14 days → ~0.1 at 45 days
        age_seconds = (now - timestamp.replace(tzinfo=timezone.utc)).total_seconds()
        age_days = age_seconds / 86400
        recency = math.exp(-0.05 * age_days)

        # Emotional resonance: memories emotionally aligned with current state
        # are more easily recalled (mood-congruent memory effect)
        emotional_resonance = emotional_intensity
        if current_emotion is not None:
            emotional_resonance = min(1.0, emotional_intensity * (0.5 + current_emotion.arousal()))

        score = (
            self.similarity_weight * semantic_similarity
            + self.importance_weight * importance
            + self.recency_weight * recency
            + self.emotional_weight * emotional_resonance
        )
        return score

    async def update_salience(self, memory_id: str, npc_id: str) -> None:
        """Increment access count when memory is recalled."""
        client = await get_qdrant()
        # Qdrant doesn't support partial payload update in older clients,
        # so we fetch and re-upsert
        results = await client.retrieve(
            collection_name=self.collection,
            ids=[memory_id],
            with_payload=True,
            with_vectors=True,
        )
        if not results:
            return
        point = results[0]
        payload = point.payload
        payload["access_count"] = payload.get("access_count", 0) + 1
        payload["last_accessed"] = datetime.now(timezone.utc).isoformat()

        await client.upsert(
            collection_name=self.collection,
            points=[PointStruct(
                id=memory_id,
                vector=point.vector,
                payload=payload,
            )],
        )

    async def decay_memories(self, npc_id: str, decay_rate: float = 0.01) -> None:
        """
        Reduce salience of all memories for an NPC (background sim tick).
        Very low-salience memories can be pruned.
        """
        client = await get_qdrant()

        scroll_result = await client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="npc_id", match=MatchValue(value=npc_id))]
            ),
            limit=1000,
            with_payload=True,
            with_vectors=True,
        )

        points, _ = scroll_result
        to_delete = []
        to_update = []

        for point in points:
            salience = point.payload.get("salience", 1.0)
            importance = point.payload.get("importance", 0.5)
            # High-importance memories decay more slowly
            effective_decay = decay_rate * (1.0 - importance * 0.8)
            new_salience = salience * (1.0 - effective_decay)

            if new_salience < 0.05:
                to_delete.append(point.id)
            else:
                payload = point.payload
                payload["salience"] = new_salience
                to_update.append(PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=payload,
                ))

        if to_delete:
            await client.delete(
                collection_name=self.collection,
                points_selector=to_delete,
            )
        if to_update:
            await client.upsert(
                collection_name=self.collection,
                points=to_update,
            )

    async def get_memory_count(self, npc_id: str) -> int:
        client = await get_qdrant()
        result = await client.count(
            collection_name=self.collection,
            count_filter=Filter(
                must=[FieldCondition(key="npc_id", match=MatchValue(value=npc_id))]
            ),
        )
        return result.count

    def _memory_to_text(self, memory: Memory) -> str:
        """Build embeddable text from memory fields."""
        parts = [memory.event]
        if memory.participants:
            parts.append(f"Involved: {', '.join(memory.participants)}")
        if memory.location:
            parts.append(f"Location: {memory.location}")
        if memory.tags:
            parts.append(f"Tags: {', '.join(memory.tags)}")
        return ". ".join(parts)

    def _point_to_memory(self, point: ScoredPoint) -> Memory:
        """Reconstruct Memory object from Qdrant payload."""
        p = point.payload
        return Memory(
            memory_id=p["memory_id"],
            npc_id=p["npc_id"],
            memory_type=MemoryType(p["memory_type"]),
            event=p["event"],
            participants=p.get("participants", []),
            location=p.get("location"),
            emotion_at_time=EmotionVector(**p["emotion_at_time"]),
            importance=p["importance"],
            emotional_intensity=p["emotional_intensity"],
            timestamp=datetime.fromisoformat(p["timestamp"]),
            tags=p.get("tags", []),
            access_count=p.get("access_count", 0),
            salience=p.get("salience", 1.0),
        )


# ─────────────────────────────────────────────
# MEMORY FACTORY HELPERS
# ─────────────────────────────────────────────

def create_interaction_memory(
    npc_id: str,
    player_id: str,
    player_message: str,
    npc_response: str,
    emotion: EmotionVector,
    importance: float = 0.4,
) -> Memory:
    return Memory(
        npc_id=npc_id,
        memory_type=MemoryType.EPISODIC,
        event=f"Talked with {player_id}: they said '{player_message[:100]}' and I responded.",
        participants=[player_id],
        emotion_at_time=emotion,
        importance=importance,
        emotional_intensity=emotion.arousal(),
        tags=["player_interaction", "dialogue"],
    )


def create_world_event_memory(
    npc_id: str,
    event_description: str,
    emotion: EmotionVector,
    severity: float = 0.5,
    is_direct: bool = True,
) -> Memory:
    importance = severity * (1.0 if is_direct else 0.5)
    return Memory(
        npc_id=npc_id,
        memory_type=MemoryType.EPISODIC,
        event=event_description,
        emotion_at_time=emotion,
        importance=min(1.0, importance),
        emotional_intensity=emotion.arousal(),
        tags=["world_event"],
    )


# Singleton
memory_engine = MemoryEngine()
