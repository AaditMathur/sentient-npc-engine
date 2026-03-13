"""
API Routes — Sentient NPC Engine 3.0

POST /npc/create       → Create a new NPC
POST /npc/interact     → Player interacts with NPC
GET  /npc/{npc_id}     → Get NPC state
GET  /npc/{npc_id}/memories → Get NPC memories
GET  /npc/{npc_id}/crime-awareness → Get crime awareness
POST /world/event      → Broadcast a world event
POST /world/crime      → Report a crime (triggers rumor cascade)
GET  /health           → Health check
"""
from __future__ import annotations

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CreateNPCRequest, InteractRequest, InteractResponse,
    NPCStateResponse, WorldEventRequest, WorldEvent,
    MemoryQuery, MemoryType, CrimeReportRequest, CrimeRecord,
    EventType,
)
from app.database import get_db
from app.brain.npc_brain import npc_brain
from app.memory.engine import memory_engine
from app.world.events import event_producer
import structlog

logger = structlog.get_logger()
router = APIRouter()


# ─────────────────────────────────────────────
# NPC ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/npc/create", response_model=Dict[str, Any], tags=["NPC"])
async def create_npc(
    request: CreateNPCRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new NPC with initial cognitive state.

    Example:
    ```json
    {
      "name": "Aldric the Merchant",
      "archetype": "merchant",
      "faction": "Traders Guild",
      "location": "Ironhaven Market",
      "background": "A seasoned trader who has seen hard times...",
      "speech_style": "formal medieval, slightly suspicious",
      "initial_goals": ["increase_wealth", "sell_goods"]
    }
    ```
    """
    try:
        npc = await npc_brain.create_npc(db, request)
        return {
            "npc_id": npc.npc_id,
            "name": npc.name,
            "archetype": npc.archetype,
            "faction": npc.faction,
            "location": npc.location,
            "personality": npc.personality.model_dump(),
            "emotion_state": npc.emotion_state.model_dump(),
            "goals": [g.name for g in npc.goals],
            "created": True,
        }
    except Exception as e:
        logger.error("create_npc_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/npc/interact", response_model=InteractResponse, tags=["NPC"])
async def interact_with_npc(
    request: InteractRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Full cognitive pipeline: player sends message, NPC responds with
    contextual dialogue, emotion, and action.

    Example:
    ```json
    {
      "npc_id": "abc-123",
      "player_id": "player_456",
      "player_message": "Do you know anything about the dragon attacks?"
    }
    ```
    """
    try:
        response = await npc_brain.interact(db, request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("interact_error", npc_id=request.npc_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/npc/{npc_id}", response_model=NPCStateResponse, tags=["NPC"])
async def get_npc_state(
    npc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the current cognitive state of an NPC.
    Includes emotion vector, active goals, and relationship count.
    """
    npc = await npc_brain.repo.get(db, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")

    memory_count = await memory_engine.get_memory_count(npc_id)
    active_goals = [g for g in npc.goals if g.status.value == "active"]

    return NPCStateResponse(
        npc_id=npc.npc_id,
        name=npc.name,
        archetype=npc.archetype,
        emotion_state=npc.emotion_state,
        dominant_emotion=npc.emotion_state.dominant(),
        mood_valence=npc.emotion_state.valence(),
        active_goals=active_goals,
        relationship_count=len(npc.relationships),
        memory_count=memory_count,
        location=npc.location,
        last_interaction=npc.last_interaction,
    )


@router.get("/npc/{npc_id}/memories", tags=["NPC"])
async def get_npc_memories(
    npc_id: str,
    query: str = Query(..., description="What to search for in memories"),
    top_k: int = Query(10, ge=1, le=50),
    memory_type: Optional[MemoryType] = Query(None),
):
    """
    Retrieve relevant memories for an NPC via vector similarity search.

    Example: GET /npc/abc-123/memories?query=dragon+attack&top_k=5
    """
    mem_query = MemoryQuery(
        npc_id=npc_id,
        query_text=query,
        top_k=top_k,
        memory_type=memory_type,
    )
    results = await memory_engine.retrieve(mem_query)
    return {
        "npc_id": npc_id,
        "query": query,
        "memories": [
            {
                "memory_id": mem.memory_id,
                "event": mem.event,
                "type": mem.memory_type.value,
                "importance": mem.importance,
                "score": round(score, 4),
                "timestamp": mem.timestamp.isoformat(),
                "tags": mem.tags,
            }
            for mem, score in results
        ],
    }


@router.get("/npc/{npc_id}/relationships", tags=["NPC"])
async def get_npc_relationships(npc_id: str):
    """Get all relationships for an NPC from the social graph."""
    from app.social.graph import social_graph
    relationships = await social_graph.get_all_relationships(npc_id)
    return {
        "npc_id": npc_id,
        "relationships": [r.model_dump() for r in relationships],
    }


@router.get("/npc/{npc_id}/goals", tags=["NPC"])
async def get_npc_goals(
    npc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all goals and their status for an NPC."""
    npc = await npc_brain.repo.get(db, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")
    return {
        "npc_id": npc_id,
        "goals": [g.model_dump() for g in npc.goals],
    }


@router.get("/npc/{npc_id}/crime-awareness", tags=["NPC", "Crime"])
async def get_npc_crime_awareness(
    npc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Query what crimes an NPC knows about.
    Returns awareness level, crime type, perpetrator, and whether they believe it.
    """
    npc = await npc_brain.repo.get(db, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")

    from app.rumor.rumor_network import rumor_network
    awareness = rumor_network.get_npc_crime_awareness(npc)
    return {
        "npc_id": npc_id,
        "npc_name": npc.name,
        "crimes_known": len(awareness),
        "crime_awareness": awareness,
        "active_behavior_modifiers": npc.behavior_modifiers,
    }


# ─────────────────────────────────────────────
# WORLD EVENT ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/world/event", tags=["World"])
async def publish_world_event(
    request: WorldEventRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Broadcast a world event to all affected NPCs.
    Events are processed asynchronously via Redis Streams.

    Example:
    ```json
    {
      "event_type": "dragon_killed",
      "description": "The great dragon Vorthex has been slain in the Eastern Mountains",
      "location": "Eastern Mountains",
      "affected_factions": ["Hunters Guild", "Merchants"],
      "severity": 0.9,
      "radius": 500.0
    }
    ```
    """
    event = WorldEvent(
        event_type=request.event_type,
        description=request.description,
        location=request.location,
        affected_factions=request.affected_factions,
        severity=request.severity,
        radius=request.radius,
        metadata=request.metadata,
    )

    entry_id = await event_producer.publish(event)

    return {
        "event_id": event.event_id,
        "stream_entry_id": entry_id,
        "event_type": event.event_type.value,
        "status": "queued",
        "message": "Event queued for NPC reaction processing",
    }


@router.post("/world/crime", tags=["World", "Crime"])
async def report_crime(
    request: CrimeReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Report a crime committed by a player or NPC.
    Triggers the full rumor propagation cascade:
    - Witnesses get direct awareness
    - Rumors spread through social graph (multi-hop)
    - NPCs react with emotion, behavior changes, and memory

    Example:
    ```json
    {
      "perpetrator_id": "player_456",
      "victim_id": "npc_merchant_01",
      "victim_name": "Aldric the Merchant",
      "crime_type": "theft",
      "description": "Stole 50 gold coins from the market stall",
      "location": "Ironhaven Market",
      "severity": 0.6,
      "witnesses": ["npc_guard_01", "npc_bystander_02"],
      "affected_factions": ["Traders Guild"]
    }
    ```
    """
    try:
        crime = CrimeRecord(
            perpetrator_id=request.perpetrator_id,
            victim_id=request.victim_id,
            victim_name=request.victim_name,
            crime_type=request.crime_type,
            description=request.description,
            location=request.location,
            severity=request.severity,
            witnesses=request.witnesses,
            metadata=request.metadata,
        )

        event = WorldEvent(
            event_type=EventType.CRIME_COMMITTED,
            description=request.description or f"A {request.crime_type.value} was committed",
            location=request.location,
            affected_factions=request.affected_factions,
            affected_npcs=request.witnesses,
            severity=request.severity,
            metadata={
                "crime_id": crime.crime_id,
                "crime_type": request.crime_type.value,
                "perpetrator_id": request.perpetrator_id,
                "victim_id": request.victim_id,
                "victim_name": request.victim_name,
            },
            propagates_as_rumor=True,
        )
        entry_id = await event_producer.publish(event)

        from app.rumor.rumor_network import rumor_network
        background_tasks.add_task(
            _run_crime_cascade, rumor_network, crime, db
        )

        return {
            "crime_id": crime.crime_id,
            "event_id": event.event_id,
            "stream_entry_id": entry_id,
            "crime_type": crime.crime_type.value,
            "severity": crime.severity,
            "witnesses": crime.witnesses,
            "status": "crime_reported",
            "message": (
                f"Crime reported: {crime.crime_type.value}. "
                f"Rumor cascade initiated with {len(crime.witnesses)} witnesses."
            ),
        }

    except Exception as e:
        logger.error("crime_report_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _run_crime_cascade(rumor_network, crime: CrimeRecord, db) -> None:
    """Background task to run the full rumor cascade."""
    try:
        # Run rumor cascade
        rumor = await rumor_network.cascade(
            crime=crime, witness_npc_ids=crime.witnesses, db=db, max_hops=3,
        )
        
        # Record causality
        from app.causality.tracker import causality_tracker, CausalEventType
        crime_node = causality_tracker.record_event(
            event_type=CausalEventType.CRIME,
            description=f"{crime.crime_type.value} committed by {crime.perpetrator_id}",
            primary_actor_id=crime.perpetrator_id,
            affected_actors=[crime.victim_id] if crime.victim_id else [],
            severity=crime.severity,
            location=crime.location,
            metadata={"crime_id": crime.crime_id},
        )
        
        # Create legend if significant
        from app.culture.legends import cultural_memory
        if crime.severity > 0.6 and len(crime.witnesses) >= 2:
            legend = cultural_memory.create_legend_from_event(
                event_description=crime.description or f"A {crime.crime_type.value} was committed",
                protagonist_id=crime.perpetrator_id,
                protagonist_name=crime.perpetrator_id,
                event_type=crime.crime_type.value,
                severity=crime.severity,
                witnesses=crime.witnesses,
                location=crime.location,
                metadata={"crime_id": crime.crime_id},
            )
            if legend:
                logger.info("legend_created_from_crime", legend_id=legend.legend_id, crime_id=crime.crime_id)
        
        # Generate quests for affected NPCs
        from app.quests.generator import quest_generator
        from app.brain.npc_brain import npc_brain
        
        # Victim generates quest
        if crime.victim_id:
            victim = await npc_brain.repo.get(db, crime.victim_id)
            if victim:
                quest = quest_generator.generate_quest_from_crime(
                    npc=victim,
                    crime=crime,
                    awareness_level="victim",
                )
                if quest:
                    logger.info("quest_generated_from_crime", quest_id=quest.quest_id, crime_id=crime.crime_id)
        
        # Witnesses might generate quests
        for witness_id in crime.witnesses[:2]:  # Limit to first 2 witnesses
            witness = await npc_brain.repo.get(db, witness_id)
            if witness:
                quest = quest_generator.generate_quest_from_crime(
                    npc=witness,
                    crime=crime,
                    awareness_level="direct_witness",
                )
                if quest:
                    logger.info("quest_generated_by_witness", quest_id=quest.quest_id, witness=witness.name)
        
        logger.info(
            "api_crime_cascade_complete",
            crime_id=crime.crime_id,
            total_heard=len(rumor.heard_by),
        )
    except Exception as e:
        logger.error("api_crime_cascade_error", crime_id=crime.crime_id, error=str(e))


@router.get("/world/events/recent", tags=["World"])
async def get_recent_events(limit: int = Query(20, ge=1, le=100)):
    """Read recent events from the Redis stream."""
    from app.database import get_redis
    redis = await get_redis()
    raw = await redis.xrevrange(
        "world:events",
        count=limit,
    )
    events = []
    for entry_id, data in raw:
        events.append({
            "entry_id": entry_id,
            "event_id": data.get("event_id"),
            "event_type": data.get("event_type"),
            "description": data.get("description"),
            "severity": data.get("severity"),
            "timestamp": data.get("timestamp"),
        })
    return {"events": events}


# ─────────────────────────────────────────────
# ADMIN / SYSTEM
# ─────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health_check():
    """System health check — verifies all backend connections."""
    status: Dict[str, Any] = {"status": "ok", "services": {}}

    # Redis
    try:
        from app.database import get_redis
        redis = await get_redis()
        await redis.ping()
        status["services"]["redis"] = "ok"
    except Exception as e:
        status["services"]["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Qdrant
    try:
        from app.database import get_qdrant
        client = await get_qdrant()
        await client.get_collections()
        status["services"]["qdrant"] = "ok"
    except Exception as e:
        status["services"]["qdrant"] = f"error: {e}"
        status["status"] = "degraded"

    # Neo4j
    try:
        from app.database import get_neo4j_driver
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run("RETURN 1")
        status["services"]["neo4j"] = "ok"
    except Exception as e:
        status["services"]["neo4j"] = f"error: {e}"
        status["status"] = "degraded"

    return status


@router.get("/npc", tags=["NPC"])
async def list_npcs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all active NPCs."""
    npcs = await npc_brain.repo.list_active(db, limit=limit, offset=offset)
    return {
        "total": len(npcs),
        "npcs": [
            {
                "npc_id": n.npc_id,
                "name": n.name,
                "archetype": n.archetype,
                "faction": n.faction,
                "location": n.location,
                "dominant_emotion": n.emotion_state.dominant(),
                "mood_valence": round(n.emotion_state.valence(), 3),
                "active_goals": len([g for g in n.goals if g.status.value == "active"]),
            }
            for n in npcs
        ],
    }
