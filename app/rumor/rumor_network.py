"""
Rumor Network Engine — Crime → Rumor → Multi-Hop Social Graph Cascade

The core feature: when a crime occurs, it generates a rumor that propagates
through the NPC social graph. Each hop degrades fidelity, and personality
traits modulate who spreads vs. suppresses rumors.

Flow:
  1. Crime committed → CrimeRecord created
  2. Witnesses get direct awareness (AwarenessLevel.DIRECT_WITNESS)
  3. Witnesses spread to trusted NPCs (hop 1 → RELIABLE_RUMOR)
  4. Those NPCs spread further (hop 2 → VAGUE_RUMOR)
  5. Final hop (hop 3 → UNCONFIRMED), then stops
  6. Each NPC who hears the rumor gets: emotion update, behavior modifier, memory
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.models import (
    CrimeRecord, CrimeType, RumorRecord, AwarenessLevel,
    NPCState, NPCBehaviorModifier,
)
from app.social.graph import social_graph
from app.memory.engine import memory_engine, create_world_event_memory
from app.emotion.engine import emotion_engine
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


# ─────────────────────────────────────────────
# CRIME → BEHAVIOR MODIFIER MAPPING
# ─────────────────────────────────────────────

CRIME_BEHAVIOR_MAP: Dict[CrimeType, Dict[str, Any]] = {
    CrimeType.MURDER: {
        "refuse_trade": True,
        "call_guards": True,
        "flee": True,
        "hostile_dialogue": True,
        "warn_others": True,
        "lock_doors": True,
    },
    CrimeType.ASSAULT: {
        "refuse_trade": True,
        "call_guards": True,
        "flee": False,
        "hostile_dialogue": True,
        "warn_others": True,
    },
    CrimeType.THEFT: {
        "refuse_trade": False,
        "increase_prices": True,
        "hostile_dialogue": False,
        "warn_others": True,
        "lock_doors": True,
    },
    CrimeType.ARSON: {
        "refuse_trade": True,
        "call_guards": True,
        "flee": True,
        "hostile_dialogue": True,
        "warn_others": True,
    },
    CrimeType.TRESPASSING: {
        "call_guards": True,
        "hostile_dialogue": False,
        "warn_others": False,
    },
    CrimeType.FRAUD: {
        "refuse_trade": True,
        "increase_prices": True,
        "hostile_dialogue": True,
        "warn_others": True,
    },
}

# Awareness level → which behaviors are active
# Higher awareness = more behaviors triggered
AWARENESS_BEHAVIOR_FILTER: Dict[AwarenessLevel, float] = {
    AwarenessLevel.DIRECT_WITNESS: 1.0,     # all behaviors active
    AwarenessLevel.RELIABLE_RUMOR: 0.8,     # most behaviors
    AwarenessLevel.VAGUE_RUMOR: 0.5,        # some behaviors
    AwarenessLevel.UNCONFIRMED: 0.2,        # minimal reaction
}

# Crime type → emotion stimulus key for the emotion engine
CRIME_EMOTION_STIMULI: Dict[CrimeType, str] = {
    CrimeType.MURDER: "crime_murder",
    CrimeType.ASSAULT: "crime_assault",
    CrimeType.THEFT: "crime_theft",
    CrimeType.ARSON: "crime_arson",
    CrimeType.TRESPASSING: "crime_trespassing",
    CrimeType.FRAUD: "crime_fraud",
}

# Hop → AwarenessLevel
HOP_TO_AWARENESS: Dict[int, AwarenessLevel] = {
    0: AwarenessLevel.DIRECT_WITNESS,
    1: AwarenessLevel.RELIABLE_RUMOR,
    2: AwarenessLevel.VAGUE_RUMOR,
    3: AwarenessLevel.UNCONFIRMED,
}


class RumorNetwork:
    """
    Orchestrates crime → rumor → multi-hop propagation through the social graph.

    Personality modulation:
    - Gossipy NPCs (honesty < 0.4): 2x more likely to spread rumors
    - Loyal NPCs (loyalty > 0.7) to perpetrator: suppress rumors about them
    - Empathetic NPCs: stronger emotional reaction
    - Brave NPCs: more likely to confront rather than flee
    """

    MAX_HOPS = 3
    FIDELITY_BY_HOP = {0: 1.0, 1: 0.7, 2: 0.5, 3: 0.3}
    SEVERITY_DAMPEN_PER_HOP = 0.2
    HOP_DELAY_SECONDS = [0, 3, 8, 15]  # delay before each hop spreads

    # ── Crime → Rumor Conversion ────────────

    def create_crime_rumor(self, crime: CrimeRecord) -> RumorRecord:
        """Convert a crime event into the initial rumor record."""
        description = self._build_crime_description(crime)
        return RumorRecord(
            source_crime_id=crime.crime_id,
            crime_type=crime.crime_type,
            perpetrator_id=crime.perpetrator_id,
            original_description=description,
            current_description=description,
            current_hop=0,
            fidelity=1.0,
            severity=crime.severity,
            heard_by=list(crime.witnesses),
            believed_by=list(crime.witnesses),
        )

    # ── Single-Hop Propagation ──────────────

    async def propagate(
        self,
        rumor: RumorRecord,
        source_npc_id: str,
        db,
        source_npc: Optional[NPCState] = None,
    ) -> List[str]:
        """
        Spread rumor from one NPC to their trusted connections.
        Returns list of NPC IDs who received the rumor.
        """
        from app.brain.npc_brain import npc_brain

        # Load source NPC if not provided
        if not source_npc:
            source_npc = await npc_brain.repo.get(db, source_npc_id)
            if not source_npc:
                return []

        # Personality-modulated spread chance
        spread_chance = self._compute_spread_chance(source_npc, rumor)
        if spread_chance < 0.1:
            logger.debug(
                "rumor_suppressed",
                npc_id=source_npc_id,
                npc_name=source_npc.name,
                reason="personality_suppression",
            )
            return []

        # Get trusted connections
        min_trust = max(0.3, 0.7 - rumor.fidelity * 0.4)
        trusting_npcs = await social_graph.get_npcs_who_trust(
            source_npc_id, min_trust=min_trust
        )

        # Filter out NPCs who already heard this rumor
        already_heard = set(rumor.heard_by)
        new_targets = [
            t for t in trusting_npcs
            if t["npc_id"] not in already_heard
        ]

        if not new_targets:
            return []

        next_hop = rumor.current_hop + 1
        awareness = HOP_TO_AWARENESS.get(next_hop, AwarenessLevel.UNCONFIRMED)
        fidelity = self.FIDELITY_BY_HOP.get(min(next_hop, 3), 0.3)
        new_severity = max(0.1, rumor.severity - self.SEVERITY_DAMPEN_PER_HOP)
        distorted_desc = self._distort_description(
            rumor.original_description, fidelity, source_npc.name
        )

        notified_ids = []
        for target in new_targets[:8]:  # cap per-hop spread
            target_id = target["npc_id"]
            try:
                target_npc = await npc_brain.repo.get(db, target_id)
                if not target_npc:
                    continue

                # Check if target would believe it (personality check)
                believes = self._would_believe(target_npc, fidelity, rumor.perpetrator_id)

                # Apply crime awareness to the target NPC
                await self.apply_crime_awareness(
                    db, target_npc, rumor, awareness, new_severity,
                    distorted_desc, believes,
                )

                # Track spread
                rumor.heard_by.append(target_id)
                if believes:
                    rumor.believed_by.append(target_id)
                rumor.spread_chain.append({
                    "spreader": source_npc_id,
                    "spreader_name": source_npc.name,
                    "receiver": target_id,
                    "receiver_name": target_npc.name,
                    "hop": next_hop,
                    "believed": believes,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                notified_ids.append(target_id)

                logger.info(
                    "rumor_spread",
                    from_npc=source_npc.name,
                    to_npc=target_npc.name,
                    crime_type=rumor.crime_type.value,
                    hop=next_hop,
                    believed=believes,
                )

            except Exception as e:
                logger.error(
                    "rumor_spread_error",
                    target_id=target_id,
                    error=str(e),
                )

        return notified_ids

    # ── Full Multi-Hop Cascade ──────────────

    async def cascade(
        self,
        crime: CrimeRecord,
        witness_npc_ids: List[str],
        db,
        max_hops: int = 3,
    ) -> RumorRecord:
        """
        Orchestrate the full multi-hop rumor cascade from a crime.

        1. Create rumor from crime
        2. Witnesses are hop 0 (direct awareness)
        3. Each hop: spread from current layer to next
        4. Stop at max_hops or when no new NPCs reached
        """
        from app.brain.npc_brain import npc_brain

        rumor = self.create_crime_rumor(crime)

        # Hop 0: Direct witnesses get awareness
        for witness_id in witness_npc_ids:
            try:
                witness_npc = await npc_brain.repo.get(db, witness_id)
                if witness_npc:
                    await self.apply_crime_awareness(
                        db, witness_npc, rumor,
                        AwarenessLevel.DIRECT_WITNESS,
                        crime.severity,
                        rumor.original_description,
                        believes=True,
                    )
            except Exception as e:
                logger.error("witness_awareness_error", npc_id=witness_id, error=str(e))

        # Multi-hop cascade
        current_spreaders = list(witness_npc_ids)
        for hop in range(1, min(max_hops + 1, self.MAX_HOPS + 1)):
            if not current_spreaders:
                break

            # Delay between hops — rumors take time
            delay = self.HOP_DELAY_SECONDS[min(hop, len(self.HOP_DELAY_SECONDS) - 1)]
            if delay > 0:
                await asyncio.sleep(delay)

            rumor.current_hop = hop
            rumor.fidelity = self.FIDELITY_BY_HOP.get(min(hop, 3), 0.3)
            rumor.severity = max(0.1, crime.severity - hop * self.SEVERITY_DAMPEN_PER_HOP)

            next_layer = []
            for spreader_id in current_spreaders[:10]:  # cap sources per hop
                newly_reached = await self.propagate(rumor, spreader_id, db)
                next_layer.extend(newly_reached)

            current_spreaders = list(set(next_layer))

            logger.info(
                "rumor_cascade_hop",
                hop=hop,
                spreaders=len(current_spreaders),
                total_heard=len(rumor.heard_by),
                crime_type=crime.crime_type.value,
            )

        rumor.is_active = False
        logger.info(
            "rumor_cascade_complete",
            crime_id=crime.crime_id,
            total_heard=len(rumor.heard_by),
            total_believed=len(rumor.believed_by),
            total_hops=rumor.current_hop,
        )

        return rumor

    # ── Apply Crime Awareness to NPC ────────

    async def apply_crime_awareness(
        self,
        db,
        npc: NPCState,
        rumor: RumorRecord,
        awareness_level: AwarenessLevel,
        severity: float,
        description: str,
        believes: bool,
    ) -> None:
        """
        Apply crime awareness to an NPC:
        1. Store in known_crimes
        2. Apply emotion stimulus
        3. Create behavior modifier
        4. Store memory
        5. Update relationship with perpetrator
        6. Persist
        """
        from app.brain.npc_brain import npc_brain

        # 1. Track crime awareness
        npc.known_crimes[rumor.source_crime_id] = {
            "awareness_level": awareness_level.value,
            "crime_type": rumor.crime_type.value,
            "perpetrator_id": rumor.perpetrator_id,
            "severity": severity,
            "description": description,
            "believed": believes,
            "learned_at": datetime.now(timezone.utc).isoformat(),
        }

        # 2. Apply emotion stimulus
        stimulus_key = CRIME_EMOTION_STIMULI.get(rumor.crime_type, "crime_theft")
        is_direct = awareness_level == AwarenessLevel.DIRECT_WITNESS
        npc.emotion_state = emotion_engine.process_event(
            emotion=npc.emotion_state,
            event_type=stimulus_key,
            personality=npc.personality,
            severity=severity,
            is_direct=is_direct,
        )

        # 3. Create behavior modifier (only if believed)
        if believes:
            modifier = self._create_behavior_modifier(
                rumor, awareness_level, npc.personality
            )
            npc.behavior_modifiers.append(modifier.model_dump())

        # 4. Store memory
        memory_desc = self._build_memory_description(
            rumor, awareness_level, description
        )
        memory = create_world_event_memory(
            npc_id=npc.npc_id,
            event_description=memory_desc,
            emotion=npc.emotion_state,
            severity=severity,
            is_direct=is_direct,
        )
        memory.tags.extend(["crime", rumor.crime_type.value, "rumor"])
        memory_id = await memory_engine.store(memory)
        npc.recent_memory_ids.append(memory_id)

        # 5. Update world knowledge
        if "recent_events" not in npc.world_knowledge:
            npc.world_knowledge["recent_events"] = []
        npc.world_knowledge["recent_events"].insert(0, memory_desc)
        npc.world_knowledge["recent_events"] = npc.world_knowledge["recent_events"][:10]

        # Track known criminals
        if "known_criminals" not in npc.world_knowledge:
            npc.world_knowledge["known_criminals"] = {}
        npc.world_knowledge["known_criminals"][rumor.perpetrator_id] = {
            "crime_type": rumor.crime_type.value,
            "severity": severity,
            "awareness": awareness_level.value,
            "believed": believes,
        }

        # 6. Update relationship with perpetrator (trust ↓, fear ↑)
        if believes:
            rel_delta = self._compute_relationship_delta(rumor.crime_type, severity)
            await social_graph.update_relationship_delta(
                npc.npc_id, rumor.perpetrator_id, rel_delta
            )

        # 7. Persist
        await npc_brain.repo.save(db, npc)

    # ── Query Crime Awareness ───────────────

    def get_npc_crime_awareness(self, npc: NPCState) -> List[Dict[str, Any]]:
        """Return structured crime awareness info for an NPC."""
        awareness = []
        for crime_id, info in npc.known_crimes.items():
            awareness.append({
                "crime_id": crime_id,
                **info,
            })
        return awareness

    def get_crime_context_for_dialogue(
        self,
        npc: NPCState,
        player_id: str,
    ) -> str:
        """
        Build dialogue context about crimes the NPC knows the player committed.
        Injected into the LLM prompt during interact().
        """
        player_crimes = [
            info for info in npc.known_crimes.values()
            if info.get("perpetrator_id") == player_id and info.get("believed")
        ]

        if not player_crimes:
            return ""

        lines = ["\n[CRIME AWARENESS — You know about the following crimes by this person:]"]
        for crime in player_crimes:
            level = crime.get("awareness_level", "unknown")
            crime_type = crime.get("crime_type", "unknown")
            desc = crime.get("description", "")
            if level == "direct_witness":
                lines.append(f"- You WITNESSED them commit {crime_type}: {desc}")
            elif level == "reliable_rumor":
                lines.append(f"- You heard a credible report that they committed {crime_type}: {desc}")
            elif level == "vague_rumor":
                lines.append(f"- There are rumors they may have been involved in {crime_type}")
            else:
                lines.append(f"- Unconfirmed whispers about them and some {crime_type}")

        # Active behavior modifiers
        active_mods = [
            m for m in npc.behavior_modifiers
            if m.get("perpetrator_id") == player_id
        ]
        if active_mods:
            mod = active_mods[0]
            if mod.get("refuse_trade"):
                lines.append("[You should REFUSE to trade with this person.]")
            if mod.get("hostile_dialogue"):
                lines.append("[Speak with hostility, suspicion, and contempt.]")
            if mod.get("call_guards"):
                lines.append("[Consider calling the guards or threatening to do so.]")
            if mod.get("flee"):
                lines.append("[You feel unsafe. Consider ending the conversation and fleeing.]")

        return "\n".join(lines)

    # ── Internal Helpers ────────────────────

    def _build_crime_description(self, crime: CrimeRecord) -> str:
        """Build a natural language crime description."""
        victim = f" against {crime.victim_name or crime.victim_id}" if crime.victim_id else ""
        location = f" at {crime.location}" if crime.location else ""
        return (
            f"A {crime.crime_type.value} was committed{victim}{location}. "
            f"{crime.description}"
        ).strip()

    def _distort_description(
        self, original: str, fidelity: float, spreader_name: str
    ) -> str:
        """Distort rumor description based on fidelity level."""
        if fidelity >= 0.7:
            return f"{spreader_name} says: '{original}'"
        elif fidelity >= 0.5:
            return f"Word is spreading that {original.lower()} (heard from {spreader_name})"
        else:
            return (
                f"There are unconfirmed rumors about a crime near "
                f"{spreader_name}'s area. Details are unclear."
            )

    def _compute_spread_chance(self, npc: NPCState, rumor: RumorRecord) -> float:
        """
        Personality-modulated spread chance.
        Gossipy (low honesty) NPCs spread more. Loyal NPCs may suppress.
        """
        base_chance = 0.6

        # Low honesty → gossip more
        gossip_bonus = (1.0 - npc.personality.honesty) * 0.4
        # High curiosity → spread interesting info
        curiosity_bonus = npc.personality.curiosity * 0.2
        # High loyalty to perpetrator → suppress
        loyalty_penalty = 0.0
        if rumor.perpetrator_id in npc.relationships:
            rel = npc.relationships[rumor.perpetrator_id]
            if rel.friendship > 0.6:
                loyalty_penalty = npc.personality.loyalty * 0.5

        chance = base_chance + gossip_bonus + curiosity_bonus - loyalty_penalty
        return max(0.0, min(1.0, chance))

    def _would_believe(
        self, npc: NPCState, fidelity: float, perpetrator_id: str
    ) -> bool:
        """
        Does this NPC believe the rumor?
        Based on fidelity, NPC personality, and relationship with perpetrator.
        """
        # Base belief from fidelity
        belief = fidelity

        # Curious NPCs are more open to believing
        belief += npc.personality.curiosity * 0.1

        # If NPC trusts the perpetrator, less likely to believe
        if perpetrator_id in npc.relationships:
            rel = npc.relationships[perpetrator_id]
            trust_penalty = rel.trust * 0.3
            belief -= trust_penalty

        # Suspicious NPCs (low trust baseline) believe more easily
        if npc.personality.honesty < 0.4:
            belief += 0.1

        return belief > 0.4

    def _create_behavior_modifier(
        self,
        rumor: RumorRecord,
        awareness: AwarenessLevel,
        personality: Any,
    ) -> NPCBehaviorModifier:
        """Create behavior modifier based on crime type and awareness level."""
        base_behaviors = CRIME_BEHAVIOR_MAP.get(rumor.crime_type, {})
        awareness_filter = AWARENESS_BEHAVIOR_FILTER.get(awareness, 0.2)

        # Filter behaviors based on awareness (less aware = fewer reactions)
        filtered = {}
        priority_order = [
            "call_guards", "flee", "hostile_dialogue", "refuse_trade",
            "warn_others", "increase_prices", "lock_doors",
        ]

        active_count = max(1, int(len(priority_order) * awareness_filter))
        for i, behavior in enumerate(priority_order):
            if behavior in base_behaviors and base_behaviors[behavior]:
                filtered[behavior] = i < active_count

        # Brave NPCs don't flee, they confront
        if personality.bravery > 0.7:
            filtered["flee"] = False
            filtered["hostile_dialogue"] = True

        return NPCBehaviorModifier(
            crime_id=rumor.source_crime_id,
            crime_type=rumor.crime_type,
            perpetrator_id=rumor.perpetrator_id,
            awareness_level=awareness,
            **{k: v for k, v in filtered.items() if isinstance(v, bool)},
        )

    def _compute_relationship_delta(
        self, crime_type: CrimeType, severity: float
    ) -> Dict[str, float]:
        """Compute relationship changes based on crime type."""
        deltas = {
            CrimeType.MURDER:       {"trust": -0.6, "fear": +0.5, "friendship": -0.5, "respect": -0.4},
            CrimeType.ASSAULT:      {"trust": -0.4, "fear": +0.4, "friendship": -0.3, "respect": -0.2},
            CrimeType.THEFT:        {"trust": -0.5, "fear": +0.1, "friendship": -0.2},
            CrimeType.ARSON:        {"trust": -0.5, "fear": +0.4, "friendship": -0.4, "respect": -0.3},
            CrimeType.TRESPASSING:  {"trust": -0.2, "friendship": -0.1},
            CrimeType.FRAUD:        {"trust": -0.5, "friendship": -0.3, "respect": -0.2},
        }
        base = deltas.get(crime_type, {"trust": -0.3})
        return {k: v * severity for k, v in base.items()}

    def _build_memory_description(
        self,
        rumor: RumorRecord,
        awareness: AwarenessLevel,
        description: str,
    ) -> str:
        """Build memory description based on how the NPC learned about the crime."""
        if awareness == AwarenessLevel.DIRECT_WITNESS:
            return f"I witnessed a {rumor.crime_type.value}: {description}"
        elif awareness == AwarenessLevel.RELIABLE_RUMOR:
            return f"I heard from a trusted source about a {rumor.crime_type.value}: {description}"
        elif awareness == AwarenessLevel.VAGUE_RUMOR:
            return f"There are rumors of a {rumor.crime_type.value}. {description}"
        else:
            return f"Unconfirmed whispers of a possible {rumor.crime_type.value} in the area."


# Singleton
rumor_network = RumorNetwork()
