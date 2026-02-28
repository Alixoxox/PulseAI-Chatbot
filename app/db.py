import motor.motor_asyncio
import pymongo
from app.config import get_settings


class MongoManager:
    """Eager-initialized async MongoDB connection manager (for FastAPI routes)."""

    client: motor.motor_asyncio.AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        """Connect to MongoDB and verify with a ping. Called at startup."""
        settings = get_settings()
        cls.client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.MONGODB_URI,
            maxPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )
        await cls.client.admin.command("ping")
        cls.db = cls.client[settings.MONGODB_DB]
        print(f"✅ MongoDB connected (async) — database: {settings.MONGODB_DB}")

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
        if SyncMongo.client:
            SyncMongo.client.close()
        print("🔌 MongoDB connections closed")

    @classmethod
    def get_db(cls):
        if cls.db is None:
            raise RuntimeError("MongoDB not connected. Call MongoManager.connect() first.")
        return cls.db


class SyncMongo:
    """Sync MongoDB client for LangChain tools (runs in thread pool)."""

    client: pymongo.MongoClient = None
    db = None

    @classmethod
    def connect(cls):
        """Connect synchronously. Called at startup."""
        settings = get_settings()
        cls.client = pymongo.MongoClient(
            settings.MONGODB_URI,
            maxPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )
        cls.client.admin.command("ping")
        cls.db = cls.client[settings.MONGODB_DB]
        print(f"✅ MongoDB connected (sync) — database: {settings.MONGODB_DB}")

    @classmethod
    def get_db(cls):
        if cls.db is None:
            raise RuntimeError("SyncMongo not connected. Call SyncMongo.connect() first.")
        return cls.db
