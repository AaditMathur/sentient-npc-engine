"""
Database migration and initialization script.
Run once before starting the server for the first time.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import init_all_databases, AsyncSessionLocal
from app.models import NPCState, PersonalityVector, EmotionVector, Goal, GoalStatus
from app.brain.npc_brain import NPCRepository
from app.social.graph import social_graph
import structlog

logger = structlog.get_logger()


async def seed_demo_npcs():
    """Seed the database with example NPCs for testing."""
    repo = NPCRepository()

    demo_npcs = [
        {
            "name": "Aldric the Merchant",
            "archetype": "merchant",
            "faction": "Traders Guild",
            "location": "Ironhaven Market",
            "background": "A weathered merchant who has traveled all the roads between the Five Cities. He's seen wars, famines, and three dragon attacks. Trust is earned, not given.",
            "speech_style": "formal medieval, slightly suspicious of strangers",
            "personality": PersonalityVector(greed=0.75, empathy=0.35, honesty=0.5, bravery=0.3, curiosity=0.55, loyalty=0.4, aggression=0.2),
            "goals": [
                Goal(name="increase_wealth", description="Maximize profit this market season", base_weight=0.8, status=GoalStatus.ACTIVE),
                Goal(name="sell_goods", description="Move the silk shipment before prices drop", base_weight=0.7, status=GoalStatus.ACTIVE),
            ]
        },
        {
            "name": "Captain Sera Valdris",
            "archetype": "guard",
            "faction": "City Watch",
            "location": "Ironhaven Gate",
            "background": "A decorated veteran of the Northern Wars who now keeps the peace in Ironhaven. She is incorruptible but not unkind. She's seen too much death to take it lightly.",
            "speech_style": "direct and authoritative, military cadence",
            "personality": PersonalityVector(greed=0.1, empathy=0.45, honesty=0.9, bravery=0.85, curiosity=0.3, loyalty=0.95, aggression=0.5),
            "goals": [
                Goal(name="protect_village", description="Keep Ironhaven safe from bandits", base_weight=0.9, status=GoalStatus.ACTIVE),
            ]
        },
        {
            "name": "Mira the Herbalist",
            "archetype": "healer",
            "faction": "Circle of Healers",
            "location": "Ironhaven Apothecary",
            "background": "A gentle soul who grew up foraging in the Greywood. She knows remedies for every ailment but struggles with the ugliness she sees in people.",
            "speech_style": "soft-spoken, uses herbal metaphors, deeply empathetic",
            "personality": PersonalityVector(greed=0.1, empathy=0.95, honesty=0.8, bravery=0.4, curiosity=0.7, loyalty=0.65, aggression=0.05),
            "goals": [
                Goal(name="help_villagers", description="Prepare medicines for the coming winter", base_weight=0.8, status=GoalStatus.ACTIVE),
                Goal(name="gather_information", description="Learn about the plague spreading in the East", base_weight=0.6, status=GoalStatus.PENDING),
            ]
        },
    ]

    created = []
    async with AsyncSessionLocal() as db:
        for npc_data in demo_npcs:
            goals = npc_data.pop("goals", [])
            personality = npc_data.pop("personality")
            npc = NPCState(
                **npc_data,
                personality=personality,
                goals=goals,
            )
            await repo.create(db, npc)
            await social_graph.upsert_npc_node(npc)
            created.append(npc)
            logger.info("demo_npc_created", name=npc.name, npc_id=npc.npc_id)
        await db.commit()

    # Create some relationships
    async with AsyncSessionLocal() as db:
        if len(created) >= 2:
            from app.models import Relationship, RelationshipType
            # Aldric and Sera know each other
            await social_graph.upsert_relationship(
                created[0].npc_id,
                created[1].npc_id,
                Relationship(
                    target_id=created[1].npc_id,
                    target_name=created[1].name,
                    relationship_type=RelationshipType.NEUTRAL,
                    trust=0.6,
                    friendship=0.4,
                    respect=0.7,
                    interaction_count=12,
                )
            )
            logger.info("demo_relationship_created",
                        source=created[0].name,
                        target=created[1].name)

    return created


async def main():
    print("=" * 60)
    print("  Sentient NPC Engine 3.0 — Database Migration")
    print("=" * 60)

    print("\n[1/3] Initializing databases...")
    await init_all_databases()
    print("  ✓ PostgreSQL tables created")
    print("  ✓ Qdrant collection initialized")
    print("  ✓ Neo4j constraints created")

    print("\n[2/3] Seeding demo NPCs...")
    npcs = await seed_demo_npcs()
    print(f"  ✓ Created {len(npcs)} demo NPCs")
    for npc in npcs:
        print(f"      - {npc.name} [{npc.archetype}] → {npc.npc_id}")

    print("\n[3/3] Migration complete!")
    print("\nStart the server with:")
    print("  uvicorn app.main:app --reload --port 8000")
    print("\nStart the background worker with:")
    print("  python workers/simulation_worker.py")
    print("\nAPI docs at: http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
