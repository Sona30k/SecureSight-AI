# ShieldIQ Deployment

This deployment runs the React application behind an unprivileged Nginx container and keeps FastAPI, PostgreSQL, Redis, Neo4j, Celery, and uploaded evidence on a private Docker network.

PostgreSQL, Redis, and Neo4j are not published to the host. API and worker containers also join a separate egress network so configured cloud AI providers and authorized government/bank webhooks remain reachable.

## Production prerequisites

- Linux host with Docker Engine 26+ and Docker Compose v2
- A DNS name pointing to the host
- TLS termination through a load balancer, Caddy, Traefik, or an ingress controller
- At least 4 CPU cores, 8 GB RAM, and persistent encrypted storage

## Configure secrets

```bash
cp .env.production.example .env.production
openssl rand -hex 32
openssl rand -hex 32
```

Put unique generated values into `SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, and `NEO4J_PASSWORD`. Set `APP_DOMAIN` to the public hostname. Never commit `.env.production`.

If GPT or Gemini is enabled, place its key only in `.env.production` or the deployment platform's secret manager. Keep `DEMO_MODE=false`.

## Validate and deploy

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

The API container runs `alembic upgrade head` before Uvicorn starts. Do not run the Faker seed in production.

The default backend image is lightweight. Set `BACKEND_DOCKERFILE=docker/Dockerfile.ai` before building when the deployment must include local YOLO, EasyOCR, PyTorch classifiers, Whisper, and transformer inference. Budget additional build time, disk space, and memory for that image.

Ollama is not started automatically. Point `OLLAMA_BASE_URL` to an authorized reachable Ollama service, or leave automatic routing to configured cloud providers and the built-in safety fallback.

The frontend listens on `APP_PORT` (default `8080`). Terminate HTTPS in front of that port and forward the original `Host` and `X-Forwarded-Proto` headers.

## Health endpoints

- Nginx: `/healthz`
- API liveness: `/api/health/live`
- API readiness: `/api/health/ready`
- Full dependency status: `/api/health`
- Prometheus metrics: `/api/metrics`

Readiness requires PostgreSQL. Redis and Neo4j report separately so the core API can remain available while optional intelligence services recover.

## Operations

View logs:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api worker
```

Apply a new release:

```bash
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --remove-orphans
```

Back up PostgreSQL:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U shieldiq -d shieldiq -Fc > shieldiq-$(date +%F).dump
```

Back up the named `uploads` and `neo4j_data` volumes using encrypted storage. Test restores before a public demo or release.

## Security checklist

- Use HTTPS only and enable HSTS at the TLS terminator
- Restrict host firewall access to SSH and the TLS proxy
- Rotate all example passwords before first startup
- Store database volumes on encrypted disks
- Keep API documentation disabled in production
- Configure institution-approved AI checkpoints before presenting forensic accuracy claims
- Configure retention policies for evidence, audit logs, and personal data
- Connect an external log and metrics collector
- Run dependency and container-image scanning in CI
