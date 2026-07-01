# ShieldIQ Code Review

Review scope: frontend, API, database models and migrations, authentication/RBAC, uploads, AI integration, async tasks, deployment, tests, and responsive UI.

## Corrected findings

### Critical

- Privileged roles could self-register. Public privileged registration is now blocked unless explicit demo mode is enabled.
- Rate limiting was configured but its middleware was absent. `SlowAPIMiddleware` is now active.
- AI endpoints returned predictions without consistently storing them. A shared `AnalysisRecorder` now persists ownership, duration, model version, confidence, results, and an audit event.
- Upload validation trusted browser MIME headers. Currency/OCR uploads now verify JPEG, PNG, or WebP file signatures and use server-generated filenames.
- Migration `0002` collided with the dynamic initial schema on fresh databases. It now inspects the schema and works for fresh and previously migrated installations.

### High

- Frontend dashboards and workflows used hardcoded operational data. Authentication, analytics, reports, scam analysis, currency detection, graph analysis, hotspots, chat, and profile updates now use the FastAPI APIs.
- JWT expiry caused abrupt logout. The Axios client now performs a single-flight refresh and retries the original request.
- RBAC existed in backend helpers but was not mirrored in navigation. Protected routes now enforce role access in the UI while the backend remains authoritative.
- Password hashing depended on a deprecated compatibility layer. New passwords use the standard-library scrypt KDF with per-password random salts.
- Duplicate scam/currency logic diverged. Shared inference pipelines now power both legacy domain endpoints and `/ai/*` contracts.

### Medium

- Dashboard metrics used multiple independent count queries. Related metrics now use aggregate and scalar-subquery batches.
- No live update transport existed. Authenticated WebSocket channels now support dashboard, alerts, reports, graph, and heatmap events.
- The frontend shipped as one large bundle. Vendor chunking reduced the application entry from roughly 858 KB to 44 KB.
- API errors and loading states were inconsistent. Shared retry/error handling and reusable loading/error/empty states were added.
- Dependencies used `latest`, making builds non-reproducible. Frontend versions are pinned and the lockfile is committed.
- Docker Compose omitted the frontend and Celery beat. Both are now included with Nginx proxying and health checks.

## Validation

- Frontend: 5 tests passing.
- Backend: 14 tests passing.
- Production TypeScript/Vite build passing.
- Fresh SQLite migration through Alembic head and idempotent demo seed passing.
- Browser-verified administrator login, live API dashboard, scam prediction persistence, mobile navigation, and zero horizontal overflow.

## Deliberate hackathon limitations

- AI heavyweight dependencies are optional; deterministic baselines keep the demo portable.
- The WebSocket hub is process-local. Use Redis pub/sub before multi-instance deployment.
- Synthetic model metrics do not represent real-world safety performance.
- Email, SMS, WhatsApp, and push delivery are provider adapters/mocks.
- The map is a lightweight geospatial visualization; production should use Leaflet/PostGIS tiles and clustering.
- Uploaded evidence should move from local disk to encrypted object storage with scanning and retention controls.
