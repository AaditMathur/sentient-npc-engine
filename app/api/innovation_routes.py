"""
Innovation API Routes — New Features for Hackathon

Endpoints for:
- Multi-NPC conversations
- Emotional contagion
- Dynamic quests
- Causality chains
- Cultural legends
- Dreams
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.brain.npc_brain import npc_brain
import structlog

logger = structlog.get_logger()
router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# MULTI-NPC CONVERSATIONS
# ═══════════════════════════════════════════════════════════════

class StartConversationRequest(BaseModel):
    npc_ids: List[str]
    topic: Optional[str] = None
    max_turns: int = 6


@router.post("/conversation/start", tags=["Conversation"])
async def start_npc_conversation(
    request: StartConversationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start an autonomous conversation between NPCs."""
    from app.conversation.multi_npc import multi_npc_conversation
    
    # Load NPCs
    npcs = []
    for npc_id in request.npc_ids:
        npc = await npc_brain.repo.get(db, npc_id)
        if not npc:
            raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")
        npcs.append(npc)
    
    # Conduct conversation
    conversation = await multi_npc_conversation.conduct_conversation(
        npcs=npcs,
        topic=request.topic,
        max_turns=request.max_turns,
    )
    
    return {
        "participants": [n.name for n in npcs],
        "topic": request.topic,
        "turns": conversation,
        "total_turns": len(conversation),
    }


@router.get("/conversation/should-talk/{npc1_id}/{npc2_id}", tags=["Conversation"])
async def check_conversation_likelihood(
    npc1_id: str,
    npc2_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if two NPCs should initiate conversation."""
    from app.conversation.multi_npc import multi_npc_conversation
    from app.social.graph import social_graph
    
    npc1 = await npc_brain.repo.get(db, npc1_id)
    npc2 = await npc_brain.repo.get(db, npc2_id)
    
    if not npc1 or not npc2:
        raise HTTPException(status_code=404, detail="NPC not found")
    
    relationship = await social_graph.get_relationship(npc1_id, npc2_id)
    should_talk, reason = await multi_npc_conversation.should_initiate_conversation(
        npc1, npc2, relationship
    )
    
    return {
        "should_talk": should_talk,
        "reason": reason,
        "npc1": npc1.name,
        "npc2": npc2.name,
    }


# ═══════════════════════════════════════════════════════════════
# EMOTIONAL CONTAGION
# ═══════════════════════════════════════════════════════════════

@router.post("/emotion/contagion/panic", tags=["Emotion"])
async def simulate_panic(
    location: str,
    panic_source: str,
    intensity: float = 0.9,
    db: AsyncSession = Depends(get_db),
):
    """Simulate panic spreading through NPCs at a location."""
    from app.emotion.contagion import emotional_contagion
    
    # Get NPCs at location
    all_npcs = await npc_brain.repo.list_active(db, limit=100)
    location_npcs = [n for n in all_npcs if n.location == location]
    
    if not location_npcs:
        raise HTTPException(status_code=404, detail=f"No NPCs at {location}")
    
    # Simulate panic
    updated_emotions = emotional_contagion.simulate_crowd_panic(
        npcs=location_npcs,
        panic_source=panic_source,
        initial_intensity=intensity,
        epicenter_location=location,
    )
    
    # Save updated emotions
    for npc_id, new_emotion in updated_emotions.items():
        npc = next((n for n in location_npcs if n.npc_id == npc_id), None)
        if npc:
            npc.emotion_state = new_emotion
            await npc_brain.repo.save(db, npc)
    
    return {
        "location": location,
        "panic_source": panic_source,
        "total_npcs": len(location_npcs),
        "affected_npcs": len(updated_emotions),
        "penetration_rate": f"{len(updated_emotions)/len(location_npcs)*100:.1f}%",
    }


@router.get("/emotion/crowd-mood/{location}", tags=["Emotion"])
async def get_crowd_mood(
    location: str,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate emotional state of NPCs at a location."""
    from app.emotion.contagion import emotional_contagion
    
    all_npcs = await npc_brain.repo.list_active(db, limit=100)
    location_npcs = [n for n in all_npcs if n.location == location]
    
    if not location_npcs:
        return {"error": f"No NPCs at {location}"}
    
    mood = emotional_contagion.calculate_crowd_mood(location_npcs)
    
    return {
        "location": location,
        **mood,
    }


# ═══════════════════════════════════════════════════════════════
# DYNAMIC QUESTS
# ═══════════════════════════════════════════════════════════════

@router.get("/quests/available", tags=["Quests"])
async def get_available_quests(
    location: Optional[str] = None,
    quest_type: Optional[str] = None,
    limit: int = 20,
):
    """Get all available dynamically generated quests."""
    from app.quests.generator import quest_generator
    
    quests = quest_generator.get_available_quests(
        location=location,
        quest_type=quest_type,
    )
    
    return {
        "total": len(quests),
        "quests": [q.model_dump() for q in quests[:limit]],
    }


@router.get("/quests/{quest_id}", tags=["Quests"])
async def get_quest_details(quest_id: str):
    """Get detailed information about a specific quest."""
    from app.quests.generator import quest_generator
    
    quest = quest_generator.active_quests.get(quest_id)
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    return quest.model_dump()


# ═══════════════════════════════════════════════════════════════
# CAUSALITY CHAINS
# ═══════════════════════════════════════════════════════════════

@router.get("/causality/trace/{node_id}", tags=["Causality"])
async def trace_causality(node_id: str):
    """Trace a causal chain back to its root cause."""
    from app.causality.tracker import causality_tracker
    
    path = causality_tracker.trace_back_to_root(node_id)
    
    if not path:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return {
        "node_id": node_id,
        "chain_length": len(path),
        "root_cause": path[0].description if path else None,
        "path": [
            {
                "node_id": n.node_id,
                "description": n.description,
                "event_type": n.event_type.value,
                "severity": n.severity,
                "chain_depth": n.chain_depth,
            }
            for n in path
        ],
    }


@router.get("/causality/butterfly-effects", tags=["Causality"])
async def get_butterfly_effects(
    min_amplification: float = 5.0,
    limit: int = 10,
):
    """Get the most dramatic butterfly effect examples."""
    from app.causality.tracker import causality_tracker
    
    examples = causality_tracker.get_butterfly_effect_examples(
        min_amplification=min_amplification,
        limit=limit,
    )
    
    return {
        "total": len(examples),
        "examples": examples,
    }


@router.get("/causality/actor-impact/{actor_id}", tags=["Causality"])
async def get_actor_impact(actor_id: str):
    """Analyze an actor's causal impact on the world."""
    from app.causality.tracker import causality_tracker
    
    impact = causality_tracker.get_actor_causal_impact(actor_id)
    
    return impact


@router.post("/causality/predict", tags=["Causality"])
async def predict_consequences(
    event_type: str,
    actor_id: str,
    severity: float = 0.5,
):
    """Predict consequences of a hypothetical event."""
    from app.causality.tracker import causality_tracker
    
    predictions = causality_tracker.predict_consequences(
        hypothetical_event={
            "event_type": event_type,
            "actor_id": actor_id,
            "severity": severity,
        },
        depth=3,
    )
    
    return {
        "hypothetical_event": {
            "event_type": event_type,
            "actor_id": actor_id,
            "severity": severity,
        },
        "predictions": predictions,
    }


# ═══════════════════════════════════════════════════════════════
# CULTURAL LEGENDS
# ═══════════════════════════════════════════════════════════════

@router.get("/legends", tags=["Legends"])
async def get_legends(
    location: Optional[str] = None,
    faction: Optional[str] = None,
    min_spread: int = 5,
):
    """Get cultural narratives and legends."""
    from app.culture.legends import cultural_memory
    
    narratives = cultural_memory.get_cultural_narratives(
        location=location,
        faction=faction,
        min_spread=min_spread,
    )
    
    return {
        "total": len(narratives),
        "legends": narratives,
    }


@router.get("/legends/reputation/{protagonist_id}", tags=["Legends"])
async def get_protagonist_reputation(protagonist_id: str):
    """Get a character's reputation based on legends."""
    from app.culture.legends import cultural_memory
    
    reputation = cultural_memory.get_protagonist_reputation(protagonist_id)
    
    return reputation


@router.post("/legends/{legend_id}/tell", tags=["Legends"])
async def tell_legend(
    legend_id: str,
    teller_id: str,
    listener_id: str,
    embellish: bool = False,
):
    """Have an NPC tell a legend to another NPC."""
    from app.culture.legends import cultural_memory
    
    result = cultural_memory.tell_legend(
        legend_id=legend_id,
        teller_id=teller_id,
        listener_id=listener_id,
        embellish=embellish,
    )
    
    return result


# ═══════════════════════════════════════════════════════════════
# DREAMS
# ═══════════════════════════════════════════════════════════════

@router.post("/dreams/generate/{npc_id}", tags=["Dreams"])
async def generate_dream(
    npc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a dream for an NPC."""
    from app.dreams.engine import dream_engine
    from app.memory.engine import memory_engine
    
    npc = await npc_brain.repo.get(db, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    
    # Get recent memories
    from app.models import MemoryQuery
    mem_query = MemoryQuery(
        npc_id=npc_id,
        query_text="recent events",
        top_k=10,
    )
    memory_results = await memory_engine.retrieve(mem_query)
    memories = [m for m, _ in memory_results]
    
    # Generate dream
    dream = dream_engine.generate_dream(npc, memories)
    
    if not dream:
        return {"message": "NPC did not dream tonight"}
    
    # Apply dream effects
    npc = dream_engine.apply_dream_effects(npc, dream)
    await npc_brain.repo.save(db, npc)
    
    return dream.model_dump()


@router.get("/dreams/{npc_id}/history", tags=["Dreams"])
async def get_dream_history(
    npc_id: str,
    limit: int = 10,
):
    """Get an NPC's dream history (would need storage implementation)."""
    # This would require storing dreams in database
    return {
        "npc_id": npc_id,
        "message": "Dream history storage not yet implemented",
        "note": "Dreams are currently generated on-demand",
    }


# ═══════════════════════════════════════════════════════════════
# ANALYTICS & VISUALIZATION
# ═══════════════════════════════════════════════════════════════

@router.get("/analytics/world-state", tags=["Analytics"])
async def get_world_state_analytics(db: AsyncSession = Depends(get_db)):
    """Get comprehensive world state analytics."""
    from app.causality.tracker import causality_tracker
    from app.culture.legends import cultural_memory
    from app.quests.generator import quest_generator
    
    # Get all NPCs
    all_npcs = await npc_brain.repo.list_active(db, limit=200)
    
    # Aggregate emotions
    emotion_totals = {
        "joy": 0, "trust": 0, "fear": 0, "anger": 0,
        "sadness": 0, "surprise": 0, "disgust": 0, "anticipation": 0,
    }
    
    for npc in all_npcs:
        emotion_dict = npc.emotion_state.model_dump()
        for key in emotion_totals:
            emotion_totals[key] += emotion_dict[key]
    
    n = len(all_npcs)
    emotion_averages = {k: v / n for k, v in emotion_totals.items()} if n > 0 else {}
    
    return {
        "total_npcs": len(all_npcs),
        "average_emotions": emotion_averages,
        "dominant_world_emotion": max(emotion_averages, key=emotion_averages.get) if emotion_averages else "neutral",
        "total_causal_events": len(causality_tracker.nodes),
        "total_causal_chains": len(causality_tracker.chains),
        "total_legends": len(cultural_memory.legends),
        "active_quests": len([q for q in quest_generator.active_quests.values() if q.status == "available"]),
        "locations": list(set(n.location for n in all_npcs if n.location)),
    }
