# Day 12 Lab - Mission Answers

Student: Ngo Thanh Tinh

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. OpenAI API key and database credentials are hardcoded in source code.
2. The application logs the API key, which exposes secrets in logs.
3. Configuration such as debug mode and token limits is hardcoded.
4. The server binds to `localhost`, so it is inaccessible outside the machine/container.
5. Port `8000` is fixed instead of being read from the `PORT` environment variable.
6. Uvicorn reload mode is enabled, which is unsuitable for production.
7. There is no liveness or readiness endpoint.
8. `print()` is used instead of structured logging.
9. There is no graceful shutdown or resource cleanup.
10. The request input is not validated with a schema.

### Exercise 1.2: Basic version

The basic FastAPI application can answer requests locally, but it is not
production-ready because its configuration, security, observability, and
lifecycle behavior depend on the developer's machine.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why important? |
|---|---|---|---|
| Configuration | Hardcoded | Environment variables | Supports different environments without editing code |
| Secrets | In source and logs | Loaded from environment | Prevents accidental credential exposure |
| Network binding | `localhost` | `0.0.0.0` | Allows traffic from containers and cloud routers |
| Port | Fixed at 8000 | Read from `PORT` | Cloud platforms inject their assigned port |
| Logging | `print()` | Structured JSON logs | Easier to search, parse, and monitor |
| Health checks | Missing | `/health` and `/ready` | Enables restart and traffic-routing decisions |
| Shutdown | Abrupt | Lifespan and SIGTERM handling | Allows in-flight requests and cleanup to finish |
| Debug reload | Always enabled | Controlled by environment | Avoids extra processes and instability in production |
| Input validation | Minimal | Pydantic models | Returns predictable validation errors |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. The basic base image is `python:3.11`.
2. The working directory is `/app`.
3. `requirements.txt` is copied before source code to reuse Docker's dependency
   layer cache when only application code changes.
4. `CMD` supplies a default command that can be replaced at runtime.
   `ENTRYPOINT` defines the executable that normally remains fixed, while extra
   command-line arguments are appended to it.

### Exercise 2.2: Basic container

The basic image packages Python, dependencies, application code, and the mock
LLM into one reproducible runtime. It is intentionally larger because it uses
the full Python image and a single build stage.

### Exercise 2.3: Multi-stage build and image size

- Develop image: expected to be close to or above 1 GB because it uses
  `python:3.11`.
- Final production image: **284 MB**.
- Requirement: **passed**, because the final image is below 500 MB.

Stage 1 installs build tools and Python dependencies. Stage 2 copies only the
installed runtime packages and application files into `python:3.11-slim`.
Build tools are therefore excluded from the deployed image.

### Exercise 2.4: Docker Compose architecture

```text
Client -> Agent API :8000 -> Redis :6379
```

Docker Compose starts:

- `agent`: FastAPI production agent.
- `redis`: shared conversation, rate-limit, and budget state.

Services communicate over the Compose network through the hostname `redis`.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

The repository includes `06-lab-complete/railway.toml`. Deployment requires
logging in to the student's Railway account and creating the public service.

- Platform: Railway or Render
- Public URL: pending account deployment
- Screenshot: add to `screenshots/` after deployment

### Exercise 3.2: Railway and Render comparison

| Item | Railway | Render |
|---|---|---|
| Configuration | `railway.toml` | `render.yaml` |
| Deployment style | CLI or Git integration | Git Blueprint |
| Environment variables | CLI/dashboard | Dashboard/Blueprint |
| Health check | Platform service settings | `healthCheckPath` |
| Best use here | Fast CLI deployment | Reproducible Git-based deployment |

Only one working public deployment is required.

### Exercise 3.3: Cloud Run

`cloudbuild.yaml` describes the image build and deployment pipeline.
`service.yaml` describes the Cloud Run service, container, environment, and
scaling configuration. This exercise is optional.

## Part 4: API Security

### Exercise 4.1: API key authentication

The `X-API-Key` header is read by FastAPI's `APIKeyHeader`. Missing or invalid
keys return HTTP 401. The real key comes from `AGENT_API_KEY`, so rotation only
requires updating the cloud environment variable and restarting/redeploying the
service.

### Exercise 4.2: JWT authentication

The advanced example authenticates username/password credentials, creates a
signed HS256 token containing subject, role, issue time, and expiry, then
verifies the `Authorization: Bearer <token>` header on protected endpoints.
Expired tokens return 401 and invalid tokens return 403.

### Exercise 4.3: Rate limiting

The final agent uses a 60-second sliding window with a default limit of
**10 requests per minute per user**. Redis sorted sets are used when Redis is
available, allowing all agent replicas to share the same counters. Requests
over the limit return HTTP 429 with `Retry-After: 60`.

The advanced learning example gives administrators a separate higher-limit
bucket rather than disabling rate limits completely.

### Exercise 4.4: Cost guard implementation

The final implementation:

1. Estimates input and output token costs.
2. Stores spending under `budget:<user_id>:<YYYY-MM>`.
3. Applies a 32-day expiration to old budget records.
4. Rejects requests with HTTP 402 when the next cost would exceed
   **$10 per month per user**.
5. Uses Redis in the production stack and an in-memory fallback only for simple
   local execution.

## Part 5: Scaling and Reliability

### Exercise 5.1: Health checks

- `GET /health` is a liveness endpoint and returns process, version, uptime,
  request count, LLM mode, and Redis status.
- `GET /ready` is a readiness endpoint. It returns 503 while the app is not
  initialized or when a configured Redis dependency is unavailable.

### Exercise 5.2: Graceful shutdown

The application logs SIGTERM, uses FastAPI lifespan cleanup, marks itself not
ready during shutdown, and configures Uvicorn with a 30-second graceful
shutdown timeout.

### Exercise 5.3: Stateless design

Conversation history is stored under `history:<user_id>` in Redis with a
30-day TTL. Rate-limit counters and monthly spending also use Redis. Therefore,
multiple agent replicas can serve the same user without depending on one
process's memory.

### Exercise 5.4: Load balancing

The agent can be scaled with:

```bash
docker compose up --scale agent=3
```

For a public production deployment, the cloud platform's router/load balancer
distributes traffic among replicas. Redis remains the shared state service.

### Exercise 5.5: Stateless test

Test procedure:

1. Send a request using a fixed `user_id`.
2. Scale or restart an agent instance.
3. Send another request with the same `user_id`.
4. Verify `history_items` continues increasing and `storage` is `redis`.

## Final Project Summary

The project includes:

- REST AI agent with validated request models.
- API key authentication.
- Redis-backed conversation history.
- Redis-backed sliding-window rate limiting.
- Redis-backed monthly cost guard.
- Health, readiness, and protected metrics endpoints.
- Structured JSON logging and security headers.
- Graceful shutdown.
- Multi-stage, non-root Docker image measuring 284 MB.
- Docker Compose, Railway, and Render configuration.
