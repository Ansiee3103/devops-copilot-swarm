import json
import redis
from backend.config import settings
from backend.logger import get_logger

logger = get_logger("cache")

# ── Redis Client ──────────────────────────────────────────
redis_client = redis.Redis(
    host     = settings.REDIS_HOST,
    port     = settings.REDIS_PORT,
    db       = 0,
    decode_responses = True
)

def cache_get(key: str):
    try:
        value = redis_client.get(key)
        if value:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(value)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")
        return None

def cache_set(key: str, value: dict, ttl: int = 300):
    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(value)
        )
        logger.debug(f"Cache SET: {key} (ttl={ttl}s)")
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")

def cache_delete(key: str):
    try:
        redis_client.delete(key)
        logger.debug(f"Cache DELETE: {key}")
    except Exception as e:
        logger.warning(f"Cache delete failed: {e}")

def cache_publish(channel: str, message: dict):
    try:
        redis_client.publish(channel, json.dumps(message))
    except Exception as e:
        logger.warning(f"Cache publish failed: {e}")