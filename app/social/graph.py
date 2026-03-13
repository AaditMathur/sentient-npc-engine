"""
Social Relationship Graph Engine — backed by Neo4j.

Graph schema:
  (:NPC {npc_id, name, faction, archetype})
  -[:KNOWS {trust, fear, friendship, respect, faction_alignment, interaction_count}]->
  (:NPC)

Also supports Player nodes for player-NPC relationships.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from app.models import Relationship, RelationshipType, NPCState
from app.database import get_neo4j_driver


class SocialGraph:
    """Manages NPC relationship graph via Neo4j async driver."""

    async def upsert_npc_node(self, npc: NPCState) -> None:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (n:NPC {npc_id: $npc_id})
                SET n.name = $name,
                    n.archetype = $archetype,
                    n.faction = $faction,
                    n.location = $location,
                    n.updated_at = datetime()
                """,
                npc_id=npc.npc_id,
                name=npc.name,
                archetype=npc.archetype,
                faction=npc.faction or "",
                location=npc.location or "",
            )

    async def upsert_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship: Relationship,
    ) -> None:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (s:NPC {npc_id: $source_id})
                MERGE (t:NPC {npc_id: $target_id})
                MERGE (s)-[r:KNOWS]->(t)
                SET r.trust = $trust,
                    r.fear = $fear,
                    r.friendship = $friendship,
                    r.respect = $respect,
                    r.faction_alignment = $faction_alignment,
                    r.relationship_type = $rel_type,
                    r.interaction_count = $interaction_count,
                    r.last_interaction = datetime()
                """,
                source_id=source_id,
                target_id=target_id,
                trust=relationship.trust,
                fear=relationship.fear,
                friendship=relationship.friendship,
                respect=relationship.respect,
                faction_alignment=relationship.faction_alignment,
                rel_type=relationship.relationship_type.value,
                interaction_count=relationship.interaction_count,
            )

    async def get_relationship(
        self,
        source_id: str,
        target_id: str,
    ) -> Optional[Relationship]:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (s:NPC {npc_id: $source_id})-[r:KNOWS]->(t:NPC {npc_id: $target_id})
                RETURN r, t.name as target_name
                """,
                source_id=source_id,
                target_id=target_id,
            )
            record = await result.single()
            if not record:
                return None
            r = record["r"]
            return Relationship(
                target_id=target_id,
                target_name=record["target_name"],
                relationship_type=RelationshipType(r.get("relationship_type", "neutral")),
                trust=r.get("trust", 0.5),
                fear=r.get("fear", 0.0),
                friendship=r.get("friendship", 0.5),
                respect=r.get("respect", 0.5),
                faction_alignment=r.get("faction_alignment", 0.0),
                interaction_count=r.get("interaction_count", 0),
            )

    async def get_all_relationships(
        self,
        npc_id: str,
        limit: int = 50,
    ) -> List[Relationship]:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (s:NPC {npc_id: $npc_id})-[r:KNOWS]->(t:NPC)
                RETURN r, t.npc_id as target_id, t.name as target_name
                ORDER BY r.friendship DESC, r.trust DESC
                LIMIT $limit
                """,
                npc_id=npc_id,
                limit=limit,
            )
            relationships = []
            async for record in result:
                r = record["r"]
                relationships.append(Relationship(
                    target_id=record["target_id"],
                    target_name=record["target_name"],
                    relationship_type=RelationshipType(r.get("relationship_type", "neutral")),
                    trust=r.get("trust", 0.5),
                    fear=r.get("fear", 0.0),
                    friendship=r.get("friendship", 0.5),
                    respect=r.get("respect", 0.5),
                    faction_alignment=r.get("faction_alignment", 0.0),
                    interaction_count=r.get("interaction_count", 0),
                ))
            return relationships

    async def get_faction_members(
        self,
        faction: str,
        limit: int = 100,
    ) -> List[str]:
        """Get all NPC IDs in a faction."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (n:NPC {faction: $faction})
                RETURN n.npc_id as npc_id
                LIMIT $limit
                """,
                faction=faction,
                limit=limit,
            )
            npc_ids = []
            async for record in result:
                npc_ids.append(record["npc_id"])
            return npc_ids

    async def update_relationship_delta(
        self,
        source_id: str,
        target_id: str,
        deltas: Dict[str, float],
    ) -> None:
        """Apply incremental changes to relationship metrics."""
        existing = await self.get_relationship(source_id, target_id)
        if existing is None:
            existing = Relationship(
                target_id=target_id,
                target_name=target_id,
            )
        rel_dict = existing.model_dump()
        for key, delta in deltas.items():
            if key in rel_dict and isinstance(rel_dict[key], float):
                rel_dict[key] = max(0.0, min(1.0, rel_dict[key] + delta))
        existing = existing.model_copy(update=rel_dict)
        existing.interaction_count += 1
        await self.upsert_relationship(source_id, target_id, existing)

    async def find_shortest_path(
        self,
        source_id: str,
        target_id: str,
    ) -> List[str]:
        """
        Find shortest relationship chain between two NPCs.
        Useful for rumor propagation and social influence.
        """
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH path = shortestPath(
                    (s:NPC {npc_id: $source_id})-[:KNOWS*..6]->(t:NPC {npc_id: $target_id})
                )
                RETURN [n in nodes(path) | n.npc_id] as path_ids
                """,
                source_id=source_id,
                target_id=target_id,
            )
            record = await result.single()
            return record["path_ids"] if record else []

    async def get_npcs_who_trust(
        self,
        target_id: str,
        min_trust: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Find NPCs that highly trust a given NPC (for rumor propagation)."""
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (s:NPC)-[r:KNOWS]->(t:NPC {npc_id: $target_id})
                WHERE r.trust >= $min_trust
                RETURN s.npc_id as npc_id, s.name as name, r.trust as trust
                ORDER BY r.trust DESC
                """,
                target_id=target_id,
                min_trust=min_trust,
            )
            records = []
            async for record in result:
                records.append({
                    "npc_id": record["npc_id"],
                    "name": record["name"],
                    "trust": record["trust"],
                })
            return records

    async def get_relationship_summary_for_prompt(
        self,
        npc_id: str,
        player_id: str,
    ) -> str:
        """Returns natural language relationship summary for LLM prompt."""
        rel = await self.get_relationship(npc_id, player_id)
        if rel is None:
            return "You have never met this person before."

        lines = []
        if rel.trust > 0.7:
            lines.append(f"You trust {rel.target_name} deeply.")
        elif rel.trust < 0.3:
            lines.append(f"You are very suspicious of {rel.target_name}.")
        else:
            lines.append(f"You have moderate trust in {rel.target_name}.")

        if rel.fear > 0.5:
            lines.append("They intimidate you.")
        if rel.friendship > 0.7:
            lines.append("You consider them a friend.")
        elif rel.friendship < 0.3:
            lines.append("You dislike them.")
        if rel.interaction_count > 0:
            lines.append(f"You have interacted {rel.interaction_count} time(s) before.")

        return " ".join(lines)


# Singleton
social_graph = SocialGraph()
