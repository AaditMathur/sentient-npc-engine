"""
Database layer — PostgreSQL, Qdrant, Neo4j, Redis connections.
All connections are async and connection-pooled.
"""
from __future__ import annotations
import json
import asyncio
from typing import Optional, Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON
from sqlalchemy.sql import func
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance
from neo4j import AsyncGraphDatabase

from app.config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────
# POSTGRESQL
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class NPCRecord(Base):
    __tablename__ = "npcs"

    npc_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    archetype = Column(String, nullable=False)
    faction = Column(String, nullable=True)
    location = Column(String, nullable=True)
    personality_json = Column(JSON, nullable=False)
    emotion_state_json = Column(JSON, nullable=False)
    goals_json = Column(JSON, default=[])
    relationships_json = Column(JSON, default={})
    recent_memory_ids_json = Column(JSON, default=[])
    background = Column(Text, default="")
    speech_style = Column(String, default="neutral")
    knowledge_base_json = Column(JSON, default={})
    world_knowledge_json = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    sim_tick = Column(Integer, default=0)
    offline_ticks = Column(Integer, default=0)
    last_interaction = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_postgres():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ─────────────────────────────────────────────
# QDRANT (Vector Memory)
# ─────────────────────────────────────────────

_qdrant_client: Optional[AsyncQdrantClient] = None


async def get_qdrant() -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
    return _qdrant_client


async def init_qdrant():
    client = await get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.qdrant_collection_memories not in names:
        await client.create_collection(
            collection_name=settings.qdrant_collection_memories,
            vectors_config=VectorParams(
                size=settings.vector_dimension,
                distance=Distance.COSINE,
            ),
        )


# ─────────────────────────────────────────────
# NEO4J (Social Graph)
# ─────────────────────────────────────────────

_neo4j_driver = None


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _neo4j_driver


async def init_neo4j():
    driver = get_neo4j_driver()
    async with driver.session() as session:
        # Create constraints and indexes
        await session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NPC) REQUIRE n.npc_id IS UNIQUE"
        )
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:NPC) ON (n.faction)"
        )


# ─────────────────────────────────────────────
# REDIS (Cache + Streams)
# ─────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    redis = await get_redis()
    await redis.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> Optional[Any]:
    redis = await get_redis()
    data = await redis.get(key)
    return json.loads(data) if data else None


async def cache_delete(key: str) -> None:
    redis = await get_redis()
    await redis.delete(key)


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

async def init_all_databases():
    await asyncio.gather(
        init_postgres(),
        init_qdrant(),
        init_neo4j(),
    )
