"""
Goal-Oriented Action Planning (GOAP)

Implements a regressive A* planner that finds action sequences
to satisfy NPC goals given current world state.

Pipeline:
  Goals → Priority Ranking → Action Graph → Plan Selection → Execution
"""
from __future__ import annotations

import heapq
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from copy import deepcopy

from app.models import Goal, Action, GoalStatus, PersonalityVector, EmotionVector
from app.personality.engine import rank_goals


# ─────────────────────────────────────────────
# ACTION LIBRARY
# All available NPC actions with preconditions and effects.
# ─────────────────────────────────────────────

ACTION_LIBRARY: List[Action] = [
    Action(
        name="buy_goods",
        preconditions={"has_gold": True, "near_market": True},
        effects={"has_goods": True, "has_gold": False},
        cost=1.5,
        duration_ticks=2,
    ),
    Action(
        name="sell_goods",
        preconditions={"has_goods": True, "near_market": True},
        effects={"has_gold": True, "has_goods": False, "wealth_increased": True},
        cost=1.0,
        duration_ticks=2,
    ),
    Action(
        name="travel_to_market",
        preconditions={"is_mobile": True},
        effects={"near_market": True},
        cost=2.0,
        duration_ticks=5,
    ),
    Action(
        name="patrol_village",
        preconditions={"is_guard": True},
        effects={"village_protected": True},
        cost=1.0,
        duration_ticks=3,
    ),
    Action(
        name="recruit_ally",
        preconditions={"has_gold": True, "reputation_high": True},
        effects={"has_ally": True},
        cost=2.5,
        duration_ticks=4,
    ),
    Action(
        name="gather_information",
        preconditions={"near_tavern": True},
        effects={"has_information": True},
        cost=1.0,
        duration_ticks=2,
    ),
    Action(
        name="travel_to_tavern",
        preconditions={"is_mobile": True},
        effects={"near_tavern": True},
        cost=1.5,
        duration_ticks=3,
    ),
    Action(
        name="spread_rumor",
        preconditions={"has_information": True, "near_npc": True},
        effects={"rumor_spread": True, "reputation_increased": True},
        cost=0.5,
        duration_ticks=1,
    ),
    Action(
        name="attack_enemy",
        preconditions={"has_weapon": True, "near_enemy": True},
        effects={"enemy_defeated": True},
        cost=3.0,
        duration_ticks=2,
    ),
    Action(
        name="flee",
        preconditions={"is_mobile": True},
        effects={"near_enemy": False, "is_safe": True},
        cost=1.0,
        duration_ticks=2,
    ),
    Action(
        name="request_help",
        preconditions={"has_ally": True},
        effects={"has_backup": True},
        cost=0.5,
        duration_ticks=1,
    ),
    Action(
        name="rest",
        preconditions={},
        effects={"is_rested": True},
        cost=0.5,
        duration_ticks=4,
    ),
    Action(
        name="pray",
        preconditions={},
        effects={"morale_high": True},
        cost=0.3,
        duration_ticks=1,
    ),
    Action(
        name="craft_item",
        preconditions={"has_materials": True, "near_workshop": True},
        effects={"has_goods": True},
        cost=2.0,
        duration_ticks=6,
    ),
    Action(
        name="negotiate_trade",
        preconditions={"near_npc": True},
        effects={"wealth_increased": True, "relationship_improved": True},
        cost=1.5,
        duration_ticks=2,
    ),
]

# Index by name for fast lookup
ACTION_MAP: Dict[str, Action] = {a.name: a for a in ACTION_LIBRARY}


# ─────────────────────────────────────────────
# GOAL DEFINITIONS
# ─────────────────────────────────────────────

GOAL_LIBRARY: Dict[str, Goal] = {
    "increase_wealth": Goal(
        name="increase_wealth",
        description="Accumulate more gold and valuable items",
        target_state={"wealth_increased": True},
        base_weight=0.6,
    ),
    "sell_goods": Goal(
        name="sell_goods",
        description="Sell goods at market for profit",
        target_state={"has_gold": True, "has_goods": False, "wealth_increased": True},
        base_weight=0.5,
    ),
    "protect_village": Goal(
        name="protect_village",
        description="Ensure the village is safe from threats",
        target_state={"village_protected": True},
        base_weight=0.7,
    ),
    "gain_reputation": Goal(
        name="gain_reputation",
        description="Increase standing in the community",
        target_state={"reputation_increased": True},
        base_weight=0.4,
    ),
    "gather_information": Goal(
        name="gather_information",
        description="Learn new information about the world",
        target_state={"has_information": True},
        base_weight=0.5,
    ),
    "eliminate_threat": Goal(
        name="eliminate_threat",
        description="Defeat or remove a threat",
        target_state={"enemy_defeated": True},
        base_weight=0.6,
    ),
    "escape_danger": Goal(
        name="escape_danger",
        description="Get to safety as quickly as possible",
        target_state={"is_safe": True},
        base_weight=0.9,
    ),
    "spread_rumors": Goal(
        name="spread_rumors",
        description="Share information (or misinformation) with others",
        target_state={"rumor_spread": True},
        base_weight=0.3,
    ),
}


# ─────────────────────────────────────────────
# A* PLANNER
# ─────────────────────────────────────────────

@dataclass(order=True)
class PlanNode:
    f_cost: float
    g_cost: float = field(compare=False)
    state: Dict[str, Any] = field(compare=False)
    plan: List[str] = field(compare=False)


class GOAPPlanner:
    """
    Regressive Goal-Oriented Action Planner.

    Works backward from goal state to find cheapest action sequence
    that satisfies the goal given current world state.
    """

    def plan(
        self,
        current_state: Dict[str, Any],
        goal: Goal,
        available_actions: Optional[List[Action]] = None,
        max_depth: int = 8,
    ) -> List[str]:
        """
        Returns ordered list of action names to achieve goal.
        Empty list if no plan found.
        """
        actions = available_actions or ACTION_LIBRARY
        target = goal.target_state

        # Check if goal already satisfied
        if self._state_satisfies(current_state, target):
            return []

        # A* search
        open_heap: List[PlanNode] = []
        start = PlanNode(
            f_cost=self._heuristic(current_state, target),
            g_cost=0.0,
            state=deepcopy(current_state),
            plan=[],
        )
        heapq.heappush(open_heap, start)

        visited: Set[str] = set()
        best_plan: Optional[List[str]] = None
        best_cost = float("inf")

        while open_heap:
            node = heapq.heappop(open_heap)

            state_key = self._state_key(node.state)
            if state_key in visited:
                continue
            visited.add(state_key)

            # Depth limit
            if len(node.plan) >= max_depth:
                continue

            # Try each action
            for action in actions:
                if not self._preconditions_met(node.state, action.preconditions):
                    continue

                new_state = deepcopy(node.state)
                self._apply_effects(new_state, action.effects)
                new_plan = node.plan + [action.name]
                new_g = node.g_cost + action.cost

                if new_g >= best_cost:
                    continue

                if self._state_satisfies(new_state, target):
                    best_plan = new_plan
                    best_cost = new_g
                    continue

                h = self._heuristic(new_state, target)
                new_node = PlanNode(
                    f_cost=new_g + h,
                    g_cost=new_g,
                    state=new_state,
                    plan=new_plan,
                )
                heapq.heappush(open_heap, new_node)

        return best_plan or []

    def _preconditions_met(
        self,
        state: Dict[str, Any],
        preconditions: Dict[str, Any],
    ) -> bool:
        for key, required in preconditions.items():
            if state.get(key) != required:
                return False
        return True

    def _apply_effects(
        self,
        state: Dict[str, Any],
        effects: Dict[str, Any],
    ) -> None:
        state.update(effects)

    def _state_satisfies(
        self,
        state: Dict[str, Any],
        target: Dict[str, Any],
    ) -> bool:
        for key, required in target.items():
            if state.get(key) != required:
                return False
        return True

    def _heuristic(
        self,
        state: Dict[str, Any],
        target: Dict[str, Any],
    ) -> float:
        """Count unsatisfied goal conditions."""
        unsatisfied = sum(
            1 for key, val in target.items()
            if state.get(key) != val
        )
        return float(unsatisfied)

    def _state_key(self, state: Dict[str, Any]) -> str:
        return str(sorted(state.items()))


# ─────────────────────────────────────────────
# HIGH-LEVEL GOAL MANAGER
# ─────────────────────────────────────────────

class GoalManager:
    def __init__(self):
        self.planner = GOAPPlanner()

    def select_and_plan(
        self,
        available_goals: List[Goal],
        personality: PersonalityVector,
        emotion: EmotionVector,
        world_state: Dict[str, Any],
        max_active: int = 3,
    ) -> List[Goal]:
        """
        1. Rank goals by priority (personality + emotion modulated)
        2. Plan action sequence for top goals
        3. Return active goals with plans attached
        """
        pending = [g for g in available_goals if g.status == GoalStatus.PENDING]
        ranked = rank_goals(pending, personality, emotion)
        active = ranked[:max_active]

        for goal in active:
            plan = self.planner.plan(world_state, goal)
            goal.action_plan = plan
            goal.status = GoalStatus.ACTIVE

        return active

    def evaluate_goal_completion(
        self,
        goal: Goal,
        world_state: Dict[str, Any],
    ) -> bool:
        """Check if goal's target state has been reached."""
        return all(
            world_state.get(k) == v
            for k, v in goal.target_state.items()
        )

    def get_next_action(self, goal: Goal) -> Optional[str]:
        """Returns next action name from goal's plan."""
        if goal.action_plan:
            return goal.action_plan[0]
        return None

    def advance_goal(self, goal: Goal) -> None:
        """Mark first action as done, advance plan."""
        if goal.action_plan:
            goal.action_plan.pop(0)
        if not goal.action_plan:
            goal.status = GoalStatus.COMPLETED
            goal.progress = 1.0


# Singletons
goap_planner = GOAPPlanner()
goal_manager = GoalManager()
