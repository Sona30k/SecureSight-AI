# ShieldIQ Backend

Production-oriented FastAPI backend for the ShieldIQ Digital Public Safety Intelligence Platform.

## Capabilities

- JWT access/refresh authentication with token revocation and five-role RBAC
- Digital-arrest NLP pipeline and explainable rule-based risk engine
- Currency-image upload, validation, storage, and CNN-compatible inference adapter
- Neo4j fraud-network creation and visualization JSON
- GeoJSON crime heatmaps, hotspots, statistics, reports, analytics, notifications and AI chat
- Async SQLAlchemy, PostgreSQL, Alembic, Redis, Celery, rate limiting, CORS, structured logs and Prometheus metrics
- Docker Compose infrastructure and SQLite-backed API tests
- Full hackathon AI/ML subsystem with generated datasets, trainable baselines and optional heavyweight model adapters

The dedicated AI documentation is in [`ai/README.md`](ai/README.md). It includes dataset generation, training, evaluation and all `/ai/*` endpoint contracts.

## Quick start with Docker

```bash
cd backend
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed
```

Open Swagger at `http://localhost:8000/docs`, ReDoc at `/redoc`, health at `/health`, and metrics at `/metrics`.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Change DATABASE_URL and service URLs if services are on localhost.
alembic upgrade head
uvicorn app.main:app --reload
```

For a zero-infrastructure local run, set:

```env
DATABASE_URL=sqlite+aiosqlite:///./shieldiq.db
```

Then create the schema with `alembic upgrade head`. Redis and Neo4j degrade gracefully in `/health`; graph endpoints return `503` when Neo4j is offline.

## Tests

```bash
pytest -q --cov=app
```

## API notes

All domain endpoints require `Authorization: Bearer <access_token>`. Register and login at `/auth/register` and `/auth/login`. Use the returned refresh token only at `/auth/refresh`; logout increments the user token version and invalidates every active token.

The AI implementations expose stable service interfaces and deterministic development adapters. Replace `CurrencyVisionModel`, `NLPAnalyzer`, `SpeechAnalysisService`, `OCRService`, `GraphAIService`, or `ChatService` provider methods when production models are available without changing endpoint contracts.

Uploaded currency images are restricted by MIME type and size, assigned non-user-controlled names, and stored under `STORAGE_PATH/currency`. In production, point this adapter to encrypted object storage and add malware scanning.
