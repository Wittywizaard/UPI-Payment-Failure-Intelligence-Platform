# Architecture

## System overview

```mermaid
flowchart TB
    subgraph Generation["Data Generation (offline / entrypoint)"]
        GEN["generate_transactions.py<br/>deterministic, seeded"]
        GT["ground_truth.json<br/>(RCA-eval only, never<br/>fed to detection engine)"]
        GEN -.writes.-> GT
    end

    subgraph DB["PostgreSQL 16"]
        TXN[(transactions<br/>~760K rows)]
        REF[(error_codes,<br/>users, incidents,<br/>interventions,<br/>experiments,<br/>audit_logs,<br/>pipeline_runs)]
    end

    subgraph Backend["FastAPI Backend"]
        AUTH["Auth<br/>JWT + bcrypt + RBAC"]
        METRICS["Metrics Engine<br/>PSR / failure / recovery /<br/>retry / duplicate rate"]
        FP["Fingerprint Engine<br/>curated dimension scan<br/>+ dedup"]
        ANOM["Anomaly Detector<br/>rolling same-hour baseline"]
        RCA["RCA Engine<br/>orchestrates the above"]
        AI["AI Assistant<br/>intent -> analytics -> LLM"]
        API["REST API<br/>/api/*"]

        API --> AUTH
        API --> METRICS
        API --> FP
        API --> ANOM
        API --> RCA
        API --> AI
        RCA --> ANOM
        RCA --> FP
        AI --> METRICS
        AI --> FP
        AI --> RCA
    end

    subgraph LLM["Anthropic API (optional)"]
        CLAUDE["Claude<br/>explanation layer only"]
    end

    subgraph Frontend["Next.js Frontend"]
        UI["9 screens:<br/>Overview, Failure Explorer,<br/>RCA Workspace, Incidents,<br/>Interventions, Experiments,<br/>AI Analyst, Settings, Login"]
    end

    GEN -->|bulk COPY| TXN
    METRICS -->|parameterized SQL| TXN
    FP -->|parameterized SQL| TXN
    ANOM -->|parameterized SQL| TXN
    AUTH <--> REF
    RCA <--> REF
    AI -.explanation only, never<br/>computes numbers.-> CLAUDE
    UI <-->|JSON over HTTPS,<br/>Bearer JWT| API
```

## Why this shape

**PostgreSQL does the heavy aggregation; Pandas shapes and ranks it.** The `transactions` table
holds ~760K rows. Rather than pulling that into memory for every dashboard request, `GET`
endpoints run parameterized SQL aggregations (counts, sums, group-bys) directly against
Postgres, and Pandas is used where the TRD calls for it: merging observed-vs-baseline
comparisons, computing contribution scores, and deduplicating nested fingerprints — logic that's
awkward to express as a single SQL query but fast once the heavy counting is already done in the
database. See `docs/decisions.md` D18.

**The RCA engine is an orchestrator, not a new computation.** `run_rca()` calls
`detect_anomaly()` (rolling baseline comparison) and, only if an anomaly is found,
`run_fingerprint_scan()` (dimension-combination search). Both of those exist and are tested
independently — RCA composes them and adds evidence assembly, severity, and recommended
actions on top. Nothing in the RCA path recomputes a number a lower-level engine already
computed.

**The AI Assistant never computes anything itself.** `parse_intent()` is rule-based keyword
matching — deliberately not an LLM call — so which analytics function runs is fully
deterministic before any model is involved (D36). The LLM (when configured) is handed only the
already-validated structured result and instructed never to introduce a number that isn't in
it; when no LLM key is configured, a template fallback produces the same shape of grounded
answer (D38).

**Auth is a bearer-token API, not session cookies.** The JWT carries `sub` (email) and `role`;
`require_role(...)` builds a role-checking dependency reused across every write endpoint. This
keeps the API equally usable from the Next.js frontend, `/docs` Swagger UI, or a future mobile
client (D29).

## Demo-scenario data flow

This is the exact path exercised by the Playwright `demo-scenario.spec.ts` suite and the
backend's `test_incidents_lifecycle.py`:

```mermaid
sequenceDiagram
    participant U as PM (browser)
    participant FE as Next.js Frontend
    participant API as FastAPI
    participant ANOM as Anomaly Detector
    participant FP as Fingerprint Engine
    participant DB as PostgreSQL

    U->>FE: Open Overview
    FE->>API: GET /api/dashboard
    API->>ANOM: detect_anomaly(last 24h)
    ANOM->>DB: aggregate PSR (observed vs. 7-day baseline)
    DB-->>ANOM: counts
    ANOM-->>API: anomaly=true, severity
    API-->>FE: KPIs + anomaly banner
    U->>FE: Click anomaly banner -> RCA Workspace
    FE->>API: GET /api/rca/ad-hoc?start&end
    API->>ANOM: detect_anomaly(window)
    API->>FP: run_fingerprint_scan(window)
    FP->>DB: grouped counts per curated dimension set
    DB-->>FP: volumes, failure counts
    FP-->>API: ranked, deduped fingerprints
    API-->>FE: RCA (fingerprint, evidence, AI summary, recommended actions)
    U->>FE: Click "Create Incident"
    FE->>API: POST /api/incidents (RBAC: pm/ops/engineer/admin only)
    API->>DB: INSERT incidents + audit_logs
    U->>FE: Click "Create Intervention"
    FE->>API: POST /api/interventions
    API->>DB: INSERT interventions + audit_logs
    U->>FE: Click "Measure Impact"
    FE->>API: POST /api/interventions/{id}/measure-impact
    API->>DB: compute_core_metrics(before window), compute_core_metrics(after window)
    API->>DB: UPDATE interventions SET actual_impact
    API-->>FE: before/after PSR, recovery rate, guardrail status
```

## Component responsibilities

| Component | Responsibility | Key files |
|---|---|---|
| Synthetic Generator | Deterministic transaction generation, injected anomaly, retries/duplicates | `data/generator/generate_transactions.py` |
| Metrics Engine | PSR, failure rate, recovery rate, retry rate, duplicate rate, value at risk | `backend/app/analytics/metrics.py` |
| Fingerprint Engine | Curated multi-dimension search, contribution scoring, dedup | `backend/app/analytics/fingerprint.py` |
| Anomaly Detector | Rolling same-hour-of-day baseline comparison, severity assignment | `backend/app/analytics/anomaly.py` |
| RCA Engine | Orchestration, evidence assembly, recommended actions | `backend/app/analytics/rca.py` |
| AI Assistant | Intent detection, routing, LLM explanation with template fallback | `backend/app/ai/` |
| Auth / RBAC | JWT issuance/verification, 6-role permission matrix | `backend/app/core/security.py`, `backend/app/core/deps.py` |
| API | REST endpoints, request validation, error normalization | `backend/app/api/routes/` |
| Frontend | 9 screens, typed API client, auth context | `frontend/app/`, `frontend/lib/` |

## What this diagram deliberately leaves out

Per the TRD's own scoping (Section 17), Kafka/streaming, a data warehouse, and advanced ML
anomaly models are **not** part of this architecture — the MVP is
`Generator -> PostgreSQL -> Pandas Analytics -> FastAPI -> Next.js`, and that's what's actually
built and tested. The roadmap section of the PRD (Section 31) describes where streaming and
predictive detection would fit in a V2/V3, but adding them here would be scope not requested by
the current build phase, not a missing piece of this MVP.
