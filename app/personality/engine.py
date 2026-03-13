"""
Personality Engine
Modulates dialogue, goal selection, and negotiation based on
the NPC's personality vector.
"""
from __future__ import annotations
from typing import List, Dict
from app.models import PersonalityVector, EmotionVector, Goal


# ─────────────────────────────────────────────
# PERSONALITY → DIALOGUE TONE MAPPING
# ─────────────────────────────────────────────

def get_dialogue_tone(personality: PersonalityVector, emotion: EmotionVector) -> str:
    """
    Returns a rich tone descriptor string for LLM prompt injection.
    Combines personality traits with current emotional state.
    """
    tones = []

    # Personality-driven tone
    if personality.greed > 0.7:
        tones.append("greedy and transactional, always looking for profit")
    if personality.bravery > 0.7:
        tones.append("bold and direct, unafraid to speak their mind")
    elif personality.bravery < 0.3:
        tones.append("nervous and hesitant, choosing words carefully")
    if personality.empathy > 0.7:
        tones.append("warm and compassionate, genuinely concerned about others")
    elif personality.empathy < 0.3:
        tones.append("cold and indifferent to the problems of others")
    if personality.loyalty > 0.7:
        tones.append("fiercely loyal to their allies")
    if personality.curiosity > 0.7:
        tones.append("inquisitive, often asking questions")
    if personality.honesty > 0.7:
        tones.append("bluntly honest, even if it's uncomfortable")
    elif personality.honesty < 0.3:
        tones.append("evasive and prone to half-truths")
    if personality.aggression > 0.7:
        tones.append("aggressive and confrontational")

    # Emotion-driven modifiers
    dominant = emotion.dominant()
    if dominant == "anger":
        tones.append("currently angry and short-tempered")
    elif dominant == "fear":
        tones.append("currently frightened and jumpy")
    elif dominant == "joy":
        tones.append("currently in good spirits")
    elif dominant == "sadness":
        tones.append("currently melancholy and withdrawn")
    elif dominant == "trust":
        tones.append("currently open and trusting")
    elif dominant == "disgust":
        tones.append("currently disgusted and dismissive")

    base = "; ".join(tones) if tones else "balanced and measured"
    return base


# ─────────────────────────────────────────────
# PERSONALITY → GOAL PRIORITY MODIFIERS
# ─────────────────────────────────────────────

# Maps goal names to personality trait amplifiers
GOAL_PERSONALITY_MODIFIERS: Dict[str, Dict[str, float]] = {
    "increase_wealth":      {"greed": +0.4, "empathy": -0.2},
    "sell_goods":           {"greed": +0.2, "curiosity": +0.1},
    "protect_village":      {"loyalty": +0.4, "bravery": +0.3, "empathy": +0.2},
    "gain_reputation":      {"greed": +0.1, "loyalty": +0.1, "honesty": -0.1},
    "gather_information":   {"curiosity": +0.5},
    "eliminate_threat":     {"bravery": +0.3, "aggression": +0.4},
    "form_alliance":        {"loyalty": +0.2, "empathy": +0.2, "honesty": +0.1},
    "seek_revenge":         {"aggression": +0.4, "loyalty": +0.2, "bravery": +0.1},
    "escape_danger":        {"bravery": -0.3, "fear_mod": +0.3},
    "help_villagers":       {"empathy": +0.5, "loyalty": +0.2, "greed": -0.3},
    "hoard_resources":      {"greed": +0.5, "empathy": -0.2},
    "spread_rumors":        {"honesty": -0.3, "curiosity": +0.2},
}

# Maps goal names to emotion amplifiers
GOAL_EMOTION_MODIFIERS: Dict[str, Dict[str, float]] = {
    "increase_wealth":      {"joy": +0.2, "anticipation": +0.3},
    "protect_village":      {"fear": +0.1, "anger": +0.1},
    "eliminate_threat":     {"anger": +0.3, "fear": -0.1},
    "escape_danger":        {"fear": +0.5},
    "seek_revenge":         {"anger": +0.5, "sadness": +0.2},
    "help_villagers":       {"joy": +0.1},
    "gather_information":   {"anticipation": +0.3},
}


def compute_goal_priority(
    goal: Goal,
    personality: PersonalityVector,
    emotion: EmotionVector,
) -> float:
    """
    priority = base_weight × personality_modifier × emotion_modifier

    Formula ensures:
    - Goals aligned with personality get boosted
    - Goals misaligned with personality get reduced
    - Emotional state can create urgency (e.g. anger boosts revenge goals)
    """
    personality_dict = personality.model_dump()
    emotion_dict = emotion.model_dump()

    # Personality modifier
    p_mod = 1.0
    p_modifiers = GOAL_PERSONALITY_MODIFIERS.get(goal.name, {})
    for trait, weight in p_modifiers.items():
        if trait in personality_dict:
            p_mod += weight * personality_dict[trait]

    # Emotion modifier
    e_mod = 1.0
    e_modifiers = GOAL_EMOTION_MODIFIERS.get(goal.name, {})
    for emotion_dim, weight in e_modifiers.items():
        if emotion_dim in emotion_dict:
            e_mod += weight * emotion_dict[emotion_dim]

    priority = goal.base_weight * max(0.1, p_mod) * max(0.1, e_mod)
    return min(1.0, priority)


def rank_goals(
    goals: List[Goal],
    personality: PersonalityVector,
    emotion: EmotionVector,
) -> List[Goal]:
    """Return goals sorted by computed priority descending."""
    for goal in goals:
        goal.current_priority = compute_goal_priority(goal, personality, emotion)
    return sorted(goals, key=lambda g: g.current_priority, reverse=True)


# ─────────────────────────────────────────────
# NEGOTIATION BEHAVIOR
# ─────────────────────────────────────────────

def negotiation_stance(personality: PersonalityVector) -> Dict[str, float]:
    """
    Returns negotiation parameters based on personality.
    Used to modify trade/quest negotiation logic.
    """
    return {
        # How much above/below fair price they'll aim for
        "price_markup": personality.greed * 0.4,
        # Willingness to accept a deal (0=never, 1=always)
        "deal_acceptance_threshold": 0.3 + (1 - personality.greed) * 0.4,
        # How much trust modifies willingness to negotiate
        "trust_sensitivity": personality.loyalty * 0.5,
        # Aggression in negotiation — threatens/demands
        "bluff_probability": personality.aggression * 0.4 + (1 - personality.honesty) * 0.3,
        # Will they reveal information freely
        "information_sharing": personality.honesty * 0.6 + personality.empathy * 0.2,
    }


def get_personality_prompt_block(
    personality: PersonalityVector,
    emotion: EmotionVector,
    archetype: str,
) -> str:
    """Build the personality/emotion block for LLM prompts."""
    tone = get_dialogue_tone(personality, emotion)
    traits = personality.describe()
    neg = negotiation_stance(personality)

    return f"""PERSONALITY & EMOTIONAL STATE:
Archetype: {archetype}
Core traits: {traits}
Current tone: {tone}
Negotiation style: markup={neg['price_markup']:.1f}, bluff_prob={neg['bluff_probability']:.1f}

Dominant emotion: {emotion.dominant()} (valence: {emotion.valence():+.2f})
"""
