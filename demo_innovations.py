"""
Demo Script for Innovation Features
Showcases all hackathon features in action
"""
import asyncio
import httpx
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"


async def demo_multi_npc_conversation():
    """Demo: NPCs talking to each other autonomously"""
    print("\n" + "="*60)
    print("🗣️  DEMO: Multi-NPC Conversations")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Create two NPCs
        print("\n1. Creating NPCs...")
        
        merchant = await client.post(f"{API_BASE}/npc/create", json={
            "name": "Aldric the Merchant",
            "archetype": "merchant",
            "location": "Market Square",
            "background": "A seasoned trader who values honesty",
            "speech_style": "formal, business-like",
        })
        merchant_data = merchant.json()
        merchant_id = merchant_data["npc_id"]
        print(f"   ✓ Created {merchant_data['name']}")
        
        guard = await client.post(f"{API_BASE}/npc/create", json={
            "name": "Captain Ironheart",
            "archetype": "guard",
            "location": "Market Square",
            "background": "Dedicated to law and order",
            "speech_style": "gruff, authoritative",
        })
        guard_data = guard.json()
        guard_id = guard_data["npc_id"]
        print(f"   ✓ Created {guard_data['name']}")
        
        # Start conversation
        print("\n2. Starting autonomous conversation...")
        conv = await client.post(f"{API_BASE}/conversation/start", json={
            "npc_ids": [merchant_id, guard_id],
            "topic": "security_concerns",
            "max_turns": 4
        })
        conv_data = conv.json()
        
        print(f"\n   Conversation between {' and '.join(conv_data['participants'])}:")
        for turn in conv_data["turns"]:
            print(f"\n   {turn['speaker_name']}: \"{turn['dialogue']}\"")
            if turn.get('action'):
                print(f"   *{turn['action']}*")
        
        print(f"\n   ✓ Conversation completed with {conv_data['total_turns']} turns")
        
        return merchant_id, guard_id


async def demo_emotional_contagion(merchant_id, guard_id):
    """Demo: Panic spreading through a crowd"""
    print("\n" + "="*60)
    print("😱 DEMO: Emotional Contagion")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Create more NPCs at the location
        print("\n1. Creating crowd of NPCs...")
        npc_ids = [merchant_id, guard_id]
        
        for i in range(5):
            npc = await client.post(f"{API_BASE}/npc/create", json={
                "name": f"Citizen {i+1}",
                "archetype": "innkeeper",
                "location": "Market Square",
            })
            npc_ids.append(npc.json()["npc_id"])
        
        print(f"   ✓ Created crowd of {len(npc_ids)} NPCs")
        
        # Simulate panic
        print("\n2. Simulating panic event...")
        panic = await client.post(f"{API_BASE}/emotion/contagion/panic", json={
            "location": "Market Square",
            "panic_source": "Dragon spotted flying overhead!",
            "intensity": 0.9
        })
        panic_data = panic.json()
        
        print(f"   ✓ Panic spread to {panic_data['affected_npcs']}/{panic_data['total_npcs']} NPCs")
        print(f"   ✓ Penetration rate: {panic_data['penetration_rate']}")
        
        # Check crowd mood
        print("\n3. Checking crowd mood...")
        mood = await client.get(f"{API_BASE}/emotion/crowd-mood/Market Square")
        mood_data = mood.json()
        
        print(f"   Dominant emotion: {mood_data['dominant_emotion']}")
        print(f"   Average valence: {mood_data['average_valence']:.2f}")
        print(f"   Average arousal: {mood_data['average_arousal']:.2f}")
        
        return npc_ids


async def demo_crime_and_quests(merchant_id, guard_id):
    """Demo: Crime triggers quests and legends"""
    print("\n" + "="*60)
    print("⚔️  DEMO: Dynamic Quest Generation")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Commit a crime
        print("\n1. Committing a crime...")
        crime = await client.post(f"{API_BASE}/world/crime", json={
            "perpetrator_id": "player_shadow",
            "victim_id": merchant_id,
            "victim_name": "Aldric the Merchant",
            "crime_type": "theft",
            "description": "Stole 100 gold coins and a precious amulet from the market stall",
            "location": "Market Square",
            "severity": 0.75,
            "witnesses": [guard_id],
            "affected_factions": ["Traders Guild"]
        })
        crime_data = crime.json()
        print(f"   ✓ Crime reported: {crime_data['crime_type']}")
        print(f"   ✓ Crime ID: {crime_data['crime_id']}")
        
        # Wait for quest generation
        await asyncio.sleep(2)
        
        # Check generated quests
        print("\n2. Checking generated quests...")
        quests = await client.get(f"{API_BASE}/quests/available")
        quests_data = quests.json()
        
        print(f"   ✓ {quests_data['total']} quests generated")
        for quest in quests_data['quests'][:3]:
            print(f"\n   Quest: {quest['title']}")
            print(f"   Type: {quest['quest_type']}")
            print(f"   Reward: {quest['rewards']['gold']} gold")
            print(f"   Urgency: {quest['urgency']:.2f}")
        
        return crime_data['crime_id']


async def demo_causality_chains(crime_id):
    """Demo: Butterfly effects and causality tracking"""
    print("\n" + "="*60)
    print("⚡ DEMO: Causality Chains & Butterfly Effects")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Get butterfly effects
        print("\n1. Analyzing butterfly effects...")
        butterfly = await client.get(f"{API_BASE}/causality/butterfly-effects?min_amplification=1.0")
        butterfly_data = butterfly.json()
        
        if butterfly_data['total'] > 0:
            print(f"   ✓ Found {butterfly_data['total']} butterfly effect chains")
            for example in butterfly_data['examples'][:2]:
                print(f"\n   Chain: {example['title']}")
                print(f"   Root cause: {example['root_cause']}")
                print(f"   Butterfly score: {example['butterfly_score']:.1f}")
                print(f"   Amplification: {example['amplification']:.1f}x")
                print(f"   Total affected: {example['total_actors_affected']} entities")
        else:
            print("   ℹ️  No butterfly effects yet (need more events)")
        
        # Predict consequences
        print("\n2. Predicting consequences of future theft...")
        predict = await client.post(f"{API_BASE}/causality/predict", json={
            "event_type": "theft",
            "actor_id": "player_shadow",
            "severity": 0.8
        })
        predict_data = predict.json()
        
        print("   Predicted consequences:")
        for pred in predict_data['predictions'][:3]:
            print(f"   - {pred['consequence_type']}: {pred['probability']*100:.0f}% likely")
            print(f"     Confidence: {pred['confidence']*100:.0f}%")


async def demo_legends():
    """Demo: Cultural memory and legend formation"""
    print("\n" + "="*60)
    print("📜 DEMO: Cultural Legends")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Get legends
        print("\n1. Checking cultural legends...")
        legends = await client.get(f"{API_BASE}/legends?min_spread=1")
        legends_data = legends.json()
        
        if legends_data['total'] > 0:
            print(f"   ✓ Found {legends_data['total']} legends")
            for legend in legends_data['legends'][:3]:
                print(f"\n   Legend: {legend['title']}")
                print(f"   Status: {legend['status']}")
                print(f"   Protagonist: {legend['protagonist']}")
                print(f"   Spread: {legend['spread']} NPCs know this")
                print(f"   Fidelity: {legend['fidelity']*100:.0f}%")
                print(f"   Age: {legend['age_days']} days")
        else:
            print("   ℹ️  No legends yet (need more significant events)")
        
        # Check protagonist reputation
        print("\n2. Checking protagonist reputation...")
        rep = await client.get(f"{API_BASE}/legends/reputation/player_shadow")
        rep_data = rep.json()
        
        print(f"   Reputation score: {rep_data['reputation_score']:.2f}")
        print(f"   Category: {rep_data['category']}")
        print(f"   Legend count: {rep_data['legend_count']}")
        if rep_data.get('most_famous_legend'):
            print(f"   Most famous: {rep_data['most_famous_legend']}")


async def demo_dreams(npc_id):
    """Demo: NPC dreams and subconscious processing"""
    print("\n" + "="*60)
    print("💭 DEMO: Dreams & Subconscious")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # Generate dream
        print("\n1. Generating dream for NPC...")
        dream = await client.post(f"{API_BASE}/dreams/generate/{npc_id}")
        dream_data = dream.json()
        
        if 'message' in dream_data:
            print(f"   {dream_data['message']}")
        else:
            print(f"   ✓ Dream generated: {dream_data['dream_type']}")
            print(f"\n   Content: {dream_data['content']}")
            print(f"\n   Symbolism: {', '.join(dream_data['symbolism'])}")
            print(f"   Vividness: {dream_data['vividness']*100:.0f}%")
            print(f"   Interpretation: {dream_data['interpretation']}")
            
            if dream_data.get('emotion_impact'):
                print(f"\n   Emotional impact:")
                for emotion, change in dream_data['emotion_impact'].items():
                    print(f"   - {emotion}: {change:+.2f}")


async def demo_analytics():
    """Demo: World state analytics"""
    print("\n" + "="*60)
    print("📊 DEMO: World Analytics")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        analytics = await client.get(f"{API_BASE}/analytics/world-state")
        data = analytics.json()
        
        print(f"\n   Total NPCs: {data['total_npcs']}")
        print(f"   Dominant emotion: {data['dominant_world_emotion']}")
        print(f"   Causal events: {data['total_causal_events']}")
        print(f"   Causal chains: {data['total_causal_chains']}")
        print(f"   Legends: {data['total_legends']}")
        print(f"   Active quests: {data['active_quests']}")
        print(f"   Locations: {', '.join(data['locations'])}")
        
        print("\n   Average emotions:")
        for emotion, value in data['average_emotions'].items():
            bar = "█" * int(value * 20)
            print(f"   {emotion:12s} {bar} {value:.2f}")


async def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("🎮 SENTIENT NPC ENGINE 3.0 - INNOVATION DEMO")
    print("="*60)
    print("\nThis demo showcases all hackathon innovation features:")
    print("- Multi-NPC Conversations")
    print("- Emotional Contagion")
    print("- Dynamic Quest Generation")
    print("- Causality Chains & Butterfly Effects")
    print("- Cultural Legends")
    print("- Dreams & Subconscious")
    print("- Real-time Analytics")
    
    try:
        # Run demos in sequence
        merchant_id, guard_id = await demo_multi_npc_conversation()
        npc_ids = await demo_emotional_contagion(merchant_id, guard_id)
        crime_id = await demo_crime_and_quests(merchant_id, guard_id)
        await demo_causality_chains(crime_id)
        await demo_legends()
        await demo_dreams(merchant_id)
        await demo_analytics()
        
        print("\n" + "="*60)
        print("✅ DEMO COMPLETE!")
        print("="*60)
        print("\nNext steps:")
        print("1. Visit the dashboard: http://localhost:8000/dashboard")
        print("2. Explore the API docs: http://localhost:8000/docs")
        print("3. Check INNOVATION_API.md for detailed documentation")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure the server is running:")
        print("  uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
