# Engineering Decisions Log

Decisions made where the PRD/TRD left implementation details unspecified. Each favors the
simplest secure, testable approach, per the spec's own guidance.

## D1 — Authentication
Self-hosted JWT auth (email + bcrypt password hash), issued by the FastAPI backend. No external
identity provider — avoids an unnecessary dependency for a portfolio build while still giving
real, server-side-enforced RBAC.

## D2 — LLM provider for the AI Assistant
Anthropic API, called only from the backend (`app/ai/`), with the API key in an environment
variable that is never sent to the frontend. The frontend only ever calls `POST /api/ai/analyze`.

## D3 — Currency for Value at Risk
INR (₹), matching the "Cr" (crore) figures used throughout the spec's example screens.

## D4 — Eligibility rule for PSR denominator
A transaction is **eligible** unless: `status = 'USER_CANCELLED'`-equivalent error code, OR it
is flagged as internal/test traffic, OR it is a detected duplicate (`is_duplicate = true`).
`is_eligible` is materialized as a column on `transactions` at generation time so every metric
query uses the same, single definition rather than re-deriving it ad hoc.

## D5 — Anomaly injection window
A single deliberately injected anomaly: `BANK_A × Android × U28 × app v4.2.1`, confined to
`18:00–20:00` on the last full day of the generated dataset. Ground truth for this window is
written to `data/generator/ground_truth.json` and used only by the RCA-evaluation test suite,
never surfaced to the RCA engine itself.

## D6 — Real-time vs. batch
The pipeline is batch (generator → load → analytics). The UI never implies real-time; it always
shows "Data fresh as of {last successful `pipeline_runs` completion}," backed by the
`/api/data-freshness` endpoint implemented in Phase 1.

## D7 — Dataset size
750,000 transactions by default (`SYNTHETIC_TRANSACTION_COUNT` in `.env`), inside the spec's
500K–1M target range. Configurable via env var for anyone who wants to push to 1M.

## D8 — Transactions table not fully ORM-mapped
Given the fact table's size, analytics reads use `pandas.read_sql` with explicit column
selection and indexes tuned for the fingerprint engine's group-by dimensions, rather than
SQLAlchemy ORM object hydration, which would be unnecessarily slow at this scale.

## D9 — Local database for Phase 1 validation
Phase 1 validated the schema and backend against a real local PostgreSQL 16 instance (not
mocked) — schema applied cleanly, `error_codes` seeded and verified, `/api/health` and
`/api/data-freshness` confirmed live against real data before considering Phase 1 complete.

## D10 — Anomaly segment size
The injected fingerprint (`BANK_A × Android × U28 × v4.2.1 × 18:00–20:00`) is generated as an
explicit oversampled segment (`ANOMALY_SEGMENT_TXN_COUNT_FRACTION` in `dimensions.py`) rather
than emerging purely from independent per-dimension probabilities, which would produce too few
matching transactions at this dataset's scale to be a meaningful, demoable signal. At the default
750K-transaction target this yields ~10.5K affected transactions with a 41.7% failure rate against
a ~3.9% baseline — clearly detectable, independently verified via raw SQL against the loaded
database, not just in the generator script.

## D11 — Transactions table not managed by SQLAlchemy's ORM insert path
Given the volume (750K+ rows), the transactions table is bulk-loaded via PostgreSQL's native
`COPY` command (`data/generator/load_to_postgres.py`) rather than ORM `bulk_insert_mappings` or
row-by-row inserts. This loaded 760,451 rows in ~20 seconds; ORM-based insertion at this scale
would be substantially slower and isn't needed since the generator, not the API, is the writer.

## D12 — Duplicate and retry modeling
Retries and duplicate transactions are generated as explicit follow-up rows linked via
`original_transaction_id`, rather than mutating the original row, so both the original attempt
and the retry/duplicate remain independently queryable — required for the Recovery Rate and
Duplicate Rate metric definitions in the PRD's Metrics Dictionary.

## D13 — Fingerprint search uses a curated dimension-set list, not the full powerset
With ~9 candidate dimensions, an exhaustive powerset search (511 combinations) would be both
computationally wasteful and would surface mostly meaningless combinations. The fingerprint
engine (`app/analytics/fingerprint.py`) searches a curated list of single, pair, triple, and
quadruple dimension combinations chosen to match realistic incident patterns (single bank/PSP
issue, device+OS+app-version regression, network-class issue, and the compound
bank×device×OS×app-version pattern the RCA screen is built around).

## D14 — Fingerprint dedup keeps a broader fingerprint only if it explains MORE, not less
A broader (fewer-dimension) fingerprint is dropped only when a more specific one that fully
contains it already explains an equal or greater share of incremental failures. If a broader
segment (e.g. "WIFI" across all banks) explains *more* incremental failure than one of its
narrower specializations (e.g. "BANK_A × WIFI"), both are kept — they represent genuinely
different findings (a platform-wide network issue vs. a bank-specific one), not redundancy.

## D15 — Fingerprint contribution is capped at 100% for display
Contribution is computed against each segment's own historical baseline rate, while the
normalizing denominator uses the dataset's overall baseline rate. Because these can differ
slightly, a very precisely-matching segment can compute to slightly over 100% before display
rounding; this is clipped to 100% for UI clarity rather than re-normalizing all contributions
against a shared denominator, which would make each individual contribution less interpretable
on its own.

## D16 — PSR + Failure Rate is not always exactly 100%
Eligible `PENDING` transactions are correctly included in the PSR/Failure Rate denominator
(they are real, eligible, unresolved outcomes) but excluded from both numerators, since they
are neither a success nor a failure yet. This produces a small, expected gap versus 100%
(bounded by the synthetic dataset's ~0.2% pending rate) rather than an error.

## D17 — Anomaly detection and fingerprint scanning both use a rolling same-hour-of-day baseline
Rather than a flat trailing average, the baseline for both engines is built from the same
clock-hour window on each of the preceding N days (default 7), which controls for the
dataset's built-in time-of-day traffic and failure-rate shape (see `HOURLY_WEIGHTS` in the
generator) and avoids flagging normal evening traffic spikes as anomalies.

## D18 — Metrics/fingerprint queries run as parameterized SQL, shaped by Pandas
Given the transactions table's size (750K+ rows), aggregation (counts, sums, group-bys) runs
as parameterized SQL against PostgreSQL for speed, with Pandas used to assemble, merge, and
rank the results (baseline vs. observed comparisons, contribution scoring, dedup). This
follows the TRD's "PostgreSQL → Pandas Analytics" architecture while avoiding pulling 750K raw
rows into memory for every dashboard request.

## D19 — Extra endpoints beyond the strict API contract
`GET /api/experiments` (a list endpoint) and `POST /api/experiments` are added beyond the
contract's single `GET /api/experiments/{id}`, since the Experiment Analysis screen needs
something to list/link to, and the build spec explicitly asks for an "experiment tracker."
Similarly, `POST /api/interventions/{id}/measure-impact` is an explicit action endpoint (not
listed verbatim in the contract) rather than folding real metrics computation into the generic
`PATCH /api/interventions/{id}`, keeping "recompute real numbers from the analytics engine" and
"update arbitrary fields" as separate, clearer operations.

## D20 — Incident status transitions are validated as a state machine
Valid transitions are `open → {investigating, closed}`, `investigating → {mitigated, open,
closed}`, `mitigated → {resolved, investigating}`, `resolved → {closed, investigating}`,
`closed → {}` (terminal). An invalid transition (e.g. `open → resolved`, skipping
investigation) is rejected with `400 INVALID_TRANSITION` rather than silently allowed, since
the PRD explicitly enumerates the incident lifecycle as an ordered workflow.

## D21 — Audit actor identity: header first, then real auth (superseded)
Phase 4 used a temporary `X-Actor` header for audit attribution, since auth didn't exist yet.
Phase 5 removed it entirely: every write endpoint now resolves the actor from the verified JWT
via `get_current_user`, never from a client-supplied header. This entry is kept for the
historical record of the decision path; see D23 for the current mechanism.

## D22 — Before/after impact measurement always recomputes from the live analytics engine
`measure-impact` never accepts pre-computed before/after numbers from the client — it takes
only time windows and (optional) filters, and always calls `compute_core_metrics` fresh against
the database. This guarantees an intervention's reported impact can never drift from what the
same metrics engine would report elsewhere in the product (Dashboard, Failure Explorer, RCA).

## D23 — Auth endpoints extend beyond the strict API contract
`POST /api/auth/login` and `GET /api/auth/me` are not in the PRD's API contract, but the
contract cannot function without them once protected endpoints require a bearer token. JWTs are
issued with a `sub` (email) and `role` claim and expire after `JWT_EXPIRES_MINUTES` (default 8
hours). `X-Actor` headers from Phase 4 are removed entirely; every audit-log entry now uses the
authenticated user's email, resolved server-side from the verified token — never client-supplied.

## D24 — Role permission matrix
| Role | Read (dashboard/failures/RCA/incidents/interventions/experiments) | Create/update incidents | Create/update interventions | Create experiments |
|---|---|---|---|---|
| admin | ✓ | ✓ | ✓ | ✓ |
| pm | ✓ | ✓ | ✓ | ✓ |
| ops | ✓ | ✓ | ✓ | ✗ |
| engineer | ✓ | ✓ | ✓ | ✗ |
| support | ✓ | ✗ | ✗ | ✗ |
| viewer | ✓ | ✗ | ✗ | ✗ |

This follows the PRD's persona table (Section 7): PM and Ops own incident/intervention
workflows; Engineer participates in diagnosis and can update incidents; Support and Leadership
are consumers of the analysis, not authors of it; only PM (and Admin) define experiments, since
experiment design is a product decision.

## D25 — Demo users share one password
All six seeded demo accounts (`data/generator/seed_users.py`) use the same password
(`Demo123!`) so a portfolio reviewer only needs one credential to explore every role. This is
explicitly documented as a local/demo convenience — a production deployment would require
per-user credentials and a real password-reset flow, neither of which adds value to a portfolio
build.

## D26 — Rate limiting applied to `/api/auth/login` now; `/api/ai/analyze` in Phase 8
The PRD calls for rate limiting on "sensitive/AI endpoints." Login is rate-limited now (10
requests/minute per IP via `slowapi`) since it's the only sensitive endpoint that exists before
Phase 8; the same `slowapi` `Limiter` instance will be reused to rate-limit the AI Assistant
endpoint once it's built, rather than introducing a second rate-limiting mechanism later.

## D27 — bcrypt version pinned to 4.0.1
`passlib` 1.7.4's bcrypt backend detection is incompatible with `bcrypt` >= 4.1 (a known
upstream issue — `bcrypt.__about__` was removed). `requirements.txt` pins `bcrypt==4.0.1`
explicitly rather than leaving it to floating resolution, since the incompatibility causes
password hashing to fail outright, not just emit a warning.

## D28 — System font stack instead of next/font
`next/font/google` requires fetching font CSS from Google Fonts at build time. This sandbox's
network egress is restricted to package registries only, so the build failed until switched to
a system-font stack (`Inter` first, falling back through the OS's native UI font). This also
removes a build-time external dependency for anyone building the project behind a restrictive
firewall — a reasonable trade for a portfolio/ops-console build where the exact typeface matters
less than build reliability.

## D29 — Token storage: localStorage, not httpOnly cookies
The JWT is stored in `localStorage` and attached manually via an `Authorization: Bearer` header
on every request, rather than an httpOnly cookie set by the backend. This keeps the API a clean,
stateless bearer-token API usable identically by the web frontend, API docs/Swagger UI, and any
future mobile client, at the cost of the (accepted, documented) XSS-exposure trade-off inherent
to localStorage token storage — acceptable for a portfolio/demo build with synthetic data and no
real user PII.

## D30 — Auth guarding is client-side, not via Next.js middleware
Protected routes live under the `(app)` route group, and `AppShell` redirects to `/login`
client-side if `useAuth()` resolves to no user. This was chosen over Next.js middleware-based
route protection because the auth check depends on validating a bearer token against the FastAPI
backend (via `/api/auth/me`), not just checking cookie presence — middleware would need to make
the same round-trip anyway, so the added complexity of edge-middleware auth wasn't justified for
this build.

## D31 — Frontend built and verified without a browser
This environment has no headless browser/screenshot tool. Verification for each screen is:
TypeScript compiles with zero errors (`next build`), the production server serves HTTP 200 for
every route, and a real end-to-end check confirms the exact fetch calls each page makes return
correct data from the live backend (e.g. the RCA page's call returns the real injected
fingerprint, P0 severity, and evidence rows). Visual/pixel fidelity against the Figma file could
not be verified by rendering — the person should do a visual pass themselves after running
`docker compose up`.

## D32 — Failure Fingerprint Detail is merged into the RCA Workspace, not a separate screen
The design spec lists "Failure Fingerprint Detail" as its own screen, but its content (the
fingerprint label, contribution bars, evidence) is exactly what the RCA Workspace already shows
for its top-ranked fingerprint. Rather than duplicate that view behind a second route with no
distinguishing content given the backend's current data shape (there is no standalone
`GET /api/failures/{fingerprint_id}` endpoint yet — fingerprints are ephemeral scan results, not
persisted entities), the RCA Workspace serves as both screens' content for this build. A
dedicated Fingerprint Detail screen becomes worth adding once fingerprints are persisted
entities with their own IDs (a natural Phase 7+ extension).

## D33 — `GET /api/interventions` (list) added, matching the `GET /api/experiments` precedent
Same rationale as D19: the Intervention Center screen needs something to list and browse, and
the API contract's single `GET /api/interventions/{id}` isn't enough on its own. Supports
optional `incident_id` and `status` filters.

## D34 — AI Analyst screen ships as an honest "coming in Phase 8" state, not a fake chat UI
Per the "do not fake functionality" requirement, the AI Analyst screen shows its intended
architecture and the suggested questions from the spec, but the input is visibly disabled
rather than accepting text that goes nowhere. This is a legitimate empty/upcoming state, not a
placeholder pretending to work. **Superseded by Phase 8**: the AI Assistant backend now exists,
so this screen was upgraded to a real, functional interface (see D36-D38).

## D35 — "Yesterday" resolves relative to a fixed platform "now", one day after the dataset ends
The synthetic dataset's last generated day is 2026-08-29 (where the injected anomaly lives).
`PLATFORM_NOW` is fixed at 2026-08-30 00:00 UTC so that the PRD's example question ("Why did
PSR drop yesterday?") naturally resolves to the anomaly day without requiring the person to
know the exact demo date. "Today" therefore resolves to 2026-08-30, which has no data --
producing a clean, honest "insufficient data" response rather than a misleading one.

## D36 — Intent detection is rule-based, not an LLM call
Per the PRD's explicit requirement that "the LLM must NOT directly invent calculations," intent
parsing (`app/ai/intent.py`) uses keyword matching, not a model call. This guarantees which
analytics function will run is fully deterministic and auditable before any LLM is involved --
the LLM's only job is explaining an already-computed, validated structured result.

## D37 — A dedicated single-dimension scan exists alongside the multi-combo fingerprint scan
`scan_single_dimension()` in `app/analytics/fingerprint.py` ranks contribution for one
dimension without the multi-combo dedup applied in `run_fingerprint_scan()`. This was added
after testing revealed a real design interaction: the RCA screen's dedup correctly drops a
broader single-dimension finding (e.g. "BANK_A" alone) when a more specific fingerprint (e.g.
"BANK_A × Android × U28 × v4.2.1") already explains it with equal or greater contribution --
but a question specifically asking "which bank contributed most?" needs exactly that dropped
finding. Using the deduped multi-combo results for this question returned "insufficient data"
even when a clear answer existed; the dedicated single-dimension scan fixes this.

## D38 — AI Assistant works fully without an LLM API key configured
If `ANTHROPIC_API_KEY` is unset (as in this build/demo environment), `explain_with_llm()`
returns `None` and every intent handler falls back to either the RCA engine's existing
template-based summary or a plain enumeration of the structured result's fields -- never a
generic "AI unavailable" error. The response includes `llm_used: false` so the frontend can
show a "template summary" badge, being transparent about which explanation path produced the
answer without ever leaving the person without a data-grounded response. Rate limiting
(10/minute per IP, matching D26) is enforced on `/api/ai/analyze` regardless of which path
answers.

## D39 — CI uses the same 750K-row dataset size as local development, not a smaller one
Initially the CI workflow used a smaller (50K-row) synthetic dataset to keep the pipeline fast.
Testing this locally before committing to it revealed a real problem: several tests assert
specific values derived from the 750K-row run (e.g. the injected anomaly segment's ~58.28%
PSR), and because changing `--count` changes the entire RNG draw sequence (not just its length),
a 50K-row run computes a *different* segment PSR (57.00% -- confirmed by generating both scales
and comparing), which falls outside the `pytest.approx(58.28, abs=1.0)` tolerance and would have
made CI flaky. Since the generator takes only ~20 seconds even at 750K rows, CI now uses the
exact same seed and count as local development, reproducing byte-identical results and avoiding
scale-dependent test drift entirely, rather than loosening test tolerances to paper over it.

## D40 — Backend entrypoint auto-seeds and auto-generates data on first `docker compose up`
Per the PRD's Section 23 requirement that `docker compose up --build` should lead straight to
explorable demo data, `backend/entrypoint.sh` waits for Postgres, seeds `error_codes`/demo
users/the demo experiment (idempotently, via `ON CONFLICT` upserts), checks whether
`transactions` already has a realistic row count, and only runs the ~20-30 second synthetic
generation + load step if it doesn't. This was tested against two real database states (a
freshly-migrated empty database, and the existing 760K-row database) to confirm both branches
work correctly before being wired into the Docker image, since this script cannot be verified
by actually building the image in this sandbox (no Docker daemon available here — see D31 for
the same limitation applied to frontend verification).

## D41 — Backend Docker image gets a real `HEALTHCHECK`, and Compose start_period accounts for first-boot seeding
`docker-compose.yml`'s backend health check uses a 90-second `start_period` specifically because
first boot on a fresh volume includes the ~20-30 second dataset generation step from D40; a
shorter grace period would cause Compose to report the backend as unhealthy (and block the
frontend's `depends_on: condition: service_healthy`) during completely normal first-run seeding.

## D42 — Playwright E2E tests were written and structurally verified, but not executed here
`frontend/e2e/` contains 17 tests across 4 files covering the PRD's Section 24 demo scenario
end-to-end (Overview → anomaly → Failure Explorer → RCA fingerprint → Create Incident → Create
Intervention → measured before/after impact), the full authentication flow, RBAC enforcement
visible in the UI, and the AI Analyst screen. This sandbox has no Docker daemon and, separately,
Playwright's browser-binary CDN (`playwright.azureedge.net` and its mirrors) is not in this
environment's network allowlist — confirmed by actually attempting `npx playwright install
chromium`, which failed with a 403 from the egress proxy. What *was* verified here: every test
file type-checks with zero errors (`tsc --noEmit` across the whole frontend, e2e included), and
`npx playwright test --list` (which parses and registers tests without needing a browser)
confirms all 17 tests are discovered with valid syntax and correct Playwright API usage. The
CI workflow (`.github/workflows/ci.yml`, `e2e` job) runs them for real on GitHub's
non-restricted runners: it seeds the same 750K-row dataset as the backend job, boots both
servers, installs Chromium via `playwright install --with-deps`, and runs the suite — this is
the first point at which these tests actually execute against a live browser.

## D43 — E2E tests run serially, sharing seeded demo accounts and mutating real state
`playwright.config.ts` sets `workers: 1` and `fullyParallel: false` deliberately: several tests
create real incidents and interventions against the shared demo dataset (e.g. the RBAC test
creates an incident as PM, signs out, and views it as viewer), so parallel execution would
introduce race conditions between tests rather than the isolated, independent tests Playwright
is normally built for. This trades raw speed for correctness given the dataset is shared
across the whole suite by design (it's the same seeded synthetic data the manual demo walks
through), not a fresh fixture per test.

## D44 — Observability uses plain numbered SQL files, not a migration framework; access is admin/engineer/ops only
`sql/migrations/002_observability.sql` follows the same pattern as `001_init.sql` (a plain,
idempotent SQL file applied on fresh volumes via `docker-entrypoint-initdb.d`, or manually via
`psql -f` against an existing database) rather than introducing Alembic or another migration
framework for what is, at this scale, a single additive table. `GET /api/observability` is
restricted to admin/engineer/ops roles: PSR, incidents, and interventions are product/ops
signals every persona needs, but API latency, DB query timing, and pipeline run history are
operational internals that a PM or Support persona has no use for day to day (see the RBAC
matrix in D24, which this extends rather than replaces).

## D45 — Database query latency is tracked in-process, not logged per-query to a table
`app/db/session.py` uses SQLAlchemy's `before_cursor_execute`/`after_cursor_execute` events to
maintain simple in-memory counters (total query count and cumulative duration since process
start) rather than writing a row per SQL query to a table the way `api_request_logs` captures
per-request HTTP metrics. Given the transactions table alone can produce dozens of queries per
RCA/fingerprint scan, per-query logging would multiply write volume far beyond what a "database
query latency" health signal needs — an average is sufficient to answer "is the database
noticeably slow right now," which is the operational question this exists to answer. These
counters reset on process restart, which is an accepted trade-off for a lightweight, zero-extra-
storage implementation.

## D46 — `/api/health` and `/api/data-freshness` are excluded from request-log metrics
Docker/Compose health checks poll `/api/health` every few seconds by design (see D41's
`start_period`/`interval` configuration). Logging every one of those probes to
`api_request_logs` would dominate the table with liveness noise rather than real feature usage,
making the per-feature latency/error-rate breakdown in `/api/observability` less meaningful, not
more. Both endpoints are still fully functional and instrumented via FastAPI's normal request
lifecycle — they're just excluded from the persisted metrics table, verified by
`test_health_and_freshness_endpoints_excluded_from_logs` actually calling `/api/health` twice
and confirming the row count in `api_request_logs` doesn't change.
