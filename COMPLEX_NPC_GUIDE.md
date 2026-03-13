# Complex NPC Data Model - Enhancement Guide

## Overview

The NPC data model has been significantly enhanced with 13 new complex systems that make NPCs more realistic, dynamic, and emergent in their behavior.

## New Systems Added

### 1. Physiological & Biological Systems (`PhysiologicalState`)
NPCs now have physical needs and conditions:
- Health, stamina, hunger, thirst, fatigue, pain, intoxication
- Injuries with healing rates and combat/mobility effects
- Diseases (contagious or not)
- Status effects (buffs/debuffs)
- Circadian rhythm and sleep tracking

**Use cases:**
- NPCs get tired and need rest
- Injuries affect combat performance
- Hunger drives behavior (seeking food)
- Disease can spread through populations

### 2. Skills & Competencies (`SkillSet`, `Profession`)
NPCs have learned abilities and career progression:
- Combat, crafting, social, magic, and knowledge skills
- Skill experience and learning rates
- Natural talents and specializations
- Job levels, certifications, guild memberships

**Use cases:**
- Skill checks for actions
- NPCs improve over time
- Career advancement affects behavior
- Guild politics and professional networks

### 3. Economic & Inventory System (`EconomicState`, `Inventory`)
NPCs manage wealth and possessions:
- Multiple currency types
- Income sources and expenses
- Debts with interest rates
- Item ownership (equipped, carried, stored)
- Sentimental and stolen items tracking

**Use cases:**
- Trading and bartering
- Debt collection quests
- Theft detection
- Economic simulation

### 4. Social Dynamics (`SocialIdentity`, `CulturalBackground`)
Deeper social and cultural systems:
- Social class hierarchy
- Multi-dimensional reputation (by faction, location)
- Fame and infamy tracking
- Family networks, mentors, apprentices
- Cultural identity (ethnicity, language, religion)
- Customs, taboos, moral alignment

**Use cases:**
- Class-based interactions
- Reputation consequences
- Cultural conflicts
- Family drama quests
- Religious faction dynamics

### 5. Cognitive Complexity (`CognitiveState`, `BeliefSystem`)
Mental processes and biases:
- Intelligence, wisdom, creativity
- Cognitive biases (confirmation, optimism, risk aversion)
- Stress, anxiety, mental fatigue
- Trauma markers with triggers
- Phobias and addictions
- Belief systems with confidence levels
- Trusted/distrusted information sources

**Use cases:**
- NPCs make biased decisions
- PTSD and trauma responses
- Addiction-driven behavior
- Misinformation spread
- Mental health mechanics

### 6. Temporal & Routine Systems (`DailyRoutine`, `LifeHistory`)
Schedules and biographical depth:
- Hour-by-hour daily schedules
- Habits with triggers and strength
- Weekly patterns
- Life events with impact levels
- Formative experiences and regrets
- Past relationships

**Use cases:**
- Predictable NPC locations
- Time-based encounters
- Character backstory integration
- Long-term character arcs

### 7. Environmental Awareness (`SpatialAwareness`, `ContextualMemory`)
Understanding of space and context:
- Known locations with familiarity ratings
- Mental map quality
- Favorite and avoided places
- Territory and home/work locations
- Context-dependent memory recall

**Use cases:**
- Navigation behavior
- Location-based memories
- Territorial conflicts
- Exploration patterns

### 8. Personality Dynamics (`PersonalityDynamics`)
Personality evolution over time:
- Base vs current personality
- Openness to change and stability
- Recent influences tracking
- Long-term personality trends
- Life satisfaction effects

**Use cases:**
- Character development
- Traumatic events changing personality
- Maturity progression
- Dynamic character arcs

## Integration with NPCState

All new systems are integrated into the main `NPCState` class:

```python
class NPCState(BaseModel):
    # ... existing fields ...
    
    # Complex systems
    physiology: PhysiologicalState
    skills: SkillSet
    profession: Optional[Profession]
    economy: EconomicState
    inventory: Inventory
    social_identity: SocialIdentity
    cultural_background: CulturalBackground
    cognitive_state: CognitiveState
    beliefs: BeliefSystem
    routine: DailyRoutine
    life_history: LifeHistory
    spatial_awareness: SpatialAwareness
    contextual_memory: ContextualMemory
    personality_dynamics: PersonalityDynamics
```

## Example Usage

See `example_complex_npc.py` for complete examples:

1. **Complex Merchant NPC**: Full economic system, daily routine, social networks
2. **Battle-Scarred Guard**: Combat injuries, PTSD, trauma responses

## Implementation Considerations

### Performance
- These systems add significant data to each NPC
- Consider lazy loading for inactive NPCs
- Use database indexing for frequently queried fields
- Cache computed values (e.g., total_wealth)

### Simulation
- Physiological needs decay over time (hunger, fatigue)
- Skills improve with use
- Injuries heal gradually
- Routines drive autonomous behavior
- Personality can shift based on experiences

### AI Integration
- LLM prompts should include relevant system states
- Cognitive biases affect decision-making
- Beliefs influence dialogue generation
- Skills determine action success rates

### Database Schema
- Consider separate tables for complex nested structures
- Use JSONB for flexible data (PostgreSQL)
- Index frequently queried fields (social_class, location)
- Implement archival for inactive NPCs

## Migration Path

To migrate existing NPCs:

1. All new fields have sensible defaults
2. Existing NPCs will auto-initialize with default values
3. Gradually populate complex systems through gameplay
4. Use background jobs to enrich NPC data over time

## Future Enhancements

Potential additions:
- Genetic traits and heredity
- Dynamic aging and life stages
- Pregnancy and child-rearing
- Mental illness systems
- Addiction recovery mechanics
- Skill teaching/learning between NPCs
- Dynamic faction creation
- Weather/season preferences
- Food preferences and allergies
- Sleep disorders

## API Impact

New endpoints to consider:
- `GET /npc/{id}/skills` - Skill details
- `GET /npc/{id}/inventory` - Inventory management
- `GET /npc/{id}/routine` - Daily schedule
- `POST /npc/{id}/injury` - Apply injury
- `POST /npc/{id}/learn` - Skill training
- `GET /npc/{id}/biography` - Life history

## Testing

Key test scenarios:
- Injury healing over time
- Skill progression
- Economic transactions
- Routine adherence vs spontaneity
- Trauma trigger responses
- Personality drift
- Memory context associations
