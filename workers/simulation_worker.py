"""
Background Simulation Worker

Runs continuously, ticking all active NPCs even when players are offline.

Each simulation tick:
  1. Emotion decay (toward baseline)
  2. Memory salience decay
  3. Goal re-evaluation + re-planning
  4. Rumor propagation from world events
  5. Routine simulation (NPC goes to sleep, works, etc.)
  6. State persistence

Designed to handle millions of NPCs via batched async processing.
"""
from __future__ import annotations

import asyncio
import json
import time
import signal
import sys
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_all_databases, get_redis
from app.brain.npc_brain import npc_brain
from app.world.events import event_consumer, rumor_propagator
from app.social.graph import social_graph
from app.models import EventType, CrimeRecord, CrimeType
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Graceful shutdown flag
_shutdown = False


def handle_shutdown(signum, frame):
    global _shutdown
    logger.info("shutdown_signal_received", signum=signum)
    _shutdown = True


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# ─────────────────────────────────────────────
# NPC BATCH TICK
# ─────────────────────────────────────────────

async def tick_npc_batch(
    db: AsyncSession,
    npc_ids: List[str],
    elapsed_ticks: int = 1,
) -> None:
    """
    Run simulation tick for a batch of NPCs concurrently.
    Bounded concurrency to avoid overwhelming the database.
    """
    semaphore = asyncio.Semaphore(20)

    async def tick_single(npc_id: str):
        async with semaphore:
            try:
                await npc_brain.simulation_tick(db, npc_id, elapsed_ticks)
            except Exception as e:
                logger.error("npc_tick_error", npc_id=npc_id, error=str(e))

    await asyncio.gather(*[tick_single(npc_id) for npc_id in npc_ids])


# ─────────────────────────────────────────────
# WORLD EVENT PROCESSING LOOP
# ─────────────────────────────────────────────

async def process_world_events(db: AsyncSession) -> int:
    """
    Read pending world events from Redis stream and dispatch
    reactions to all affected NPCs.
    Returns number of events processed.
    """
    await event_consumer.ensure_group()
    event_batch = await event_consumer.read_events(batch_size=20)

    if not event_batch:
        return 0

    processed = 0

    for entry_id, event in event_batch:
        try:
            logger.info(
                "processing_world_event",
                event_id=event.event_id,
                event_type=event.event_type.value,
                severity=event.severity,
            )

            # Find NPCs to notify
            # Priority: explicitly named NPCs, then faction members
            target_npc_ids = list(event.affected_npcs)

            # Add faction members
            for faction in event.affected_factions:
                faction_members = await social_graph.get_faction_members(faction, limit=200)
                target_npc_ids.extend(faction_members)

            # Deduplicate
            target_npc_ids = list(set(target_npc_ids))

            if not target_npc_ids:
                logger.info("no_npcs_to_notify", event_id=event.event_id)
                await event_consumer.ack(entry_id)
                processed += 1
                continue

            # React (direct witnesses)
            reactions = await asyncio.gather(*[
                npc_brain.react_to_world_event(db, npc_id, event, is_direct=True)
                for npc_id in target_npc_ids[:50]  # cap at 50 direct reactors
            ], return_exceptions=True)

            logger.info(
                "npc_reactions_processed",
                event_id=event.event_id,
                npc_count=len(target_npc_ids),
                reactions=sum(1 for r in reactions if not isinstance(r, Exception)),
            )

            # Rumor propagation (async background task)
            if event.propagates_as_rumor and target_npc_ids:
                asyncio.create_task(
                    propagate_rumor(db, event, target_npc_ids)
                )

            # Crime event → full rumor cascade through social graph
            if event.event_type == EventType.CRIME_COMMITTED:
                asyncio.create_task(
                    propagate_crime_rumors(db, event, target_npc_ids)
                )

            await event_consumer.ack(entry_id)
            processed += 1

        except Exception as e:
            logger.error("event_processing_error", entry_id=entry_id, error=str(e))

    return processed


# ─────────────────────────────────────────────
# RUMOR PROPAGATION
# ─────────────────────────────────────────────

async def propagate_rumor(db, original_event, source_npc_ids: List[str]) -> None:
    """
    Spread event as rumors through the social graph.
    Each hop degrades fidelity and severity.
    """
    await asyncio.sleep(5)  # Slight delay — rumors take time to spread

    for source_id in source_npc_ids[:10]:  # limit propagation sources
        try:
            # Get NPCs who trust the source
            trusting_npcs = await social_graph.get_npcs_who_trust(
                source_id, min_trust=0.5
            )

            if not trusting_npcs:
                continue

            # Get source NPC name for rumor attribution
            source_npc = await npc_brain.repo.get(db, source_id)
            if not source_npc:
                continue

            # Create rumor variant (hop=1)
            rumor = rumor_propagator.create_rumor_variant(
                original=original_event,
                hop=1,
                spreader_name=source_npc.name,
            )

            # Notify 2nd-degree NPCs with reduced severity
            for target in trusting_npcs[:5]:
                target_id = target["npc_id"]
                if target_id not in source_npc_ids:
                    await npc_brain.react_to_world_event(
                        db, target_id, rumor, is_direct=False
                    )

        except Exception as e:
            logger.error("rumor_propagation_error", source_id=source_id, error=str(e))


async def propagate_crime_rumors(db, event, witness_npc_ids: List[str]) -> None:
    """
    Full crime → rumor cascade through the social graph.
    Converts a CRIME_COMMITTED world event into a CrimeRecord and triggers
    multi-hop propagation via the RumorNetwork.
    """
    from app.rumor.rumor_network import rumor_network

    try:
        # Extract crime info from event metadata
        metadata = event.metadata or {}
        crime_type_str = metadata.get("crime_type", "theft")
        try:
            crime_type = CrimeType(crime_type_str)
        except ValueError:
            crime_type = CrimeType.THEFT

        crime = CrimeRecord(
            perpetrator_id=metadata.get("perpetrator_id", "unknown"),
            victim_id=metadata.get("victim_id"),
            victim_name=metadata.get("victim_name"),
            crime_type=crime_type,
            description=event.description,
            location=event.location,
            severity=event.severity,
            witnesses=list(witness_npc_ids),
            metadata=metadata,
        )

        rumor = await rumor_network.cascade(
            crime=crime,
            witness_npc_ids=witness_npc_ids,
            db=db,
            max_hops=3,
        )

        logger.info(
            "crime_rumor_cascade_complete",
            crime_id=crime.crime_id,
            crime_type=crime.crime_type.value,
            total_heard=len(rumor.heard_by),
            total_believed=len(rumor.believed_by),
        )

    except Exception as e:
        logger.error("crime_rumor_cascade_error", error=str(e))


# ─────────────────────────────────────────────
# ROUTINE SIMULATION
# ─────────────────────────────────────────────

DAILY_ROUTINES = {
    "merchant":  [(6, "wake"), (8, "open_stall"), (18, "close_stall"), (22, "sleep")],
    "guard":     [(0, "patrol"), (6, "change_shift"), (12, "rest"), (18, "patrol")],
    "innkeeper": [(5, "wake"), (7, "open_inn"), (23, "close_inn"), (0, "sleep")],
    "wizard":    [(10, "wake"), (11, "study"), (20, "experiment"), (2, "sleep")],
}


def get_current_routine_activity(archetype: str, hour: int) -> Optional[str]:
    """Return what activity an NPC archetype should be doing at a given hour."""
    routines = DAILY_ROUTINES.get(archetype.lower(), [])
    current = None
    for routine_hour, activity in sorted(routines):
        if hour >= routine_hour:
            current = activity
    return current


# ─────────────────────────────────────────────
# STATS TRACKING
# ─────────────────────────────────────────────

class WorkerStats:
    def __init__(self):
        self.tick_count = 0
        self.events_processed = 0
        self.errors = 0
        self.start_time = time.time()

    def report(self):
        uptime = time.time() - self.start_time
        logger.info(
            "worker_stats",
            tick_count=self.tick_count,
            events_processed=self.events_processed,
            errors=self.errors,
            uptime_seconds=round(uptime),
            ticks_per_minute=round(self.tick_count / (uptime / 60), 1),
        )


# ─────────────────────────────────────────────
# MAIN SIMULATION LOOP
# ─────────────────────────────────────────────

async def simulation_loop():
    """
    Main worker loop. Runs until shutdown signal received.

    Architecture:
      - Event processing: runs every tick
      - NPC ticks: batched by page (handle millions of NPCs)
      - Stats: reported every 60 ticks
    """
    global _shutdown

    await init_all_databases()
    stats = WorkerStats()

    logger.info(
        "simulation_worker_started",
        tick_interval=settings.sim_tick_interval_seconds,
        worker_concurrency=settings.worker_concurrency,
    )

    batch_size = settings.max_npcs_per_worker
    page = 0

    while not _shutdown:
        tick_start = time.time()

        async with AsyncSessionLocal() as db:
            try:
                # ── World Events ──
                events_done = await process_world_events(db)
                stats.events_processed += events_done

                # ── NPC Batch Tick ──
                npcs = await npc_brain.repo.list_active(
                    db,
                    limit=batch_size,
                    offset=page * batch_size,
                )

                if not npcs:
                    # Wrap around to first page
                    page = 0
                    logger.info("npc_tick_cycle_complete", total_ticks=stats.tick_count)
                else:
                    npc_ids = [n.npc_id for n in npcs]
                    await tick_npc_batch(db, npc_ids, elapsed_ticks=1)
                    page += 1
                    logger.debug(
                        "npc_batch_ticked",
                        page=page,
                        batch_size=len(npc_ids),
                    )

                await db.commit()
                stats.tick_count += 1

            except Exception as e:
                stats.errors += 1
                logger.error("simulation_loop_error", error=str(e))
                await db.rollback()

        # Stats report every 60 ticks
        if stats.tick_count % 60 == 0:
            stats.report()

        # Sleep until next tick
        elapsed = time.time() - tick_start
        sleep_time = max(0, settings.sim_tick_interval_seconds - elapsed)
        await asyncio.sleep(sleep_time)

    logger.info("simulation_worker_stopped")


if __name__ == "__main__":
    asyncio.run(simulation_loop())
