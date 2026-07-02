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
- Scam probability, risk score, confidence, and threat level
- Suspicious keyword highlighting
- Authority, threat, financial-demand, and manipulation signals
- Conversation-stage timeline
- Caller history and reputation
- Block, report, save-evidence, and notify-police actions
- PDF evidence report
- Dashboard statistics and WebSocket updates
- PostgreSQL case storage and optional Neo4j synchronization for high-risk cases

### Counterfeit Currency Detection

- JPG, PNG, and WebP upload
- Image-quality and single-note validation
- Note boundary and perspective correction
- Denomination, series, and legal-tender checks
- Security-feature measurements
- Serial-number checks when OCR is available
- Forensic heatmap and explanation
- Detection history, statistics, and PDF report
- Detection of withdrawn Indian banknote series and specimen/proof notes

The default currency pipeline uses measured image features. Optional YOLO, ResNet, and OCR models can be configured for stronger detection.

### Fraud and Crime Intelligence

- Fraud-network graph view
- Neo4j adapter for graph relationships
- Crime hotspot and heatmap views
- Fraud-report table and filters
- Dashboard and analytics charts
- Role-aware sidebar navigation

### AI Assistant

- Full assistant page and floating chat panel
- Text, image, audio, and PDF input
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
- 30 backend tests pass
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
- AI results are decision-support signals and require human review.
