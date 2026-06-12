import json
import logging
import signal
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_and_record_budget
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_available, redis_client
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
MAX_HISTORY_ITEMS = 20
_is_ready = False
_request_count = 0
_error_count = 0
_memory_history: dict[str, list[dict]] = defaultdict(list)


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(user_id: str) -> list[dict]:
    if redis_client is not None:
        raw_items = redis_client.lrange(_history_key(user_id), 0, MAX_HISTORY_ITEMS - 1)
        return [json.loads(item) for item in raw_items]
    return list(_memory_history[user_id])


def append_history(user_id: str, role: str, content: str) -> None:
    item = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if redis_client is not None:
        key = _history_key(user_id)
        redis_client.lpush(key, json.dumps(item))
        redis_client.ltrim(key, 0, MAX_HISTORY_ITEMS - 1)
        redis_client.expire(key, 30 * 24 * 3600)
        return

    _memory_history[user_id].insert(0, item)
    _memory_history[user_id] = _memory_history[user_id][:MAX_HISTORY_ITEMS]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "redis": redis_available(),
    }))
    _is_ready = True
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round((time.time() - start) * 1000, 1),
        }))
        return response
    except Exception:
        _error_count += 1
        raise


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_items: int
    monthly_cost_usd: float
    storage: str
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
):
    check_rate_limit(body.user_id)

    input_tokens = len(body.question.split()) * 2
    monthly_cost = check_and_record_budget(body.user_id, input_tokens=input_tokens)

    history = load_history(body.user_id)
    context_hint = ""
    if history:
        recent = list(reversed(history[:4]))
        context_hint = " ".join(f"{item['role']}: {item['content']}" for item in recent)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": body.user_id,
        "q_len": len(body.question),
        "history_items": len(history),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    prompt = f"{context_hint}\nuser: {body.question}" if context_hint else body.question
    answer = llm_ask(prompt)
    output_tokens = len(answer.split()) * 2
    monthly_cost = check_and_record_budget(body.user_id, output_tokens=output_tokens)

    append_history(body.user_id, "user", body.question)
    append_history(body.user_id, "assistant", answer)

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_items=len(load_history(body.user_id)),
        monthly_cost_usd=round(monthly_cost, 6),
        storage="redis" if redis_client is not None else "in-memory",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "llm": "mock" if not settings.openai_api_key else "openai",
            "redis": redis_available(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if settings.redis_url and not redis_available():
        raise HTTPException(503, "Redis not available")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "redis": redis_available(),
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info("Starting %s on %s:%s", settings.app_name, settings.host, settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
