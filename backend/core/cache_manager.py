import json
import hashlib
import functools
from typing import Callable
from backend.core.logger import get_logger

logger = get_logger("cache")

def get_redis():
    try:
        import redis
        from backend.core.config import settings
        return redis.Redis(
            host             = settings.REDIS_HOST,
            port             = settings.REDIS_PORT,
            db               = 0,
            decode_responses = True,
            socket_timeout   = 2
        )
    except:
        return None

def _safe_serialize(obj) -> str:
    """Serialize only JSON-safe types — skip DB sessions etc."""
    safe = {}
    for k, v in obj.items():
        try:
            json.dumps(v)   # test if serializable
            safe[k] = v
        except (TypeError, ValueError):
            pass            # ✅ skip non-serializable (Session, etc.)
    return json.dumps(safe, sort_keys=True)

def cached(ttl: int = 300, prefix: str = ""):
    """Cache decorator — safely ignores non-serializable args"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            r   = get_redis()

            # ✅ Build cache key from only serializable kwargs
            key_content = _safe_serialize(kwargs)
            key = f"{prefix}:{func.__name__}:{hashlib.md5(key_content.encode()).hexdigest()}"

            if r:
                try:
                    cached_val = r.get(key)
                    if cached_val:
                        logger.debug(f"Cache HIT: {key}")
                        return json.loads(cached_val)
                except:
                    pass

            result = func(*args, **kwargs)

            if r:
                try:
                    r.setex(key, ttl, json.dumps(result))
                    logger.debug(f"Cache SET: {key} (ttl={ttl}s)")
                except Exception as e:
                    logger.warning(f"Cache set failed: {e}")

            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """Invalidate cache keys matching pattern"""
    r = get_redis()
    if not r:
        return
    try:
        keys = r.keys(f"*{pattern}*")
        if keys:
            r.delete(*keys)
            logger.info(f"Invalidated {len(keys)} keys: {pattern}")
    except:
        pass