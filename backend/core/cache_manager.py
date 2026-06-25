import json
import hashlib
import functools
from typing import Any, Optional, Callable
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

def cache_key(*args, **kwargs) -> str:
    content = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return f"cache:{hashlib.md5(content.encode()).hexdigest()}"

def cached(ttl: int = 300, prefix: str = ""):
    """Cache decorator for any function"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            r   = get_redis()
            key = f"{prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

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
                except:
                    pass

            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """Invalidate all cache keys matching pattern"""
    r = get_redis()
    if not r:
        return
    try:
        keys = r.keys(f"*{pattern}*")
        if keys:
            r.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys: {pattern}")
    except:
        pass