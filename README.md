# UPI Payment Failure Intelligence Platform (UPI-FIP)

An internal FinTech payment-observability platform: **Detect → Diagnose → Intervene → Measure**.

> ⚠️ **Portfolio simulation.** This project uses synthetic transaction data only. It does not
> process, authorize, route, or settle real UPI payments, and never handles UPI PINs, account
> credentials, or other payment secrets. All volumes, PSR figures, and experiment outcomes
> shown in the demo are simulated/project results.

## Status: Phase 12 (Deployment + Observability) COMPLETE — full PRD build plan finished

- [x] Repository structure
- [x] PostgreSQL schema (migrations applied and verified against a live database)
- [x] FastAPI backend — boots, connects to Postgres, `/api/health` and `/api/data-freshness` live
- [x] Deterministic synthetic transaction generator — **760,451 rows, bulk-loaded and
      independently verified via raw SQL**, with the injected `BANK_A × Android × U28 × v4.2.1 ×
      18:00–20:00` anomaly (10,533 affected transactions, 41.7% vs. 3.9% baseline failure rate)
- [x] **Metrics engine, Failure Fingerprint engine, Anomaly detection, RCA engine** — all
      verified against live data; the injected anomaly is correctly rediscovered end-to-end
- [x] Full API surface (dashboard, failures, RCA, incidents, interventions, experiments, auth,
      AI assistant, observability) — all live and tested
- [x] **Auth / RBAC**: JWT login, bcrypt hashing, 6-role permission matrix, rate-limited login,
      6 seeded demo users — verified live
- [x] **Frontend — all 9 screens built, verified, and functional**, including a live
      Observability panel on Settings (admin/engineer/ops only)
- [x] **AI Assistant**: 5 intents, grounded in real analytics, works with or without an LLM key
- [x] **True one-command local experience**: `docker compose up --build` auto-seeds everything
      and generates the synthetic dataset only on first boot
- [x] Backend Docker `HEALTHCHECK`, `.dockerignore` for both services, GitHub Actions CI
      (backend tests + frontend build + a real Playwright browser run)
- [x] **Playwright E2E suite** (17 tests / 4 files) covering the full demo scenario, auth, RBAC,
      and the AI Analyst — executes for real in CI; structurally verified here (see D42)
- [x] **`docs/architecture.md`**: system diagram, demo-scenario sequence diagram, component
      responsibility table, and an explicit "what's deliberately out of scope" section
- [x] **Observability** (PRD Section 22 — the last previously-open gap): every API request's
      method, path, status, and latency is logged to `api_request_logs` (with health-check noise
      deliberately excluded, D46); RCA generation and AI Assistant calls surface as their own
      latency/error-rate groups automatically, derived from the route path rather than a second
      logging mechanism; database query count/average latency is tracked in-process via
      SQLAlchemy events (D45); `GET /api/observability` (admin/engineer/ops only, D44) exposes
      all of it plus recent pipeline-run health. Verified live: generated real traffic across
      5 feature groups and confirmed the endpoint correctly aggregated it — including a genuine
      real finding (the dashboard endpoint's ~2.6s avg latency stood out as measurably slower
      than other routes, exactly the kind of signal this feature exists to surface)
- [x] **65 backend tests passing** (14 generator + 51 integration, including 9 new observability
      tests covering RBAC, real measured traffic aggregation, and health-check exclusion)
- [ ] Portfolio case study / demo video (Phase 13 — outside code scope; requires you to actually
      run and look at the product)

> **Note on deployment/E2E verification**: this sandbox has no Docker daemon and its network
> blocks the Playwright browser-binary CDN (both confirmed by actually attempting them, not
> assumed) — see D31, D42. Everything that *could* be verified without those was: every
> `entrypoint.sh` code path tested against real databases, all E2E tests confirmed
> structurally valid via `playwright test --list` and zero TypeScript errors, and both actually
> execute for real in GitHub Actions CI, which has unrestricted network access.

See `docs/decisions.md` for the 46 engineering decisions made where the spec left room for
implementation choice, and `docs/architecture.md` for the system architecture diagram, the
demo-scenario sequence diagram, and component responsibilities.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

First boot takes ~30-60s longer than subsequent ones: the backend automatically waits for
Postgres, seeds the error-code taxonomy, demo users, and demo experiment, and generates +
loads the 750K-row synthetic dataset (including the injected failure anomaly) before starting
the API. Subsequent `docker compose up` runs skip regeneration since the data already exists.

Then open http://localhost:3000 and sign in with any demo account (password `Demo123!` — see
below). The FastAPI docs are at http://localhost:8000/docs.

## Manual / step-by-step setup (equivalent to what the entrypoint automates)

```bash
# 1. Stand up Postgres 16 locally and apply the schema
psql -U postgres -c "CREATE USER upi_fip WITH PASSWORD 'localtest' SUPERUSER;"
psql -U postgres -c "CREATE DATABASE upi_fip OWNER upi_fip;"
psql -U upi_fip -d upi_fip -f sql/migrations/001_init.sql

# 2. Seed the error-code taxonomy
cd data/generator
python seed_error_codes.py

# 3. Generate the synthetic dataset (deterministic; ~760K rows, ~20s)
python generate_transactions.py --seed 42 --count 750000 \
  --out transactions.csv --ground-truth-out ground_truth.json

# 4. Bulk-load it
python load_to_postgres.py --csv transactions.csv --truncate

# 5. Run the backend
cd ../../backend
pip install -r requirements.txt
uvicorn app.main:app --reload
curl http://localhost:8000/api/health
curl http://localhost:8000/api/data-freshness

# 6. Run the generator's test suite
cd ../data/generator
pytest tests/test_generator.py -v

# 7. Run the analytics engine's integration test suite (requires the loaded dataset)
cd ../../backend
DATABASE_URL_TEST="postgresql+psycopg2://upi_fip:localtest@localhost:5432/upi_fip" \
  pytest tests/integration/test_analytics.py -v

# 8. Try the RCA engine directly against the injected anomaly
#    (Note: as of Phase 5, this and all API calls below require an Authorization
#    header once auth is seeded — see step 12-13 for how to get a token.)
curl "http://localhost:8000/api/rca/ad-hoc?start=2026-08-29T18:00:00&end=2026-08-29T20:00:00"

# 9. Seed the demo experiment (Phase 4)
cd ../data/generator
python seed_experiment.py

# 10. Run the incident/intervention/experiment lifecycle tests
cd ../../backend
pytest tests/integration/test_incidents_lifecycle.py -v

# 12. Seed demo users (Phase 5 — one per RBAC role, shared password Demo123!)
cd ../data/generator
python seed_users.py

# 13. Log in and try a protected endpoint
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"pm@upi-fip.dev","password":"Demo123!"}' | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -s http://localhost:8000/api/dashboard -H "Authorization: Bearer $TOKEN"

# 14. Run the auth/RBAC-aware integration test suite
cd ../../backend
pytest tests/integration/ -v
```

## Demo accounts (Phase 5)

All accounts share the password `Demo123!` (local/demo convenience only — see `docs/decisions.md` D25):

| Email | Role | Can create/update incidents & interventions | Can create experiments |
|---|---|---|---|
| admin@upi-fip.dev | admin | ✓ | ✓ |
| pm@upi-fip.dev | pm | ✓ | ✓ |
| ops@upi-fip.dev | ops | ✓ | ✗ |
| engineer@upi-fip.dev | engineer | ✓ | ✗ |
| support@upi-fip.dev | support | ✗ (read-only) | ✗ |
| viewer@upi-fip.dev | viewer | ✗ (read-only) | ✗ |

## Running the frontend (Phase 6)

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000 — you'll land on `/login`. Pick any demo account card (password
pre-fills to `Demo123!`) and sign in. All 9 screens are live: Overview (`/`), Failure Explorer
(`/failures`, with a "Load known anomaly" button), RCA Workspace (`/rca`, defaults to the
injected anomaly window — this is the hero screen: run it, then use the **Create Incident** and
**Create Intervention** buttons to walk the full demo scenario), Incidents (`/incidents`),
Intervention Center (`/interventions`), Experiments (`/experiments`), **AI Analyst**
(`/ai-analyst` — try "Why did PSR drop yesterday?"), and Settings (`/settings`, showing your
role's permissions).

## Running the AI Assistant (Phase 8)

```bash
cd backend
pytest tests/integration/test_ai_assistant.py -v
```

Works out of the box with no configuration — every answer is grounded in the real analytics
engines, with a template-based explanation when no LLM key is set. To get natural
LLM-phrased explanations instead, add your key to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

No code changes needed; the fallback path is automatic either way (see `docs/decisions.md` D38).

## Running the E2E test suite (Phase 11)

Requires the full stack running (both `docker compose up` or the manual backend+frontend setup
above, seeded with the synthetic dataset):

```bash
cd frontend
npx playwright install --with-deps chromium   # first time only
npx playwright test
```

Add `--ui` for Playwright's interactive test runner, or `--headed` to watch the browser. See
`docs/decisions.md` D42 for why these couldn't be executed inside the environment that built
this project, and D43 for why they run serially rather than in parallel.

## Running the observability endpoint (Phase 12)

```bash
cd backend
pytest tests/integration/test_observability.py -v
```

Or check it live (sign in as `admin@upi-fip.dev`, `ops@upi-fip.dev`, or `engineer@upi-fip.dev` —
it's a 403 for other roles by design, see D44):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@upi-fip.dev","password":"Demo123!"}' | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -s "http://localhost:8000/api/observability?window_minutes=60" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Or just open `/settings` in the app while signed in as one of those three roles — the same data
renders there in a panel.

## Repository structure

```
upi-fip/
├── docker-compose.yml
├── .env.example
├── sql/migrations/          # PostgreSQL schema
├── backend/                 # FastAPI + Pandas analytics
│   └── app/
│       ├── core/            # config, security
│       ├── db/              # SQLAlchemy session + models
│       ├── schemas/         # Pydantic request/response models
│       ├── api/routes/      # dashboard, failures, rca, incidents, interventions, experiments, ai
│       ├── analytics/       # metrics, fingerprint engine, anomaly detection, RCA
│       └── ai/              # intent parsing + LLM orchestration
├── data/generator/          # deterministic synthetic transaction generator + seed scripts
├── frontend/                # Next.js + TypeScript + Tailwind
└── docs/                    # architecture + decisions
```

## Tech stack

Next.js/TypeScript/Tailwind · FastAPI · PostgreSQL · Pandas · Claude API (server-side only) ·
Pytest/Playwright · Docker Compose.

## Design reference

The UI is built against a Figma design system covering all 9 core screens (Overview, Failure
Explorer, Fingerprint Detail, RCA Workspace, Incident Detail, Intervention Detail, Experiment
Analysis, AI Analyst, Settings/RBAC).
