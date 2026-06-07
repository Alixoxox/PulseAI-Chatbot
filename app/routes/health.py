from fastapi import APIRouter
from app.db import MongoManager
from app.cache import RedisCache

router = APIRouter()

@router.get("/health")
async def health():
    """Health check endpoint for Render monitoring."""
    status = {"status": "ok", "mongodb": "connected", "redis": "connected"}

    try:
        db = MongoManager.get_db()
        await db.command("ping")
    except Exception:
        status["mongodb"] = "disconnected"
        status["status"] = "degraded"

    try:
        if not RedisCache.client:
            raise Exception("Redis client not initialized")
        RedisCache.client.ping()
    except Exception:
        status["redis"] = "disconnected"
        status["status"] = "degraded"
    return status
