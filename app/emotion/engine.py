"""
Emotion Engine
Implements a 8-dimensional emotion vector with:
- Decay (emotions return to baseline over time)
- Stimulus response (events modify emotions)
- Personality-modulated response intensity
"""
from __future__ import annotations
import math
from typing import Dict
from app.models import EmotionVector, PersonalityVector, EventType


# ─────────────────────────────────────────────
# EVENT → EMOTION STIMULUS TABLE
# Each event type maps to deltas across emotion dimensions.
# Values are base stimuli before personality modulation.
# ─────────────────────────────────────────────

EVENT_STIMULI: Dict[str, Dict[str, float]] = {
    # Hostile events
    EventType.PLAYER_ATTACK:    {"fear": +0.6, "anger": +0.5, "surprise": +0.4, "joy": -0.3, "trust": -0.2},
    "theft":                    {"anger": +0.4, "trust": -0.4, "sadness": +0.2},
    "murder_witnessed":         {"fear": +0.7, "sadness": +0.4, "anger": +0.3, "surprise": +0.5},
    EventType.ASSASSINATION:    {"fear": +0.5, "anger": +0.3, "surprise": +0.6, "trust": -0.3},
    EventType.WAR_DECLARED:     {"fear": +0.4, "anger": +0.3, "sadness": +0.2, "anticipation": +0.3},

    # Positive events
    "gift":                     {"trust": +0.3, "joy": +0.4, "surprise": +0.2},
    "compliment":               {"joy": +0.2, "trust": +0.1},
    "helped_by_player":         {"trust": +0.5, "joy": +0.3, "anticipation": +0.2},
    "trade_success":            {"joy": +0.3, "trust": +0.1},

    # World events
    EventType.DRAGON_KILLED:    {"joy": +0.4, "fear": -0.3, "surprise": +0.3, "anticipation": +0.2},
    EventType.MARKET_FIRE:      {"fear": +0.3, "sadness": +0.4, "anger": +0.2, "surprise": +0.4},
    EventType.PLAGUE:           {"fear": +0.6, "sadness": +0.5, "anticipation": -0.3},
    EventType.FESTIVAL:         {"joy": +0.5, "surprise": +0.2, "anticipation": +0.3},

    # Social events
    "betrayal":                 {"anger": +0.5, "sadness": +0.4, "trust": -0.7, "surprise": +0.3},
    "alliance_formed":          {"trust": +0.4, "joy": +0.2, "anticipation": +0.3},
    "public_humiliation":       {"anger": +0.3, "sadness": +0.5, "disgust": +0.2},

    # Rumor
    EventType.RUMOR:            {"surprise": +0.2, "anticipation": +0.2},

    # Crime stimuli (used by rumor_network)
    "crime_murder":      {"fear": +0.7, "anger": +0.5, "sadness": +0.4, "disgust": +0.5, "trust": -0.3, "surprise": +0.4},
    "crime_assault":     {"fear": +0.5, "anger": +0.6, "surprise": +0.3, "trust": -0.3},
    "crime_theft":       {"anger": +0.4, "trust": -0.5, "disgust": +0.2, "surprise": +0.2},
    "crime_arson":       {"fear": +0.6, "anger": +0.4, "sadness": +0.4, "surprise": +0.4, "trust": -0.2},
    "crime_trespassing": {"anger": +0.2, "surprise": +0.3, "trust": -0.1},
    "crime_fraud":       {"anger": +0.3, "trust": -0.5, "disgust": +0.3, "surprise": +0.2},
}

# Baseline emotion state (resting point for decay)
EMOTION_BASELINE: Dict[str, float] = {
    "joy": 0.4,
    "trust": 0.5,
    "fear": 0.0,
    "anger": 0.0,
    "sadness": 0.0,
    "surprise": 0.0,
    "disgust": 0.0,
    "anticipation": 0.3,
}


class EmotionEngine:
    """
    Manages emotion state updates for NPCs.

    Update formula:
        E(t+1) = decay(E(t)) + stimulus(event) × personality_modifier

    Decay formula:
        e_i(t+1) = e_i(t) + decay_rate × (baseline_i - e_i(t))
    """

    def __init__(self, decay_rate: float = 0.05):
        self.decay_rate = decay_rate

    def apply_decay(
        self,
        emotion: EmotionVector,
        ticks: int = 1,
    ) -> EmotionVector:
        """
        Move each emotion dimension toward its baseline.
        Called each simulation tick.
        """
        emotion_dict = emotion.model_dump()
        for dim, value in emotion_dict.items():
            baseline = EMOTION_BASELINE.get(dim, 0.0)
            # exponential decay toward baseline
            emotion_dict[dim] = baseline + (value - baseline) * math.exp(
                -self.decay_rate * ticks
            )
            emotion_dict[dim] = max(0.0, min(1.0, emotion_dict[dim]))
        return EmotionVector(**emotion_dict)

    def apply_stimulus(
        self,
        emotion: EmotionVector,
        event_type: str,
        personality: PersonalityVector,
        severity: float = 1.0,
        is_direct_witness: bool = True,
    ) -> EmotionVector:
        """
        Update emotion vector based on an event.

        Personality modulates the response:
        - High bravery → reduced fear response
        - High empathy → amplified sadness/joy
        - High aggression → amplified anger response
        - Low empathy → reduced trust/joy
        """
        stimuli = EVENT_STIMULI.get(event_type, {})
        if not stimuli:
            return emotion

        # Rumor dampening — indirect events have reduced effect
        witness_factor = 1.0 if is_direct_witness else 0.4

        emotion_dict = emotion.model_dump()

        for dim, delta in stimuli.items():
            # Personality modulation
            modifier = self._personality_modifier(dim, delta, personality)
            scaled_delta = delta * severity * witness_factor * modifier

            new_val = emotion_dict[dim] + scaled_delta
            emotion_dict[dim] = max(0.0, min(1.0, new_val))

        return EmotionVector(**emotion_dict)

    def _personality_modifier(
        self,
        emotion_dim: str,
        delta: float,
        p: PersonalityVector,
    ) -> float:
        """
        Returns a multiplier [0.2, 2.0] based on personality traits.
        """
        modifier = 1.0

        if emotion_dim == "fear":
            # Brave NPCs fear less, cowards fear more
            modifier = 2.0 - p.bravery  # bravery=1.0 → 1.0x, bravery=0.0 → 2.0x
        elif emotion_dim == "anger":
            modifier = 0.5 + p.aggression + (1.0 - p.empathy) * 0.5
        elif emotion_dim == "sadness":
            modifier = 0.5 + p.empathy
        elif emotion_dim == "joy":
            modifier = 0.5 + p.empathy * 0.5
        elif emotion_dim == "trust":
            if delta < 0:  # trust loss
                modifier = 2.0 - p.loyalty  # loyal NPCs lose trust slower
            else:
                modifier = 0.5 + p.empathy * 0.5
        elif emotion_dim == "disgust":
            modifier = 0.5 + (1.0 - p.empathy) * 0.5

        return max(0.2, min(2.0, modifier))

    def process_event(
        self,
        emotion: EmotionVector,
        event_type: str,
        personality: PersonalityVector,
        severity: float = 1.0,
        is_direct: bool = True,
        elapsed_ticks: int = 0,
    ) -> EmotionVector:
        """
        Full emotion update: decay first, then apply stimulus.
        """
        decayed = self.apply_decay(emotion, ticks=elapsed_ticks)
        updated = self.apply_stimulus(decayed, event_type, personality, severity, is_direct)
        return updated

    def emotion_to_prompt_fragment(self, emotion: EmotionVector) -> str:
        """Convert emotion state to natural language for LLM prompt injection."""
        dominant = emotion.dominant()
        valence = emotion.valence()
        arousal = emotion.arousal()

        mood = "positive" if valence > 0.2 else "negative" if valence < -0.2 else "neutral"
        energy = "high-energy" if arousal > 0.6 else "calm"

        lines = [
            f"Current dominant emotion: {dominant}",
            f"Overall mood: {mood}, {energy}",
        ]

        notable = {
            k: v for k, v in emotion.model_dump().items()
            if v > 0.5
        }
        if notable:
            details = ", ".join(f"{k}={v:.2f}" for k, v in notable.items())
            lines.append(f"Strong emotions: {details}")

        return "\n".join(lines)

    def blend_emotions(
        self,
        e1: EmotionVector,
        e2: EmotionVector,
        weight: float = 0.5,
    ) -> EmotionVector:
        """Weighted blend of two emotion vectors (for rumor propagation)."""
        d1 = e1.model_dump()
        d2 = e2.model_dump()
        blended = {
            k: d1[k] * (1 - weight) + d2[k] * weight
            for k in d1
        }
        return EmotionVector(**blended)


# Singleton
emotion_engine = EmotionEngine()
