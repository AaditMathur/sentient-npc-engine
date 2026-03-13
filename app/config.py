from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    
    app_version: str = "3.0.0"
    debug: bool = False
    
    # DB
    database_url: str = "postgresql+asyncpg://npc:npc@localhost:5432/sentient_npc"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream_world_events: str = "world_events"
    redis_stream_npc_reactions: str = "npc_reactions"
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_memories: str = "npc_memories"
    vector_dimension: int = 1536
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "npcengine"
    
    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-3-haiku-20240307"
    llm_max_tokens: int = 1000
    
    # Simulation
    sim_tick_interval_seconds: int = 10
    worker_concurrency: int = 10
    max_npcs_per_worker: int = 50
    cache_npc_state_ttl: int = 300
    max_active_goals: int = 3
    memory_decay_rate: float = 0.01

def get_settings():
    return Settings()
