# AgentOptimize — Production Infrastructure Plan

## Design Principles

1. **Pilot-friendly**: Free or near-free for the first 2-3 customers
2. **Single-binary deployable**: One container, one database, minimal ops burden
3. **Upgrade path**: Every choice has a clear scale-up option when revenue arrives
4. **No vendor lock-in**: Open-source stack, standard protocols (OTel, SQL)

---

## Architecture: Pilot Stack

```
Customer Agent Frameworks
  |
  | (OTLP/HTTP or gRPC)
  v
┌─────────────────────────────────────────────┐
│  OTel Collector (optional, for fan-out)     │
└──────────────────┬──────────────────────────┘
                   |
                   v
┌─────────────────────────────────────────────┐
│  AgentOptimize Server (FastAPI)             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Ingestion│ │Detectors │ │ Autopilot   │ │
│  │ Pipeline │ │& Engine  │ │ (Router,    │ │
│  │          │ │          │ │  Verifier,  │ │
│  │          │ │          │ │  Recovery)  │ │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
│       └─────┬──────┘              │        │
│             v                     │        │
│  ┌────────────────────┐          │        │
│  │  SQLite / DuckDB   │◄─────────┘        │
│  │  (embedded DB)     │                   │
│  └────────────────────┘                   │
└─────────────────────────────────────────────┘
         |
         v
    Dashboard UI (static SPA served from same container)
```

### Why this stack?

| Component | Pilot Choice | Cost | Scale-up Path |
|-----------|-------------|------|---------------|
| Database | **SQLite** (traces, recs, proofs) | Free | → PostgreSQL → ClickHouse |
| Cache | In-process dict | Free | → Redis |
| API | FastAPI (already built) | Free | → Add workers with Gunicorn |
| Auth | API key middleware | Free | → OAuth2 / OIDC |
| Deployment | Single Docker container | Free (self-hosted) | → Fly.io / Railway ($5/mo) |
| OTel Collector | Optional sidecar | Free | → Managed OTel |
| Monitoring | Structured logs + /health | Free | → Prometheus + Grafana |
| CI/CD | GitHub Actions | Free (public repo) | → Private repo minutes |

### Cost estimate for pilot

| Item | Monthly Cost |
|------|-------------|
| Fly.io shared-cpu-1x (256MB) | $0 (free tier) or $1.94 |
| Persistent volume (1GB) | $0.15 |
| Domain (optional) | $0 (use fly.dev subdomain) |
| **Total** | **~$2/month** |

Alternative: Customer self-hosts the Docker container — $0.

---

## Implementation Checklist

### Phase 1: Persistence (SQLite)
- [x] SQLite-backed trace warehouse (replace in-memory dict)
- [x] SQLite-backed recommendation store
- [x] SQLite-backed proof and canary store
- [x] Auto-migration on startup
- [x] Retention-based cleanup job

### Phase 2: Auth & Security
- [x] API key authentication middleware
- [x] Tenant isolation via API key → tenant_id mapping
- [x] Rate limiting (simple token bucket)
- [x] Request logging with structured audit trail

### Phase 3: Testing
- [ ] Core model unit tests
- [ ] Detector accuracy tests
- [ ] API contract tests (httpx + pytest)
- [ ] Lifecycle state machine tests
- [ ] Evaluator edge case tests

### Phase 4: Deployment
- [x] Production Dockerfile (multi-stage, slim)
- [x] Fly.io deployment config (fly.toml)
- [x] Health check and readiness probes
- [x] Structured JSON logging for production
- [x] Environment-based config override

### Phase 5: Dashboard (future)
- [ ] Static SPA (React/Preact or plain HTML+htmx)
- [ ] Served from same FastAPI container
- [ ] Executive opportunity view
- [ ] Recommendation management
- [ ] Canary monitoring view

---

## Database Schema (SQLite)

```sql
-- Traces
CREATE TABLE traces (
    trace_id TEXT PRIMARY KEY,
    tenant_id TEXT,
    task_class TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_ms REAL,
    total_cost REAL,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    model_call_count INTEGER,
    tool_call_count INTEGER,
    retry_count INTEGER,
    success INTEGER,
    source_framework TEXT,
    data JSON,  -- Full NormalizedTrace serialized
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_traces_tenant ON traces(tenant_id);
CREATE INDEX idx_traces_time ON traces(start_time);
CREATE INDEX idx_traces_cost ON traces(total_cost);

-- Recommendations
CREATE TABLE recommendations (
    recommendation_id TEXT PRIMARY KEY,
    tenant_id TEXT,
    status TEXT,
    priority TEXT,
    category TEXT,
    title TEXT,
    business_value_score REAL,
    monthly_savings REAL,
    annual_savings REAL,
    confidence TEXT,
    data JSON,  -- Full Recommendation serialized
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_recs_tenant ON recommendations(tenant_id);
CREATE INDEX idx_recs_status ON recommendations(status);

-- Proofs
CREATE TABLE proofs (
    proof_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    status TEXT,
    actual_savings_pct REAL,
    quality_preserved INTEGER,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Canaries
CREATE TABLE canaries (
    canary_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    status TEXT,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

-- API Keys
CREATE TABLE api_keys (
    key_hash TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Audit Log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    action TEXT,
    resource TEXT,
    resource_id TEXT,
    actor TEXT,
    details JSON,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## API Key Authentication

Simple API key auth for pilots:

```
Authorization: Bearer ao_live_abc123def456
```

- Keys are SHA-256 hashed in the database
- Each key maps to a tenant_id
- All queries are automatically scoped to the tenant
- Admin keys can access cross-tenant endpoints

---

## Environment Variables

```bash
# Required
AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db

# Optional
AGENTOPTIMIZE_CONFIG_PATH=/app/config.yaml
AGENTOPTIMIZE_LOG_FORMAT=json          # json or console
AGENTOPTIMIZE_LOG_LEVEL=info
AGENTOPTIMIZE_API_KEY_REQUIRED=true    # false for local dev
AGENTOPTIMIZE_CORS_ORIGINS=*
AGENTOPTIMIZE_HOST=0.0.0.0
AGENTOPTIMIZE_PORT=8080
```
