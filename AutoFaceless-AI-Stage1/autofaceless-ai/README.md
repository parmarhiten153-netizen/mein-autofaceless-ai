# AutoFaceless AI — Free-First Edition

Stage 1 implementation: responsive Next.js dashboard, FastAPI API, PostgreSQL schema, password authentication, timezone-aware daily quota, idempotent job creation, quota audit events, job history and cancellation before processing.

> Important: Stage 1 queues job records only. Script generation, TTS, stock-media retrieval, FFmpeg rendering, persistent worker processing and YouTube OAuth are not implemented yet. The UI says this clearly; do not treat a queued job as a finished video.

## Resource note
The development container available during initial work had 3 logical CPUs, about 5.8 GiB RAM and a 32 GiB filesystem. Docker, PostgreSQL and Redis executables were not present in that environment. Docker Compose below provisions PostgreSQL for a deployment, but no cloud server has been provisioned by this project.

## Local development

Requirements: Python 3.11+, Node.js 22+, npm. For a full local setup, use Docker Compose and Docker Engine.

1. Copy `.env.example` to `.env` and replace all example secrets.
2. Set `POSTGRES_PASSWORD` and `JWT_SECRET` to long random values. Do not commit `.env`.
3. Run `docker compose up --build`.
4. Open `http://localhost:3000`; API health: `http://localhost:8000/health`; interactive API docs: `http://localhost:8000/docs`.

Frontend and API must be reachable from the browser. For a remote deployment, set `NEXT_PUBLIC_API_URL` to the public HTTPS API URL and `ALLOWED_ORIGINS` to the frontend origin, then rebuild the frontend.

## Run the API without Docker (SQLite development only)

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

SQLite is for local development and basic tests only. Production quota concurrency requires PostgreSQL. The API serializes same-user job creation with a PostgreSQL row lock and reserves quota in the same transaction as the job and audit record.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Tests cover registration/login, dashboard quota, duplicate idempotency keys, quota rejection, and invalid timezones. These tests are not a substitute for a PostgreSQL concurrency/load test.

## Stage 1 API

- `POST /api/auth/register` — create account; password minimum 10 characters.
- `POST /api/auth/login` — receive bearer token.
- `GET /api/auth/me` — current account.
- `PATCH /api/settings/timezone` — body `{"timezone":"Asia/Kolkata"}`.
- `GET /api/dashboard` — quota and job summary.
- `POST /api/jobs` — create a job; requires a unique per-intent `idempotency_key`.
- `GET /api/jobs` — recent jobs.
- `POST /api/jobs/{id}/cancel` — cancel queued/processing jobs; only queued jobs release quota because processing may already have incurred work.
- `DELETE /api/account` — delete account and associated records (database foreign keys cascade).

## Quota semantics

- Default quota is 2 per user's local calendar day.
- A reservation consumes quota while queued or processing. Completed usage is stored separately in the daily usage row.
- A repeated request with the same idempotency key returns the existing job rather than consuming another slot.
- Quota reservations and audit records are committed atomically with the job.
- Queued cancellation releases the reservation. Processing cancellation does not release it automatically because meaningful work may have started.
- Failed-job release and worker lifecycle accounting will be connected in Stage 4 when the worker exists.

## Production checklist

- Deploy behind HTTPS and configure secure secret values.
- Use a managed or backed-up PostgreSQL database; validate backup restoration.
- Configure a reverse proxy, rate limiting, email verification and password reset before public multi-user launch.
- Add database migrations (Alembic) before evolving schema in production; Stage 1 uses `create_all` for initial bootstrap only.
- Set a retention policy and storage quotas before generating real media.
- Do not enable paid APIs or cloud upgrades automatically.
