# KVH — AI-Powered Assessment Platform

An enterprise assessment platform: pick an industry and a compliance/maturity
standard, answer Claude-generated questions, and get an AI-written scorecard,
executive report, and downloadable `.docx` — free, capped at 2 full AI
reports per day per email.

## Stack

- **Backend:** Python 3.11 + FastAPI + SQLAlchemy (async) + Alembic
- **Database:** PostgreSQL (SQLite locally for dev — see `app/config.py`)
- **AI:** Anthropic Claude API (`claude-opus-4-8`) — question generation, scoring, report writing, "why this score" explanations
- **Documents:** `python-docx` for the downloadable report
- **Frontend:** Plain HTML/CSS/vanilla JS, multi-page, served as static files by FastAPI

## Project structure

```
maturity-assess/
├── app/
│   ├── main.py              # FastAPI app, routers, static file mount
│   ├── config.py             # env var loading
│   ├── schemas.py            # Pydantic models (also used as Claude structured-output schemas)
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── session.py         # async engine/session
│   │   └── seed.py            # idempotent starter industries/standards/templates
│   ├── ai/                   # Claude integration
│   │   ├── claude_client.py
│   │   ├── prompt_templates.py
│   │   ├── question_generator.py
│   │   ├── scoring_engine.py
│   │   └── report_generator.py   # narrative generation + .docx rendering
│   ├── routers/               # industries, assessments, leads, dashboard, admin
│   └── middleware/            # admin session auth, AI rate limiting
├── alembic/                  # DB migrations
├── public/                   # frontend (index, assessment, learn/*, connect, dashboard, admin/*)
├── requirements.txt
└── railpack.json              # Railway deploy config (start command)
```

## Run it locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # fill in ANTHROPIC_API_KEY at minimum
alembic upgrade head
python -m app.db.seed

uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000**.

## Environment variables

| Var | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | From console.anthropic.com |
| `DATABASE_URL` | No | Defaults to a local SQLite file. Use a Postgres URL in production. |
| `SESSION_SECRET` | Recommended | Signs the admin session cookie |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | Recommended | bcrypt hash; without it, a dev fallback (`admin` / `admin`) is used |
| `RESEND_API_KEY`, `NOTIFY_EMAIL`, `NOTIFY_FROM_EMAIL` | No | Optional email notification on new leads |
| `AI_REPORTS_PER_DAY` | No | Defaults to 2 — the free-tier cap on full AI reports per email per day |

## API reference

- `GET /api/industries`, `GET /api/industries/{id}/standards`, `GET /api/standards/{id}/templates`
- `POST /api/assessments/start` — `{ template_id, tier, email? }` → AI-generated questions
- `POST /api/assessments/{id}/submit` — `{ email?, responses }` → scorecard (+ full report for premium)
- `GET /api/assessments/{id}/result`, `GET /api/assessments/{id}/report.docx`
- `POST /api/assessments/{id}/explain-score` — `{ category }` → AI explanation
- `POST /api/leads`, `GET /api/leads`
- `GET /api/dashboard/stats`
- `POST /api/admin/login`, CRUD under `/api/admin/{industries,standards,templates,questions}`
- `POST /api/document-assessments` — `multipart: file, document_title?, email?` → a Controlled Document
  Maturity Assessment (upload a procedure/policy/standard, no questionnaire) scored against a fixed
  15-category rubric
- `GET /api/document-assessments/{id}`, `GET /api/document-assessments/{id}/report.docx`

Interactive docs at `/docs` (FastAPI auto-generated).

## Deployment (Railway)

`railpack.json` sets the start command (runs Alembic migrations + seed, then
`uvicorn`). Provision a Postgres plugin in the same Railway project and set
`DATABASE_URL` to its internal connection string, plus the env vars above.

## Not yet built

- Real payments — everything is free with the daily AI-report cap
- End-user accounts/login — assessment continuity is by email, not auth
