"""
Temporal Causality Chain Tracker — The Butterfly Effect Engine

Tracks cause-and-effect relationships across the game world:
- Event A causes Event B causes Event C
- Player actions have cascading consequences
- NPCs' decisions influence other NPCs
- World state evolves based on causal chains

Enables visualization of:
- "How did we get here?" - trace back to root causes
- "What will happen if...?" - predict future consequences
- Butterfly effect demonstrations
"""
from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class CausalEventType(str, Enum):
    PLAYER_ACTION = "player_action"
    NPC_DECISION = "npc_decision"
    WORLD_EVENT = "world_event"
    CRIME = "crime"
    CONVERSATION = "conversation"
    QUEST_COMPLETION = "quest_completion"
    EMOTION_CHANGE = "emotion_change"
    RELATIONSHIP_CHANGE = "relationship_change"
    GOAL_CHANGE = "goal_change"
    ECONOMIC_CHANGE = "economic_change"
    FACTION_CHANGE = "faction_change"


class CausalNode(BaseModel):
    """A single event in the causal chain."""
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: CausalEventType
    description: str
    
    # Actors involved
    primary_actor_id: Optional[str] = None
    primary_actor_name: Optional[str] = None
    affected_actors: List[str] = []
    
    # Temporal data
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Causal relationships
    caused_by: List[str] = []  # Node IDs that caused this event
    causes: List[str] = []      # Node IDs this event caused
    
    # Impact metrics
    severity: float = 0.5  # How significant is this event (0-1)
    scope: int = 1         # How many entities affected
    
    # Context
    location: Optional[str] = None
    faction: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    # Chain analysis
    chain_depth: int = 0   # How many steps from root cause
    is_root_cause: bool = False
    is_terminal: bool = False  # Has no further consequences (yet)


class CausalChain(BaseModel):
    """A sequence of causally linked events."""
    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    root_cause: str  # Node ID of the initiating event
    terminal_effects: List[str] = []  # Node IDs of final consequences
    
    nodes: List[str] = []  # All node IDs in this chain
    total_depth: int = 0
    total_actors_affected: int = 0
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Narrative summary
    summary: str = ""
    butterfly_effect_score: float = 0.0  # How much did small cause amplify


class CausalityTracker:
    """
    Tracks and analyzes cause-effect relationships across the game world.
    
    Maintains a directed acyclic graph (DAG) of causal relationships.
    """

    def __init__(self):
        self.nodes: Dict[str, CausalNode] = {}
        self.chains: Dict[str, CausalChain] = {}
        self.actor_involvement: Dict[str, List[str]] = {}  # actor_id -> node_ids

    def record_event(
        self,
        event_type: CausalEventType,
        description: str,
        primary_actor_id: Optional[str] = None,
        primary_actor_name: Optional[str] = None,
        affected_actors: Optional[List[str]] = None,
        caused_by: Optional[List[str]] = None,
        severity: float = 0.5,
        location: Optional[str] = None,
        faction: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CausalNode:
        """
        Record a new causal event.
        
        Args:
            event_type: Type of event
            description: Human-readable description
            primary_actor_id: Who initiated this event
            affected_actors: Who was affected
            caused_by: List of node IDs that caused this event
            severity: Impact magnitude (0-1)
            location: Where it happened
            metadata: Additional context
        
        Returns:
            The created CausalNode
        """
        node = CausalNode(
            event_type=event_type,
            description=description,
            primary_actor_id=primary_actor_id,
            primary_actor_name=primary_actor_name,
            affected_actors=affected_actors or [],
            caused_by=caused_by or [],
            severity=severity,
            scope=len(affected_actors or []) + 1,
            location=location,
            faction=faction,
            metadata=metadata or {},
        )
        
        # Calculate chain depth
        if not caused_by:
            node.is_root_cause = True
            node.chain_depth = 0
        else:
            max_parent_depth = max(
                self.nodes[parent_id].chain_depth
                for parent_id in caused_by
                if parent_id in self.nodes
            )
            node.chain_depth = max_parent_depth + 1
        
        # Update parent nodes
        for parent_id in caused_by or []:
            if parent_id in self.nodes:
                self.nodes[parent_id].causes.append(node.node_id)
                self.nodes[parent_id].is_terminal = False
        
        # Store node
        self.nodes[node.node_id] = node
        
        # Track actor involvement
        if primary_actor_id:
            if primary_actor_id not in self.actor_involvement:
                self.actor_involvement[primary_actor_id] = []
            self.actor_involvement[primary_actor_id].append(node.node_id)
        
        for actor_id in affected_actors or []:
            if actor_id not in self.actor_involvement:
                self.actor_involvement[actor_id] = []
            self.actor_involvement[actor_id].append(node.node_id)
        
        # Update or create chains
        self._update_chains(node)
        
        logger.info(
            "causal_event_recorded",
            node_id=node.node_id,
            event_type=event_type.value,
            chain_depth=node.chain_depth,
            severity=severity,
        )
        
        return node

    def _update_chains(self, node: CausalNode) -> None:
        """Update causal chains when a new node is added."""
        if node.is_root_cause:
            # Create new chain
            chain = CausalChain(
                title=f"Chain: {node.description[:50]}",
                root_cause=node.node_id,
                nodes=[node.node_id],
                total_depth=0,
                total_actors_affected=node.scope,
                summary=node.description,
            )
            self.chains[chain.chain_id] = chain
            node.metadata["chain_id"] = chain.chain_id
        else:
            # Add to existing chain(s)
            for parent_id in node.caused_by:
                parent = self.nodes.get(parent_id)
                if parent and "chain_id" in parent.metadata:
                    chain_id = parent.metadata["chain_id"]
                    chain = self.chains.get(chain_id)
                    if chain:
                        chain.nodes.append(node.node_id)
                        chain.total_depth = max(chain.total_depth, node.chain_depth)
                        chain.total_actors_affected += node.scope
                        chain.last_updated = datetime.now(timezone.utc)
                        
                        # Update terminal effects
                        if parent_id in chain.terminal_effects:
                            chain.terminal_effects.remove(parent_id)
                        chain.terminal_effects.append(node.node_id)
                        
                        # Calculate butterfly effect score
                        root = self.nodes.get(chain.root_cause)
                        if root:
                            chain.butterfly_effect_score = (
                                chain.total_actors_affected / max(1, root.scope)
                            ) * (chain.total_depth / 10.0)
                        
                        node.metadata["chain_id"] = chain_id

    def trace_back_to_root(self, node_id: str) -> List[CausalNode]:
        """
        Trace a causal chain backwards to find root cause(s).
        
        Returns:
            List of nodes from root cause to the given node
        """
        if node_id not in self.nodes:
            return []
        
        path = []
        current = self.nodes[node_id]
        visited = set()
        
        def _trace_recursive(node: CausalNode):
            if node.node_id in visited:
                return
            visited.add(node.node_id)
            
            if node.is_root_cause:
                path.insert(0, node)
                return
            
            # Trace through parents (take first parent for simplicity)
            if node.caused_by:
                parent_id = node.caused_by[0]
                if parent_id in self.nodes:
                    _trace_recursive(self.nodes[parent_id])
            
            path.append(node)
        
        _trace_recursive(current)
        return path

    def predict_consequences(
        self,
        hypothetical_event: Dict[str, Any],
        depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Predict potential consequences of a hypothetical event.
        
        Uses historical patterns to estimate likely outcomes.
        
        Args:
            hypothetical_event: Event description with type, actors, etc.
            depth: How many steps ahead to predict
        
        Returns:
            List of predicted consequence scenarios
        """
        event_type = hypothetical_event.get("event_type")
        _actor_id = hypothetical_event.get("actor_id")
        
        # Find similar historical events
        similar_events = [
            node for node in self.nodes.values()
            if node.event_type == event_type
        ]
        
        if not similar_events:
            return [{
                "prediction": "No historical data for this event type",
                "confidence": 0.0,
            }]
        
        # Analyze what typically follows this event type
        consequence_patterns = {}
        for event in similar_events:
            for consequence_id in event.causes:
                consequence = self.nodes.get(consequence_id)
                if consequence:
                    key = consequence.event_type.value
                    if key not in consequence_patterns:
                        consequence_patterns[key] = {
                            "count": 0,
                            "avg_severity": 0.0,
                            "examples": [],
                        }
                    consequence_patterns[key]["count"] += 1
                    consequence_patterns[key]["avg_severity"] += consequence.severity
                    consequence_patterns[key]["examples"].append(consequence.description)
        
        # Calculate probabilities
        total_consequences = sum(p["count"] for p in consequence_patterns.values())
        predictions = []
        
        for event_type, data in consequence_patterns.items():
            probability = data["count"] / max(1, total_consequences)
            avg_severity = data["avg_severity"] / data["count"]
            
            predictions.append({
                "consequence_type": event_type,
                "probability": probability,
                "expected_severity": avg_severity,
                "example": data["examples"][0] if data["examples"] else "",
                "confidence": min(0.9, probability * (data["count"] / 10)),
            })
        
        # Sort by probability
        predictions.sort(key=lambda x: x["probability"], reverse=True)
        
        return predictions[:5]  # Top 5 predictions

    def get_butterfly_effect_examples(
        self,
        min_amplification: float = 5.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find the most dramatic butterfly effect examples.
        
        Args:
            min_amplification: Minimum ratio of final impact to initial impact
            limit: Maximum number of examples to return
        
        Returns:
            List of dramatic causal chains
        """
        examples = []
        
        for chain in self.chains.values():
            if chain.butterfly_effect_score >= min_amplification:
                root = self.nodes.get(chain.root_cause)
                terminal_nodes = [
                    self.nodes[nid] for nid in chain.terminal_effects
                    if nid in self.nodes
                ]
                
                examples.append({
                    "chain_id": chain.chain_id,
                    "title": chain.title,
                    "root_cause": root.description if root else "Unknown",
                    "root_severity": root.severity if root else 0,
                    "root_scope": root.scope if root else 0,
                    "final_effects": [n.description for n in terminal_nodes],
                    "total_actors_affected": chain.total_actors_affected,
                    "chain_depth": chain.total_depth,
                    "butterfly_score": chain.butterfly_effect_score,
                    "amplification": chain.total_actors_affected / max(1, root.scope if root else 1),
                })
        
        # Sort by butterfly effect score
        examples.sort(key=lambda x: x["butterfly_score"], reverse=True)
        
        return examples[:limit]

    def get_actor_causal_impact(self, actor_id: str) -> Dict[str, Any]:
        """
        Analyze an actor's causal impact on the world.
        
        Returns:
            - Events initiated
            - Events affected by
            - Total downstream consequences
            - Butterfly effect score
        """
        if actor_id not in self.actor_involvement:
            return {
                "actor_id": actor_id,
                "events_initiated": 0,
                "events_affected_by": 0,
                "total_consequences": 0,
                "butterfly_score": 0.0,
            }
        
        node_ids = self.actor_involvement[actor_id]
        nodes = [self.nodes[nid] for nid in node_ids if nid in self.nodes]
        
        initiated = [n for n in nodes if n.primary_actor_id == actor_id]
        affected = [n for n in nodes if actor_id in n.affected_actors]
        
        # Count downstream consequences
        total_consequences = 0
        for node in initiated:
            total_consequences += len(self._get_all_descendants(node.node_id))
        
        # Calculate butterfly score
        butterfly_score = 0.0
        for node in initiated:
            if node.is_root_cause and "chain_id" in node.metadata:
                chain = self.chains.get(node.metadata["chain_id"])
                if chain:
                    butterfly_score = max(butterfly_score, chain.butterfly_effect_score)
        
        return {
            "actor_id": actor_id,
            "events_initiated": len(initiated),
            "events_affected_by": len(affected),
            "total_consequences": total_consequences,
            "butterfly_score": butterfly_score,
            "most_impactful_action": initiated[0].description if initiated else None,
        }

    def _get_all_descendants(self, node_id: str) -> Set[str]:
        """Get all descendant nodes (recursive)."""
        descendants = set()
        
        def _recurse(nid: str):
            if nid in descendants:
                return
            descendants.add(nid)
            
            node = self.nodes.get(nid)
            if node:
                for child_id in node.causes:
                    _recurse(child_id)
        
        node = self.nodes.get(node_id)
        if node:
            for child_id in node.causes:
                _recurse(child_id)
        
        return descendants

    def generate_narrative_summary(self, chain_id: str) -> str:
        """Generate a human-readable narrative of a causal chain."""
        chain = self.chains.get(chain_id)
        if not chain:
            return "Chain not found"
        
        nodes = [self.nodes[nid] for nid in chain.nodes if nid in self.nodes]
        if not nodes:
            return "No events in chain"
        
        # Sort by timestamp
        nodes.sort(key=lambda n: n.timestamp)
        
        narrative_parts = [
            f"**{chain.title}**\n",
            f"It all started when: {nodes[0].description}\n",
        ]
        
        for i, node in enumerate(nodes[1:], 1):
            narrative_parts.append(f"{i}. This led to: {node.description}")
        
        narrative_parts.append(
            f"\nIn total, this chain affected {chain.total_actors_affected} entities "
            f"across {chain.total_depth} degrees of separation."
        )
        
        if chain.butterfly_effect_score > 5.0:
            narrative_parts.append(
                f"\n🦋 Butterfly Effect Score: {chain.butterfly_effect_score:.1f} "
                f"- A small action created massive consequences!"
            )
        
        return "\n".join(narrative_parts)


# Singleton
causality_tracker = CausalityTracker()
