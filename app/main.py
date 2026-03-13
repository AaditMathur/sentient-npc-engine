"""
Sentient NPC Engine 3.0 — FastAPI Application
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.routes import router
from app.database import init_all_databases
from app.config import get_settings

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all database connections and collections on startup."""
    logger.info("sentient_npc_engine_starting", version=settings.app_version)
    await init_all_databases()
    logger.info("databases_initialized")
    yield
    logger.info("sentient_npc_engine_shutdown")


app = FastAPI(
    title="Sentient NPC Engine 3.0",
    description="""
Production-grade AI middleware that turns game NPCs into autonomous cognitive agents.

## Features
- 🧠 **Cognitive Pipeline**: Full perception → memory → emotion → goal → dialogue loop
- 💾 **Hybrid Memory**: Vector similarity search across episodic, semantic & emotional memory  
- 😤 **Emotion Engine**: 8D emotion vector with decay, personality-modulated responses
- 🎯 **GOAP Planner**: Goal-oriented action planning with A* search
- 🕸️ **Social Graph**: NPC relationship tracking via Neo4j
- 🌍 **World Events**: Redis Streams event bus for real-time NPC reactions
- ⚙️ **Background Sim**: NPCs evolve even when players are offline
    """,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router, prefix="/api/v1")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    return {
        "engine": "Sentient NPC Engine 3.0",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
