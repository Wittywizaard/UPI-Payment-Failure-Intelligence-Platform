# UPI Payment Failure Intelligence Platform (UPI-FIP)

An internal FinTech payment-observability platform designed to actively monitor, diagnose, and resolve UPI payment failures. 

The core philosophy of this platform is **Detect → Diagnose → Intervene → Measure**. Instead of merely displaying dashboards, UPI-FIP actively scans for anomalies, pinpoints the specific root causes (e.g., Bank A + Android App v4.2.1), and tracks the success of interventions.

> ⚠️ **Note:** This is a portfolio simulation project. It uses deterministically generated synthetic transaction data. It does not process, authorize, route, or settle real UPI payments, and it never handles real UPI PINs, account credentials, or other payment secrets.

## Key Features

- **Anomaly Detection & Analytics:** Automatically monitors Payment Success Rates (PSR) against historical baselines and triggers alerts during abnormal drops.
- **Failure Fingerprint Engine:** Scans thousands of dimensional combinations (Bank × OS × Device × Error Code) to isolate the exact cluster of failed transactions causing a drop.
- **Root Cause Analysis (RCA) Engine:** Orchestrates anomaly detection and fingerprinting to generate human-readable RCA reports with estimated value-at-risk.
- **Incident & Intervention Management:** Allows Product Managers and Operations teams to track P1 incidents, log interventions, and measure the "Before vs. After" recovery rate.
- **AI Assistant:** A built-in orchestration layer that allows users to ask natural language questions (e.g., *"Why did PSR drop yesterday?"*). The system routes validated metrics to an LLM to generate grounded, fact-based explanations.
- **Role-Based Access Control (RBAC):** Secure JWT authentication with a 6-role permission matrix (Admin, PM, Ops, Engineer, Support, Viewer).

## Tech Stack

- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI
- **Database:** PostgreSQL 16
- **Analytics:** Pandas, SQLAlchemy
- **Testing:** Pytest (Backend), Playwright (E2E Frontend)
- **Deployment:** Docker Compose

## Quickstart

The easiest way to run this project is using Docker. The first boot takes a bit longer (~30-60s) as it deterministically generates 750,000 synthetic transactions to populate the dashboard.

```bash
# 1. Clone the repository
git clone https://github.com/Wittywizaard/UPI-Payment-Failure-Intelligence-Platform.git
cd UPI-Payment-Failure-Intelligence-Platform

# 2. Set up environment variables
cp .env.example .env

# 3. Start the application
docker compose up --build
```

Once running, open [http://localhost:3000](http://localhost:3000) in your browser. The backend API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Demo Accounts

You can log in to the platform using any of the seeded demo accounts. **All accounts share the same password: `Demo123!`**

| Email | Role | Capabilities |
|---|---|---|
| `admin@upi-fip.dev` | Admin | Full Access |
| `pm@upi-fip.dev` | PM | Incidents, Interventions, Experiments |
| `ops@upi-fip.dev` | Ops | Incidents, Interventions |
| `engineer@upi-fip.dev` | Engineer | Incidents, Interventions |
| `support@upi-fip.dev` | Support | Read-only |
| `viewer@upi-fip.dev` | Viewer | Read-only |

## System Architecture

**PostgreSQL does the heavy aggregation; Pandas shapes and ranks it.** 
To handle ~750K rows efficiently, GET endpoints run parameterized SQL aggregations (counts, sums, group-bys) directly against Postgres. Pandas is used for complex operations like merging observed-vs-baseline comparisons and deduplicating nested fingerprints.

**The AI Assistant never computes anything itself.**
Intent parsing is rule-based keyword matching. The LLM (when configured) is handed only the already-validated structured result and instructed never to introduce a number that isn't in it.

## Testing

The project includes an extensive test suite:
- **Backend:** 65 integration and unit tests using `pytest`.
- **Frontend/E2E:** 17 Playwright E2E tests covering the full demo scenario, authentication, RBAC, and the AI Analyst.

To run tests manually (requires local Python/Node environments):
```bash
# Backend Tests
cd backend
pytest tests/ -v

# Frontend E2E Tests
cd frontend
npx playwright test
```
