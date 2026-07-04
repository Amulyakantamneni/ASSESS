# MaturityAssess — Full Stack App

A working frontend + backend for the Process Maturity & Gap Assessment site.
Every button on the page now does real work:

| Button | What it does |
|---|---|
| **Start Assessment** (hero) | Opens a multi-step questionnaire modal, calls the backend, and shows a real scored result with maturity level + top gaps + recommendations. |
| Any **Approach card** | Same flow, pre-tagged with which approach the visitor picked (stored with the session). |
| **Learn More** | Smooth-scrolls to the Approaches section (no backend needed). |
| **Request Assessment** (CTA at bottom) | Opens a lead-capture form (name/email/company/message) that POSTs to the backend and is stored as a lead. |
| **Talk to an Expert** (after seeing results) | Opens the same lead form, pre-filled with the visitor's result summary. |

## Stack

- **Backend:** Node.js + Express
- **Storage:** Simple JSON-file datastore (`db.js`) — zero native dependencies, so it installs anywhere (including restricted sandboxes) with no build step. Swap for Postgres/MySQL later without touching the routes much (see "Upgrading storage" below).
- **Frontend:** Plain HTML/CSS/vanilla JS (the original design, now wired to real endpoints instead of `alert()`)

## Project structure

```
maturity-assess/
├── server.js              # Express app entrypoint
├── db.js                   # JSON-file datastore helper
├── questions.js             # Question bank + scoring/gap-analysis logic
├── routes/
│   ├── leads.js             # POST/GET /api/leads
│   └── assessment.js        # POST /api/assessment/start, /submit, GET /:id
├── public/
│   └── index.html           # Frontend (served statically by Express)
├── data/                    # JSON "tables" get created here at runtime
├── package.json
├── .env.example
└── README.md
```

## Run it locally

```bash
cd maturity-assess
npm install
cp .env.example .env      # optional, defaults to PORT=3000 anyway
npm start
```

Then open **http://localhost:3000** — the frontend and API are served from the same app.

## API reference

### `GET /api/health`
Simple uptime check.

### `POST /api/assessment/start`
Body: `{ "approach": "self-assessment" }`
Returns a `sessionId` and the full question set (8 categories, 5 options each).

### `POST /api/assessment/submit`
Body: `{ "sessionId": "...", "answers": { "documentation": 3, "quality_compliance": 2, ... } }`
Scores the answers, stores the result, and returns:
- `overallScore` and `overallLevel` (1–5 maturity level)
- per-category `score`/`gap`
- `topGaps` (biggest 3 gaps)
- `recommendations` (one per top gap)

### `GET /api/assessment/:resultId`
Fetch a previously computed result by id.

### `POST /api/leads`
Body: `{ "name": "...", "email": "...", "company": "...", "message": "..." }`
Validates and stores a lead. Returns a confirmation message.

### `GET /api/leads`
Lists all captured leads, newest first. **This is unauthenticated — see "Before going to production" below.**

## Before going to production

This is a complete, working app, but a few things are intentionally left for you to decide based on your real needs:

1. **Protect `GET /api/leads`.** Right now anyone who finds the URL can see your leads. Add a simple API key check or move it behind your auth system before deploying publicly.
2. **Add outbound notifications.** Right now leads are only saved to disk. Wire up an email (e.g. via [Resend](https://resend.com), [SendGrid](https://sendgrid.com), or SMTP) or a Slack webhook inside `routes/leads.js` right after `db.insert('leads', lead)` so you actually get notified.
3. **Upgrading storage.** The JSON file store works well for low-to-moderate traffic and is trivial to inspect (`cat data/leads.json`), but for production scale swap `db.js` for a real database:
   - **Postgres** (e.g. via [Supabase](https://supabase.com) or [Neon](https://neon.tech)) — best if you deploy to a serverless platform, since JSON files don't persist reliably across serverless invocations.
   - **SQLite with `better-sqlite3`** — great option if you're on a normal VPS (not serverless). It was skipped in the sandbox this was built in only because that environment couldn't reach the internet to download native build headers — that restriction won't exist on your own machine or a real host.
4. **CORS**: currently wide open (`cors()` with no options). Lock `origin` down to your real domain once you know it.

## Deployment options

### Option A — Render / Railway (easiest, recommended)
1. Push this folder to a GitHub repo.
2. Create a new **Web Service** on [Render](https://render.com) or [Railway](https://railway.app), point it at the repo.
3. Build command: `npm install` — Start command: `npm start`.
4. Done — you get a public URL and free HTTPS. Note: on Render's free tier, the filesystem is ephemeral on redeploys, so migrate to Postgres (see above) once leads matter to you.

### Option B — Your own VPS (DigitalOcean, Linode, EC2, etc.)
```bash
git clone <your-repo>
cd maturity-assess
npm install
npm install -g pm2         # process manager so it survives reboots/crashes
pm2 start server.js --name maturity-assess
pm2 save
```
Put Nginx or Caddy in front for HTTPS + your domain.

### Option C — Vercel/Netlify (serverless)
Possible, but you'd need to:
- Convert `server.js`'s routes into individual serverless functions (`/api/leads.js`, `/api/assessment/start.js`, etc.)
- Replace the JSON file store with a real hosted database (serverless functions don't have a persistent local disk)

Given the app is small, **Option A (Render/Railway)** is the least amount of rework and the best fit.

## Testing it yourself

```bash
# Health check
curl http://localhost:3000/api/health

# Start an assessment
curl -X POST http://localhost:3000/api/assessment/start \
  -H "Content-Type: application/json" \
  -d '{"approach":"self-assessment"}'

# Submit answers (use the sessionId from above)
curl -X POST http://localhost:3000/api/assessment/submit \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"<id>","answers":{"documentation":2,"quality_compliance":3,"metrics":1,"decision_making":4,"risk_management":2,"resource_allocation":3,"employee_capability":2,"innovation":1}}'

# Submit a lead
curl -X POST http://localhost:3000/api/leads \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Doe","email":"jane@example.com","company":"Acme Corp","message":"Interested in a facilitated assessment."}'
```
