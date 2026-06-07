import json
import hashlib
from upstash_redis import Redis
from app.config import get_settings


class RedisCache:
    client: Redis | None = None

    @classmethod
    def connect(cls):
        s = get_settings()

        url = (s.UPSTASH_REDIS_REST_URL or "").strip()
        token = (s.UPSTASH_REDIS_REST_TOKEN or "").strip()

        if not url or not token:
            cls.client = None
            print("⚠️ Redis disabled: missing UPSTASH_REDIS_REST_URL or TOKEN")
            return

        try:
            cls.client = Redis(url=url, token=token)
            cls.client.ping()
            print("✅ Redis connected")
        except Exception as e:
            cls.client = None
            print(f"⚠️ Redis disabled: {e}")

    @classmethod
    def get(cls, key: str):
        if not cls.client:
            return None

        try:
            val = cls.client.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    @classmethod
    def set(cls, key: str, value, ttl: int = 300):
        if not cls.client:
            return

        try:
            cls.client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            pass

    @classmethod
    def make_key(cls, prefix: str, *args) -> str:
        raw = f"{prefix}:{'|'.join(str(a) for a in args)}"
        return hashlib.md5(raw.encode()).hexdigest()
