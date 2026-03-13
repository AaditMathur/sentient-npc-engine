"""
Example: Creating a Complex NPC with Enhanced Data Model
Demonstrates the new physiological, cognitive, social, and economic systems.
"""
from models import (
    NPCState, PersonalityVector, EmotionVector,
    PhysiologicalState, SkillSet, Profession, EconomicState,
    SocialIdentity, CulturalBackground, CognitiveState,
    DailyRoutine, LifeHistory, SpatialAwareness,
    Item, Injury, ScheduledActivity, LifeEvent,
    SocialClass, Habit, LocationKnowledge
)
from datetime import datetime, timedelta


def create_complex_merchant_npc():
    """Create a detailed merchant NPC with full complexity"""
    
    # Basic personality
    personality = PersonalityVector(
        greed=0.7,
        bravery=0.4,
        empathy=0.6,
        loyalty=0.8,
        curiosity=0.5,
        honesty=0.6,
        aggression=0.2
    )
    
    # Skills for a merchant
    skills = SkillSet(
        social_skills={
            "persuasion": 0.8,
            "deception": 0.4,
            "negotiation": 0.9,
            "intimidation": 0.3
        },
        knowledge_domains={
            "economics": 0.8,
            "geography": 0.7,
            "appraisal": 0.9
        },
        crafting_skills={
            "accounting": 0.7
        },
        learning_rate=0.6,
        specializations=["trade", "finance"],
        natural_talents={"charisma": 0.8}
    )
    
    # Profession details
    profession = Profession(
        primary_job="merchant",
        secondary_jobs=["moneylender"],
        job_level=5,
        job_experience=1500.0,
        reputation_score=0.75,
        guild_memberships=["Traders Guild", "Merchants Association"]
    )
    
    # Economic state
    economy = EconomicState(
        currency={"gold": 5000, "silver": 2000},
        total_wealth=7000.0,
        haggling_skill=0.85,
        price_memory={
            "sword": 50.0,
            "bread": 0.5,
            "horse": 200.0
        }
    )
    
    # Social identity
    social_identity = SocialIdentity(
        social_class=SocialClass.MERCHANT,
        titles=["Master Trader"],
        reputation_by_faction={
            "Traders Guild": 0.9,
            "City Guard": 0.6,
            "Thieves Guild": 0.3
        },
        fame_level=0.6,
        leadership_score=0.7,
        close_friends=["npc_001", "npc_045"],
        family_members=["npc_102", "npc_103"]
    )
    
    # Cultural background
    culture = CulturalBackground(
        ethnicity="coastal_human",
        native_language="common",
        known_languages=["common", "elvish", "dwarvish"],
        accent="merchant_formal",
        religion="Goddess of Fortune",
        religious_devotion=0.6,
        moral_alignment="lawful_neutral",
        customs=["morning_prayer", "tea_ceremony"],
        taboos=["theft", "breaking_contracts"]
    )
    
    # Cognitive state
    cognitive = CognitiveState(
        intelligence=0.7,
        wisdom=0.8,
        creativity=0.6,
        risk_aversion=0.6,
        loss_aversion=0.7,
        stress_level=0.3
    )
    
    # Daily routine
    routine = DailyRoutine(
        schedule={
            6: ScheduledActivity(activity_name="morning_prayer", duration_hours=0.5),
            7: ScheduledActivity(activity_name="breakfast", duration_hours=1.0),
            8: ScheduledActivity(activity_name="open_shop", location="market_square", duration_hours=8.0),
            18: ScheduledActivity(activity_name="dinner", duration_hours=1.5),
            20: ScheduledActivity(activity_name="accounting", duration_hours=2.0),
            22: ScheduledActivity(activity_name="sleep", duration_hours=8.0)
        },
        habits=[
            Habit(
                habit_name="count_coins",
                trigger="end_of_day",
                frequency="daily",
                strength=0.9
            )
        ],
        routine_adherence=0.8,
        spontaneity=0.2
    )
    
    # Life history
    life_history = LifeHistory(
        age=45,
        birthplace="Port City",
        life_events=[
            LifeEvent(
                event_name="inherited_shop",
                description="Inherited father's trading business",
                impact_level=0.9,
                age_at_event=25
            ),
            LifeEvent(
                event_name="survived_plague",
                description="Lost wife to plague but survived",
                impact_level=0.8,
                age_at_event=35
            )
        ],
        formative_experiences=["apprenticed_to_father", "first_major_trade_deal"],
        major_achievements=["guild_master_rank", "opened_three_shops"],
        regrets=["not_spending_time_with_wife"]
    )
    
    # Spatial awareness
    spatial = SpatialAwareness(
        known_locations={
            "market_square": LocationKnowledge(
                location_name="market_square",
                familiarity=1.0,
                safety_rating=0.9,
                visit_count=5000
            ),
            "docks": LocationKnowledge(
                location_name="docks",
                familiarity=0.8,
                safety_rating=0.6,
                visit_count=500
            )
        },
        favorite_places=["market_square", "guild_hall"],
        avoided_places=["dark_alley", "slums"],
        home_location="merchant_district",
        work_location="market_square",
        mental_map_quality=0.9,
        sense_of_direction=0.8
    )
    
    # Physiological state (healthy merchant)
    physiology = PhysiologicalState(
        health=0.9,
        stamina=0.7,
        hunger=0.2,
        fatigue=0.3,
        circadian_rhythm=0.7  # morning person
    )
    
    # Create the full NPC
    npc = NPCState(
        name="Aldric the Prosperous",
        archetype="merchant",
        faction="Traders Guild",
        location="market_square",
        personality=personality,
        background="A successful merchant who inherited his father's business and expanded it into a trading empire. Lost his wife to plague 10 years ago but found solace in his work.",
        speech_style="formal_merchant",
        
        # Complex systems
        physiology=physiology,
        skills=skills,
        profession=profession,
        economy=economy,
        social_identity=social_identity,
        cultural_background=culture,
        cognitive_state=cognitive,
        routine=routine,
        life_history=life_history,
        spatial_awareness=spatial
    )
    
    return npc


def create_complex_guard_npc():
    """Create a battle-hardened guard with injuries and trauma"""
    
    # Guard with combat injuries
    physiology = PhysiologicalState(
        health=0.7,
        stamina=0.8,
        pain=0.3,
        injuries=[
            Injury(
                injury_type="sword_scar",
                severity=0.4,
                location="left_arm",
                healing_rate=0.05,
                affects_combat=True
            )
        ]
    )
    
    # Combat skills
    skills = SkillSet(
        combat_skills={
            "swordsmanship": 0.9,
            "shield_defense": 0.8,
            "hand_to_hand": 0.7
        },
        social_skills={
            "intimidation": 0.8,
            "perception": 0.7
        },
        learning_rate=0.4
    )
    
    # Traumatized from war
    cognitive = CognitiveState(
        intelligence=0.5,
        wisdom=0.6,
        stress_level=0.5,
        trauma_markers=[
            {
                "event_description": "Witnessed massacre during war",
                "severity": 0.8,
                "triggers": ["blood", "screaming", "fire"]
            }
        ],
        phobias=["fire"]
    )
    
    npc = NPCState(
        name="Marcus the Scarred",
        archetype="guard",
        faction="City Watch",
        location="city_gate",
        personality=PersonalityVector(
            bravery=0.9,
            loyalty=0.9,
            aggression=0.6,
            empathy=0.4
        ),
        background="A veteran guard who survived the Great War but carries the scars, both physical and mental.",
        speech_style="gruff_military",
        
        physiology=physiology,
        skills=skills,
        cognitive_state=cognitive,
        life_history=LifeHistory(
            age=38,
            birthplace="Capital City",
            life_events=[
                LifeEvent(
                    event_name="great_war",
                    description="Fought in the Great War for 5 years",
                    impact_level=1.0,
                    age_at_event=25
                )
            ]
        )
    )
    
    return npc


if __name__ == "__main__":
    # Create examples
    merchant = create_complex_merchant_npc()
    guard = create_complex_guard_npc()
    
    print(f"Created merchant: {merchant.name}")
    print(f"  - Wealth: {merchant.economy.total_wealth} gold")
    print(f"  - Social class: {merchant.social_identity.social_class}")
    print(f"  - Age: {merchant.life_history.age}")
    print(f"  - Skills: {list(merchant.skills.social_skills.keys())}")
    print(f"  - Daily routine: {len(merchant.routine.schedule)} scheduled activities")
    
    print(f"\nCreated guard: {guard.name}")
    print(f"  - Health: {guard.physiology.health}")
    print(f"  - Injuries: {len(guard.physiology.injuries)}")
    print(f"  - Trauma markers: {len(guard.cognitive_state.trauma_markers)}")
    print(f"  - Combat skills: {list(guard.skills.combat_skills.keys())}")
