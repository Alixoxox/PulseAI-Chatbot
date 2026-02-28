from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import MongoManager, SyncMongo
from app.cache import RedisCache
from app.agent import get_agent
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting CryptoBot...")
    await MongoManager.connect()
    SyncMongo.connect()
    RedisCache.connect()
    get_agent()
    print("✅ CryptoBot ready!")
    yield #pause here till the process is set to be closed
    await MongoManager.close()


app = FastAPI(title="CryptoBot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(health_router, tags=["Health"])
