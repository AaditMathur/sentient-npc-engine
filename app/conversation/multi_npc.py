"""
Multi-NPC Conversation Engine — Autonomous NPC-to-NPC Interactions

Enables NPCs to:
- Initiate conversations with each other based on proximity, relationships, goals
- Gossip about crimes, rumors, and world events
- Form alliances, rivalries, and romantic relationships
- Create emergent storylines without player involvement
"""
from __future__ import annotations

import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    NPCState,
    Relationship, RelationshipType,
)
from app.personality.engine import get_personality_prompt_block
from app.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


class ConversationTurn(dict):
    """A single turn in a multi-NPC conversation."""
    def __init__(
        self,
        speaker_id: str,
        speaker_name: str,
        dialogue: str,
        action: Optional[str] = None,
        emotion_after: Optional[Dict[str, float]] = None,
        internal_thought: Optional[str] = None,
    ):
        super().__init__(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            dialogue=dialogue,
            action=action,
            emotion_after=emotion_after,
            internal_thought=internal_thought,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class MultiNPCConversation:
    """Manages autonomous conversations between multiple NPCs."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.active_conversations: Dict[str, List[ConversationTurn]] = {}

    async def should_initiate_conversation(
        self,
        npc1: NPCState,
        npc2: NPCState,
        relationship: Optional[Relationship] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if two NPCs should start talking.
        Returns (should_talk, reason)
        """
        # Same location required
        if npc1.location != npc2.location:
            return False, "different_locations"

        # Check relationship
        if relationship:
            # Strong relationships increase likelihood
            if relationship.friendship > 0.7 or relationship.trust > 0.7:
                if random.random() < 0.4:
                    return True, "strong_friendship"
            
            # Enemies might confront each other
            if relationship.relationship_type == RelationshipType.ENEMY:
                if random.random() < 0.3:
                    return True, "confrontation"
            
            # Fear prevents conversation
            if relationship.fear > 0.7:
                return False, "too_afraid"

        # Shared goals or complementary archetypes
        if self._have_complementary_interests(npc1, npc2):
            if random.random() < 0.3:
                return True, "complementary_interests"

        # Recent world events create conversation topics
        if npc1.world_knowledge.get("recent_events") and random.random() < 0.25:
            return True, "world_events"

        # Crime awareness creates gossip opportunities
        if npc1.known_crimes and random.random() < 0.35:
            return True, "gossip_about_crime"

        return False, "no_reason"

    def _have_complementary_interests(self, npc1: NPCState, npc2: NPCState) -> bool:
        """Check if NPCs have reasons to interact."""
        complementary_pairs = [
            ("merchant", "guard"),
            ("merchant", "customer"),
            ("healer", "guard"),
            ("wizard", "apprentice"),
            ("innkeeper", "traveler"),
        ]
        
        pair = tuple(sorted([npc1.archetype.lower(), npc2.archetype.lower()]))
        return any(
            pair == tuple(sorted(comp)) 
            for comp in complementary_pairs
        )

    async def conduct_conversation(
        self,
        npcs: List[NPCState],
        topic: Optional[str] = None,
        max_turns: int = 6,
    ) -> List[ConversationTurn]:
        """
        Orchestrate a multi-turn conversation between NPCs.
        
        Args:
            npcs: List of 2-4 NPCs participating
            topic: Optional conversation starter
            max_turns: Maximum conversation length
        
        Returns:
            List of conversation turns with dialogue and state changes
        """
        if len(npcs) < 2:
            raise ValueError("Need at least 2 NPCs for conversation")
        
        conversation_id = f"conv_{npcs[0].npc_id}_{npcs[1].npc_id}_{int(datetime.now().timestamp())}"
        turns: List[ConversationTurn] = []
        
        # Determine initial topic
        if not topic:
            topic = await self._determine_topic(npcs)
        
        logger.info(
            "multi_npc_conversation_start",
            conversation_id=conversation_id,
            participants=[n.name for n in npcs],
            topic=topic,
        )
        
        # Conversation loop
        for turn_num in range(max_turns):
            speaker = npcs[turn_num % len(npcs)]
            listeners = [n for n in npcs if n.npc_id != speaker.npc_id]
            
            # Generate speaker's response
            turn = await self._generate_turn(
                speaker=speaker,
                listeners=listeners,
                conversation_history=turns,
                topic=topic,
                turn_number=turn_num,
            )
            
            turns.append(turn)
            
            # Check if conversation should end
            if self._should_end_conversation(turns, turn):
                logger.info(
                    "conversation_ended_naturally",
                    conversation_id=conversation_id,
                    turns=len(turns),
                )
                break
        
        self.active_conversations[conversation_id] = turns
        return turns

    async def _determine_topic(self, npcs: List[NPCState]) -> str:
        """Determine what NPCs should talk about."""
        # Check for shared crime knowledge
        shared_crimes = set(npcs[0].known_crimes.keys())
        for npc in npcs[1:]:
            shared_crimes &= set(npc.known_crimes.keys())
        
        if shared_crimes:
            crime_id = list(shared_crimes)[0]
            crime_info = npcs[0].known_crimes[crime_id]
            return f"gossip_about_{crime_info.get('crime_type', 'crime')}"
        
        # Check for shared world events
        events_0 = set(npcs[0].world_knowledge.get("recent_events", []))
        events_1 = set(npcs[1].world_knowledge.get("recent_events", []))
        shared_events = events_0 & events_1
        
        if shared_events:
            return f"discuss_event: {list(shared_events)[0][:50]}"
        
        # Check for complementary goals
        if npcs[0].archetype == "merchant" and any(g.name == "sell_goods" for g in npcs[0].goals):
            return "trade_negotiation"
        
        # Default topics based on archetypes
        archetype_topics = {
            "guard": "security_concerns",
            "merchant": "business_matters",
            "wizard": "magical_research",
            "healer": "health_concerns",
            "innkeeper": "local_gossip",
        }
        
        return archetype_topics.get(npcs[0].archetype.lower(), "casual_chat")

    async def _generate_turn(
        self,
        speaker: NPCState,
        listeners: List[NPCState],
        conversation_history: List[ConversationTurn],
        topic: str,
        turn_number: int,
    ) -> ConversationTurn:
        """Generate a single conversation turn using LLM."""
        system_prompt = self._build_conversation_system_prompt(speaker)
        user_prompt = self._build_conversation_user_prompt(
            speaker, listeners, conversation_history, topic, turn_number
        )
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
            )
            
            import json
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            
            data = json.loads(raw)
            
            return ConversationTurn(
                speaker_id=speaker.npc_id,
                speaker_name=speaker.name,
                dialogue=data.get("dialogue", "..."),
                action=data.get("action"),
                emotion_after=data.get("emotion_update"),
                internal_thought=data.get("internal_thought"),
            )
            
        except Exception as e:
            logger.error("conversation_turn_error", speaker=speaker.name, error=str(e))
            return ConversationTurn(
                speaker_id=speaker.npc_id,
                speaker_name=speaker.name,
                dialogue="...",
                action=None,
            )

    def _build_conversation_system_prompt(self, npc: NPCState) -> str:
        """Build system prompt for NPC in conversation."""
        personality_block = get_personality_prompt_block(
            npc.personality, npc.emotion_state, npc.archetype
        )
        
        return f"""You are {npc.name}, a {npc.archetype} having a conversation with other NPCs.
You are NOT an AI. You are a real person in a fantasy world.

{personality_block}

CURRENT EMOTION: {npc.emotion_state.dominant()} (valence: {npc.emotion_state.valence():+.2f})

RESPONSE FORMAT (JSON only):
{{
  "dialogue": "<what you say - keep it natural and conversational, 1-2 sentences>",
  "action": "<optional physical action>",
  "emotion_update": {{
    "joy": <0.0-1.0>, "trust": <0.0-1.0>, "fear": <0.0-1.0>,
    "anger": <0.0-1.0>, "sadness": <0.0-1.0>, "surprise": <0.0-1.0>,
    "disgust": <0.0-1.0>, "anticipation": <0.0-1.0>
  }},
  "internal_thought": "<your private thought>"
}}

Be authentic to your personality and current emotional state. React naturally to what others say."""

    def _build_conversation_user_prompt(
        self,
        speaker: NPCState,
        listeners: List[NPCState],
        history: List[ConversationTurn],
        topic: str,
        turn_number: int,
    ) -> str:
        """Build user prompt with conversation context."""
        blocks = []
        
        # Participants
        listener_names = ", ".join(n.name for n in listeners)
        blocks.append(f"CONVERSATION WITH: {listener_names}")
        blocks.append(f"TOPIC: {topic}")
        blocks.append(f"LOCATION: {speaker.location or 'unknown'}")
        
        # Conversation history
        if history:
            history_lines = []
            for turn in history[-5:]:  # Last 5 turns
                history_lines.append(
                    f"{turn['speaker_name']}: \"{turn['dialogue']}\""
                )
            blocks.append("CONVERSATION SO FAR:\n" + "\n".join(history_lines))
        else:
            blocks.append("You are starting this conversation.")
        
        # Context about listeners
        for listener in listeners:
            rel_key = listener.npc_id
            if rel_key in speaker.relationships:
                rel = speaker.relationships[rel_key]
                blocks.append(
                    f"\nYour relationship with {listener.name}: "
                    f"{rel.relationship_type.value} "
                    f"(trust: {rel.trust:.2f}, friendship: {rel.friendship:.2f})"
                )
        
        # Crime awareness for gossip
        if "gossip" in topic.lower() or "crime" in topic.lower():
            if speaker.known_crimes:
                crime_info = list(speaker.known_crimes.values())[0]
                blocks.append(
                    f"\nYou know about a {crime_info.get('crime_type')} "
                    f"committed by {crime_info.get('perpetrator_id')}"
                )
        
        blocks.append("\nRespond naturally as your character would. Return JSON only.")
        
        return "\n".join(blocks)

    def _should_end_conversation(
        self,
        history: List[ConversationTurn],
        last_turn: ConversationTurn,
    ) -> bool:
        """Determine if conversation should end."""
        if len(history) < 3:
            return False
        
        # Check for farewell keywords
        farewell_keywords = [
            "goodbye", "farewell", "see you", "must go", "take my leave",
            "be off", "until next", "good day"
        ]
        
        dialogue = last_turn["dialogue"].lower()
        if any(kw in dialogue for kw in farewell_keywords):
            return True
        
        # Check for very short responses (conversation dying)
        if len(dialogue.split()) < 3 and len(history) > 4:
            return True
        
        return False

    async def gossip_cascade(
        self,
        npcs: List[NPCState],
        crime_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Simulate gossip spreading through a group of NPCs.
        Each NPC shares what they know with others nearby.
        """
        gossip_sessions = []
        
        # NPCs who know about the crime
        informed_npcs = [npc for npc in npcs if crime_id in npc.known_crimes]
        uninformed_npcs = [npc for npc in npcs if crime_id not in npc.known_crimes]
        
        if not informed_npcs or not uninformed_npcs:
            return gossip_sessions
        
        # Pair informed with uninformed for gossip
        for informed in informed_npcs[:3]:  # Limit to avoid explosion
            for uninformed in uninformed_npcs[:2]:
                if informed.location == uninformed.location:
                    # Quick gossip exchange
                    crime_info = informed.known_crimes[crime_id]
                    
                    conversation = await self.conduct_conversation(
                        npcs=[informed, uninformed],
                        topic=f"gossip_about_{crime_info.get('crime_type')}",
                        max_turns=4,
                    )
                    
                    gossip_sessions.append({
                        "gossiper": informed.name,
                        "listener": uninformed.name,
                        "crime_id": crime_id,
                        "conversation": conversation,
                    })
                    
                    # Listener now knows about the crime (with reduced fidelity)
                    uninformed.known_crimes[crime_id] = {
                        **crime_info,
                        "awareness_level": "vague_rumor",
                        "heard_from": informed.npc_id,
                    }
        
        return gossip_sessions


# Singleton
multi_npc_conversation = MultiNPCConversation()
