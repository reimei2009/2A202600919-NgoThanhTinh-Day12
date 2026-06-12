from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings
from app.redis_client import redis_client

_memory_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(user_id: str) -> None:
    """Sliding-window rate limit per user."""
    now = time.time()
    window_seconds = 60
    limit = settings.rate_limit_per_minute

    if redis_client is not None:
        key = f"rate:{user_id}"
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 5)
        _, count, _, _ = pipe.execute()
        if count >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
        return

    window = _memory_windows[user_id]
    while window and window[0] < now - window_seconds:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} req/min",
            headers={"Retry-After": "60"},
        )
    window.append(now)
