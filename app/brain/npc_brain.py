"""
NPC Brain — The Central Cognitive Pipeline

Perception → Memory Retrieval → Emotion Update → Personality Influence
→ Goal Planner → Dialogue Generator → Action Executor → State Persistence

This is the orchestration layer that connects all subsystems.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    NPCState, PersonalityVector, EmotionVector, Memory,
    MemoryQuery, MemoryType, Goal, GoalStatus,
    InteractRequest, InteractResponse, WorldEvent,
    CreateNPCRequest,
)
from app.database import NPCRecord, cache_get, cache_set, cache_delete
from app.emotion.engine import emotion_engine
from app.memory.engine import (
    memory_engine, MemoryQuery,
    create_interaction_memory, create_world_event_memory,
)
from app.personality.engine import get_personality_prompt_block
from app.goals.planner import goal_manager, GOAL_LIBRARY
from app.social.graph import social_graph
from app.dialogue.generator import dialogue_generator
from app.config import get_settings
import structlog

# Import new innovation systems
from app.causality.tracker import causality_tracker, CausalEventType
from app.culture.legends import cultural_memory
from app.quests.generator import quest_generator

logger = structlog.get_logger()
settings = get_settings()


# ─────────────────────────────────────────────
# NPC REPOSITORY
# ─────────────────────────────────────────────

class NPCRepository:
    """Handles NPC state persistence and caching."""

    async def create(self, db: AsyncSession, npc: NPCState) -> NPCState:
        # Robust serialization: ensure everything is converted to dicts for JSON columns
        record = NPCRecord(
            npc_id=npc.npc_id,
            name=npc.name,
            archetype=npc.archetype,
            faction=npc.faction,
            location=npc.location,
            personality_json=json.loads(npc.personality.model_dump_json()),
            emotion_state_json=json.loads(npc.emotion_state.model_dump_json()),
            goals_json=[json.loads(g.model_dump_json()) for g in npc.goals],
            relationships_json={k: json.loads(v.model_dump_json()) for k, v in npc.relationships.items()},
            recent_memory_ids_json=npc.recent_memory_ids,
            background=npc.background,
            speech_style=npc.speech_style,
            knowledge_base_json=npc.knowledge_base,
            world_knowledge_json=npc.world_knowledge,
            is_active=npc.is_active,
            sim_tick=npc.sim_tick,
            offline_ticks=npc.offline_ticks,
        )
        db.add(record)
        await db.flush()
        return npc

    async def get(self, db: AsyncSession, npc_id: str) -> Optional[NPCState]:
        """Load NPC state with Redis cache."""
        cache_key = f"npc:{npc_id}"
        cached = await cache_get(cache_key)
        if cached:
            return self._dict_to_state(cached)

        result = await db.execute(
            select(NPCRecord).where(NPCRecord.npc_id == npc_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        npc = self._record_to_state(record)
        await cache_set(cache_key, npc.model_dump(), ttl=settings.cache_npc_state_ttl)
        return npc

    async def save(self, db: AsyncSession, npc: NPCState) -> None:
        """Persist updated NPC state and invalidate cache."""
        result = await db.execute(
            select(NPCRecord).where(NPCRecord.npc_id == npc.npc_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            await self.create(db, npc)
            return

        record.emotion_state_json = npc.emotion_state.model_dump()
        record.goals_json = [g.model_dump() for g in npc.goals]
        record.relationships_json = {k: v.model_dump() for k, v in npc.relationships.items()}
        record.recent_memory_ids_json = npc.recent_memory_ids[-100:]  # keep last 100
        record.location = npc.location
        record.sim_tick = npc.sim_tick
        record.offline_ticks = npc.offline_ticks
        record.last_interaction = npc.last_interaction
        record.world_knowledge_json = npc.world_knowledge
        record.knowledge_base_json = npc.knowledge_base
        record.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await cache_delete(f"npc:{npc.npc_id}")

    async def list_active(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NPCState]:
        result = await db.execute(
            select(NPCRecord)
            .where(NPCRecord.is_active == True)
            .limit(limit)
            .offset(offset)
        )
        records = result.scalars().all()
        return [self._record_to_state(r) for r in records]

    def _record_to_state(self, r: NPCRecord) -> NPCState:
        from app.models import Relationship
        return NPCState(
            npc_id=r.npc_id,
            name=r.name,
            archetype=r.archetype,
            faction=r.faction,
            location=r.location,
            personality=PersonalityVector(**r.personality_json),
            emotion_state=EmotionVector(**r.emotion_state_json),
            goals=[Goal(**g) for g in (r.goals_json or [])],
            relationships={
                k: Relationship(**v)
                for k, v in (r.relationships_json or {}).items()
            },
            recent_memory_ids=r.recent_memory_ids_json or [],
            background=r.background or "",
            speech_style=r.speech_style or "neutral",
            knowledge_base=r.knowledge_base_json or {},
            world_knowledge=r.world_knowledge_json or {},
            is_active=r.is_active,
            sim_tick=r.sim_tick,
            offline_ticks=r.offline_ticks,
            last_interaction=r.last_interaction,
        )

    def _dict_to_state(self, data: Dict) -> NPCState:
        return NPCState(**data)


# ─────────────────────────────────────────────
# NPC BRAIN — Cognitive Pipeline
# ─────────────────────────────────────────────

class NPCBrain:
    """
    The central orchestrator of the NPC cognitive pipeline.

    Wires together:
      EmotionEngine + MemoryEngine + PersonalityEngine +
      GoalManager + SocialGraph + DialogueGenerator
    """

    def __init__(self):
        self.repo = NPCRepository()

    # ── CREATE ──────────────────────────────────

    async def create_npc(
        self,
        db: AsyncSession,
        request: CreateNPCRequest,
    ) -> NPCState:
        """Instantiate a new NPC with initial cognitive state."""
        personality = request.personality or self._default_personality(request.archetype)
        goals = []
        for goal_name in request.initial_goals:
            if goal_name in GOAL_LIBRARY:
                goals.append(GOAL_LIBRARY[goal_name].model_copy())

        npc = NPCState(
            name=request.name,
            archetype=request.archetype,
            faction=request.faction,
            location=request.location,
            personality=personality,
            background=request.background,
            speech_style=request.speech_style,
            goals=goals,
        )

        await self.repo.create(db, npc)
        await social_graph.upsert_npc_node(npc)

        logger.info("npc_created", npc_id=npc.npc_id, name=npc.name, archetype=npc.archetype)
        return npc

    # ── INTERACT ────────────────────────────────

    async def interact(
        self,
        db: AsyncSession,
        request: InteractRequest,
    ) -> InteractResponse:
        """
        Full cognitive pipeline for a player↔NPC interaction.

        1. Load NPC state
        2. Retrieve relevant memories
        3. Load relationship
        4. Apply emotion stimulus (player approaching)
        5. Re-rank goals
        6. Generate dialogue via LLM
        7. Apply emotion update from LLM
        8. Update relationship
        9. Store new memory
        10. Persist state
        """
        # 1. Load NPC
        npc = await self.repo.get(db, request.npc_id)
        if not npc:
            raise ValueError(f"NPC {request.npc_id} not found")

        # 2. Retrieve relevant memories
        mem_query = MemoryQuery(
            npc_id=npc.npc_id,
            query_text=request.player_message,
            top_k=5,
        )
        memory_results = await memory_engine.retrieve(
            mem_query,
            current_emotion=npc.emotion_state,
        )
        memories = [m for m, _ in memory_results]
        memory_texts = [m.event for m in memories]

        # 3. Load relationship from social graph
        relationship = await social_graph.get_relationship(
            npc.npc_id, request.player_id
        )

        # 4. Apply perception emotion stimulus
        # Player approaching triggers mild anticipation
        npc.emotion_state = emotion_engine.apply_stimulus(
            npc.emotion_state,
            "interaction_start",
            npc.personality,
            severity=0.2,
        )

        # 5. Re-rank goals with current emotion
        world_state = npc.world_knowledge or {}
        if npc.goals:
            active = goal_manager.select_and_plan(
                npc.goals,
                npc.personality,
                npc.emotion_state,
                world_state,
                max_active=settings.max_active_goals,
            )
            # Merge back (keep completed/failed goals)
            active_ids = {g.goal_id for g in active}
            npc.goals = active + [
                g for g in npc.goals
                if g.goal_id not in active_ids
                and g.status in (GoalStatus.COMPLETED, GoalStatus.FAILED)
            ]

        # 6. Generate dialogue via LLM
        # Inject crime awareness context
        from app.rumor.rumor_network import rumor_network
        crime_context = rumor_network.get_crime_context_for_dialogue(npc, request.player_id)

        world_context = {
            "recent_events": list(npc.world_knowledge.get("recent_events", [])),
            "location": npc.location,
            "crime_awareness": crime_context,
            "known_criminals": npc.world_knowledge.get("known_criminals", {}),
        }
        llm_result = await dialogue_generator.generate(
            npc=npc,
            player_id=request.player_id,
            player_message=request.player_message,
            memories=memories,
            relationship=relationship,
            world_context=world_context,
        )

        dialogue = llm_result.get("dialogue", "...")
        npc_action = llm_result.get("npc_action")
        emotion_dict = llm_result.get("emotion_update", {})
        rel_delta = llm_result.get("relationship_delta", {})
        mem_tags = llm_result.get("memory_tags", ["interaction"])

        # 7. Apply emotion update
        if emotion_dict:
            try:
                npc.emotion_state = EmotionVector(**{
                    k: max(0.0, min(1.0, float(v)))
                    for k, v in emotion_dict.items()
                    if k in EmotionVector.model_fields
                })
            except Exception:
                pass

        # 8. Update relationship
        if rel_delta:
            await social_graph.update_relationship_delta(
                npc.npc_id, request.player_id, rel_delta
            )

        # 9. Store interaction memory
        importance = self._compute_interaction_importance(
            request.player_message, npc.emotion_state
        )
        new_memory = create_interaction_memory(
            npc_id=npc.npc_id,
            player_id=request.player_id,
            player_message=request.player_message,
            npc_response=dialogue,
            emotion=npc.emotion_state,
            importance=importance,
        )
        new_memory.tags = mem_tags
        memory_id = await memory_engine.store(new_memory)
        npc.recent_memory_ids.append(memory_id)

        # 10. Record causality
        causality_tracker.record_event(
            event_type=CausalEventType.PLAYER_ACTION,
            description=f"Player {request.player_id} interacted with {npc.name}: {request.player_message[:50]}",
            primary_actor_id=request.player_id,
            affected_actors=[npc.npc_id],
            severity=importance,
            location=npc.location,
        )
        
        # 11. Persist state
        npc.last_interaction = datetime.now(timezone.utc)
        await self.repo.save(db, npc)

        return InteractResponse(
            npc_id=npc.npc_id,
            dialogue=dialogue,
            npc_action=npc_action,
            emotion_after=npc.emotion_state,
            memories_recalled=memory_texts,
            relationship_delta=rel_delta,
        )

    # ── WORLD EVENT REACTION ─────────────────

    async def react_to_world_event(
        self,
        db: AsyncSession,
        npc_id: str,
        event: WorldEvent,
        is_direct: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a world event for a single NPC.
        Updates emotion, stores memory, returns reaction summary.
        """
        npc = await self.repo.get(db, npc_id)
        if not npc:
            return {"error": f"NPC {npc_id} not found"}

        # Apply emotion stimulus
        npc.emotion_state = emotion_engine.process_event(
            emotion=npc.emotion_state,
            event_type=event.event_type.value,
            personality=npc.personality,
            severity=event.severity,
            is_direct=is_direct,
        )

        # Store memory of event
        memory = create_world_event_memory(
            npc_id=npc.npc_id,
            event_description=event.description,
            emotion=npc.emotion_state,
            severity=event.severity,
            is_direct=is_direct,
        )
        memory_id = await memory_engine.store(memory)
        npc.recent_memory_ids.append(memory_id)

        # Update world knowledge
        if "recent_events" not in npc.world_knowledge:
            npc.world_knowledge["recent_events"] = []
        npc.world_knowledge["recent_events"].insert(0, event.description)
        npc.world_knowledge["recent_events"] = npc.world_knowledge["recent_events"][:10]

        await self.repo.save(db, npc)

        from app.world.events import get_quick_reaction
        reaction = get_quick_reaction(event.event_type.value)

        return {
            "npc_id": npc_id,
            "npc_name": npc.name,
            "reaction": reaction,
            "emotion_after": npc.emotion_state.model_dump(),
            "dominant_emotion": npc.emotion_state.dominant(),
        }

    # ── BACKGROUND SIMULATION TICK ───────────

    async def simulation_tick(
        self,
        db: AsyncSession,
        npc_id: str,
        elapsed_ticks: int = 1,
    ) -> None:
        """
        Background simulation: runs when player is offline.
        - Decay emotions toward baseline
        - Decay memory salience
        - Re-evaluate goals
        - Increment counters
        """
        npc = await self.repo.get(db, npc_id)
        if not npc or not npc.is_active:
            return

        # Emotion decay
        npc.emotion_state = emotion_engine.apply_decay(
            npc.emotion_state,
            ticks=elapsed_ticks,
        )

        # Memory decay (async, handled by memory engine)
        await memory_engine.decay_memories(
            npc_id=npc_id,
            decay_rate=settings.memory_decay_rate,
        )

        # Goal re-evaluation
        pending_goals = [g for g in npc.goals if g.status in (GoalStatus.PENDING, GoalStatus.ACTIVE)]
        if pending_goals:
            goal_manager.select_and_plan(
                pending_goals,
                npc.personality,
                npc.emotion_state,
                npc.world_knowledge,
                max_active=settings.max_active_goals,
            )

        npc.sim_tick += elapsed_ticks
        npc.offline_ticks += elapsed_ticks
        await self.repo.save(db, npc)

    # ── HELPERS ─────────────────────────────

    def _default_personality(self, archetype: str) -> PersonalityVector:
        """Archetype-based personality defaults."""
        presets = {
            "merchant":  PersonalityVector(greed=0.7, empathy=0.4, honesty=0.5, bravery=0.3, curiosity=0.5, loyalty=0.4, aggression=0.2),
            "guard":     PersonalityVector(greed=0.2, empathy=0.3, honesty=0.7, bravery=0.8, curiosity=0.3, loyalty=0.8, aggression=0.5),
            "wizard":    PersonalityVector(greed=0.3, empathy=0.4, honesty=0.6, bravery=0.5, curiosity=0.9, loyalty=0.5, aggression=0.2),
            "thief":     PersonalityVector(greed=0.8, empathy=0.3, honesty=0.1, bravery=0.6, curiosity=0.6, loyalty=0.4, aggression=0.4),
            "healer":    PersonalityVector(greed=0.2, empathy=0.9, honesty=0.8, bravery=0.4, curiosity=0.5, loyalty=0.7, aggression=0.1),
            "innkeeper": PersonalityVector(greed=0.4, empathy=0.6, honesty=0.6, bravery=0.3, curiosity=0.5, loyalty=0.5, aggression=0.1),
            "bandit":    PersonalityVector(greed=0.9, empathy=0.1, honesty=0.1, bravery=0.7, curiosity=0.3, loyalty=0.3, aggression=0.8),
        }
        return presets.get(archetype.lower(), PersonalityVector())

    def _compute_interaction_importance(
        self,
        message: str,
        emotion: EmotionVector,
    ) -> float:
        """
        Estimate memory importance based on arousal + message length/keywords.
        """
        base = 0.3
        arousal_bonus = emotion.arousal() * 0.3
        keywords = ["attack", "kill", "love", "hate", "betrayal", "quest", "dragon", "treasure"]
        keyword_bonus = sum(0.05 for kw in keywords if kw in message.lower())
        return min(1.0, base + arousal_bonus + keyword_bonus)


# Singleton
npc_brain = NPCBrain()
