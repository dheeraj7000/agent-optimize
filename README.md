# AgentOptimize

**Observe. Diagnose. Optimize. Prove.**

[![CI](https://github.com/dheeraj7000/agent-optimize/actions/workflows/ci.yml/badge.svg)](https://github.com/dheeraj7000/agent-optimize/actions/workflows/ci.yml)

A framework-agnostic optimization layer for production AI agents. AgentOptimize uses OpenTelemetry traces to identify inefficient model calls, context growth, retries, tool usage, and agent topology — then validates lower-cost configurations against historical workloads before production deployment.

## Core Promise

Tell companies exactly where their agentic AI systems are wasting money, quantify the waste, and recommend the lowest-risk optimization that preserves output quality, reliability, and functionality.

## Dashboard

The built-in dashboard ships with a dark-first glass UI (Geist typography, mint→cyan accents) covering Overview, Recommendations, Trace Explorer, Validation, Autopilot, and an interactive Quickstart.

| Overview | Trace Explorer |
|----------|----------------|
| ![Overview — dark glass dashboard](docs/screenshots/overview.png) | ![Trace Explorer — waste attribution](docs/screenshots/traces.png) |
| **Autopilot** | **Validation** |
| ![Autopilot — policy modes and decisions](docs/screenshots/autopilot.png) | ![Validation — proofs and canaries](docs/screenshots/validation.png) |

> **Adding screenshots:** run `agent-optimize serve`, open `http://localhost:8080`, press `⌘/Ctrl+Shift+4` (or your OS screenshot tool) on each page, and save the images as `docs/screenshots/<name>.png` (1920×1080 recommended). The table above will render them automatically once the files exist.

## Interactive API Docs

The server auto-generates full OpenAPI documentation for all 60 endpoints:

- **Swagger UI:** [`/docs`](http://localhost:8080/docs) — interactive request/response explorer
- **ReDoc:** [`/redoc`](http://localhost:8080/redoc) — reference-style rendering
- **OpenAPI spec:** [`/openapi.json`](http://localhost:8080/openapi.json) — for client generation

Run the server locally, then open [`http://localhost:8080/docs`](http://localhost:8080/docs) to try every endpoint from the browser.

## Architecture

```
OpenTelemetry
  |
Telemetry Normalizer
  |
Trace Warehouse (SQLite / in-memory)
  |
  +--> Cost Analyzer
  +--> Path / Critical-Path Analyzer
  +--> Quality Engine (6 evaluators)
  |
Waste Detectors (7 built-in)
  |
Optimization Engine
  |
Recommendations (with lifecycle)
  pending → accepted → replaying → validated → deployed → verified
  |
Counterfactual Replay → Savings Proof → Canary Monitor
  |
Autopilot (policy engine + model router + adaptive verifier + recovery selector)
  |
React Dashboard
```

## Quick Start

### 1. Prerequisites
- Python >= 3.11
- Node.js >= 18 and npm

### 2. Setup & Installation

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -e ".[dev]"

# Build the React dashboard frontend
cd dashboard
npm install
npm run build
cd ..
```

### 3. Run the Server

```bash
# Run server (in-memory mode — no setup needed)
agent-optimize serve
```

The server hosts both the API and the React SPA:
- **Dashboard / Web UI:** [http://localhost:8080](http://localhost:8080)
- **API Documentation (Swagger):** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Health Check:** [http://localhost:8080/health](http://localhost:8080/health)
- **OTLP Trace Ingestion:** `http://localhost:8080/v1/traces`

### 4. Seed Demo Data (Optional)

To explore the dashboard immediately with sample metrics, traces, and waste opportunities:

```bash
curl -X POST http://localhost:8080/api/onboarding/seed-demo \
  -H "Content-Type: application/json" \
  -d '{"count": 20}'
```

> Demo seeding is **disabled in production** — the endpoint returns 403 when `AGENTOPTIMIZE_ENV=production` or when API-key auth is required.

### Persistent Storage (Optional)

```bash
# Use SQLite for traces, recommendations, proofs (survives restarts)
export AGENTOPTIMIZE_DB_PATH=./data/agentoptimize.db
agent-optimize serve
```

### Dashboard Development (Hot Reload)

For active frontend development:

```bash
cd dashboard
npm install
npm run dev    # Hot reload at http://localhost:5173, proxies API to :8080
npm run build  # Production build served by FastAPI
cd ..
```

### With Docker

```bash
# Development (with OTel Collector sidecar)
docker compose up

# Production
docker build -f Dockerfile.production -t agentoptimize .
docker run -v data:/data -p 8080:8080 -e AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db agentoptimize
```

## API Overview (60 endpoints)

Browse all endpoints interactively at [`/docs`](http://localhost:8080/docs).

### V0 — Observe

| Endpoint | Description |
|----------|-------------|
| `POST /v1/traces` | OTLP/HTTP trace ingestion |
| `GET /api/traces` | List and filter traces |
| `GET /api/traces/{id}` | Full trace with all spans |
| `GET /api/traces/{id}/cost` | Cost breakdown by model, component, agent |
| `GET /api/dashboard/stats` | Aggregate statistics |
| `GET /api/dashboard/runs` | Lightweight run summaries |

### V1 — Diagnose

| Endpoint | Description |
|----------|-------------|
| `GET /api/traces/{id}/waste` | Waste detection report for a trace |
| `GET /api/dashboard/opportunities` | Executive opportunity dashboard |

### V2 — Optimize

| Endpoint | Description |
|----------|-------------|
| `POST /api/recommendations/generate` | Generate recommendations from traces |
| `GET /api/recommendations` | List (filter by status, category, priority) |
| `GET /api/recommendations/stats` | Aggregate savings by status/priority/category |
| `GET /api/recommendations/{id}` | Full detail: impact, evidence, confidence, config |
| `POST /api/recommendations/{id}/accept\|reject\|deploy\|verify\|rollback` | Lifecycle transitions |
| `POST /api/experiments` | Create replay experiment |
| `POST /api/experiments/{id}/run` | Run projection-based replay |

### V3 — Prove

| Endpoint | Description |
|----------|-------------|
| `GET /api/validation/evaluators` | List quality evaluators |
| `POST /api/validation/prove` | Validate savings from replay |
| `GET /api/validation/proofs` | List savings proofs |
| `POST /api/validation/canaries` | Create canary deployment |
| `POST /api/validation/canaries/{id}/start\|checkpoint\|complete` | Canary lifecycle |

### V4 — Autopilot

| Endpoint | Description |
|----------|-------------|
| `GET /api/autopilot/status` | Mode, stats, component health |
| `POST /api/autopilot/mode` | Set mode (off/suggest/supervised/autonomous) |
| `POST /api/autopilot/constraints` | Set quality/SLA/risk guardrails |
| `POST /api/autopilot/route` | Get model routing decision |
| `POST /api/autopilot/verify` | Get adaptive verification decision |
| `POST /api/autopilot/recover` | Get recovery decision |
| `GET /api/autopilot/decisions` | List recent decisions |
| `POST /api/autopilot/decisions/{id}/approve\|reject` | Approve/reject (supervised mode) |

## Waste Detectors

7 built-in money-leak detectors, each producing evidence-backed detections:

1. **Model overprovisioning** — frontier models used for low-complexity calls
2. **Context duplication** — growing input tokens with low novelty across multi-turn calls
3. **Retry waste** — failed retry sequences and repeated tool failures
4. **Unnecessary verification** — verification on simple successful runs
5. **Redundant tool calls** — duplicate tool calls detected by input hash
6. **Bad routing** — every call goes to the same premium model
7. **Serialization waste** — independent spans running serially

## Quality Evaluators

6 evaluators guard every optimization:

1. **Success rate** — min threshold + max regression from baseline
2. **Latency SLA** — P95 stays within bounds
3. **Cost bounds** — candidate actually saves money
4. **Error rate** — error rate doesn't exceed limits
5. **Statistical quality** — Z-test on success rate regression
6. **Model-based quality** — LLM-as-judge stub (requires provider config)

## Recommendation Lifecycle

```
pending → accepted → replaying → validated → deployed → verified
                  ↘ rejected                           ↘ rolled_back
```

Each recommendation includes:
- **Impact projection**: cost, quality, latency, reliability, and risk
- **Confidence score**: sample size, workload coverage, variance, evaluator agreement
- **Evidence chain**: statistical summary + trace samples
- **Config comparison**: side-by-side current vs. proposed
- **Business value score**: composite ranking (0-100)
- **Action items**: step-by-step implementation guide

## Autopilot

4 operating modes: `off → suggest → supervised → autonomous`

- **Policy engine**: customer-defined constraints (quality, latency, cost, reliability, risk)
- **Model router**: complexity/risk classification → 3-tier model routing
- **Adaptive verifier**: skip verification when risk is low and confidence is high
- **Recovery selector**: learned fallback strategies that minimize cost-to-success

## Security

Authentication posture by environment:

| Environment | Auth | Notes |
|-------------|------|-------|
| Local dev (`agent-optimize serve`) | Off by default | Zero-setup quickstart; unauthenticated boots are logged with a warning |
| Production Docker image | **Required** (baked into `Dockerfile.production`) | |
| Fly.io deploy | **Required** (set in `fly.toml`) | |
| Any deployment with `AGENTOPTIMIZE_API_KEY_REQUIRED=true` | Required | Wildcard CORS is refused when auth is on |

The dashboard shows a **security banner** whenever the server reports `auth_required: false` and no API key is configured — open the dashboard as `http://localhost:8080/?key=YOUR_KEY` to authenticate.

### Generating API Keys

```bash
# Generate a key for a tenant (SQLite DB required when auth is on)
agent-optimize create-key --tenant customer-acme --name "prod key"

# List existing keys
agent-optimize list-keys --tenant customer-acme
```

Then send the key with requests:

```bash
curl -H "Authorization: Bearer ao_live_..." http://your-host/api/traces
```

And configure your OpenTelemetry exporter:

```python
OTLPSpanExporter(
    endpoint="http://your-host/v1/traces",
    headers={"Authorization": "Bearer ao_live_..."},
)
```

## Configuration

```bash
cp config.example.yaml config.yaml
```

### Environment Variables

```bash
AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db  # SQLite path (omit for in-memory)
AGENTOPTIMIZE_ENV=production                   # Enables production security posture
AGENTOPTIMIZE_API_KEY_REQUIRED=true            # Enable API key auth
AGENTOPTIMIZE_LOG_FORMAT=json                  # json or console
AGENTOPTIMIZE_LOG_LEVEL=info                   # debug, info, warning, error
AGENTOPTIMIZE_CORS_ORIGINS=*                   # Comma-separated origins
```

## Deployment

### Fly.io (~$2/month)

```bash
# 1. Generate a production API key first (required: fly.toml enforces auth)
export AGENTOPTIMIZE_DB_PATH=./data/agentoptimize.db
agent-optimize create-key --tenant production

# 2. Launch
fly launch --copy-config --no-deploy
fly volumes create agentoptimize_data --size 1
fly deploy

# 3. Configure your OTel exporters and dashboard access with the key
```

### Self-hosted ($0)

```bash
docker build -f Dockerfile.production -t agentoptimize .
docker run -d -p 8080:8080 -v ./data:/data \
  -e AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db \
  agentoptimize
```

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v       # 103 tests
python -m ruff check src/        # Linting
```

## Project Structure

```
src/agent_optimize/
├── models/                    # Data models (traces, waste, recommendations, proofs)
├── ingestion/                 # OTel normalizer + OTLP/HTTP receiver
├── warehouse/                 # In-memory trace warehouse
├── storage/                   # SQLite persistence (traces, recommendations, proofs, canaries)
├── cost/                      # Cost catalog + analyzer
├── detectors/                 # 7 money-leak detectors + registry
├── evaluation/                # 6 quality evaluators + registry
├── optimization/              # Engine, recommender, replay, validator, canary manager
├── autopilot/                 # Policy engine, router, verifier, recovery selector
├── auth/                      # API key middleware
├── api/                       # FastAPI app + routes
└── cli.py                     # CLI entry point

dashboard/                     # React SPA (Vite + Tailwind, dark-first glass UI)
tests/                         # 103 tests
docs/                          # Infrastructure plan + screenshots
```

## Roadmap

| Phase | Status | Exit Criterion |
|-------|--------|----------------|
| V0 - Observe | ✅ Done | Accurate trace and cost accounting |
| V1 - Diagnose | ✅ Done | High-precision opportunities with evidence |
| V2 - Optimize | ✅ Done | Teams can prioritize fixes by business value |
| V3 - Prove | ✅ Done | Savings validated before production |
| V4 - Autopilot | ✅ Done | Automated changes within quality/SLA/risk constraints |
