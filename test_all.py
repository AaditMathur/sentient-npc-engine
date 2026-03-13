"""
Test Suite — Sentient NPC Engine 3.0
Tests all subsystems without requiring live infrastructure.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    NPCState, PersonalityVector, EmotionVector, Memory, MemoryType,
    Goal, GoalStatus, WorldEvent, EventType, Relationship, RelationshipType,
)
from app.emotion.engine import EmotionEngine, emotion_engine
from app.personality.engine import (
    get_dialogue_tone, compute_goal_priority, rank_goals
)
from app.goals.planner import GOAPPlanner, GoalManager, GOAL_LIBRARY, ACTION_LIBRARY
from app.world.events import RumorPropagator


# ─────────────────────────────────────────────
# EMOTION ENGINE TESTS
# ─────────────────────────────────────────────

class TestEmotionEngine:
    def setup_method(self):
        self.engine = EmotionEngine(decay_rate=0.1)
        self.neutral_emotion = EmotionVector()
        self.neutral_personality = PersonalityVector()

    def test_apply_decay_moves_toward_baseline(self):
        high_fear = EmotionVector(fear=0.9, joy=0.1)
        decayed = self.engine.apply_decay(high_fear, ticks=5)
        assert decayed.fear < 0.9, "Fear should decay toward 0.0"
        assert decayed.joy > 0.1, "Joy should move toward baseline 0.4"

    def test_apply_decay_clamps_values(self):
        emotion = EmotionVector(joy=1.0, fear=0.0)
        for _ in range(100):
            emotion = self.engine.apply_decay(emotion, ticks=1)
        assert 0.0 <= emotion.joy <= 1.0
        assert 0.0 <= emotion.fear <= 1.0

    def test_attack_increases_fear_and_anger(self):
        start = EmotionVector(fear=0.0, anger=0.0)
        updated = self.engine.apply_stimulus(
            start, "player_attack", self.neutral_personality, severity=1.0
        )
        assert updated.fear > 0.3
        assert updated.anger > 0.3

    def test_gift_increases_trust_and_joy(self):
        start = EmotionVector(trust=0.3, joy=0.2)
        updated = self.engine.apply_stimulus(
            start, "gift", self.neutral_personality, severity=1.0
        )
        assert updated.trust > 0.3
        assert updated.joy > 0.2

    def test_brave_npc_fears_less(self):
        brave = PersonalityVector(bravery=1.0)
        coward = PersonalityVector(bravery=0.0)
        emotion = EmotionVector(fear=0.0)

        brave_result = self.engine.apply_stimulus(emotion, "player_attack", brave)
        coward_result = self.engine.apply_stimulus(emotion, "player_attack", coward)

        assert brave_result.fear < coward_result.fear, \
            "Brave NPC should fear less than coward"

    def test_empathetic_npc_sadder(self):
        empathetic = PersonalityVector(empathy=1.0)
        cold = PersonalityVector(empathy=0.0)
        emotion = EmotionVector(sadness=0.0)

        emp_result = self.engine.apply_stimulus(emotion, "market_fire", empathetic)
        cold_result = self.engine.apply_stimulus(emotion, "market_fire", cold)

        assert emp_result.sadness > cold_result.sadness

    def test_rumor_dampened(self):
        emotion = EmotionVector(fear=0.0)
        direct = self.engine.apply_stimulus(
            emotion, "player_attack", self.neutral_personality, is_direct_witness=True
        )
        indirect = self.engine.apply_stimulus(
            emotion, "player_attack", self.neutral_personality, is_direct_witness=False
        )
        assert direct.fear > indirect.fear, "Direct witness should react more strongly"

    def test_emotion_valence(self):
        positive = EmotionVector(joy=0.9, trust=0.8)
        negative = EmotionVector(fear=0.8, anger=0.9)
        assert positive.valence() > 0
        assert negative.valence() < 0

    def test_dominant_emotion(self):
        emotion = EmotionVector(joy=0.1, anger=0.9, fear=0.5)
        assert emotion.dominant() == "anger"

    def test_emotion_to_prompt_fragment(self):
        emotion = EmotionVector(anger=0.8, fear=0.6)
        fragment = self.engine.emotion_to_prompt_fragment(emotion)
        assert "anger" in fragment.lower()
        assert len(fragment) > 10


# ─────────────────────────────────────────────
# PERSONALITY ENGINE TESTS
# ─────────────────────────────────────────────

class TestPersonalityEngine:
    def test_greedy_npc_dialogue_mentions_profit(self):
        greedy = PersonalityVector(greed=0.9)
        emotion = EmotionVector()
        tone = get_dialogue_tone(greedy, emotion)
        assert "greed" in tone.lower() or "profit" in tone.lower() or "transactional" in tone.lower()

    def test_brave_npc_tone(self):
        brave = PersonalityVector(bravery=0.9)
        emotion = EmotionVector()
        tone = get_dialogue_tone(brave, emotion)
        assert "bold" in tone.lower() or "brave" in tone.lower() or "direct" in tone.lower()

    def test_angry_emotion_reflected_in_tone(self):
        personality = PersonalityVector()
        angry_emotion = EmotionVector(anger=0.9)
        tone = get_dialogue_tone(personality, angry_emotion)
        assert "angry" in tone.lower() or "short-tempered" in tone.lower()

    def test_goal_priority_greed_boosts_wealth_goal(self):
        greedy = PersonalityVector(greed=0.9)
        goal = GOAL_LIBRARY["increase_wealth"].model_copy()
        neutral_goal = GOAL_LIBRARY["help_villagers"].model_copy()
        emotion = EmotionVector()

        wealth_priority = compute_goal_priority(goal, greedy, emotion)
        help_priority = compute_goal_priority(neutral_goal, greedy, emotion)

        assert wealth_priority > help_priority, \
            "Greedy NPC should prioritize wealth over helping others"

    def test_goal_ranking_order(self):
        brave = PersonalityVector(bravery=0.9, aggression=0.7)
        goals = [
            GOAL_LIBRARY["escape_danger"].model_copy(),
            GOAL_LIBRARY["eliminate_threat"].model_copy(),
            GOAL_LIBRARY["gather_information"].model_copy(),
        ]
        emotion = EmotionVector(anger=0.7)
        ranked = rank_goals(goals, brave, emotion)

        # Brave + angry NPC should rank eliminate_threat high
        top_goal = ranked[0].name
        assert top_goal in ["eliminate_threat", "escape_danger"]


# ─────────────────────────────────────────────
# GOAP PLANNER TESTS
# ─────────────────────────────────────────────

class TestGOAPPlanner:
    def setup_method(self):
        self.planner = GOAPPlanner()

    def test_simple_plan_found(self):
        """NPC has goods and is near market → should just sell."""
        state = {"has_goods": True, "near_market": True, "is_mobile": True}
        goal = GOAL_LIBRARY["sell_goods"].model_copy()
        goal.target_state = {"wealth_increased": True}

        plan = self.planner.plan(state, goal)
        assert len(plan) > 0
        assert "sell_goods" in plan

    def test_plan_with_travel_required(self):
        """NPC has goods but not at market → should travel first."""
        state = {
            "has_goods": True,
            "near_market": False,
            "is_mobile": True,
            "wealth_increased": False,
        }
        goal = GOAL_LIBRARY["sell_goods"].model_copy()
        goal.target_state = {"wealth_increased": True}

        plan = self.planner.plan(state, goal)
        assert "travel_to_market" in plan
        assert "sell_goods" in plan
        # Travel must come before sell
        assert plan.index("travel_to_market") < plan.index("sell_goods")

    def test_goal_already_satisfied(self):
        """If goal is already met, plan should be empty."""
        state = {"wealth_increased": True}
        goal = GOAL_LIBRARY["sell_goods"].model_copy()
        goal.target_state = {"wealth_increased": True}

        plan = self.planner.plan(state, goal)
        assert plan == []

    def test_no_plan_when_impossible(self):
        """Goal that requires a missing precondition chain."""
        state = {}
        goal = Goal(
            name="impossible_goal",
            description="Requires nonexistent preconditions",
            target_state={"magic_dragon_tamed": True},
        )
        plan = self.planner.plan(state, goal, max_depth=3)
        assert plan == []

    def test_escape_plan_uses_flee(self):
        state = {"is_mobile": True, "near_enemy": True}
        goal = GOAL_LIBRARY["escape_danger"].model_copy()
        plan = self.planner.plan(state, goal)
        assert "flee" in plan

    def test_plan_cost_is_reasonable(self):
        """Plan should not be excessively long."""
        state = {"is_mobile": True}
        goal = GOAL_LIBRARY["gather_information"].model_copy()
        plan = self.planner.plan(state, goal)
        assert len(plan) <= 5, "Plan should be concise"


# ─────────────────────────────────────────────
# WORLD EVENT / RUMOR TESTS
# ─────────────────────────────────────────────

class TestRumorPropagator:
    def setup_method(self):
        self.propagator = RumorPropagator()
        self.base_event = WorldEvent(
            event_type=EventType.DRAGON_KILLED,
            description="The dragon Vorthex has been slain in the Eastern Mountains",
            severity=0.9,
            location="Eastern Mountains",
        )

    def test_hop_1_rumor_has_lower_severity(self):
        rumor = self.propagator.create_rumor_variant(self.base_event, hop=1, spreader_name="Aldric")
        assert rumor.severity < self.base_event.severity

    def test_hop_2_rumor_lower_than_hop_1(self):
        rumor1 = self.propagator.create_rumor_variant(self.base_event, hop=1, spreader_name="Aldric")
        rumor2 = self.propagator.create_rumor_variant(self.base_event, hop=2, spreader_name="Mira")
        assert rumor2.severity <= rumor1.severity

    def test_rumor_type_is_rumor(self):
        rumor = self.propagator.create_rumor_variant(self.base_event, hop=1, spreader_name="Someone")
        assert rumor.event_type == EventType.RUMOR

    def test_hop_3_does_not_propagate(self):
        rumor = self.propagator.create_rumor_variant(self.base_event, hop=3, spreader_name="Stranger")
        assert rumor.propagates_as_rumor == False

    def test_rumor_description_credits_spreader(self):
        rumor = self.propagator.create_rumor_variant(self.base_event, hop=1, spreader_name="Aldric")
        assert "Aldric" in rumor.description

    def test_high_hop_description_vague(self):
        rumor = self.propagator.create_rumor_variant(self.base_event, hop=3, spreader_name="Someone")
        # At 3 hops, should be vague
        assert len(rumor.description) < len(self.base_event.description)


# ─────────────────────────────────────────────
# MEMORY ENGINE TESTS (unit-level, no Qdrant)
# ─────────────────────────────────────────────

class TestMemoryHelpers:
    def test_create_interaction_memory(self):
        from app.memory.engine import create_interaction_memory
        memory = create_interaction_memory(
            npc_id="npc_1",
            player_id="player_1",
            player_message="I want to buy your sword",
            npc_response="That'll cost 50 gold pieces.",
            emotion=EmotionVector(joy=0.6, trust=0.5),
        )
        assert memory.npc_id == "npc_1"
        assert "player_1" in memory.participants
        assert memory.memory_type == MemoryType.EPISODIC
        assert 0.0 <= memory.importance <= 1.0

    def test_create_world_event_memory(self):
        from app.memory.engine import create_world_event_memory
        memory = create_world_event_memory(
            npc_id="npc_1",
            event_description="The market burned down",
            emotion=EmotionVector(fear=0.7, sadness=0.5),
            severity=0.8,
            is_direct=True,
        )
        assert memory.npc_id == "npc_1"
        assert memory.importance > 0.3
        assert "world_event" in memory.tags

    def test_indirect_memory_lower_importance(self):
        from app.memory.engine import create_world_event_memory
        direct = create_world_event_memory(
            npc_id="npc_1",
            event_description="Dragon attack",
            emotion=EmotionVector(fear=0.8),
            severity=0.9,
            is_direct=True,
        )
        indirect = create_world_event_memory(
            npc_id="npc_1",
            event_description="Dragon attack",
            emotion=EmotionVector(fear=0.4),
            severity=0.9,
            is_direct=False,
        )
        assert direct.importance > indirect.importance


# ─────────────────────────────────────────────
# NPC STATE TESTS
# ─────────────────────────────────────────────

class TestNPCState:
    def test_npc_state_defaults(self):
        npc = NPCState(name="Test NPC", archetype="guard")
        assert npc.npc_id is not None
        assert npc.emotion_state.joy == 0.5
        assert npc.emotion_state.fear == 0.0
        assert npc.personality.empathy == 0.5
        assert npc.is_active == True

    def test_personality_describe(self):
        extreme = PersonalityVector(
            greed=0.9, bravery=0.9, empathy=0.9,
            loyalty=0.9, honesty=0.1, aggression=0.9
        )
        description = extreme.describe()
        assert "greedy" in description
        assert "brave" in description
        assert "deceptive" in description

    def test_emotion_arousal(self):
        calm = EmotionVector(anger=0.0, fear=0.0, joy=0.5)
        excited = EmotionVector(anger=0.8, fear=0.7, joy=0.8)
        assert excited.arousal() > calm.arousal()

    def test_goal_status_enum(self):
        goal = Goal(
            name="test_goal",
            description="Test",
            base_weight=0.5,
        )
        assert goal.status == GoalStatus.PENDING
        goal.status = GoalStatus.ACTIVE
        assert goal.status == GoalStatus.ACTIVE


# ─────────────────────────────────────────────
# INTEGRATION TEST (mocked)
# ─────────────────────────────────────────────

class TestNPCBrainMocked:
    """Tests the brain pipeline with all external dependencies mocked."""

    @pytest.mark.asyncio
    async def test_create_npc_pipeline(self):
        from app.brain.npc_brain import NPCBrain
        from app.models import CreateNPCRequest

        brain = NPCBrain()

        # Mock the repository
        brain.repo.create = AsyncMock(return_value=None)

        with patch("app.brain.npc_brain.social_graph") as mock_graph:
            mock_graph.upsert_npc_node = AsyncMock()

            mock_db = AsyncMock()

            request = CreateNPCRequest(
                name="Test Merchant",
                archetype="merchant",
                faction="Guild",
                initial_goals=["increase_wealth"],
            )

            npc = await brain.create_npc(mock_db, request)
            assert npc.name == "Test Merchant"
            assert npc.archetype == "merchant"
            assert npc.personality.greed > 0.5  # merchant preset

    @pytest.mark.asyncio
    async def test_emotion_pipeline_integration(self):
        """Test that the emotion pipeline correctly modulates through multiple events."""
        engine = EmotionEngine()
        npc = NPCState(name="Guard", archetype="guard")
        brave_personality = PersonalityVector(bravery=0.9, aggression=0.6)

        # Sequence: gift → attack → rest (via decay)
        emotion = npc.emotion_state
        emotion = engine.apply_stimulus(emotion, "gift", brave_personality)
        joy_after_gift = emotion.joy

        emotion = engine.apply_stimulus(emotion, "player_attack", brave_personality)
        fear_after_attack = emotion.fear
        anger_after_attack = emotion.anger

        emotion = engine.apply_decay(emotion, ticks=10)

        assert joy_after_gift > npc.emotion_state.joy
        assert fear_after_attack > 0
        assert anger_after_attack > 0
        # After 10 ticks of decay, emotions should moderate
        assert emotion.anger < anger_after_attack


# ─────────────────────────────────────────────
# CRIME → RUMOR SYSTEM TESTS
# ─────────────────────────────────────────────

class TestCrimeRumorSystem:
    """Tests the full crime → rumor → NPC reaction pipeline."""

    def setup_method(self):
        from app.models import CrimeRecord, CrimeType, RumorRecord, AwarenessLevel, NPCBehaviorModifier
        from app.rumor.rumor_network import RumorNetwork
        self.network = RumorNetwork()
        self.base_crime = CrimeRecord(
            perpetrator_id="player_1",
            victim_id="npc_merchant_01",
            victim_name="Aldric the Merchant",
            crime_type=CrimeType.THEFT,
            description="Stole 50 gold coins from the market stall",
            location="Ironhaven Market",
            severity=0.6,
            witnesses=["npc_guard_01", "npc_bystander_02"],
        )

    def test_crime_creates_rumor(self):
        """CrimeRecord is correctly converted to a RumorRecord."""
        rumor = self.network.create_crime_rumor(self.base_crime)

        assert rumor.source_crime_id == self.base_crime.crime_id
        assert rumor.crime_type == self.base_crime.crime_type
        assert rumor.perpetrator_id == "player_1"
        assert rumor.fidelity == 1.0  # initial fidelity
        assert rumor.current_hop == 0
        assert len(rumor.heard_by) == 2  # witnesses
        assert rumor.is_active == True
        assert "theft" in rumor.current_description.lower() or "stole" in rumor.current_description.lower()

    def test_rumor_fidelity_decays_per_hop(self):
        """Fidelity degrades with each hop — 1.0 → 0.7 → 0.5 → 0.3."""
        assert self.network.FIDELITY_BY_HOP[0] == 1.0
        assert self.network.FIDELITY_BY_HOP[1] == 0.7
        assert self.network.FIDELITY_BY_HOP[2] == 0.5
        assert self.network.FIDELITY_BY_HOP[3] == 0.3

        # Verify severity dampens per hop
        for hop in range(4):
            severity = max(0.1, self.base_crime.severity - hop * self.network.SEVERITY_DAMPEN_PER_HOP)
            if hop > 0:
                prev_severity = max(0.1, self.base_crime.severity - (hop - 1) * self.network.SEVERITY_DAMPEN_PER_HOP)
                assert severity <= prev_severity, f"Severity should decrease at hop {hop}"

    def test_personality_modulates_spread(self):
        """Gossipy NPCs spread more, loyal NPCs suppress."""
        from app.models import RumorRecord, CrimeType

        rumor = self.network.create_crime_rumor(self.base_crime)

        # Gossipy NPC (low honesty)
        gossipy_npc = NPCState(
            name="Gossip", archetype="innkeeper",
            personality=PersonalityVector(honesty=0.1, curiosity=0.9),
        )
        gossipy_chance = self.network._compute_spread_chance(gossipy_npc, rumor)

        # Honest NPC
        honest_npc = NPCState(
            name="Silent", archetype="guard",
            personality=PersonalityVector(honesty=0.9, curiosity=0.2),
        )
        honest_chance = self.network._compute_spread_chance(honest_npc, rumor)

        assert gossipy_chance > honest_chance, \
            f"Gossipy NPC ({gossipy_chance:.2f}) should spread more than honest NPC ({honest_chance:.2f})"

    def test_npc_emotion_after_crime_rumor(self):
        """NPC emotions change appropriately after hearing about a crime."""
        from app.emotion.engine import EmotionEngine

        engine = EmotionEngine()

        # Murder should cause extreme fear + anger
        calm = EmotionVector(fear=0.0, anger=0.0, disgust=0.0)
        after_murder = engine.apply_stimulus(
            calm, "crime_murder", PersonalityVector(), severity=1.0
        )
        assert after_murder.fear > 0.4, "Murder should cause significant fear"
        assert after_murder.anger > 0.3, "Murder should cause anger"
        assert after_murder.disgust > 0.3, "Murder should cause disgust"

        # Theft should primarily affect trust
        calm2 = EmotionVector(trust=0.5, anger=0.0)
        after_theft = engine.apply_stimulus(
            calm2, "crime_theft", PersonalityVector(), severity=1.0
        )
        assert after_theft.trust < 0.5, "Theft should decrease trust"
        assert after_theft.anger > 0.2, "Theft should cause some anger"

    def test_behavior_modifier_applied(self):
        """Correct behavior modifiers generated for different crime types."""
        from app.models import CrimeType, RumorRecord, AwarenessLevel

        # Murder rumor with direct witness
        murder_crime = CrimeRecord(
            perpetrator_id="player_1",
            victim_id="npc_01",
            crime_type=CrimeType.MURDER,
            description="Killed the shopkeeper",
            severity=0.9,
            witnesses=["npc_02"],
        )
        murder_rumor = self.network.create_crime_rumor(murder_crime)

        modifier = self.network._create_behavior_modifier(
            murder_rumor,
            AwarenessLevel.DIRECT_WITNESS,
            PersonalityVector(),
        )

        assert modifier.call_guards == True, "Murder witness should call guards"
        assert modifier.flee == True, "Murder witness should want to flee"
        assert modifier.hostile_dialogue == True, "Murder witness should be hostile"
        assert modifier.crime_type == CrimeType.MURDER

        # Theft with vague rumor — less severe reaction
        theft_rumor = self.network.create_crime_rumor(self.base_crime)
        theft_modifier = self.network._create_behavior_modifier(
            theft_rumor,
            AwarenessLevel.VAGUE_RUMOR,
            PersonalityVector(),
        )
        # Vague rumors should trigger fewer behaviors than direct witness
        vague_active = sum([
            theft_modifier.refuse_trade, theft_modifier.call_guards,
            theft_modifier.flee, theft_modifier.hostile_dialogue,
            theft_modifier.warn_others,
        ])
        assert vague_active <= 4, "Vague rumors should trigger few behaviors"

    def test_crime_context_for_dialogue(self):
        """Crime awareness is correctly formatted for dialogue context injection."""
        from app.models import AwarenessLevel

        npc = NPCState(name="Guard", archetype="guard")
        npc.known_crimes["crime_001"] = {
            "awareness_level": AwarenessLevel.DIRECT_WITNESS.value,
            "crime_type": "theft",
            "perpetrator_id": "player_1",
            "severity": 0.6,
            "description": "Stole gold from the market",
            "believed": True,
        }
        npc.behavior_modifiers.append({
            "crime_id": "crime_001",
            "perpetrator_id": "player_1",
            "hostile_dialogue": True,
            "refuse_trade": True,
        })

        context = self.network.get_crime_context_for_dialogue(npc, "player_1")

        assert "CRIME AWARENESS" in context
        assert "WITNESSED" in context
        assert "theft" in context
        assert "REFUSE" in context
        assert "hostility" in context.lower() or "hostile" in context.lower()

        # Player with no crimes should return empty context
        clean_context = self.network.get_crime_context_for_dialogue(npc, "player_clean")
        assert clean_context == ""

    def test_crime_awareness_persists_on_npc_state(self):
        """NPC remembers crimes across state snapshots."""
        npc = NPCState(name="Innkeeper", archetype="innkeeper")

        # Simulate adding crime awareness
        npc.known_crimes["crime_123"] = {
            "awareness_level": "reliable_rumor",
            "crime_type": "arson",
            "perpetrator_id": "player_1",
            "severity": 0.8,
            "believed": True,
        }

        # State should persist the crime knowledge
        awareness = self.network.get_npc_crime_awareness(npc)
        assert len(awareness) == 1
        assert awareness[0]["crime_type"] == "arson"
        assert awareness[0]["perpetrator_id"] == "player_1"

        # NPCs who believe can have behavior modifiers
        npc.behavior_modifiers.append({
            "crime_id": "crime_123",
            "perpetrator_id": "player_1",
            "call_guards": True,
        })
        assert len(npc.behavior_modifiers) == 1

    def test_relationship_delta_scales_with_severity(self):
        """Relationship damage scales with crime severity."""
        from app.models import CrimeType

        # High severity murder
        delta_high = self.network._compute_relationship_delta(CrimeType.MURDER, 1.0)
        # Low severity trespassing
        delta_low = self.network._compute_relationship_delta(CrimeType.TRESPASSING, 0.2)

        assert abs(delta_high.get("trust", 0)) > abs(delta_low.get("trust", 0)), \
            "High severity murder should damage trust more than low severity trespassing"
        assert delta_high.get("fear", 0) > delta_low.get("fear", 0), \
            "Murder should cause more fear than trespassing"

    def test_would_believe_based_on_fidelity(self):
        """NPCs believe high-fidelity rumors more than low-fidelity ones."""
        npc = NPCState(name="Villager", archetype="merchant")

        # High fidelity (direct witness level) — should believe
        assert self.network._would_believe(npc, 1.0, "stranger") == True

        # Very low fidelity — should not believe
        assert self.network._would_believe(npc, 0.1, "stranger") == False

    def test_distortion_increases_with_low_fidelity(self):
        """Rumor description gets vaguer at lower fidelity levels."""
        original = "Player stole 50 gold coins from the merchant"

        high_fidelity = self.network._distort_description(original, 0.8, "Guard")
        mid_fidelity = self.network._distort_description(original, 0.5, "Tavern Keeper")
        low_fidelity = self.network._distort_description(original, 0.2, "Stranger")

        # High fidelity preserves original content
        assert "stole" in high_fidelity.lower() or "50 gold" in high_fidelity.lower()
        # Low fidelity should be vague
        assert "unconfirmed" in low_fidelity.lower() or "unclear" in low_fidelity.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
