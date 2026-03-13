"""
Core Pydantic models for Sentient NPC Engine 3.0
These are the canonical data structures used across all subsystems.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class MemoryType(str, Enum):
    EPISODIC = "episodic"      # specific events
    SEMANTIC = "semantic"      # general knowledge/facts
    EMOTIONAL = "emotional"    # emotionally charged events


class GoalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"


class RelationshipType(str, Enum):
    FRIEND = "friend"
    ENEMY = "enemy"
    NEUTRAL = "neutral"
    ALLY = "ally"
    RIVAL = "rival"
    ROMANTIC = "romantic"


class EventType(str, Enum):
    DRAGON_KILLED = "dragon_killed"
    MARKET_FIRE = "market_fire"
    PLAYER_ATTACK = "player_attack"
    THEFT = "theft"
    GIFT = "gift"
    RUMOR = "rumor"
    WAR_DECLARED = "war_declared"
    PLAGUE = "plague"
    FESTIVAL = "festival"
    ASSASSINATION = "assassination"
    CRIME_COMMITTED = "crime_committed"
    RUMOR_HEARD = "rumor_heard"
    CUSTOM = "custom"


class CrimeType(str, Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    MURDER = "murder"
    ARSON = "arson"
    TRESPASSING = "trespassing"
    FRAUD = "fraud"


class AwarenessLevel(str, Enum):
    DIRECT_WITNESS = "direct_witness"   # saw it happen
    RELIABLE_RUMOR = "reliable_rumor"   # heard from trusted source (hop 1)
    VAGUE_RUMOR = "vague_rumor"         # distorted info (hop 2+)
    UNCONFIRMED = "unconfirmed"         # barely credible (hop 3+)


class SocialClass(str, Enum):
    NOBLE = "noble"
    MERCHANT = "merchant"
    CRAFTSMAN = "craftsman"
    PEASANT = "peasant"
    CLERGY = "clergy"
    SOLDIER = "soldier"
    OUTLAW = "outlaw"
    SLAVE = "slave"


# ─────────────────────────────────────────────
# PERSONALITY
# ─────────────────────────────────────────────

class PersonalityVector(BaseModel):
    """
    Big-5 inspired NPC personality traits.
    All values normalized 0.0 → 1.0
    """
    greed: float = Field(0.5, ge=0.0, le=1.0)
    bravery: float = Field(0.5, ge=0.0, le=1.0)
    empathy: float = Field(0.5, ge=0.0, le=1.0)
    loyalty: float = Field(0.5, ge=0.0, le=1.0)
    curiosity: float = Field(0.5, ge=0.0, le=1.0)
    honesty: float = Field(0.5, ge=0.0, le=1.0)
    aggression: float = Field(0.3, ge=0.0, le=1.0)

    def to_dict(self) -> Dict[str, float]:
        return self.model_dump()

    def describe(self) -> str:
        """Natural language description of dominant traits."""
        traits = []
        if self.greed > 0.7:
            traits.append("greedy")
        if self.bravery > 0.7:
            traits.append("brave")
        elif self.bravery < 0.3:
            traits.append("cowardly")
        if self.empathy > 0.7:
            traits.append("empathetic")
        elif self.empathy < 0.3:
            traits.append("cold-hearted")
        if self.loyalty > 0.7:
            traits.append("deeply loyal")
        if self.curiosity > 0.7:
            traits.append("curious")
        if self.honesty > 0.7:
            traits.append("honest")
        elif self.honesty < 0.3:
            traits.append("deceptive")
        if self.aggression > 0.7:
            traits.append("aggressive")
        return ", ".join(traits) if traits else "balanced"


class PersonalityDynamics(BaseModel):
    """How personality changes over time"""
    base_personality: PersonalityVector = Field(default_factory=PersonalityVector)
    current_personality: PersonalityVector = Field(default_factory=PersonalityVector)
    openness_to_change: float = Field(0.5, ge=0.0, le=1.0)
    personality_stability: float = Field(0.7, ge=0.0, le=1.0)
    recent_influences: List[Dict[str, Any]] = []
    long_term_trends: Dict[str, float] = {}
    maturity_level: float = Field(0.5, ge=0.0, le=1.0)
    life_satisfaction: float = Field(0.5, ge=0.0, le=1.0)


# ─────────────────────────────────────────────
# EMOTIONS
# ─────────────────────────────────────────────

class EmotionVector(BaseModel):
    """
    Plutchik's wheel-inspired 6D emotion state.
    All values normalized 0.0 → 1.0
    """
    joy: float = Field(0.5, ge=0.0, le=1.0)
    trust: float = Field(0.5, ge=0.0, le=1.0)
    fear: float = Field(0.0, ge=0.0, le=1.0)
    anger: float = Field(0.0, ge=0.0, le=1.0)
    sadness: float = Field(0.0, ge=0.0, le=1.0)
    surprise: float = Field(0.0, ge=0.0, le=1.0)
    disgust: float = Field(0.0, ge=0.0, le=1.0)
    anticipation: float = Field(0.3, ge=0.0, le=1.0)

    def dominant(self) -> str:
        emotions = self.model_dump()
        return max(emotions, key=emotions.get)

    def valence(self) -> float:
        """Overall positive/negative mood -1.0 → +1.0"""
        positive = (self.joy + self.trust + self.anticipation) / 3
        negative = (self.fear + self.anger + self.sadness + self.disgust) / 4
        return positive - negative

    def arousal(self) -> float:
        """Energy level 0.0 → 1.0"""
        return (self.anger + self.fear + self.joy + self.surprise) / 4

    def to_dict(self) -> Dict[str, float]:
        return self.model_dump()


# ─────────────────────────────────────────────
# PHYSIOLOGICAL & BIOLOGICAL SYSTEMS
# ─────────────────────────────────────────────

class Injury(BaseModel):
    injury_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    injury_type: str
    severity: float = Field(0.5, ge=0.0, le=1.0)
    location: str
    healing_rate: float = 0.1
    affects_mobility: bool = False
    affects_combat: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Disease(BaseModel):
    disease_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    disease_name: str
    severity: float = Field(0.5, ge=0.0, le=1.0)
    contagious: bool = False
    symptoms: List[str] = []
    progression_rate: float = 0.1
    contracted_at: datetime = Field(default_factory=datetime.utcnow)


class StatusEffect(BaseModel):
    effect_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    effect_name: str
    effect_type: str  # "buff" or "debuff"
    magnitude: float = 1.0
    duration_ticks: int = 10
    remaining_ticks: int = 10
    stat_modifiers: Dict[str, float] = {}


class PhysiologicalState(BaseModel):
    """Physical needs and conditions"""
    health: float = Field(1.0, ge=0.0, le=1.0)
    stamina: float = Field(1.0, ge=0.0, le=1.0)
    hunger: float = Field(0.0, ge=0.0, le=1.0)
    thirst: float = Field(0.0, ge=0.0, le=1.0)
    fatigue: float = Field(0.0, ge=0.0, le=1.0)
    pain: float = Field(0.0, ge=0.0, le=1.0)
    intoxication: float = Field(0.0, ge=0.0, le=1.0)
    
    injuries: List[Injury] = []
    diseases: List[Disease] = []
    buffs: List[StatusEffect] = []
    debuffs: List[StatusEffect] = []
    
    circadian_rhythm: float = Field(0.5, ge=0.0, le=1.0)
    sleep_debt: float = Field(0.0, ge=0.0, le=1.0)
    last_meal: Optional[datetime] = None
    last_sleep: Optional[datetime] = None


# ─────────────────────────────────────────────
# SKILLS & COMPETENCIES
# ─────────────────────────────────────────────

class SkillSet(BaseModel):
    """NPC capabilities and expertise"""
    combat_skills: Dict[str, float] = {}
    crafting_skills: Dict[str, float] = {}
    social_skills: Dict[str, float] = {}
    magic_skills: Dict[str, float] = {}
    knowledge_domains: Dict[str, float] = {}
    
    skill_experience: Dict[str, float] = {}
    learning_rate: float = Field(0.5, ge=0.0, le=1.0)
    specializations: List[str] = []
    natural_talents: Dict[str, float] = {}


class Profession(BaseModel):
    """Career and economic role"""
    primary_job: str
    secondary_jobs: List[str] = []
    job_level: int = 1
    job_experience: float = 0.0
    reputation_score: float = Field(0.5, ge=0.0, le=1.0)
    certifications: List[str] = []
    guild_memberships: List[str] = []


# ─────────────────────────────────────────────
# ECONOMIC & INVENTORY SYSTEM
# ─────────────────────────────────────────────

class IncomeSource(BaseModel):
    source_name: str
    amount_per_tick: float
    reliability: float = Field(1.0, ge=0.0, le=1.0)


class Expense(BaseModel):
    expense_name: str
    amount_per_tick: float
    is_recurring: bool = True


class Debt(BaseModel):
    debt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    creditor_id: str
    creditor_name: str
    amount: float
    interest_rate: float = 0.0
    due_date: Optional[datetime] = None


class Item(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    item_type: str
    weight: float = 1.0
    value: float = 0.0
    quality: float = Field(1.0, ge=0.0, le=1.0)
    durability: float = Field(1.0, ge=0.0, le=1.0)
    properties: Dict[str, Any] = {}


class EconomicState(BaseModel):
    """Wealth and resources"""
    currency: Dict[str, float] = {}
    total_wealth: float = 0.0
    income_sources: List[IncomeSource] = []
    expenses: List[Expense] = []
    debts: List[Debt] = []
    
    haggling_skill: float = Field(0.5, ge=0.0, le=1.0)
    price_memory: Dict[str, float] = {}
    preferred_merchants: List[str] = []


class Inventory(BaseModel):
    """What the NPC owns and carries"""
    equipped_items: Dict[str, Item] = {}
    carried_items: List[Item] = []
    stored_items: Dict[str, List[Item]] = {}
    
    max_carry_weight: float = 50.0
    current_weight: float = 0.0
    
    sentimental_items: List[str] = []
    stolen_items: List[str] = []


# ─────────────────────────────────────────────
# SOCIAL DYNAMICS
# ─────────────────────────────────────────────

class SocialIdentity(BaseModel):
    """Social standing and reputation"""
    social_class: SocialClass = SocialClass.PEASANT
    titles: List[str] = []
    
    reputation_by_faction: Dict[str, float] = {}
    reputation_by_location: Dict[str, float] = {}
    fame_level: float = Field(0.0, ge=0.0, le=1.0)
    infamy_level: float = Field(0.0, ge=0.0, le=1.0)
    
    family_members: List[str] = []
    close_friends: List[str] = []
    enemies: List[str] = []
    mentors: List[str] = []
    apprentices: List[str] = []
    
    leadership_score: float = Field(0.5, ge=0.0, le=1.0)
    influence_network: Dict[str, float] = {}


class CulturalBackground(BaseModel):
    """Cultural identity and beliefs"""
    ethnicity: str = "human"
    native_language: str = "common"
    known_languages: List[str] = []
    accent: str = "neutral"
    
    religion: Optional[str] = None
    religious_devotion: float = Field(0.5, ge=0.0, le=1.0)
    political_ideology: str = "neutral"
    moral_alignment: str = "neutral"
    
    customs: List[str] = []
    taboos: List[str] = []
    festivals_celebrated: List[str] = []


# ─────────────────────────────────────────────
# COGNITIVE COMPLEXITY
# ─────────────────────────────────────────────

class TraumaMemory(BaseModel):
    trauma_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_description: str
    severity: float = Field(0.5, ge=0.0, le=1.0)
    triggers: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Addiction(BaseModel):
    addiction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    substance_or_activity: str
    severity: float = Field(0.5, ge=0.0, le=1.0)
    withdrawal_level: float = Field(0.0, ge=0.0, le=1.0)
    last_indulgence: Optional[datetime] = None


class CognitiveState(BaseModel):
    """Mental processes and biases"""
    current_focus: Optional[str] = None
    attention_span: float = Field(0.5, ge=0.0, le=1.0)
    distraction_level: float = Field(0.0, ge=0.0, le=1.0)
    
    intelligence: float = Field(0.5, ge=0.0, le=1.0)
    wisdom: float = Field(0.5, ge=0.0, le=1.0)
    creativity: float = Field(0.5, ge=0.0, le=1.0)
    mental_fatigue: float = Field(0.0, ge=0.0, le=1.0)
    
    confirmation_bias: float = Field(0.5, ge=0.0, le=1.0)
    optimism_bias: float = Field(0.5, ge=0.0, le=1.0)
    risk_aversion: float = Field(0.5, ge=0.0, le=1.0)
    loss_aversion: float = Field(0.5, ge=0.0, le=1.0)
    
    stress_level: float = Field(0.0, ge=0.0, le=1.0)
    anxiety_level: float = Field(0.0, ge=0.0, le=1.0)
    trauma_markers: List[TraumaMemory] = []
    phobias: List[str] = []
    addictions: List[Addiction] = []


class BeliefSystem(BaseModel):
    """What the NPC believes to be true"""
    core_beliefs: Dict[str, float] = {}
    misconceptions: List[str] = []
    conspiracy_theories: List[str] = []
    
    knowledge_confidence: Dict[str, float] = {}
    sources_trusted: List[str] = []
    sources_distrusted: List[str] = []


# ─────────────────────────────────────────────
# TEMPORAL & ROUTINE SYSTEMS
# ─────────────────────────────────────────────

class ScheduledActivity(BaseModel):
    activity_name: str
    location: Optional[str] = None
    duration_hours: float = 1.0
    priority: float = Field(0.5, ge=0.0, le=1.0)


class Habit(BaseModel):
    habit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    habit_name: str
    trigger: str
    frequency: str  # "daily", "weekly", etc.
    strength: float = Field(0.5, ge=0.0, le=1.0)


class Routine(BaseModel):
    routine_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    routine_name: str
    activities: List[str] = []
    time_of_day: str  # "morning", "afternoon", "evening", "night"


class LifeEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_name: str
    description: str
    impact_level: float = Field(0.5, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    age_at_event: Optional[int] = None


class PastRelationship(BaseModel):
    person_id: str
    person_name: str
    relationship_type: str
    duration_days: int
    ended_at: datetime
    reason_ended: str


class DailyRoutine(BaseModel):
    """Predictable behavior patterns"""
    schedule: Dict[int, ScheduledActivity] = {}
    weekly_patterns: Dict[str, List[str]] = {}
    
    habits: List[Habit] = []
    routines: List[Routine] = []
    
    routine_adherence: float = Field(0.7, ge=0.0, le=1.0)
    spontaneity: float = Field(0.3, ge=0.0, le=1.0)


class LifeHistory(BaseModel):
    """Long-term biographical data"""
    age: int = 25
    birthplace: str = "unknown"
    life_events: List[LifeEvent] = []
    
    childhood_memories: List[str] = []
    formative_experiences: List[str] = []
    major_achievements: List[str] = []
    regrets: List[str] = []
    
    past_relationships: List[PastRelationship] = []
    family_history: Dict[str, Any] = {}


# ─────────────────────────────────────────────
# ENVIRONMENTAL AWARENESS
# ─────────────────────────────────────────────

class LocationKnowledge(BaseModel):
    location_name: str
    familiarity: float = Field(0.5, ge=0.0, le=1.0)
    safety_rating: float = Field(0.5, ge=0.0, le=1.0)
    visit_count: int = 0
    last_visited: Optional[datetime] = None
    notable_features: List[str] = []


class SpatialAwareness(BaseModel):
    """Understanding of physical space"""
    known_locations: Dict[str, LocationKnowledge] = {}
    favorite_places: List[str] = []
    avoided_places: List[str] = []
    
    mental_map_quality: float = Field(0.5, ge=0.0, le=1.0)
    sense_of_direction: float = Field(0.5, ge=0.0, le=1.0)
    exploration_tendency: float = Field(0.5, ge=0.0, le=1.0)
    
    home_location: Optional[str] = None
    work_location: Optional[str] = None
    territorial_range: float = 100.0


class ContextualMemory(BaseModel):
    """Context-dependent recall"""
    location_associations: Dict[str, List[str]] = {}
    time_associations: Dict[str, List[str]] = {}
    person_associations: Dict[str, List[str]] = {}
    emotional_associations: Dict[str, List[str]] = {}


# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────

class Memory(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    npc_id: str
    memory_type: MemoryType
    event: str                          # description of what happened
    participants: List[str] = []        # other NPC/player IDs involved
    location: Optional[str] = None
    emotion_at_time: EmotionVector
    importance: float = Field(0.5, ge=0.0, le=1.0)  # 0=trivial, 1=life-changing
    emotional_intensity: float = Field(0.5, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = None  # populated by memory engine
    tags: List[str] = []
    # Decay tracking
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    salience: float = 1.0  # decreases over time


class MemoryQuery(BaseModel):
    npc_id: str
    query_text: str
    top_k: int = 5
    memory_type: Optional[MemoryType] = None
    recency_weight: float = 0.3
    importance_weight: float = 0.4
    similarity_weight: float = 0.3


# ─────────────────────────────────────────────
# GOALS
# ─────────────────────────────────────────────

class Action(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    preconditions: Dict[str, Any] = {}
    effects: Dict[str, Any] = {}
    cost: float = 1.0
    duration_ticks: int = 1


class Goal(BaseModel):
    goal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    target_state: Dict[str, Any] = {}
    base_weight: float = 0.5
    current_priority: float = 0.5
    status: GoalStatus = GoalStatus.PENDING
    progress: float = 0.0
    action_plan: List[str] = []        # ordered list of action names
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    required_resources: Dict[str, float] = {}


# ─────────────────────────────────────────────
# RELATIONSHIPS
# ─────────────────────────────────────────────

class Relationship(BaseModel):
    target_id: str                        # NPC or player ID
    target_name: str
    relationship_type: RelationshipType = RelationshipType.NEUTRAL
    trust: float = Field(0.5, ge=0.0, le=1.0)
    fear: float = Field(0.0, ge=0.0, le=1.0)
    friendship: float = Field(0.5, ge=0.0, le=1.0)
    respect: float = Field(0.5, ge=0.0, le=1.0)
    faction_alignment: float = Field(0.0, ge=-1.0, le=1.0)  # -1=opposing factions
    interaction_count: int = 0
    last_interaction: Optional[datetime] = None
    shared_history: List[str] = []       # notable event IDs


# ─────────────────────────────────────────────
# WORLD STATE
# ─────────────────────────────────────────────

class WorldEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    description: str
    location: Optional[str] = None
    affected_factions: List[str] = []
    affected_npcs: List[str] = []
    radius: float = 100.0               # spatial influence radius
    severity: float = Field(0.5, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}
    propagates_as_rumor: bool = True


class CrimeRecord(BaseModel):
    """A crime committed by a player or NPC."""
    crime_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    perpetrator_id: str                     # player or NPC who committed the crime
    victim_id: Optional[str] = None         # target of the crime (NPC/player ID)
    victim_name: Optional[str] = None
    crime_type: CrimeType
    description: str = ""
    location: Optional[str] = None
    severity: float = Field(0.5, ge=0.0, le=1.0)  # 0=minor, 1=heinous
    witnesses: List[str] = []               # NPC IDs who directly saw it
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class RumorRecord(BaseModel):
    """Tracks a rumor as it spreads through the social graph."""
    rumor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_crime_id: str                    # the crime that started this rumor
    crime_type: CrimeType
    perpetrator_id: str
    original_description: str
    current_description: str                # evolves with distortion
    current_hop: int = 0
    fidelity: float = Field(1.0, ge=0.0, le=1.0)
    severity: float = Field(0.5, ge=0.0, le=1.0)
    heard_by: List[str] = []                # NPC IDs who've heard this rumor
    believed_by: List[str] = []             # NPC IDs who believe it
    spread_chain: List[Dict[str, Any]] = [] # [{spreader, receiver, hop, timestamp}]
    is_active: bool = True                  # still spreading?
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NPCBehaviorModifier(BaseModel):
    """Behavioral change triggered by crime awareness."""
    crime_id: str
    crime_type: CrimeType
    perpetrator_id: str
    awareness_level: AwarenessLevel
    refuse_trade: bool = False
    call_guards: bool = False
    flee: bool = False
    increase_prices: bool = False
    lock_doors: bool = False
    hostile_dialogue: bool = False
    warn_others: bool = False


# ─────────────────────────────────────────────
# CORE NPC STATE
# ─────────────────────────────────────────────

class NPCState(BaseModel):
    """
    The complete cognitive state of an NPC.
    This is the central data structure of the engine.
    """
    npc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    archetype: str                        # e.g. "merchant", "guard", "wizard"
    faction: Optional[str] = None
    location: Optional[str] = None

    # Cognitive layers
    personality: PersonalityVector = Field(default_factory=PersonalityVector)
    emotion_state: EmotionVector = Field(default_factory=EmotionVector)

    # Goals (managed by GOAP)
    goals: List[Goal] = []

    # Relationships (lightweight refs; full data in Neo4j)
    relationships: Dict[str, Relationship] = {}

    # Memory references (full vectors in Qdrant)
    recent_memory_ids: List[str] = []

    # Background context
    background: str = ""
    speech_style: str = ""              # e.g. "formal medieval", "gruff pirate"
    knowledge_base: Dict[str, Any] = {}  # semantic facts this NPC knows

    # Crime awareness — {crime_id: {awareness_level, crime_type, perpetrator_id, ...}}
    known_crimes: Dict[str, Dict[str, Any]] = {}
    behavior_modifiers: List[Dict[str, Any]] = []  # active behavioral changes

    # World state snapshot
    world_knowledge: Dict[str, Any] = {}

    # Status
    is_active: bool = True
    last_interaction: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Simulation tracking
    sim_tick: int = 0
    offline_ticks: int = 0

    # ─── COMPLEX SYSTEMS ───
    physiology: PhysiologicalState = Field(default_factory=PhysiologicalState)
    skills: SkillSet = Field(default_factory=SkillSet)
    profession: Optional[Profession] = None
    economy: EconomicState = Field(default_factory=EconomicState)
    inventory: Inventory = Field(default_factory=Inventory)
    social_identity: SocialIdentity = Field(default_factory=SocialIdentity)
    cultural_background: CulturalBackground = Field(default_factory=CulturalBackground)
    cognitive_state: CognitiveState = Field(default_factory=CognitiveState)
    beliefs: BeliefSystem = Field(default_factory=BeliefSystem)
    routine: DailyRoutine = Field(default_factory=DailyRoutine)
    life_history: LifeHistory = Field(default_factory=LifeHistory)
    spatial_awareness: SpatialAwareness = Field(default_factory=SpatialAwareness)
    contextual_memory: ContextualMemory = Field(default_factory=ContextualMemory)
    personality_dynamics: PersonalityDynamics = Field(default_factory=PersonalityDynamics)


# ─────────────────────────────────────────────
# API REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────

class CreateNPCRequest(BaseModel):
    name: str
    archetype: str
    faction: Optional[str] = None
    location: Optional[str] = None
    personality: Optional[PersonalityVector] = None
    background: str = ""
    speech_style: str = "neutral"
    initial_goals: List[str] = []


class InteractRequest(BaseModel):
    npc_id: str
    player_id: str
    player_message: str
    context: Dict[str, Any] = {}


class InteractResponse(BaseModel):
    npc_id: str
    dialogue: str
    npc_action: Optional[str] = None
    emotion_after: EmotionVector
    memories_recalled: List[str] = []
    relationship_delta: Dict[str, float] = {}


class NPCStateResponse(BaseModel):
    npc_id: str
    name: str
    archetype: str
    emotion_state: EmotionVector
    dominant_emotion: str
    mood_valence: float
    active_goals: List[Goal]
    relationship_count: int
    memory_count: int
    location: Optional[str]
    last_interaction: Optional[datetime]


class WorldEventRequest(BaseModel):
    event_type: EventType
    description: str
    location: Optional[str] = None
    affected_factions: List[str] = []
    severity: float = 0.5
    radius: float = 100.0
    metadata: Dict[str, Any] = {}


class CrimeReportRequest(BaseModel):
    perpetrator_id: str
    victim_id: Optional[str] = None
    victim_name: Optional[str] = None
    crime_type: CrimeType
    description: str = ""
    location: Optional[str] = None
    severity: float = 0.5
    witnesses: List[str] = []
    affected_factions: List[str] = []
    metadata: Dict[str, Any] = {}
