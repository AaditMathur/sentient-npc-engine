using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;

namespace SentientNPC
{
    // ─────────────────────────────────────────────
    // DATA MODELS
    // ─────────────────────────────────────────────

    [Serializable]
    public class EmotionState
    {
        public float joy;
        public float trust;
        public float fear;
        public float anger;
        public float sadness;
        public float surprise;
        public float disgust;
        public float anticipation;

        public string DominantEmotion()
        {
            var emotions = new Dictionary<string, float>
            {
                { "joy", joy }, { "trust", trust }, { "fear", fear },
                { "anger", anger }, { "sadness", sadness }, { "surprise", surprise },
                { "disgust", disgust }, { "anticipation", anticipation }
            };
            string dominant = "neutral";
            float max = 0f;
            foreach (var kv in emotions)
                if (kv.Value > max) { max = kv.Value; dominant = kv.Key; }
            return dominant;
        }
    }

    [Serializable]
    public class PersonalityVector
    {
        public float greed = 0.5f;
        public float bravery = 0.5f;
        public float empathy = 0.5f;
        public float loyalty = 0.5f;
        public float curiosity = 0.5f;
        public float honesty = 0.5f;
        public float aggression = 0.3f;
    }

    [Serializable]
    public class NPCGoal
    {
        public string goal_id;
        public string name;
        public string description;
        public string status;
        public float current_priority;
    }

    [Serializable]
    public class NPCCreateRequest
    {
        public string name;
        public string archetype;
        public string faction;
        public string location;
        public PersonalityVector personality;
        public string background;
        public string speech_style;
        public List<string> initial_goals = new List<string>();
    }

    [Serializable]
    public class NPCCreateResponse
    {
        public string npc_id;
        public string name;
        public string archetype;
        public EmotionState emotion_state;
        public List<string> goals;
    }

    [Serializable]
    public class InteractRequest
    {
        public string npc_id;
        public string player_id;
        public string player_message;
        public Dictionary<string, object> context;
    }

    [Serializable]
    public class InteractResponse
    {
        public string npc_id;
        public string dialogue;
        public string npc_action;
        public EmotionState emotion_after;
        public List<string> memories_recalled;
        public Dictionary<string, float> relationship_delta;
    }

    [Serializable]
    public class NPCStateResponse
    {
        public string npc_id;
        public string name;
        public string archetype;
        public EmotionState emotion_state;
        public string dominant_emotion;
        public float mood_valence;
        public List<NPCGoal> active_goals;
        public int memory_count;
        public string location;
    }

    [Serializable]
    public class WorldEventRequest
    {
        public string event_type;
        public string description;
        public string location;
        public List<string> affected_factions = new List<string>();
        public float severity = 0.5f;
        public float radius = 100f;
    }

    [Serializable]
    public class WorldEventResponse
    {
        public string event_id;
        public string stream_entry_id;
        public string status;
    }

    // ─────────────────────────────────────────────
    // SENTIENT NPC CLIENT
    // ─────────────────────────────────────────────

    public class SentientNPCClient : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private string apiBaseUrl = "http://localhost:8000/api/v1";
        [SerializeField] private float requestTimeoutSeconds = 30f;

        private static SentientNPCClient _instance;
        public static SentientNPCClient Instance => _instance;

        void Awake()
        {
            if (_instance != null && _instance != this)
            {
                Destroy(gameObject);
                return;
            }
            _instance = this;
            DontDestroyOnLoad(gameObject);
        }

        // ── CREATE NPC ──────────────────────────

        public async Task<NPCCreateResponse> CreateNPC(NPCCreateRequest request)
        {
            string json = JsonConvert.SerializeObject(request);
            return await Post<NPCCreateResponse>("/npc/create", json);
        }

        // ── INTERACT ────────────────────────────

        public async Task<InteractResponse> Interact(
            string npcId,
            string playerId,
            string message)
        {
            var request = new InteractRequest
            {
                npc_id = npcId,
                player_id = playerId,
                player_message = message,
            };
            string json = JsonConvert.SerializeObject(request);
            return await Post<InteractResponse>("/npc/interact", json);
        }

        // Coroutine wrapper for use without async/await
        public IEnumerator InteractCoroutine(
            string npcId,
            string playerId,
            string message,
            Action<InteractResponse> onSuccess,
            Action<string> onError = null)
        {
            yield return PostCoroutine<InteractResponse>(
                "/npc/interact",
                JsonConvert.SerializeObject(new InteractRequest
                {
                    npc_id = npcId,
                    player_id = playerId,
                    player_message = message,
                }),
                onSuccess,
                onError
            );
        }

        // ── GET STATE ───────────────────────────

        public async Task<NPCStateResponse> GetNPCState(string npcId)
        {
            return await Get<NPCStateResponse>($"/npc/{npcId}");
        }

        // ── WORLD EVENT ─────────────────────────

        public async Task<WorldEventResponse> PublishWorldEvent(WorldEventRequest request)
        {
            string json = JsonConvert.SerializeObject(request);
            return await Post<WorldEventResponse>("/world/event", json);
        }

        // ─────────────────────────────────────────────
        // HTTP HELPERS
        // ─────────────────────────────────────────────

        private async Task<T> Post<T>(string endpoint, string jsonBody)
        {
            var tcs = new TaskCompletionSource<T>();
            StartCoroutine(PostCoroutine<T>(endpoint, jsonBody,
                result => tcs.SetResult(result),
                error => tcs.SetException(new Exception(error))
            ));
            return await tcs.Task;
        }

        private async Task<T> Get<T>(string endpoint)
        {
            var tcs = new TaskCompletionSource<T>();
            StartCoroutine(GetCoroutine<T>(endpoint,
                result => tcs.SetResult(result),
                error => tcs.SetException(new Exception(error))
            ));
            return await tcs.Task;
        }

        private IEnumerator PostCoroutine<T>(
            string endpoint,
            string jsonBody,
            Action<T> onSuccess,
            Action<string> onError)
        {
            string url = apiBaseUrl + endpoint;
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);

            using var request = new UnityWebRequest(url, "POST");
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = (int)requestTimeoutSeconds;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    T result = JsonConvert.DeserializeObject<T>(request.downloadHandler.text);
                    onSuccess?.Invoke(result);
                }
                catch (Exception e)
                {
                    onError?.Invoke($"Deserialization error: {e.Message}");
                }
            }
            else
            {
                onError?.Invoke($"HTTP Error {request.responseCode}: {request.error}");
            }
        }

        private IEnumerator GetCoroutine<T>(
            string endpoint,
            Action<T> onSuccess,
            Action<string> onError)
        {
            string url = apiBaseUrl + endpoint;

            using var request = UnityWebRequest.Get(url);
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = (int)requestTimeoutSeconds;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    T result = JsonConvert.DeserializeObject<T>(request.downloadHandler.text);
                    onSuccess?.Invoke(result);
                }
                catch (Exception e)
                {
                    onError?.Invoke($"Deserialization error: {e.Message}");
                }
            }
            else
            {
                onError?.Invoke($"HTTP Error {request.responseCode}: {request.error}");
            }
        }
    }

    // ─────────────────────────────────────────────
    // SENTIENT NPC COMPONENT
    // Attach to any NPC GameObject in your scene
    // ─────────────────────────────────────────────

    public class SentientNPCComponent : MonoBehaviour
    {
        [Header("NPC Identity")]
        public string npcId;
        public string npcName;
        public string archetype = "merchant";
        public string faction;
        public string background;
        public string speechStyle = "neutral medieval";

        [Header("Initial Goals")]
        public List<string> initialGoals = new List<string> { "increase_wealth" };

        [Header("State (Read-Only — set at runtime)")]
        [SerializeField] private string dominantEmotion = "neutral";
        [SerializeField] private float moodValence = 0f;
        [SerializeField] private string lastDialogue;

        // Events
        public event Action<InteractResponse> OnInteractComplete;
        public event Action<string> OnAPIError;

        private bool _initialized = false;

        async void Start()
        {
            if (string.IsNullOrEmpty(npcId))
            {
                await InitializeNPC();
            }
            else
            {
                await RefreshState();
            }
        }

        public async Task InitializeNPC()
        {
            var request = new NPCCreateRequest
            {
                name = npcName,
                archetype = archetype,
                faction = faction,
                location = gameObject.scene.name,
                background = background,
                speech_style = speechStyle,
                initial_goals = initialGoals,
            };

            try
            {
                var response = await SentientNPCClient.Instance.CreateNPC(request);
                npcId = response.npc_id;
                UpdateFromEmotion(response.emotion_state);
                _initialized = true;
                Debug.Log($"[SentientNPC] {npcName} initialized with ID: {npcId}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[SentientNPC] Failed to initialize {npcName}: {e.Message}");
                OnAPIError?.Invoke(e.Message);
            }
        }

        public async Task<InteractResponse> SayToNPC(string playerId, string message)
        {
            if (string.IsNullOrEmpty(npcId))
            {
                Debug.LogWarning("[SentientNPC] NPC not initialized yet.");
                return null;
            }

            try
            {
                var response = await SentientNPCClient.Instance.Interact(npcId, playerId, message);
                lastDialogue = response.dialogue;
                UpdateFromEmotion(response.emotion_after);
                OnInteractComplete?.Invoke(response);
                return response;
            }
            catch (Exception e)
            {
                Debug.LogError($"[SentientNPC] Interact error: {e.Message}");
                OnAPIError?.Invoke(e.Message);
                return null;
            }
        }

        public async Task RefreshState()
        {
            if (string.IsNullOrEmpty(npcId)) return;
            try
            {
                var state = await SentientNPCClient.Instance.GetNPCState(npcId);
                dominantEmotion = state.dominant_emotion;
                moodValence = state.mood_valence;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[SentientNPC] RefreshState error: {e.Message}");
            }
        }

        private void UpdateFromEmotion(EmotionState emotion)
        {
            if (emotion == null) return;
            dominantEmotion = emotion.DominantEmotion();
        }

        // Inspector button for testing in Play mode
        [ContextMenu("Test: Say Hello")]
        void TestSayHello()
        {
            StartCoroutine(SentientNPCClient.Instance.InteractCoroutine(
                npcId, "test_player", "Hello, how are you today?",
                response => Debug.Log($"[SentientNPC] {npcName}: {response.dialogue}"),
                error => Debug.LogError($"[SentientNPC] Error: {error}")
            ));
        }
    }

    // ─────────────────────────────────────────────
    // WORLD EVENT BROADCASTER
    // Attach to a manager GameObject to fire world events
    // ─────────────────────────────────────────────

    public class WorldEventBroadcaster : MonoBehaviour
    {
        public static WorldEventBroadcaster Instance { get; private set; }

        void Awake()
        {
            Instance = this;
        }

        public async Task BroadcastEvent(
            string eventType,
            string description,
            string location = null,
            List<string> affectedFactions = null,
            float severity = 0.5f,
            float radius = 100f)
        {
            var request = new WorldEventRequest
            {
                event_type = eventType,
                description = description,
                location = location ?? gameObject.scene.name,
                affected_factions = affectedFactions ?? new List<string>(),
                severity = severity,
                radius = radius,
            };

            try
            {
                var response = await SentientNPCClient.Instance.PublishWorldEvent(request);
                Debug.Log($"[WorldEvent] Published: {eventType} (ID: {response.event_id})");
            }
            catch (Exception e)
            {
                Debug.LogError($"[WorldEvent] Failed to publish event: {e.Message}");
            }
        }

        // ── Convenience methods ──

        public void DragonKilled(string location, float severity = 0.9f)
            => _ = BroadcastEvent("dragon_killed",
                "The great dragon has been slain!",
                location, severity: severity);

        public void MarketFire(string location)
            => _ = BroadcastEvent("market_fire",
                "The market is on fire!",
                location, severity: 0.7f);

        public void PlayerAttacked(string victimId, string location)
            => _ = BroadcastEvent("player_attack",
                $"A player attacked someone near {location}",
                location, severity: 0.6f);

        public void Festival(string location)
            => _ = BroadcastEvent("festival",
                "A grand festival has begun!",
                location, severity: 0.4f);
    }
}
