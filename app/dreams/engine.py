"""
Dream & Subconscious Engine — NPCs Dream and Process Memories

NPCs have dreams influenced by:
- Recent memories (especially emotional ones)
- Current goals and desires
- Fears and anxieties
- Personality traits

Dreams can:
- Be prophetic (hint at future events)
- Process trauma (reduce negative emotions)
- Inspire new goals
- Influence next-day behavior
- Create interesting narrative moments
"""
from __future__ import annotations

import random
from typing import List, Dict, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models import NPCState, EmotionVector, Memory, GoalStatus
import structlog

logger = structlog.get_logger()


class DreamType(str):
    NIGHTMARE = "nightmare"
    PROPHETIC = "prophetic"
    WISH_FULFILLMENT = "wish_fulfillment"
    MEMORY_PROCESSING = "memory_processing"
    ANXIETY = "anxiety"
    INSPIRATION = "inspiration"
    SURREAL = "surreal"


class Dream(BaseModel):
    """A dream experienced by an NPC."""
    dream_id: str = Field(default_factory=lambda: str(__import__("uuid").uuid4()))
    npc_id: str
    npc_name: str
    
    dream_type: str  # DreamType
    content: str
    symbolism: List[str] = []
    
    # Influences
    triggered_by_memories: List[str] = []  # Memory IDs
    triggered_by_emotions: Dict[str, float] = {}
    triggered_by_goals: List[str] = []  # Goal IDs
    
    # Effects
    emotion_impact: Dict[str, float] = {}  # Changes to emotion state
    behavior_impact: Optional[str] = None  # How it affects next day
    inspired_goal: Optional[str] = None  # New goal created
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vividness: float = 0.5  # How memorable (0-1)
    interpretation: Optional[str] = None


class DreamEngine:
    """
    Generates dreams for NPCs during rest/sleep periods.
    
    Dreams are influenced by:
    - Recent emotional memories
    - Unfulfilled goals
    - Dominant emotions
    - Personality traits
    """

    def __init__(self):
        self.dream_symbols = self._initialize_symbols()

    def _initialize_symbols(self) -> Dict[str, List[str]]:
        """Dream symbolism library."""
        return {
            "fear": ["darkness", "falling", "being chased", "monsters", "drowning"],
            "anger": ["fire", "storms", "battles", "destruction", "blood"],
            "sadness": ["rain", "empty rooms", "lost loved ones", "gray skies", "wilting flowers"],
            "joy": ["sunlight", "flying", "dancing", "feasts", "laughter"],
            "anxiety": ["being late", "losing teeth", "being naked", "mazes", "endless stairs"],
            "desire": ["treasure", "forbidden fruit", "locked doors", "distant lights", "mirrors"],
            "guilt": ["shadows following", "stains that won't wash", "broken objects", "accusing eyes"],
        }

    def generate_dream(
        self,
        npc: NPCState,
        recent_memories: List[Memory],
        hours_since_last_dream: int = 24,
    ) -> Optional[Dream]:
        """
        Generate a dream for an NPC.
        
        Args:
            npc: The NPC who is dreaming
            recent_memories: Recent memories to draw from
            hours_since_last_dream: Time since last dream (affects intensity)
        
        Returns:
            A Dream object, or None if no dream occurs
        """
        # Not everyone dreams every night
        dream_probability = 0.6 + (hours_since_last_dream / 48) * 0.3
        if random.random() > dream_probability:
            return None
        
        # Determine dream type based on NPC state
        dream_type = self._determine_dream_type(npc, recent_memories)
        
        # Generate dream content
        if dream_type == DreamType.NIGHTMARE:
            return self._generate_nightmare(npc, recent_memories)
        elif dream_type == DreamType.PROPHETIC:
            return self._generate_prophetic_dream(npc)
        elif dream_type == DreamType.WISH_FULFILLMENT:
            return self._generate_wish_fulfillment(npc)
        elif dream_type == DreamType.MEMORY_PROCESSING:
            return self._generate_memory_processing(npc, recent_memories)
        elif dream_type == DreamType.ANXIETY:
            return self._generate_anxiety_dream(npc)
        elif dream_type == DreamType.INSPIRATION:
            return self._generate_inspiration_dream(npc)
        else:
            return self._generate_surreal_dream(npc, recent_memories)

    def _determine_dream_type(
        self,
        npc: NPCState,
        recent_memories: List[Memory],
    ) -> str:
        """Determine what type of dream the NPC will have."""
        emotion = npc.emotion_state
        
        # High fear -> nightmares
        if emotion.fear > 0.7:
            return DreamType.NIGHTMARE
        
        # High anxiety/stress -> anxiety dreams
        if emotion.fear > 0.5 and emotion.anticipation > 0.6:
            return DreamType.ANXIETY
        
        # Unfulfilled goals + high desire -> wish fulfillment
        active_goals = [g for g in npc.goals if g.status == GoalStatus.ACTIVE]
        if active_goals and emotion.anticipation > 0.6:
            if random.random() < 0.3:
                return DreamType.WISH_FULFILLMENT
        
        # High curiosity + personality -> prophetic
        if npc.personality.curiosity > 0.7 and random.random() < 0.2:
            return DreamType.PROPHETIC
        
        # Traumatic recent memories -> memory processing
        traumatic_memories = [
            m for m in recent_memories
            if m.emotional_intensity > 0.7 and m.importance > 0.6
        ]
        if traumatic_memories:
            return DreamType.MEMORY_PROCESSING
        
        # Creative/curious NPCs -> inspiration
        if npc.personality.curiosity > 0.6 and random.random() < 0.25:
            return DreamType.INSPIRATION
        
        # Default: surreal
        return DreamType.SURREAL

    def _generate_nightmare(
        self,
        npc: NPCState,
        recent_memories: List[Memory],
    ) -> Dream:
        """Generate a nightmare based on fears."""
        # Find fear-inducing memories
        fear_memories = [
            m for m in recent_memories
            if m.emotion_at_time.fear > 0.6
        ]
        
        # Build nightmare content
        symbols = random.sample(self.dream_symbols["fear"], k=2)
        
        if fear_memories:
            memory = fear_memories[0]
            content = (
                f"{npc.name} dreams of {symbols[0]}. "
                f"The nightmare echoes their memory of {memory.event[:50]}... "
                f"but twisted and terrifying. {symbols[1].capitalize()} surrounds them. "
                f"They wake in a cold sweat."
            )
            triggered_memories = [memory.memory_id]
        else:
            content = (
                f"{npc.name} dreams of {symbols[0]} and {symbols[1]}. "
                f"An overwhelming sense of dread fills the dream. "
                f"They cannot escape."
            )
            triggered_memories = []
        
        # Nightmares increase fear but can reduce it slightly (catharsis)
        emotion_impact = {
            "fear": -0.1,  # Slight reduction (processing)
            "sadness": 0.05,
        }
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.NIGHTMARE,
            content=content,
            symbolism=symbols,
            triggered_by_memories=triggered_memories,
            triggered_by_emotions={"fear": npc.emotion_state.fear},
            emotion_impact=emotion_impact,
            behavior_impact="cautious and jumpy in the morning",
            vividness=0.8,
            interpretation="Processing deep fears",
        )
        
        logger.info("nightmare_generated", npc=npc.name, symbols=symbols)
        return dream

    def _generate_prophetic_dream(self, npc: NPCState) -> Dream:
        """Generate a prophetic dream that hints at future events."""
        prophecies = [
            "a great shadow falling over the land",
            "a stranger arriving with news of war",
            "a treasure hidden beneath ancient stones",
            "betrayal by someone close",
            "a choice between two paths, one light and one dark",
            "fire consuming the marketplace",
            "a reunion with someone long lost",
        ]
        
        prophecy = random.choice(prophecies)
        symbols = ["visions", "omens", "whispers"]
        
        content = (
            f"{npc.name} dreams of {prophecy}. "
            f"The vision feels unnaturally clear, as if showing what is to come. "
            f"Strange symbols and omens fill the dream."
        )
        
        # Prophetic dreams increase anticipation and curiosity
        emotion_impact = {
            "anticipation": 0.15,
            "surprise": 0.1,
        }
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.PROPHETIC,
            content=content,
            symbolism=symbols,
            triggered_by_emotions={"curiosity": npc.personality.curiosity},
            emotion_impact=emotion_impact,
            behavior_impact="watchful and alert for signs",
            vividness=0.9,
            interpretation="A glimpse of possible futures",
        )
        
        return dream

    def _generate_wish_fulfillment(self, npc: NPCState) -> Dream:
        """Generate a dream where NPC's goals are fulfilled."""
        active_goals = [g for g in npc.goals if g.status == GoalStatus.ACTIVE]
        
        if active_goals:
            goal = active_goals[0]
            content = (
                f"{npc.name} dreams of achieving their goal: {goal.name}. "
                f"In the dream, everything goes perfectly. "
                f"They feel a deep sense of satisfaction and accomplishment."
            )
            triggered_goals = [goal.goal_id]
        else:
            content = (
                f"{npc.name} dreams of success and recognition. "
                f"They are celebrated and admired by all."
            )
            triggered_goals = []
        
        # Wish fulfillment increases joy and motivation
        emotion_impact = {
            "joy": 0.15,
            "anticipation": 0.1,
        }
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.WISH_FULFILLMENT,
            content=content,
            symbolism=["success", "achievement", "glory"],
            triggered_by_goals=triggered_goals,
            emotion_impact=emotion_impact,
            behavior_impact="motivated and optimistic",
            vividness=0.7,
            interpretation="Desire for achievement",
        )
        
        return dream

    def _generate_memory_processing(
        self,
        npc: NPCState,
        recent_memories: List[Memory],
    ) -> Dream:
        """Generate a dream that processes traumatic memories."""
        # Find most emotional recent memory
        emotional_memories = sorted(
            recent_memories,
            key=lambda m: m.emotional_intensity,
            reverse=True,
        )
        
        if not emotional_memories:
            return self._generate_surreal_dream(npc, recent_memories)
        
        memory = emotional_memories[0]
        
        content = (
            f"{npc.name} dreams of {memory.event[:60]}... "
            f"but in the dream, things unfold differently. "
            f"They process the emotions, finding new perspectives. "
            f"The dream helps them come to terms with what happened."
        )
        
        # Memory processing reduces negative emotions
        emotion_impact = {
            "sadness": -0.15,
            "anger": -0.1,
            "fear": -0.1,
        }
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.MEMORY_PROCESSING,
            content=content,
            symbolism=["healing", "acceptance", "closure"],
            triggered_by_memories=[memory.memory_id],
            emotion_impact=emotion_impact,
            behavior_impact="more at peace with recent events",
            vividness=0.75,
            interpretation="Emotional healing and integration",
        )
        
        return dream

    def _generate_anxiety_dream(self, npc: NPCState) -> Dream:
        """Generate an anxiety dream about failure or inadequacy."""
        anxiety_scenarios = [
            "being unprepared for an important task",
            "losing something precious and being unable to find it",
            "trying to run but moving in slow motion",
            "speaking but no sound coming out",
            "being lost in a familiar place that has become strange",
        ]
        
        scenario = random.choice(anxiety_scenarios)
        symbols = random.sample(self.dream_symbols["anxiety"], k=2)
        
        content = (
            f"{npc.name} dreams of {scenario}. "
            f"The dream is filled with {symbols[0]} and {symbols[1]}. "
            f"A pervasive sense of inadequacy and worry fills the dream."
        )
        
        # Anxiety dreams can slightly reduce anticipation (release)
        emotion_impact = {
            "anticipation": -0.05,
            "fear": -0.05,
        }
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.ANXIETY,
            content=content,
            symbolism=symbols,
            triggered_by_emotions={
                "fear": npc.emotion_state.fear,
                "anticipation": npc.emotion_state.anticipation,
            },
            emotion_impact=emotion_impact,
            behavior_impact="slightly anxious but relieved it was just a dream",
            vividness=0.6,
            interpretation="Processing stress and worries",
        )
        
        return dream

    def _generate_inspiration_dream(self, npc: NPCState) -> Dream:
        """Generate an inspirational dream that creates new goals."""
        inspirations = [
            "a brilliant solution to a long-standing problem",
            "a new path forward that was previously unseen",
            "a creative breakthrough",
            "understanding a mystery that has puzzled them",
            "a vision of their true purpose",
        ]
        
        inspiration = random.choice(inspirations)
        
        content = (
            f"{npc.name} dreams of {inspiration}. "
            f"The dream fills them with clarity and purpose. "
            f"They wake with new ideas and determination."
        )
        
        # Inspiration increases joy and anticipation
        emotion_impact = {
            "joy": 0.1,
            "anticipation": 0.15,
        }
        
        # Might inspire a new goal
        inspired_goal = "seek_knowledge" if npc.personality.curiosity > 0.6 else None
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.INSPIRATION,
            content=content,
            symbolism=["enlightenment", "clarity", "purpose"],
            emotion_impact=emotion_impact,
            behavior_impact="inspired and energized",
            inspired_goal=inspired_goal,
            vividness=0.85,
            interpretation="Creative insight and inspiration",
        )
        
        return dream

    def _generate_surreal_dream(
        self,
        npc: NPCState,
        recent_memories: List[Memory],
    ) -> Dream:
        """Generate a surreal, nonsensical dream."""
        surreal_elements = [
            "talking animals",
            "impossible architecture",
            "shifting landscapes",
            "familiar faces on wrong bodies",
            "time flowing backwards",
            "flying without wings",
            "breathing underwater",
        ]
        
        elements = random.sample(surreal_elements, k=2)
        
        content = (
            f"{npc.name} dreams of {elements[0]} and {elements[1]}. "
            f"The dream makes no logical sense, but feels meaningful somehow. "
            f"Strange symbols and impossible events unfold."
        )
        
        dream = Dream(
            npc_id=npc.npc_id,
            npc_name=npc.name,
            dream_type=DreamType.SURREAL,
            content=content,
            symbolism=elements,
            emotion_impact={},
            behavior_impact="slightly confused but intrigued",
            vividness=0.5,
            interpretation="Random neural processing",
        )
        
        return dream

    def apply_dream_effects(self, npc: NPCState, dream: Dream) -> NPCState:
        """
        Apply dream effects to NPC's emotional state and goals.
        
        Args:
            npc: The NPC who had the dream
            dream: The dream to apply
        
        Returns:
            Updated NPC state
        """
        # Apply emotion impacts
        if dream.emotion_impact:
            emotion_dict = npc.emotion_state.model_dump()
            for emotion_key, change in dream.emotion_impact.items():
                if emotion_key in emotion_dict:
                    new_value = emotion_dict[emotion_key] + change
                    emotion_dict[emotion_key] = max(0.0, min(1.0, new_value))
            
            npc.emotion_state = EmotionVector(**emotion_dict)
        
        # Add inspired goal if any
        if dream.inspired_goal:
            from app.goals.planner import GOAL_LIBRARY
            if dream.inspired_goal in GOAL_LIBRARY:
                new_goal = GOAL_LIBRARY[dream.inspired_goal].model_copy()
                new_goal.description += " (inspired by a dream)"
                npc.goals.append(new_goal)
        
        logger.info(
            "dream_effects_applied",
            npc=npc.name,
            dream_type=dream.dream_type,
            emotion_changes=dream.emotion_impact,
        )
        
        return npc


# Singleton
dream_engine = DreamEngine()
