"""
Celery Tasks — Async distributed NPC processing.
"""
from __future__ import annotations

import asyncio
from typing import List, Dict, Any

from workers.celery_app import celery_app
from app.config import get_settings

settings = get_settings()


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    queue="world_events",
)
def process_world_event_fanout(
    self,
    event_dict: Dict[str, Any],
    target_npc_ids: List[str],
):
    """
    Fan out a world event to a large batch of NPCs.
    Used when an event affects 100s–1000s of NPCs.
    """
    from app.models import WorldEvent, EventType
    from app.database import AsyncSessionLocal
    from app.brain.npc_brain import npc_brain

    event = WorldEvent(**event_dict)

    async def _fanout():
        async with AsyncSessionLocal() as db:
            results = []
            for i in range(0, len(target_npc_ids), 50):
                batch = target_npc_ids[i:i+50]
                batch_results = await asyncio.gather(*[
                    npc_brain.react_to_world_event(db, npc_id, event)
                    for npc_id in batch
                ], return_exceptions=True)
                results.extend(batch_results)
                await db.commit()
            return len([r for r in results if not isinstance(r, Exception)])

    try:
        successful = run_async(_fanout())
        return {"processed": successful, "total": len(target_npc_ids)}
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    queue="memory",
)
def consolidate_memories(self, npc_id: str):
    """
    Consolidate and prune NPC memories.
    Runs periodically to keep memory store lean.
    """
    from app.memory.engine import memory_engine

    async def _consolidate():
        await memory_engine.decay_memories(
            npc_id=npc_id,
            decay_rate=0.02,  # stronger decay during consolidation
        )
        count = await memory_engine.get_memory_count(npc_id)
        return {"npc_id": npc_id, "remaining_memories": count}

    try:
        return run_async(_consolidate())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=1,
    queue="simulation",
)
def simulate_npc_batch(self, npc_ids: List[str], elapsed_ticks: int = 1):
    """Simulate a batch of NPCs (called from the simulation scheduler)."""
    from app.database import AsyncSessionLocal
    from workers.simulation_worker import tick_npc_batch

    async def _sim():
        async with AsyncSessionLocal() as db:
            await tick_npc_batch(db, npc_ids, elapsed_ticks)
            await db.commit()

    try:
        return run_async(_sim())
    except Exception as exc:
        raise self.retry(exc=exc)
