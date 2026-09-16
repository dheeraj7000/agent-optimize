# AgentOptimize

**Observe. Diagnose. Optimize. Prove.**

A framework-agnostic optimization layer for production AI agents. AgentOptimize uses OpenTelemetry traces to identify inefficient model calls, context growth, retries, tool usage, and agent topology — then validates lower-cost configurations against historical workloads before production deployment.

## Core Promise

Tell companies exactly where their agentic AI systems are wasting money, quantify the waste, and recommend the lowest-risk optimization that preserves output quality, reliability, and functionality.

## Architecture

```
OpenTelemetry
  |
Telemetry Normalizer
  |
Trace Warehouse
  |
  +--> Cost Analyzer
  +--> Path / Critical-Path Analyzer
  +--> Quality Engine
  |
Waste Detectors (7 built-in)
  |-- model overprovisioning
  |-- context duplication
  |-- retry waste
  |-- unnecessary verification
  |-- redundant tool calls
  |-- bad routing
  |-- serialization waste
  |
Optimization Engine
  |
Recommendations (with lifecycle)
  pending → accepted → replaying → validated → deployed → verified
  |
Replay Experiments
  |
Opportunity Dashboard
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run the server
agent-optimize serve

# Or with Docker Compose (includes OTel collector)
docker compose up
```

The server exposes:
- **OTLP endpoint**: `POST /v1/traces` — send OpenTelemetry traces here
- **Dashboard API**: `GET /api/dashboard/opportunities` — executive opportunity view
- **Recommendations**: `GET /api/recommendations` — actionable optimizations
- **API docs**: `GET /docs` — interactive Swagger UI

## Configuration

Copy and edit the example config:

```bash
cp config.example.yaml config.yaml
```

The config controls model pricing, detector thresholds, privacy settings, and warehouse retention. See `config.example.yaml` for all options.

## API Overview

### Observe (V0)
| Endpoint | Description |
|----------|-------------|
| `POST /v1/traces` | OTLP/HTTP trace ingestion |
| `GET /api/traces` | List and filter traces |
| `GET /api/traces/{id}` | Full trace with all spans |
| `GET /api/traces/{id}/cost` | Cost breakdown by model, component, agent |
| `GET /api/dashboard/stats` | Aggregate statistics |
| `GET /api/dashboard/runs` | Lightweight run summaries |

### Diagnose (V1)
| Endpoint | Description |
|----------|-------------|
| `GET /api/traces/{id}/waste` | Waste detection report for a trace |
| `GET /api/dashboard/opportunities` | Executive opportunity dashboard |

### Optimize (V2)
| Endpoint | Description |
|----------|-------------|
| `POST /api/recommendations/generate` | Generate recommendations from current traces |
| `GET /api/recommendations` | List recommendations (filter by status, category, priority) |
| `GET /api/recommendations/stats` | Aggregate savings by status, priority, category |
| `GET /api/recommendations/{id}` | Full detail: impact, evidence, confidence, config comparison |
| `POST /api/recommendations/{id}/accept` | Accept a recommendation |
| `POST /api/recommendations/{id}/reject` | Reject a recommendation |
| `POST /api/recommendations/{id}/deploy` | Mark as deployed |
| `POST /api/recommendations/{id}/verify` | Confirm savings post-deploy |
| `POST /api/recommendations/{id}/rollback` | Roll back due to regression |
| `POST /api/experiments` | Create a replay experiment |
| `POST /api/experiments/{id}/run` | Run projection-based replay |
| `GET /api/experiments/{id}` | Get experiment results |

## Waste Detectors

AgentOptimize ships with 7 money-leak detectors:

1. **Model overprovisioning** — frontier models used for low-complexity calls
2. **Context duplication** — growing input tokens with low novelty across multi-turn calls
3. **Retry waste** — failed retry sequences and repeated tool failures
4. **Unnecessary verification** — verification on simple successful runs
5. **Redundant tool calls** — duplicate tool calls detected by input hash
6. **Bad routing** — every call goes to the same premium model
7. **Serialization waste** — independent spans running serially instead of in parallel

Each detection includes confidence level, dollar estimates, evidence, and a recommended action.

## Recommendation Lifecycle

Recommendations move through a managed lifecycle:

```
pending → accepted → replaying → validated → deployed → verified
                  ↘ rejected                           ↘ rolled_back
```

Each recommendation includes:
- **Impact projection**: cost, quality, latency, reliability, and risk across five dimensions
- **Confidence score**: sample size, workload coverage, variance, evaluator agreement, drift risk
- **Evidence chain**: statistical summary + trace samples with structured payloads
- **Config comparison**: side-by-side current vs. proposed configuration
- **Business value score**: composite ranking (0-100) for prioritization
- **Action items**: step-by-step implementation guide per waste category

## Project Structure

```
src/agent_optimize/
├── models/
│   ├── traces.py              # NormalizedSpan, NormalizedTrace, RunSummary
│   ├── waste.py               # WasteDetection, WasteReport, Opportunity
│   └── recommendations.py     # Recommendation, EvidenceChain, ConfidenceScore, ImpactProjection
├── ingestion/
│   ├── normalizer.py          # OTel GenAI conventions → internal schema
│   └── otlp_receiver.py       # OTLP/HTTP endpoint
├── warehouse/
│   └── store.py               # In-memory trace warehouse
├── cost/
│   ├── catalog.py             # Provider/model pricing
│   └── analyzer.py            # Per-span cost attribution
├── detectors/                 # 7 money-leak detectors + registry
├── optimization/
│   ├── engine.py              # Opportunity generation from waste reports
│   ├── recommender.py         # V2: Recommendations with scoring and config generation
│   ├── recommendation_store.py # V2: Lifecycle store with state machine
│   └── replay.py              # Counterfactual replay framework
├── api/
│   ├── app.py                 # FastAPI factory + pipeline wiring
│   └── routes/                # health, traces, dashboard, recommendations, experiments
└── cli.py                     # CLI: serve, check-config, list-models
```

## Roadmap

| Phase | Status | Exit Criterion |
|-------|--------|----------------|
| V0 - Observe | ✅ Done | Accurate trace and cost accounting |
| V1 - Diagnose | ✅ Done | High-precision opportunities with evidence |
| V2 - Optimize | ✅ Done | Teams can prioritize fixes by business value |
| V3 - Prove | Planned | Savings validated before production |
| V4 - Autopilot | Planned | Automated changes within quality/SLA/risk constraints |
