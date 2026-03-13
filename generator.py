"""
Dialogue Generation Engine — LLM-powered contextual NPC dialogue.

Builds a rich system prompt from:
  - NPC personality + emotion state
  - Retrieved memories
  - Relationship history
  - Active goals
  - World context

Returns: { dialogue, npc_action, emotion_update, memory_tags }
"""
from __future__ import annotations

import json
from typing import List, Optional, Dict, Any, Tuple

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import (
    NPCState,
    EmotionVector,
    Memory,
    Relationship,
    Goal,
    GoalStatus,
)
from app.personality.engine import get_personality_prompt_block
from app.emotion.engine import emotion_engine
from app.config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────
# DIALOGUE GENERATOR
# ─────────────────────────────────────────────

class DialogueGenerator:
    """
    Generates contextual NPC dialogue using the Anthropic API.

    Prompt structure:
      [SYSTEM: NPC identity + world rules]
      [USER: Context block + player message]
      → [ASSISTANT: JSON response]
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def generate(
        self,
        npc: NPCState,
        player_id: str,
        player_message: str,
        memories: List[Memory],
        relationship: Optional[Relationship],
        world_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call LLM and return structured response:
        {
          "dialogue": str,
          "npc_action": str | null,
          "emotion_update": { joy, trust, fear, ... },
          "relationship_delta": { trust, friendship, fear },
          "memory_tags": [str],
          "internal_thought": str
        }
        """
        system_prompt = self._build_system_prompt(npc)
        user_prompt = self._build_user_prompt(
            npc, player_id, player_message,
            memories, relationship, world_context,
        )

        # Use synchronous client in async context (wrap if needed)
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        )

        raw = response.content[0].text
        return self._parse_response(raw, npc.emotion_state)

    def _build_system_prompt(self, npc: NPCState) -> str:
        personality_block = get_personality_prompt_block(
            npc.personality,
            npc.emotion_state,
            npc.archetype,
        )

        return f"""You are {npc.name}, a {npc.archetype} in a living fantasy world.
You are NOT an AI assistant. You are a real person with feelings, history, and goals.
NEVER break character. NEVER mention being an AI.

{personality_block}

BACKGROUND:
{npc.background or f"A {npc.archetype} going about their daily life."}

SPEECH STYLE: {npc.speech_style or "natural, period-appropriate"}
FACTION: {npc.faction or "none"}
LOCATION: {npc.location or "unknown"}

RESPONSE FORMAT:
You must respond ONLY with valid JSON in this exact structure:
{{
  "dialogue": "<what you say out loud>",
  "npc_action": "<physical action you take, or null>",
  "emotion_update": {{
    "joy": <0.0-1.0>,
    "trust": <0.0-1.0>,
    "fear": <0.0-1.0>,
    "anger": <0.0-1.0>,
    "sadness": <0.0-1.0>,
    "surprise": <0.0-1.0>,
    "disgust": <0.0-1.0>,
    "anticipation": <0.0-1.0>
  }},
  "relationship_delta": {{
    "trust": <-0.3 to +0.3>,
    "friendship": <-0.3 to +0.3>,
    "fear": <-0.3 to +0.3>
  }},
  "memory_tags": ["tag1", "tag2"],
  "internal_thought": "<your private thought, not spoken>"
}}

Rules:
- dialogue must be authentic to your character, mood, and the situation
- Keep dialogue concise (1-3 sentences usually)
- npc_action describes physical behavior (draws sword, looks away, smiles)
- emotion_update reflects how you feel AFTER this interaction
- relationship_delta is how your view of the player changed (positive=improved)
- memory_tags are 2-4 keywords categorizing this interaction
- internal_thought reveals your true inner feeling (can differ from dialogue)"""

    def _build_user_prompt(
        self,
        npc: NPCState,
        player_id: str,
        player_message: str,
        memories: List[Memory],
        relationship: Optional[Relationship],
        world_context: Dict[str, Any],
    ) -> str:
        blocks = []

        # ── Current emotional state ──
        emotion = npc.emotion_state
        blocks.append(f"""CURRENT EMOTIONAL STATE:
Dominant emotion: {emotion.dominant()}
Mood valence: {"positive" if emotion.valence() > 0 else "negative"} ({emotion.valence():+.2f})
Joy: {emotion.joy:.2f} | Trust: {emotion.trust:.2f} | Fear: {emotion.fear:.2f}
Anger: {emotion.anger:.2f} | Sadness: {emotion.sadness:.2f} | Surprise: {emotion.surprise:.2f}""")

        # ── Active goals ──
        active_goals = [g for g in npc.goals if g.status == GoalStatus.ACTIVE]
        if active_goals:
            goal_lines = "\n".join(
                f"  - {g.name}: {g.description} (priority: {g.current_priority:.2f})"
                for g in active_goals[:3]
            )
            blocks.append(f"CURRENT GOALS:\n{goal_lines}")

        # ── Relevant memories ──
        if memories:
            mem_lines = []
            for mem in memories[:5]:
                age = "recently" if (
                    (__import__("datetime").datetime.utcnow() - mem.timestamp).days < 7
                ) else "some time ago"
                mem_lines.append(f"  - [{age}] {mem.event}")
            blocks.append(f"RELEVANT MEMORIES:\n" + "\n".join(mem_lines))
        else:
            blocks.append("RELEVANT MEMORIES:\n  - No specific memories of this person.")

        # ── Relationship ──
        if relationship:
            blocks.append(f"""RELATIONSHIP WITH {player_id.upper()}:
Trust: {relationship.trust:.2f} | Friendship: {relationship.friendship:.2f}
Fear of them: {relationship.fear:.2f} | Respect: {relationship.respect:.2f}
Previous interactions: {relationship.interaction_count}
Type: {relationship.relationship_type.value}""")
        else:
            blocks.append(f"RELATIONSHIP WITH {player_id.upper()}:\n  First encounter — no history.")

        # ── World context ──
        if world_context:
            recent_events = world_context.get("recent_events", [])
            if recent_events:
                event_lines = "\n".join(f"  - {e}" for e in recent_events[:3])
                blocks.append(f"RECENT WORLD EVENTS:\n{event_lines}")

        # ── Situation ──
        blocks.append(f"""CURRENT SITUATION:
{player_id} approaches you and says: "{player_message}"

Respond as {npc.name} would authentically respond given your personality, emotions, memories, and goals.
Return ONLY the JSON response object.""")

        return "\n\n".join(blocks)

    def _parse_response(
        self,
        raw: str,
        current_emotion: EmotionVector,
    ) -> Dict[str, Any]:
        """Parse LLM JSON response, with fallback on parse error."""
        try:
            # Strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            data = json.loads(text)

            # Validate and clamp emotion values
            if "emotion_update" in data:
                eu = data["emotion_update"]
                emotion_dict = {
                    k: max(0.0, min(1.0, float(v)))
                    for k, v in eu.items()
                    if k in current_emotion.model_fields
                }
                # Blend with current (don't allow instant full replacement)
                current_dict = current_emotion.model_dump()
                blended = {
                    k: current_dict[k] * 0.4 + emotion_dict.get(k, current_dict[k]) * 0.6
                    for k in current_dict
                }
                data["emotion_update"] = blended

            # Validate relationship delta
            if "relationship_delta" in data:
                rd = data["relationship_delta"]
                data["relationship_delta"] = {
                    k: max(-0.3, min(0.3, float(v)))
                    for k, v in rd.items()
                }

            return data

        except Exception as e:
            # Graceful fallback
            return {
                "dialogue": raw[:500] if raw else "...",
                "npc_action": None,
                "emotion_update": current_emotion.model_dump(),
                "relationship_delta": {},
                "memory_tags": ["interaction"],
                "internal_thought": "",
                "_parse_error": str(e),
            }

    def build_background_thought_prompt(
        self,
        npc: NPCState,
        world_events: List[str],
    ) -> str:
        """
        For background simulation: have the NPC reflect on recent events.
        Returns a brief internal monologue (no player involved).
        """
        emotion_desc = emotion_engine.emotion_to_prompt_fragment(npc.emotion_state)
        events_text = "\n".join(f"  - {e}" for e in world_events[:3])

        return f"""You are {npc.name}, a {npc.archetype}.
{emotion_desc}

Recent events in your world:
{events_text or "  Nothing unusual."}

Respond ONLY with JSON:
{{
  "internal_thought": "<your private reflection on these events>",
  "mood_shift": "<brief description of how your mood has changed>",
  "intention": "<what you plan to do next>"
}}"""


# Singleton
dialogue_generator = DialogueGenerator()
