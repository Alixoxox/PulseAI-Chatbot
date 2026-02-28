import json, hashlib
from upstash_redis import Redis
from app.config import get_settings


class RedisCache:
    client: Redis = None

    @classmethod
    def connect(cls):
        s = get_settings()
        cls.client = Redis(url=s.UPSTASH_REDIS_REST_URL, token=s.UPSTASH_REDIS_REST_TOKEN)
        cls.client.ping()
        print("✅ Redis connected")

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
