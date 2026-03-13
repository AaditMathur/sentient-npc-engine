"""
Test script to verify all innovation features are working
"""
import sys

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from app.conversation.multi_npc import multi_npc_conversation
        print("  ✓ Multi-NPC conversation module")
    except Exception as e:
        print(f"  ✗ Multi-NPC conversation module: {e}")
        return False
    
    try:
        from app.emotion.contagion import emotional_contagion
        print("  ✓ Emotional contagion module")
    except Exception as e:
        print(f"  ✗ Emotional contagion module: {e}")
        return False
    
    try:
        from app.quests.generator import quest_generator
        print("  ✓ Quest generator module")
    except Exception as e:
        print(f"  ✗ Quest generator module: {e}")
        return False
    
    try:
        from app.causality.tracker import causality_tracker
        print("  ✓ Causality tracker module")
    except Exception as e:
        print(f"  ✗ Causality tracker module: {e}")
        return False
    
    try:
        from app.culture.legends import cultural_memory
        print("  ✓ Cultural memory module")
    except Exception as e:
        print(f"  ✗ Cultural memory module: {e}")
        return False
    
    try:
        from app.dreams.engine import dream_engine
        print("  ✓ Dream engine module")
    except Exception as e:
        print(f"  ✗ Dream engine module: {e}")
        return False
    
    return True


def test_main_app():
    """Test that main app can be imported"""
    print("\nTesting main app...")
    
    try:
        from app.main import app
        print("  ✓ Main app imports successfully")
        return True
    except Exception as e:
        print(f"  ✗ Main app import failed: {e}")
        return False


def test_api_routes():
    """Test that API routes are loaded"""
    print("\nTesting API routes...")
    
    try:
        from app.api.innovation_routes import router
        route_count = len(router.routes)
        print(f"  ✓ Innovation routes loaded: {route_count} endpoints")
        
        # List all routes
        print("\n  Available endpoints:")
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods)
                print(f"    {methods:6s} {route.path}")
        
        return True
    except Exception as e:
        print(f"  ✗ API routes failed: {e}")
        return False


def test_models():
    """Test that all models can be created"""
    print("\nTesting models...")
    
    try:
        from app.models import NPCState, EmotionVector, PersonalityVector
        
        # Create test NPC
        npc = NPCState(
            name="Test NPC",
            archetype="merchant",
            personality=PersonalityVector(),
            emotion_state=EmotionVector(),
        )
        print(f"  ✓ Created test NPC: {npc.name}")
        
        return True
    except Exception as e:
        print(f"  ✗ Model creation failed: {e}")
        return False


def test_causality():
    """Test causality tracker"""
    print("\nTesting causality tracker...")
    
    try:
        from app.causality.tracker import causality_tracker, CausalEventType
        
        # Record test event
        node = causality_tracker.record_event(
            event_type=CausalEventType.PLAYER_ACTION,
            description="Test event",
            primary_actor_id="test_player",
            severity=0.5,
        )
        
        print(f"  ✓ Recorded causal event: {node.node_id}")
        print(f"  ✓ Total events tracked: {len(causality_tracker.nodes)}")
        
        return True
    except Exception as e:
        print(f"  ✗ Causality tracker failed: {e}")
        return False


def test_legends():
    """Test legend system"""
    print("\nTesting legend system...")
    
    try:
        from app.culture.legends import cultural_memory, LegendType
        
        # Create test legend
        legend = cultural_memory.create_legend_from_event(
            event_description="A great heist was committed",
            protagonist_id="test_thief",
            protagonist_name="Shadow Thief",
            event_type="theft",
            severity=0.8,
            witnesses=["witness1", "witness2", "witness3"],
            location="Market Square",
        )
        
        if legend:
            print(f"  ✓ Created legend: {legend.title}")
            print(f"  ✓ Legend spread: {legend.spread} NPCs")
        else:
            print("  ℹ️  Legend not created (expected for low severity)")
        
        return True
    except Exception as e:
        print(f"  ✗ Legend system failed: {e}")
        return False


def test_quests():
    """Test quest generator"""
    print("\nTesting quest generator...")
    
    try:
        from app.quests.generator import quest_generator, QuestType
        from app.models import CrimeRecord, CrimeType, NPCState, PersonalityVector, EmotionVector
        
        # Create test NPC and crime
        npc = NPCState(
            name="Victim NPC",
            archetype="merchant",
            personality=PersonalityVector(aggression=0.7),
            emotion_state=EmotionVector(anger=0.8),
        )
        
        crime = CrimeRecord(
            perpetrator_id="test_criminal",
            victim_id=npc.npc_id,
            victim_name=npc.name,
            crime_type=CrimeType.THEFT,
            description="Stole valuable goods",
            severity=0.7,
            witnesses=["witness1"],
        )
        
        # Generate quest
        quest = quest_generator.generate_quest_from_crime(
            npc=npc,
            crime=crime,
            awareness_level="victim",
        )
        
        if quest:
            print(f"  ✓ Generated quest: {quest.title}")
            print(f"  ✓ Quest type: {quest.quest_type}")
            print(f"  ✓ Reward: {quest.rewards.gold} gold")
        else:
            print("  ℹ️  No quest generated")
        
        return True
    except Exception as e:
        print(f"  ✗ Quest generator failed: {e}")
        return False


def test_dreams():
    """Test dream engine"""
    print("\nTesting dream engine...")
    
    try:
        from app.dreams.engine import dream_engine
        from app.models import NPCState, PersonalityVector, EmotionVector
        
        # Create test NPC
        npc = NPCState(
            name="Dreaming NPC",
            archetype="wizard",
            personality=PersonalityVector(curiosity=0.9),
            emotion_state=EmotionVector(fear=0.7),
        )
        
        # Generate dream
        dream = dream_engine.generate_dream(npc, [], hours_since_last_dream=24)
        
        if dream:
            print(f"  ✓ Generated dream: {dream.dream_type}")
            print(f"  ✓ Vividness: {dream.vividness:.2f}")
        else:
            print("  ℹ️  No dream generated (random chance)")
        
        return True
    except Exception as e:
        print(f"  ✗ Dream engine failed: {e}")
        return False


def test_emotional_contagion():
    """Test emotional contagion"""
    print("\nTesting emotional contagion...")
    
    try:
        from app.emotion.contagion import emotional_contagion
        from app.models import NPCState, PersonalityVector, EmotionVector
        
        # Create test NPCs
        npcs = []
        for i in range(5):
            npc = NPCState(
                name=f"NPC {i}",
                archetype="innkeeper",
                personality=PersonalityVector(empathy=0.7),
                emotion_state=EmotionVector(),
                location="Market Square",
            )
            npcs.append(npc)
        
        # Simulate panic
        updated = emotional_contagion.simulate_crowd_panic(
            npcs=npcs,
            panic_source="Test panic",
            initial_intensity=0.8,
        )
        
        print(f"  ✓ Panic spread to {len(updated)}/{len(npcs)} NPCs")
        
        # Calculate crowd mood
        mood = emotional_contagion.calculate_crowd_mood(npcs)
        print(f"  ✓ Crowd mood: {mood['dominant_emotion']}")
        
        return True
    except Exception as e:
        print(f"  ✗ Emotional contagion failed: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("INNOVATION FEATURES TEST SUITE")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Main App", test_main_app),
        ("API Routes", test_api_routes),
        ("Models", test_models),
        ("Causality Tracker", test_causality),
        ("Legend System", test_legends),
        ("Quest Generator", test_quests),
        ("Dream Engine", test_dreams),
        ("Emotional Contagion", test_emotional_contagion),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8s} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for demo.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
