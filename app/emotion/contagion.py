"""
Emotional Contagion Engine — Emotions Spread Through Crowds

Models how emotions spread between NPCs in proximity:
- Panic spreads during attacks
- Joy spreads during festivals
- Anger spreads during injustice
- Fear spreads from witnesses

Uses social network topology and personality traits to determine
contagion strength and resistance.
"""
from __future__ import annotations

import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

from app.models import NPCState, EmotionVector, PersonalityVector, Relationship
import structlog

logger = structlog.get_logger()


class EmotionalContagion:
    """
    Manages emotion spreading through NPC populations.
    
    Based on social contagion models with personality modulation.
    """

    def __init__(self):
        # Contagion rates per emotion (0.0 = doesn't spread, 1.0 = highly contagious)
        self.contagion_rates = {
            "fear": 0.8,        # Fear spreads very quickly
            "anger": 0.7,       # Anger spreads in groups
            "joy": 0.6,         # Joy is moderately contagious
            "panic": 0.9,       # Panic spreads fastest
            "sadness": 0.4,     # Sadness spreads slowly
            "surprise": 0.5,    # Surprise spreads moderately
            "disgust": 0.6,     # Disgust spreads fairly well
            "trust": 0.3,       # Trust builds slowly
        }
        
        # Distance decay factor (emotions weaken with distance)
        self.distance_decay = 0.1  # per unit distance
        
        # Crowd amplification (emotions intensify in crowds)
        self.crowd_threshold = 5
        self.crowd_amplification = 1.5

    def spread_emotion(
        self,
        source_npc: NPCState,
        target_npcs: List[NPCState],
        emotion_type: str,
        intensity: float,
        relationships: Optional[Dict[str, Relationship]] = None,
        distances: Optional[Dict[str, float]] = None,
    ) -> Dict[str, EmotionVector]:
        """
        Spread an emotion from source NPC to nearby targets.
        
        Args:
            source_npc: NPC experiencing the emotion
            target_npcs: NPCs who might catch the emotion
            emotion_type: Which emotion to spread (fear, anger, joy, etc.)
            intensity: How strong the source emotion is (0.0-1.0)
            relationships: Optional relationship data for social influence
            distances: Optional distance data for spatial decay
        
        Returns:
            Dict mapping target NPC IDs to their updated emotion vectors
        """
        if emotion_type not in self.contagion_rates:
            logger.warning("unknown_emotion_type", emotion_type=emotion_type)
            return {}
        
        base_contagion = self.contagion_rates[emotion_type]
        updated_emotions: Dict[str, EmotionVector] = {}
        
        # Crowd amplification
        crowd_size = len(target_npcs) + 1
        crowd_factor = 1.0
        if crowd_size >= self.crowd_threshold:
            crowd_factor = self.crowd_amplification
            logger.info(
                "crowd_amplification_active",
                crowd_size=crowd_size,
                amplification=crowd_factor,
            )
        
        for target in target_npcs:
            # Skip if same NPC
            if target.npc_id == source_npc.npc_id:
                continue
            
            # Calculate contagion strength
            contagion_strength = self._calculate_contagion_strength(
                source_npc=source_npc,
                target_npc=target,
                base_contagion=base_contagion,
                intensity=intensity,
                relationship=relationships.get(target.npc_id) if relationships else None,
                distance=distances.get(target.npc_id) if distances else None,
                crowd_factor=crowd_factor,
            )
            
            # Apply emotion transfer
            if contagion_strength > 0.05:  # Threshold for effect
                new_emotion = self._apply_emotion_transfer(
                    target.emotion_state,
                    emotion_type,
                    contagion_strength,
                    target.personality,
                )
                
                updated_emotions[target.npc_id] = new_emotion
                
                logger.debug(
                    "emotion_contagion",
                    source=source_npc.name,
                    target=target.name,
                    emotion=emotion_type,
                    strength=round(contagion_strength, 3),
                )
        
        return updated_emotions

    def _calculate_contagion_strength(
        self,
        source_npc: NPCState,
        target_npc: NPCState,
        base_contagion: float,
        intensity: float,
        relationship: Optional[Relationship],
        distance: Optional[float],
        crowd_factor: float,
    ) -> float:
        """Calculate how strongly emotion transfers from source to target."""
        strength = base_contagion * intensity * crowd_factor
        
        # Personality modulation
        # Empathy increases susceptibility
        empathy_factor = 0.5 + (target_npc.personality.empathy * 0.5)
        strength *= empathy_factor
        
        # Relationship influence
        if relationship:
            # Trust and friendship increase contagion
            social_factor = (relationship.trust + relationship.friendship) / 2
            strength *= (0.7 + social_factor * 0.6)
            
            # Fear of source increases negative emotion contagion
            if relationship.fear > 0.5:
                strength *= 1.3
        
        # Distance decay
        if distance is not None:
            decay = math.exp(-self.distance_decay * distance)
            strength *= decay
        
        # Clamp to valid range
        return max(0.0, min(1.0, strength))

    def _apply_emotion_transfer(
        self,
        current_emotion: EmotionVector,
        emotion_type: str,
        strength: float,
        personality: PersonalityVector,
    ) -> EmotionVector:
        """Apply emotional contagion to target's emotion state."""
        new_emotion = current_emotion.model_copy()
        current_dict = new_emotion.model_dump()
        
        # Map emotion types to emotion vector fields
        emotion_mapping = {
            "fear": "fear",
            "anger": "anger",
            "joy": "joy",
            "panic": "fear",  # Panic increases fear
            "sadness": "sadness",
            "surprise": "surprise",
            "disgust": "disgust",
            "trust": "trust",
        }
        
        field = emotion_mapping.get(emotion_type)
        if not field:
            return new_emotion
        
        # Blend current emotion with contagion
        current_value = current_dict[field]
        target_value = min(1.0, current_value + strength)
        
        # Personality resistance
        if field in ["fear", "sadness"]:
            # Bravery resists fear
            resistance = personality.bravery * 0.3
            target_value *= (1.0 - resistance)
        elif field == "anger":
            # Aggression amplifies anger contagion
            amplification = personality.aggression * 0.2
            target_value *= (1.0 + amplification)
        
        # Smooth transition (don't jump instantly)
        blended_value = current_value * 0.6 + target_value * 0.4
        current_dict[field] = max(0.0, min(1.0, blended_value))
        
        # Emotional displacement (strong emotions suppress others)
        if blended_value > 0.7:
            # Reduce opposite emotions
            opposites = {
                "fear": ["joy", "trust"],
                "anger": ["joy", "trust"],
                "joy": ["fear", "anger", "sadness"],
                "sadness": ["joy"],
            }
            
            if field in opposites:
                for opp in opposites[field]:
                    current_dict[opp] *= 0.8
        
        return EmotionVector(**current_dict)

    def simulate_crowd_panic(
        self,
        npcs: List[NPCState],
        panic_source: str,
        initial_intensity: float = 0.9,
        epicenter_location: Optional[str] = None,
    ) -> Dict[str, EmotionVector]:
        """
        Simulate panic spreading through a crowd.
        
        Args:
            npcs: All NPCs in the area
            panic_source: Description of what caused panic
            initial_intensity: Starting panic level
            epicenter_location: Where panic started (for distance calc)
        
        Returns:
            Updated emotion states for all affected NPCs
        """
        if not npcs:
            return {}
        
        # Find NPCs at epicenter
        if epicenter_location:
            epicenter_npcs = [n for n in npcs if n.location == epicenter_location]
        else:
            epicenter_npcs = npcs[:max(1, len(npcs) // 3)]  # First third
        
        if not epicenter_npcs:
            epicenter_npcs = [npcs[0]]
        
        logger.info(
            "crowd_panic_simulation",
            total_npcs=len(npcs),
            epicenter_npcs=len(epicenter_npcs),
            source=panic_source,
        )
        
        # Wave 1: Epicenter NPCs experience direct panic
        updated_emotions: Dict[str, EmotionVector] = {}
        for npc in epicenter_npcs:
            panic_emotion = self._apply_emotion_transfer(
                npc.emotion_state,
                "panic",
                initial_intensity,
                npc.personality,
            )
            updated_emotions[npc.npc_id] = panic_emotion
        
        # Wave 2: Panic spreads to nearby NPCs
        remaining_npcs = [n for n in npcs if n.npc_id not in updated_emotions]
        
        for source in epicenter_npcs:
            spread_result = self.spread_emotion(
                source_npc=source,
                target_npcs=remaining_npcs,
                emotion_type="panic",
                intensity=initial_intensity * 0.8,  # Slightly reduced
            )
            updated_emotions.update(spread_result)
        
        # Wave 3: Secondary spread (panic spreads from newly panicked NPCs)
        newly_panicked = [
            npc for npc in remaining_npcs
            if npc.npc_id in updated_emotions
        ]
        
        still_calm = [
            npc for npc in remaining_npcs
            if npc.npc_id not in updated_emotions
        ]
        
        for source in newly_panicked[:5]:  # Limit to prevent explosion
            spread_result = self.spread_emotion(
                source_npc=source,
                target_npcs=still_calm,
                emotion_type="panic",
                intensity=initial_intensity * 0.5,  # Further reduced
            )
            updated_emotions.update(spread_result)
        
        logger.info(
            "panic_cascade_complete",
            affected_npcs=len(updated_emotions),
            total_npcs=len(npcs),
            penetration=f"{len(updated_emotions)/len(npcs)*100:.1f}%",
        )
        
        return updated_emotions

    def simulate_joy_spread(
        self,
        npcs: List[NPCState],
        joy_source: str,
        initial_intensity: float = 0.8,
    ) -> Dict[str, EmotionVector]:
        """Simulate joy spreading through a celebration or festival."""
        if not npcs:
            return {}
        
        # Joy spreads more evenly (less panic-like)
        updated_emotions: Dict[str, EmotionVector] = {}
        
        # Start with a few joyful NPCs
        initial_joyful = npcs[:max(2, len(npcs) // 4)]
        
        for npc in initial_joyful:
            joy_emotion = self._apply_emotion_transfer(
                npc.emotion_state,
                "joy",
                initial_intensity,
                npc.personality,
            )
            updated_emotions[npc.npc_id] = joy_emotion
        
        # Spread to others
        remaining = [n for n in npcs if n.npc_id not in updated_emotions]
        
        for source in initial_joyful:
            spread_result = self.spread_emotion(
                source_npc=source,
                target_npcs=remaining,
                emotion_type="joy",
                intensity=initial_intensity * 0.7,
            )
            updated_emotions.update(spread_result)
        
        return updated_emotions

    def calculate_crowd_mood(
        self,
        npcs: List[NPCState],
    ) -> Dict[str, Any]:
        """
        Calculate aggregate emotional state of a crowd.
        
        Returns:
            - dominant_emotion: Most common emotion
            - average_valence: Overall mood (-1 to +1)
            - average_arousal: Energy level (0 to 1)
            - emotion_distribution: Breakdown by emotion
        """
        if not npcs:
            return {
                "dominant_emotion": "neutral",
                "average_valence": 0.0,
                "average_arousal": 0.0,
                "emotion_distribution": {},
            }
        
        # Aggregate emotions
        emotion_sums = {
            "joy": 0.0, "trust": 0.0, "fear": 0.0, "anger": 0.0,
            "sadness": 0.0, "surprise": 0.0, "disgust": 0.0, "anticipation": 0.0,
        }
        
        total_valence = 0.0
        total_arousal = 0.0
        
        for npc in npcs:
            emotion_dict = npc.emotion_state.model_dump()
            for key in emotion_sums:
                emotion_sums[key] += emotion_dict[key]
            
            total_valence += npc.emotion_state.valence()
            total_arousal += npc.emotion_state.arousal()
        
        # Calculate averages
        n = len(npcs)
        emotion_averages = {k: v / n for k, v in emotion_sums.items()}
        dominant = max(emotion_averages, key=emotion_averages.get)
        
        return {
            "dominant_emotion": dominant,
            "average_valence": total_valence / n,
            "average_arousal": total_arousal / n,
            "emotion_distribution": emotion_averages,
            "crowd_size": n,
        }


# Singleton
emotional_contagion = EmotionalContagion()
