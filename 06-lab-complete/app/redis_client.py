from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

redis_client = None

if settings.redis_url:
    try:
        import redis

        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable, falling back to in-memory state: %s", exc)
        redis_client = None


def redis_available() -> bool:
    if redis_client is None:
        return False
    try:
        redis_client.ping()
        return True
    except Exception:
        return False
