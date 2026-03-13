"""
Dynamic Quest Generation — NPCs Create Quests Based on Goals & Events

NPCs autonomously generate quests when:
- Their goals are blocked
- They experience strong emotions
- World events affect them
- Crimes are committed against them

Quest types:
- Revenge quests (after being wronged)
- Protection quests (when afraid)
- Retrieval quests (when items stolen)
- Escort quests (when needing to travel)
- Investigation quests (when curious about events)
"""
from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from app.models import (
    NPCState, Goal,
    CrimeRecord, CrimeType,
)
import structlog

logger = structlog.get_logger()


class QuestType(str, Enum):
    REVENGE = "revenge"
    PROTECTION = "protection"
    RETRIEVAL = "retrieval"
    ESCORT = "escort"
    INVESTIGATION = "investigation"
    BOUNTY = "bounty"
    DELIVERY = "delivery"
    RESCUE = "rescue"
    ASSASSINATION = "assassination"
    DIPLOMACY = "diplomacy"


class QuestDifficulty(str, Enum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    LEGENDARY = "legendary"


class QuestReward(BaseModel):
    gold: int = 0
    items: List[str] = []
    reputation: Dict[str, int] = {}  # faction -> reputation change
    experience: int = 0
    special: Optional[str] = None


class Quest(BaseModel):
    quest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quest_type: QuestType
    title: str
    description: str
    quest_giver_id: str
    quest_giver_name: str
    
    # Objectives
    objectives: List[Dict[str, Any]] = []
    current_objective_index: int = 0
    
    # Requirements
    difficulty: QuestDifficulty = QuestDifficulty.MODERATE
    required_level: int = 1
    time_limit: Optional[datetime] = None
    
    # Rewards
    rewards: QuestReward = Field(default_factory=QuestReward)
    
    # State
    status: str = "available"  # available, active, completed, failed, expired
    accepted_by: Optional[str] = None
    progress: float = 0.0
    
    # Context
    related_crime_id: Optional[str] = None
    related_event_id: Optional[str] = None
    target_npc_id: Optional[str] = None
    target_location: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Emotional context
    emotional_intensity: float = 0.5
    urgency: float = 0.5


class DynamicQuestGenerator:
    """Generates quests dynamically based on NPC state and world events."""

    def __init__(self):
        self.active_quests: Dict[str, Quest] = {}
        self.quest_templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[QuestType, Dict[str, Any]]:
        """Define quest templates for each type."""
        return {
            QuestType.REVENGE: {
                "title_template": "Avenge {victim_name}",
                "description_template": (
                    "{quest_giver} seeks revenge against {perpetrator} "
                    "for {crime_description}. They want justice."
                ),
                "objectives": [
                    {"type": "confront", "target": "{perpetrator}"},
                    {"type": "report_back", "target": "{quest_giver}"},
                ],
            },
            QuestType.BOUNTY: {
                "title_template": "Bounty: {perpetrator_name}",
                "description_template": (
                    "{quest_giver} is offering a bounty for the capture or elimination "
                    "of {perpetrator}, wanted for {crime_type}."
                ),
                "objectives": [
                    {"type": "find", "target": "{perpetrator}"},
                    {"type": "defeat_or_capture", "target": "{perpetrator}"},
                    {"type": "collect_reward", "target": "{quest_giver}"},
                ],
            },
            QuestType.RETRIEVAL: {
                "title_template": "Recover Stolen {item_name}",
                "description_template": (
                    "{quest_giver} had their {item_name} stolen by {perpetrator}. "
                    "They desperately need it back."
                ),
                "objectives": [
                    {"type": "locate", "target": "{perpetrator}"},
                    {"type": "retrieve", "item": "{item_name}"},
                    {"type": "return", "target": "{quest_giver}"},
                ],
            },
            QuestType.PROTECTION: {
                "title_template": "Protect {quest_giver_name}",
                "description_template": (
                    "{quest_giver} is afraid of {threat} and needs protection. "
                    "Keep them safe for {duration}."
                ),
                "objectives": [
                    {"type": "escort", "target": "{quest_giver}", "destination": "{safe_location}"},
                    {"type": "defend", "target": "{quest_giver}", "duration": "{duration}"},
                ],
            },
            QuestType.INVESTIGATION: {
                "title_template": "Investigate {event_name}",
                "description_template": (
                    "{quest_giver} wants to know the truth about {event_description}. "
                    "Gather information and report back."
                ),
                "objectives": [
                    {"type": "gather_clues", "count": 3, "location": "{investigation_area}"},
                    {"type": "interview", "targets": ["{witness1}", "{witness2}"]},
                    {"type": "report_findings", "target": "{quest_giver}"},
                ],
            },
            QuestType.RESCUE: {
                "title_template": "Rescue {target_name}",
                "description_template": (
                    "{target_name} is in danger at {location}. "
                    "{quest_giver} needs someone to rescue them immediately."
                ),
                "objectives": [
                    {"type": "travel_to", "location": "{location}"},
                    {"type": "rescue", "target": "{target_name}"},
                    {"type": "escort_to_safety", "destination": "{safe_location}"},
                ],
            },
        }

    def generate_quest_from_crime(
        self,
        npc: NPCState,
        crime: CrimeRecord,
        awareness_level: str,
    ) -> Optional[Quest]:
        """
        Generate a quest when an NPC learns about a crime.
        
        Quest type depends on:
        - NPC's relationship to victim
        - Crime severity
        - NPC's personality and emotions
        - Awareness level
        """
        # Only direct witnesses or victims generate quests
        if awareness_level not in ["direct_witness", "victim"]:
            # Vague rumors don't generate quests
            if npc.personality.curiosity < 0.7:
                return None
        
        # Determine quest type based on NPC state
        quest_type = self._determine_crime_quest_type(npc, crime)
        if not quest_type:
            return None
        
        # Generate quest based on type
        if quest_type == QuestType.REVENGE:
            return self._generate_revenge_quest(npc, crime)
        elif quest_type == QuestType.BOUNTY:
            return self._generate_bounty_quest(npc, crime)
        elif quest_type == QuestType.RETRIEVAL:
            return self._generate_retrieval_quest(npc, crime)
        elif quest_type == QuestType.INVESTIGATION:
            return self._generate_investigation_quest(npc, crime)
        
        return None

    def _determine_crime_quest_type(
        self,
        npc: NPCState,
        crime: CrimeRecord,
    ) -> Optional[QuestType]:
        """Determine what type of quest NPC would create."""
        # Victim or high anger -> revenge
        if crime.victim_id == npc.npc_id or npc.emotion_state.anger > 0.7:
            if npc.personality.aggression > 0.5:
                return QuestType.REVENGE
            else:
                return QuestType.BOUNTY
        
        # Theft -> retrieval
        if crime.crime_type == CrimeType.THEFT:
            if crime.victim_id == npc.npc_id:
                return QuestType.RETRIEVAL
            elif npc.personality.honesty > 0.7:
                return QuestType.BOUNTY
        
        # High curiosity -> investigation
        if npc.personality.curiosity > 0.7:
            return QuestType.INVESTIGATION
        
        # Guards and lawful NPCs create bounties
        if npc.archetype.lower() in ["guard", "sheriff", "captain"]:
            return QuestType.BOUNTY
        
        return None

    def _generate_revenge_quest(
        self,
        npc: NPCState,
        crime: CrimeRecord,
    ) -> Quest:
        """Generate a revenge quest."""
        
        # Calculate rewards based on severity and NPC wealth
        base_gold = int(crime.severity * 500)
        if npc.archetype.lower() == "merchant":
            base_gold *= 2
        
        # Emotional intensity affects urgency
        urgency = min(1.0, npc.emotion_state.anger + crime.severity) / 2
        
        quest = Quest(
            quest_type=QuestType.REVENGE,
            title=f"Avenge {crime.victim_name or 'the Victim'}",
            description=(
                f"{npc.name} seeks revenge against {crime.perpetrator_id} "
                f"for {crime.crime_type.value}. {crime.description}"
            ),
            quest_giver_id=npc.npc_id,
            quest_giver_name=npc.name,
            objectives=[
                {
                    "type": "confront",
                    "target": crime.perpetrator_id,
                    "description": f"Confront {crime.perpetrator_id} about the {crime.crime_type.value}",
                },
                {
                    "type": "report_back",
                    "target": npc.npc_id,
                    "description": f"Report back to {npc.name}",
                },
            ],
            difficulty=self._calculate_difficulty(crime.severity),
            rewards=QuestReward(
                gold=base_gold,
                reputation={npc.faction: 50} if npc.faction else {},
                experience=int(crime.severity * 200),
            ),
            related_crime_id=crime.crime_id,
            target_npc_id=crime.perpetrator_id,
            emotional_intensity=npc.emotion_state.anger,
            urgency=urgency,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        self.active_quests[quest.quest_id] = quest
        logger.info(
            "quest_generated",
            quest_id=quest.quest_id,
            quest_type=quest.quest_type.value,
            quest_giver=npc.name,
        )
        
        return quest

    def _generate_bounty_quest(
        self,
        npc: NPCState,
        crime: CrimeRecord,
    ) -> Quest:
        """Generate a bounty quest."""
        base_gold = int(crime.severity * 1000)
        
        quest = Quest(
            quest_type=QuestType.BOUNTY,
            title=f"Bounty: {crime.perpetrator_id}",
            description=(
                f"{npc.name} is offering a bounty for {crime.perpetrator_id}, "
                f"wanted for {crime.crime_type.value}. {crime.description}"
            ),
            quest_giver_id=npc.npc_id,
            quest_giver_name=npc.name,
            objectives=[
                {
                    "type": "find",
                    "target": crime.perpetrator_id,
                    "description": f"Locate {crime.perpetrator_id}",
                },
                {
                    "type": "capture_or_defeat",
                    "target": crime.perpetrator_id,
                    "description": f"Capture or defeat {crime.perpetrator_id}",
                },
                {
                    "type": "collect_reward",
                    "target": npc.npc_id,
                    "description": f"Collect reward from {npc.name}",
                },
            ],
            difficulty=self._calculate_difficulty(crime.severity),
            rewards=QuestReward(
                gold=base_gold,
                reputation={npc.faction: 75} if npc.faction else {},
                experience=int(crime.severity * 300),
                special="Bounty Hunter reputation",
            ),
            related_crime_id=crime.crime_id,
            target_npc_id=crime.perpetrator_id,
            emotional_intensity=crime.severity,
            urgency=0.7,
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        
        self.active_quests[quest.quest_id] = quest
        return quest

    def _generate_retrieval_quest(
        self,
        npc: NPCState,
        crime: CrimeRecord,
    ) -> Quest:
        """Generate an item retrieval quest."""
        item_name = crime.metadata.get("stolen_item", "stolen goods")
        
        quest = Quest(
            quest_type=QuestType.RETRIEVAL,
            title=f"Recover Stolen {item_name}",
            description=(
                f"{npc.name} had their {item_name} stolen by {crime.perpetrator_id}. "
                f"They desperately need it back. {crime.description}"
            ),
            quest_giver_id=npc.npc_id,
            quest_giver_name=npc.name,
            objectives=[
                {
                    "type": "locate",
                    "target": crime.perpetrator_id,
                    "description": f"Find {crime.perpetrator_id}",
                },
                {
                    "type": "retrieve",
                    "item": item_name,
                    "description": f"Retrieve the {item_name}",
                },
                {
                    "type": "return",
                    "target": npc.npc_id,
                    "description": f"Return the {item_name} to {npc.name}",
                },
            ],
            difficulty=self._calculate_difficulty(crime.severity * 0.8),
            rewards=QuestReward(
                gold=int(crime.severity * 400),
                reputation={npc.faction: 40} if npc.faction else {},
                experience=int(crime.severity * 150),
            ),
            related_crime_id=crime.crime_id,
            target_npc_id=crime.perpetrator_id,
            emotional_intensity=npc.emotion_state.sadness + npc.emotion_state.anger,
            urgency=0.6,
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        
        self.active_quests[quest.quest_id] = quest
        return quest

    def _generate_investigation_quest(
        self,
        npc: NPCState,
        crime: CrimeRecord,
    ) -> Quest:
        """Generate an investigation quest."""
        quest = Quest(
            quest_type=QuestType.INVESTIGATION,
            title=f"Investigate the {crime.crime_type.value}",
            description=(
                f"{npc.name} wants to know the truth about the {crime.crime_type.value} "
                f"that occurred at {crime.location or 'an unknown location'}. "
                f"Gather evidence and interview witnesses."
            ),
            quest_giver_id=npc.npc_id,
            quest_giver_name=npc.name,
            objectives=[
                {
                    "type": "gather_clues",
                    "count": 3,
                    "location": crime.location,
                    "description": f"Gather 3 clues at {crime.location}",
                },
                {
                    "type": "interview_witnesses",
                    "targets": crime.witnesses[:2] if crime.witnesses else [],
                    "description": "Interview witnesses",
                },
                {
                    "type": "report_findings",
                    "target": npc.npc_id,
                    "description": f"Report findings to {npc.name}",
                },
            ],
            difficulty=QuestDifficulty.MODERATE,
            rewards=QuestReward(
                gold=int(crime.severity * 300),
                reputation={npc.faction: 30} if npc.faction else {},
                experience=int(crime.severity * 180),
                special="Investigation skill increase",
            ),
            related_crime_id=crime.crime_id,
            target_location=crime.location,
            emotional_intensity=npc.personality.curiosity,
            urgency=0.4,
            expires_at=datetime.now(timezone.utc) + timedelta(days=21),
        )
        
        self.active_quests[quest.quest_id] = quest
        return quest

    def generate_quest_from_goal(
        self,
        npc: NPCState,
        goal: Goal,
    ) -> Optional[Quest]:
        """Generate a quest when NPC's goal is blocked or needs help."""
        # Only generate quests for high-priority goals
        if goal.current_priority < 0.6:
            return None
        
        # Map goal types to quest types
        goal_to_quest = {
            "increase_wealth": QuestType.DELIVERY,
            "seek_revenge": QuestType.REVENGE,
            "find_safety": QuestType.PROTECTION,
            "gather_information": QuestType.INVESTIGATION,
        }
        
        quest_type = goal_to_quest.get(goal.name)
        if not quest_type:
            return None
        
        # Generate appropriate quest
        # (Implementation would be similar to crime quests)
        return None

    def _calculate_difficulty(self, severity: float) -> QuestDifficulty:
        """Calculate quest difficulty from severity."""
        if severity < 0.2:
            return QuestDifficulty.TRIVIAL
        elif severity < 0.4:
            return QuestDifficulty.EASY
        elif severity < 0.7:
            return QuestDifficulty.MODERATE
        elif severity < 0.9:
            return QuestDifficulty.HARD
        else:
            return QuestDifficulty.LEGENDARY

    def get_available_quests(
        self,
        player_id: Optional[str] = None,
        location: Optional[str] = None,
        quest_type: Optional[QuestType] = None,
    ) -> List[Quest]:
        """Get all available quests matching filters."""
        quests = []
        
        for quest in self.active_quests.values():
            # Filter by status
            if quest.status != "available":
                continue
            
            # Filter by location
            if location and quest.target_location and quest.target_location != location:
                continue
            
            # Filter by type
            if quest_type and quest.quest_type != quest_type:
                continue
            
            # Check expiration
            if quest.expires_at and quest.expires_at < datetime.now(timezone.utc):
                quest.status = "expired"
                continue
            
            quests.append(quest)
        
        # Sort by urgency and emotional intensity
        quests.sort(
            key=lambda q: (q.urgency * q.emotional_intensity),
            reverse=True,
        )
        
        return quests


# Singleton
quest_generator = DynamicQuestGenerator()
