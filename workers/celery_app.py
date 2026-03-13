from celery import Celery
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

celery_app = Celery(
    "npc_engine_workers",
    broker=redis_url,
    backend=redis_url,
    include=["workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
