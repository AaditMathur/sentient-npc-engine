"""
Cultural Memory & Legends System — Collective NPC Memory

Tracks how events become part of cultural memory:
- Repeated rumors become folklore
- Major events become legends
- Player reputation becomes legendary (hero or villain)
- NPCs tell stories about past events
- Cultural narratives evolve over time

Legends have:
- Fidelity (how accurate they are)
- Embellishment (how exaggerated)
- Spread (how many NPCs know them)
- Persistence (how long they last)
"""
from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class LegendType(str, Enum):
    HERO_TALE = "hero_tale"
    VILLAIN_TALE = "villain_tale"
    TRAGEDY = "tragedy"
    COMEDY = "comedy"
    MYSTERY = "mystery"
    ROMANCE = "romance"
    EPIC_BATTLE = "epic_battle"
    GREAT_HEIST = "great_heist"
    PROPHECY = "prophecy"
    CURSE = "curse"
    MIRACLE = "miracle"


class LegendStatus(str, Enum):
    RUMOR = "rumor"              # Just started spreading
    STORY = "story"              # People tell it as a story
    FOLKLORE = "folklore"        # Widely known, part of culture
    LEGEND = "legend"            # Legendary status, may be embellished
    MYTH = "myth"                # So old/embellished it's mythical


class Legend(BaseModel):
    """A cultural narrative that spreads through NPC population."""
    legend_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    legend_type: LegendType
    status: LegendStatus = LegendStatus.RUMOR
    
    # Content
    title: str
    original_event: str
    current_version: str
    embellishments: List[str] = []
    
    # Protagonist(s)
    protagonist_id: Optional[str] = None
    protagonist_name: str
    protagonist_reputation: float = 0.0  # -1 (villain) to +1 (hero)
    
    # Metrics
    fidelity: float = 1.0  # How accurate (1.0 = perfect, 0.0 = completely false)
    embellishment_factor: float = 0.0  # How exaggerated (0.0 = accurate, 1.0 = wildly exaggerated)
    spread: int = 0  # How many NPCs know this legend
    persistence: float = 1.0  # How long it will last (decays over time)
    
    # Spread tracking
    known_by: List[str] = []  # NPC IDs who know this legend
    told_count: int = 0  # How many times it's been told
    
    # Temporal
    original_event_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    legend_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_told: Optional[datetime] = None
    
    # Context
    location: Optional[str] = None
    faction: Optional[str] = None
    related_legends: List[str] = []  # Other legend IDs
    
    # Metadata
    tags: List[str] = []
    moral_lesson: Optional[str] = None


class CulturalMemory:
    """
    Manages collective memory and legend formation across NPC population.
    
    Legends form when:
    - Events are retold multiple times
    - Events have high emotional impact
    - Events involve famous/infamous characters
    - Time passes and details become fuzzy
    """

    def __init__(self):
        self.legends: Dict[str, Legend] = {}
        self.protagonist_reputations: Dict[str, float] = {}  # actor_id -> reputation
        self.legend_tellings: List[Dict[str, Any]] = []  # History of who told what to whom

    def create_legend_from_event(
        self,
        event_description: str,
        protagonist_id: str,
        protagonist_name: str,
        event_type: str,
        severity: float,
        witnesses: List[str],
        location: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Legend]:
        """
        Create a legend from a significant event.
        
        Only creates legends for events that are:
        - High severity (> 0.6)
        - Have multiple witnesses
        - Involve interesting event types
        """
        # Filter: only significant events become legends
        if severity < 0.6 or len(witnesses) < 2:
            return None
        
        # Determine legend type
        legend_type = self._classify_legend_type(event_type, severity, metadata)
        
        # Determine protagonist reputation
        reputation = self._calculate_reputation(event_type, severity, metadata)
        
        # Create legend
        legend = Legend(
            legend_type=legend_type,
            title=self._generate_title(protagonist_name, event_type, legend_type),
            original_event=event_description,
            current_version=event_description,
            protagonist_id=protagonist_id,
            protagonist_name=protagonist_name,
            protagonist_reputation=reputation,
            fidelity=1.0,
            spread=len(witnesses),
            known_by=witnesses.copy(),
            location=location,
            tags=[event_type, legend_type.value],
        )
        
        self.legends[legend.legend_id] = legend
        
        # Update protagonist reputation
        if protagonist_id not in self.protagonist_reputations:
            self.protagonist_reputations[protagonist_id] = 0.0
        
        # Reputation changes based on legend
        rep_change = reputation * severity * 0.3
        self.protagonist_reputations[protagonist_id] += rep_change
        self.protagonist_reputations[protagonist_id] = max(
            -1.0, min(1.0, self.protagonist_reputations[protagonist_id])
        )
        
        logger.info(
            "legend_created",
            legend_id=legend.legend_id,
            title=legend.title,
            protagonist=protagonist_name,
            reputation=reputation,
            spread=legend.spread,
        )
        
        return legend

    def _classify_legend_type(
        self,
        event_type: str,
        severity: float,
        metadata: Optional[Dict[str, Any]],
    ) -> LegendType:
        """Classify what type of legend this should be."""
        event_type_lower = event_type.lower()
        
        if "dragon" in event_type_lower or "battle" in event_type_lower:
            return LegendType.EPIC_BATTLE
        elif "theft" in event_type_lower or "heist" in event_type_lower:
            return LegendType.GREAT_HEIST
        elif "murder" in event_type_lower or "assassination" in event_type_lower:
            if severity > 0.8:
                return LegendType.TRAGEDY
            else:
                return LegendType.VILLAIN_TALE
        elif "rescue" in event_type_lower or "save" in event_type_lower:
            return LegendType.HERO_TALE
        elif "love" in event_type_lower or "romance" in event_type_lower:
            return LegendType.ROMANCE
        elif "mystery" in event_type_lower or "unknown" in event_type_lower:
            return LegendType.MYSTERY
        elif severity > 0.8:
            return LegendType.TRAGEDY
        else:
            return LegendType.HERO_TALE

    def _calculate_reputation(
        self,
        event_type: str,
        severity: float,
        metadata: Optional[Dict[str, Any]],
    ) -> float:
        """Calculate reputation change from event (-1 to +1)."""
        event_type_lower = event_type.lower()
        
        # Heroic acts
        if any(word in event_type_lower for word in ["rescue", "save", "protect", "defend"]):
            return 0.5 + (severity * 0.5)
        
        # Villainous acts
        if any(word in event_type_lower for word in ["murder", "theft", "assault", "crime"]):
            return -0.5 - (severity * 0.5)
        
        # Neutral/ambiguous
        return 0.0

    def _generate_title(
        self,
        protagonist_name: str,
        event_type: str,
        legend_type: LegendType,
    ) -> str:
        """Generate a dramatic title for the legend."""
        templates = {
            LegendType.HERO_TALE: [
                f"The Heroic Deeds of {protagonist_name}",
                f"{protagonist_name} the Brave",
                f"How {protagonist_name} Saved the Day",
            ],
            LegendType.VILLAIN_TALE: [
                f"The Villainy of {protagonist_name}",
                f"{protagonist_name} the Wicked",
                f"The Dark Deeds of {protagonist_name}",
            ],
            LegendType.EPIC_BATTLE: [
                f"The Battle of {protagonist_name}",
                f"{protagonist_name}'s Greatest Fight",
                f"The Day {protagonist_name} Fought the Dragon",
            ],
            LegendType.GREAT_HEIST: [
                f"The Great Heist of {protagonist_name}",
                f"How {protagonist_name} Stole the Crown",
                f"{protagonist_name} the Master Thief",
            ],
            LegendType.TRAGEDY: [
                f"The Tragedy of {protagonist_name}",
                f"The Fall of {protagonist_name}",
                f"{protagonist_name}'s Doom",
            ],
            LegendType.ROMANCE: [
                f"The Love Story of {protagonist_name}",
                f"{protagonist_name}'s Heart",
                f"The Romance of {protagonist_name}",
            ],
            LegendType.MYSTERY: [
                f"The Mystery of {protagonist_name}",
                f"{protagonist_name}'s Secret",
                f"The Enigma of {protagonist_name}",
            ],
        }
        
        options = templates.get(legend_type, [f"The Tale of {protagonist_name}"])
        return options[0]

    def tell_legend(
        self,
        legend_id: str,
        teller_id: str,
        listener_id: str,
        embellish: bool = False,
    ) -> Dict[str, Any]:
        """
        An NPC tells a legend to another NPC.
        
        Each telling:
        - Increases spread
        - May add embellishments
        - Reduces fidelity slightly
        - Updates status if spread threshold reached
        """
        legend = self.legends.get(legend_id)
        if not legend:
            return {"error": "Legend not found"}
        
        # Record telling
        telling = {
            "legend_id": legend_id,
            "teller_id": teller_id,
            "listener_id": listener_id,
            "timestamp": datetime.now(timezone.utc),
            "embellished": embellish,
        }
        self.legend_tellings.append(telling)
        
        # Update legend
        legend.told_count += 1
        legend.last_told = datetime.now(timezone.utc)
        
        # Listener now knows the legend
        if listener_id not in legend.known_by:
            legend.known_by.append(listener_id)
            legend.spread += 1
        
        # Embellishment
        if embellish:
            legend.embellishment_factor = min(1.0, legend.embellishment_factor + 0.1)
            legend.fidelity = max(0.0, legend.fidelity - 0.05)
            
            # Add embellishment
            embellishments = [
                "and the dragon was twice as large!",
                "with a sword that glowed with holy fire!",
                "single-handedly defeating an army!",
                "while the gods themselves watched!",
                "in a storm of epic proportions!",
            ]
            import random
            if random.random() < 0.3:
                legend.embellishments.append(random.choice(embellishments))
        else:
            # Even accurate retellings lose some fidelity
            legend.fidelity = max(0.0, legend.fidelity - 0.02)
        
        # Update status based on spread
        self._update_legend_status(legend)
        
        logger.debug(
            "legend_told",
            legend_id=legend_id,
            title=legend.title,
            teller=teller_id,
            listener=listener_id,
            spread=legend.spread,
            status=legend.status.value,
        )
        
        return {
            "legend_id": legend_id,
            "title": legend.title,
            "version": self._get_current_version(legend),
            "spread": legend.spread,
            "status": legend.status.value,
            "fidelity": legend.fidelity,
        }

    def _update_legend_status(self, legend: Legend) -> None:
        """Update legend status based on spread and age."""
        age_days = (datetime.now(timezone.utc) - legend.legend_created_at).days
        
        if legend.spread >= 50 and age_days >= 30:
            legend.status = LegendStatus.MYTH
        elif legend.spread >= 30 and age_days >= 14:
            legend.status = LegendStatus.LEGEND
        elif legend.spread >= 15 and age_days >= 7:
            legend.status = LegendStatus.FOLKLORE
        elif legend.spread >= 5:
            legend.status = LegendStatus.STORY
        else:
            legend.status = LegendStatus.RUMOR

    def _get_current_version(self, legend: Legend) -> str:
        """Get the current (possibly embellished) version of the legend."""
        version = legend.original_event
        
        if legend.embellishments:
            version += " " + " ".join(legend.embellishments[-3:])  # Last 3 embellishments
        
        return version

    def get_protagonist_reputation(self, protagonist_id: str) -> Dict[str, Any]:
        """
        Get a protagonist's reputation based on legends.
        
        Returns:
            - Overall reputation score
            - Number of legends
            - Reputation category (hero, villain, neutral)
            - Famous legends
        """
        reputation = self.protagonist_reputations.get(protagonist_id, 0.0)
        
        # Find legends about this protagonist
        protagonist_legends = [
            legend for legend in self.legends.values()
            if legend.protagonist_id == protagonist_id
        ]
        
        # Sort by spread
        protagonist_legends.sort(key=lambda l: l.spread, reverse=True)
        
        # Categorize
        if reputation > 0.5:
            category = "hero"
        elif reputation < -0.5:
            category = "villain"
        elif reputation > 0.2:
            category = "respected"
        elif reputation < -0.2:
            category = "disliked"
        else:
            category = "neutral"
        
        return {
            "protagonist_id": protagonist_id,
            "reputation_score": reputation,
            "category": category,
            "legend_count": len(protagonist_legends),
            "most_famous_legend": protagonist_legends[0].title if protagonist_legends else None,
            "total_spread": sum(l.spread for l in protagonist_legends),
            "legends": [
                {
                    "title": l.title,
                    "type": l.legend_type.value,
                    "status": l.status.value,
                    "spread": l.spread,
                }
                for l in protagonist_legends[:5]
            ],
        }

    def get_cultural_narratives(
        self,
        location: Optional[str] = None,
        faction: Optional[str] = None,
        min_spread: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get the dominant cultural narratives (widely known legends).
        
        Args:
            location: Filter by location
            faction: Filter by faction
            min_spread: Minimum spread to be considered
        
        Returns:
            List of cultural narratives
        """
        filtered_legends = []
        
        for legend in self.legends.values():
            if legend.spread < min_spread:
                continue
            
            if location and legend.location != location:
                continue
            
            if faction and legend.faction != faction:
                continue
            
            filtered_legends.append(legend)
        
        # Sort by spread and status
        status_weight = {
            LegendStatus.MYTH: 5,
            LegendStatus.LEGEND: 4,
            LegendStatus.FOLKLORE: 3,
            LegendStatus.STORY: 2,
            LegendStatus.RUMOR: 1,
        }
        
        filtered_legends.sort(
            key=lambda l: (status_weight[l.status] * 100 + l.spread),
            reverse=True,
        )
        
        return [
            {
                "legend_id": l.legend_id,
                "title": l.title,
                "type": l.legend_type.value,
                "status": l.status.value,
                "protagonist": l.protagonist_name,
                "reputation": l.protagonist_reputation,
                "spread": l.spread,
                "fidelity": l.fidelity,
                "embellishment": l.embellishment_factor,
                "current_version": self._get_current_version(l),
                "age_days": (datetime.now(timezone.utc) - l.legend_created_at).days,
            }
            for l in filtered_legends[:20]
        ]

    def decay_legends(self, decay_rate: float = 0.01) -> None:
        """
        Decay old legends that aren't being retold.
        
        Legends that aren't told fade from memory.
        """
        now = datetime.now(timezone.utc)
        
        for legend in self.legends.values():
            # Check when last told
            if legend.last_told:
                days_since_told = (now - legend.last_told).days
            else:
                days_since_told = (now - legend.legend_created_at).days
            
            # Decay persistence
            if days_since_told > 7:
                legend.persistence -= decay_rate * (days_since_told / 7)
                legend.persistence = max(0.0, legend.persistence)
            
            # Remove from NPCs' knowledge if persistence too low
            if legend.persistence < 0.3:
                # Forget from some NPCs
                forget_count = max(1, len(legend.known_by) // 10)
                legend.known_by = legend.known_by[forget_count:]
                legend.spread = len(legend.known_by)


# Singleton
cultural_memory = CulturalMemory()
