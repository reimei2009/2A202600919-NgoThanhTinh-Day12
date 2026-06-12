# Deployment Information

## Public URL

`PENDING: replace with the Railway or Render public URL`

## Platform

Recommended: Railway.

The repository also includes `06-lab-complete/render.yaml` for Render.

## Local Verification

Run from `06-lab-complete`:

```powershell
docker compose up -d
docker compose ps
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Readiness check:

```powershell
Invoke-RestMethod http://localhost:8000/ready
```

Authenticated request:

```powershell
$headers = @{ "X-API-Key" = "dev-key-change-me-in-production" }
$body = @{
  user_id = "student-test"
  question = "What is deployment?"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/ask `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Authentication failure:

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri http://localhost:8000/ask `
  -ContentType "application/json" `
  -Body '{"user_id":"test","question":"Hello"}'
```

Expected status: HTTP 401.

Rate-limit test:

```powershell
1..12 | ForEach-Object {
  try {
    Invoke-WebRequest `
      -Method Post `
      -Uri http://localhost:8000/ask `
      -Headers $headers `
      -ContentType "application/json" `
      -Body ('{"user_id":"rate-test","question":"Request ' + $_ + '"}')
  } catch {
    $_.Exception.Response.StatusCode.value__
  }
}
```

Expected: later requests return HTTP 429.

Stop local services:

```powershell
docker compose down
```

## Manual Railway Deployment

These steps require the student's Railway account:

1. Push this repository to GitHub.
2. Sign in at `https://railway.app`.
3. Create a project from the GitHub repository.
4. Set the service root directory to `06-lab-complete`.
5. Add a Redis service to the Railway project.
6. Add these application variables:

```text
ENVIRONMENT=production
AGENT_API_KEY=<generate-a-long-random-secret>
JWT_SECRET=<generate-another-long-random-secret>
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10
ALLOWED_ORIGINS=*
REDIS_URL=<Railway Redis connection URL>
```

7. Leave `OPENAI_API_KEY` empty to use the provided offline mock LLM.
8. Deploy and generate a public domain in Railway service settings.
9. Replace the pending URL at the top of this file.
10. Run the public tests below and capture screenshots.

Generate secrets locally without saving them to the repository:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

## Public Test Commands

After deployment:

```powershell
$url = "https://YOUR-SERVICE-DOMAIN"
$key = "YOUR-AGENT-API-KEY"

Invoke-RestMethod "$url/health"
Invoke-RestMethod "$url/ready"

$headers = @{ "X-API-Key" = $key }
$body = @{
  user_id = "public-test"
  question = "Hello from production"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$url/ask" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

## Environment Variables

- `PORT`: injected by the platform.
- `ENVIRONMENT`: set to `production`.
- `REDIS_URL`: supplied by the managed Redis service.
- `AGENT_API_KEY`: secret used by `X-API-Key`.
- `JWT_SECRET`: reserved secret for JWT support.
- `RATE_LIMIT_PER_MINUTE`: `10`.
- `MONTHLY_BUDGET_USD`: `10`.
- `ALLOWED_ORIGINS`: allowed frontend origins.
- `OPENAI_API_KEY`: optional; the project works with the mock LLM.

## Screenshots Required

Add these files after manual deployment:

- `screenshots/deployment-dashboard.png`
- `screenshots/service-running.png`
- `screenshots/public-health-test.png`
- `screenshots/authenticated-api-test.png`

Do not include API keys, Redis passwords, or other secrets in screenshots.

