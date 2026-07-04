# ShieldIQ

ShieldIQ is a digital public-safety dashboard for reviewing fraud reports, suspicious calls, counterfeit-currency images, and related risk signals.

This repository contains a React frontend, a FastAPI backend, database migrations, demo data, and tests.

## What is implemented

### Authentication

- Citizen, police, bank, telecom-provider, and administrator roles
- Registration with role-specific fields
- Email-token and phone-OTP verification
- Administrator approval for agency accounts
- bcrypt password hashing
- JWT access tokens and rotating refresh tokens
- Login lockout after repeated failures
- Password reset and password change
- Active-session list, single logout, and logout from all devices
- Backend RBAC and protected frontend routes
- Administrator account approval, rejection, blocking, and unblocking

### Digital Arrest Detection

- Transcript and audio submission
- Consent-gated live transcript sessions with incremental risk updates
- Scam probability, risk score, confidence, and threat level
- Suspicious keyword highlighting
- Authority, threat, financial-demand, and manipulation signals
- Conversation-stage timeline
- Caller history and reputation
- Block, report, save-evidence, and notify-police actions
- PDF evidence report
- Dashboard statistics and WebSocket updates
- Carrier-metadata spoof scoring with attestation provenance
- WAV signal screening for possible synthetic-voice indicators
- Signed, idempotent MHA-alert and bank-hold webhook adapters
- PostgreSQL case storage and optional Neo4j synchronization for high-risk cases

External MHA, bank, and telecom actions require authorized provider URLs and credentials. When they are not configured, ShieldIQ records `not_configured` and does not claim that an action was sent.

### Counterfeit Currency Detection

- JPG, PNG, and WebP upload
- Image-quality and single-note validation
- Note boundary and perspective correction
- Denomination, series, and legal-tender checks
- Security-feature measurements
- Optional physical UV and infrared evidence uploads
- Serial-number checks when OCR is available
- Forensic heatmap and explanation
- Detection history, statistics, and PDF report
- Detection of withdrawn Indian banknote series and specimen/proof notes
- Registered mobile, POS, scanner, and counting-machine API clients
- Batch scans, model provenance, expert review labels, and measured accuracy from reviewed cases

The default currency pipeline uses measured image features. Optional YOLO, ResNet, and OCR models can be configured for stronger detection. UV and infrared features are assessed only when physical sensor captures are supplied; the application does not simulate missing spectral data.

### Fraud and Crime Intelligence

- Fraud-network graph view
- Neo4j adapter for graph relationships
- Authenticated bank-transaction, telecom-CDR, device-fingerprint, and agency-case feeds
- Deduplicated ingestion batches and content-hashed normalized graph events
- SQL persistence with graceful Neo4j synchronization and retry-ready status
- Cross-jurisdiction case packages with SHA-256 manifests and acknowledgement
- Evidence acquisition, protected file storage, linked custody hashes, integrity verification, and download
- Crime hotspot and persisted GeoJSON heatmap views
- Authenticated GIS feed registration and GeoJSON webhook ingestion
- Patrol staging recommendations based on recent persisted incidents
- Auditable inter-district intelligence sharing and acknowledgement
- Fraud-report table and filters
- Dashboard and analytics charts
- Role-aware sidebar navigation

### AI Assistant

- Full assistant page and floating chat panel
- Text, image, audio, and PDF input
- Twelve selectable Indian languages for safety guidance
- Chunked live microphone analysis with optional Whisper transcription
- PCM voice-signal screening for possible synthetic-audio indicators
- Authenticated provider-neutral WhatsApp and IVR webhooks
- Signed, idempotency-ready NCRB submission adapter
- Risk classification, confidence, and safety recommendations
- Persistent floating-chat history in the browser session
- Suggested prompts, file attachments, and responsive layout

The included assistant is focused on fraud and public-safety questions. It uses the local analysis pipeline; it is not a general-purpose large language model.

## Technology

- React 19, TypeScript, Vite, React Router
- Framer Motion, Lucide React, Recharts
- FastAPI, Pydantic, async SQLAlchemy, Alembic
- PostgreSQL, Redis, Neo4j
- Celery worker and scheduler
- Pytest, Vitest, Testing Library

## Run locally

### Requirements

- Node.js 22+
- Python 3.12+

### Backend with SQLite

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a lightweight local setup, set these values in `backend/.env`:

```env
DATABASE_URL=sqlite+aiosqlite:///./shieldiq.db
DEMO_MODE=true
```

Then run:

```bash
alembic upgrade head
PYTHONPATH=. python scripts/seed.py
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

### Frontend

From the repository root:

```bash
npm ci
npm run dev
```

The frontend is available at `http://localhost:5173`.

## Run with Docker

```bash
cd backend
cp .env.example .env
docker compose up --build
```

This starts:

- Frontend on `http://localhost:3000`
- FastAPI on `http://localhost:8000`
- PostgreSQL
- Redis
- Neo4j
- Celery worker and scheduler

## Demo accounts

When `DEMO_MODE=true`, the seed script creates these accounts:

| Role | Email |
|---|---|
| Citizen | `citizen@shieldiq.demo` |
| Police | `police@shieldiq.demo` |
| Bank | `bank@shieldiq.demo` |
| Telecom provider | `telecom@shieldiq.demo` |
| Administrator | `admin@shieldiq.gov.in` |

Password for all demo accounts: `ShieldIQ!2026`

Do not enable demo mode in production.

## Main API routes

| Area | Routes |
|---|---|
| Authentication | `/auth/*` |
| Digital arrest | `/digital-arrest/*` |
| Counterfeit currency | `/currency/*` |
| Assistant | `/assistant/*` |
| Reports | `/reports/*` |
| Crime intelligence | `/crime/*` |
| Fraud graph | `/graph/*` |
| Analytics | `/analytics/*` |
| Notifications | `/notifications/*` |
| Health and metrics | `/health`, `/metrics` |

## Tests

Frontend:

```bash
npm test
npm run build
```

Backend:

```bash
cd backend
.venv/bin/pytest -q
```

Current test status:

- 8 frontend tests pass
- 38 backend tests pass
- Production frontend build passes

## Security included

- bcrypt password hashes
- Short-lived JWT access tokens
- Hashed, rotating refresh tokens
- Session revocation and refresh-token reuse detection
- Role-based endpoint checks
- Account verification and agency approval
- Login lockout
- Rate limiting
- Explicit CORS configuration
- Security response headers
- Upload size, MIME-type, and file-signature validation
- Audit records for authentication and important actions

Production deployment still requires HTTPS, managed secrets, backups, malware scanning for uploads, monitoring, and an independent security review.

## Data and model limitations

- Demo reports and datasets are synthetic.
- No government, bank, police, telecom, or citizen production data is included.
- Optional OCR, Whisper, YOLO, ResNet, Redis, and Neo4j features depend on their services or model files being configured.
- MHA and bank actions require configured institutional webhook endpoints; the repository does not include access to those systems.
- WhatsApp, IVR, and NCRB delivery require provider credentials and configured webhook endpoints.
- GIS ingestion accepts authenticated standards-based feeds; no agency GIS credentials or production feeds are bundled.
- Bank, telecom, device, and agency feeds require provider authorization and credentials; no live institutional data is bundled.
- The evidence chain provides tamper-evident technical records, but legal admissibility still depends on agency procedure and applicable law.
- Patrol recommendations are decision support, not autonomous dispatch.
- Live-call analysis processes consented transcript chunks supplied by a client; it does not intercept telecom calls.
- Synthetic-voice screening is heuristic unless a separately validated model is installed.
- AI results are decision-support signals and require human review.
