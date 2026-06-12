from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

from app.config import settings
from app.redis_client import redis_client

INPUT_PRICE_PER_1K = 0.00015
OUTPUT_PRICE_PER_1K = 0.0006

_memory_spend: dict[str, float] = defaultdict(float)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000) * INPUT_PRICE_PER_1K + (
        output_tokens / 1000
    ) * OUTPUT_PRICE_PER_1K


def _month_key() -> str:
    return time.strftime("%Y-%m")


def check_and_record_budget(
    user_id: str, input_tokens: int = 0, output_tokens: int = 0
) -> float:
    """Record estimated LLM cost and block users over the monthly budget."""
    cost = estimate_cost(input_tokens, output_tokens)
    budget = settings.monthly_budget_usd

    if redis_client is not None:
        key = f"budget:{user_id}:{_month_key()}"
        current = float(redis_client.get(key) or 0)
        if current + cost > budget:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(current, 6),
                    "budget_usd": budget,
                },
            )
        new_total = redis_client.incrbyfloat(key, cost)
        redis_client.expire(key, 32 * 24 * 3600)
        return float(new_total)

    key = f"{user_id}:{_month_key()}"
    if _memory_spend[key] + cost > budget:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(_memory_spend[key], 6),
                "budget_usd": budget,
            },
        )
    _memory_spend[key] += cost
    return _memory_spend[key]
