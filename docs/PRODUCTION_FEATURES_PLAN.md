# Production Features Plan

## 1. Webhook/Alerting for Canary Regressions & Autopilot Decisions

### What
A webhook system that notifies external systems (Slack, PagerDuty, email, custom HTTP) when:
- Canary checkpoint detects regression (error rate breach, latency spike)
- Canary is auto-rolled-back
- Autopilot makes or blocks a decision (especially constraint violations)
- Recommendation status changes (accepted, deployed, verified, rolled_back)
- Savings proof validates or rejects

### Design
```
Event Source → EventBus → WebhookDispatcher → HTTP POST to configured URLs
                       → AuditLog (always)
```

- `WebhookConfig`: url, secret (HMAC signing), events filter, active flag
- `WebhookEvent`: event_type, payload, timestamp, delivery status
- Async delivery with retry (3 attempts, exponential backoff)
- HMAC-SHA256 signature in `X-AgentOptimize-Signature` header for verification
- API: CRUD webhooks, list deliveries, retry failed

### Event Types
- `canary.regressed`, `canary.completed`, `canary.rolled_back`
- `autopilot.decision.applied`, `autopilot.decision.blocked`, `autopilot.decision.pending`
- `recommendation.accepted`, `recommendation.deployed`, `recommendation.verified`, `recommendation.rolled_back`
- `proof.validated`, `proof.rejected`

---

## 2. OAuth2/OIDC Auth

### What
Replace API-key-only auth with standard OAuth2/OIDC for team-based access control.

### Design
- Keep API keys as the simple path (machine-to-machine, OTLP ingestion)
- Add OAuth2 with PKCE for dashboard login (human users)
- Support external OIDC providers (Google, GitHub, Okta, Auth0)
- JWT validation middleware — check issuer, audience, expiry
- Map OIDC claims to tenant_id and roles
- Roles: `viewer`, `operator` (can accept/deploy recommendations), `admin`

### Implementation
- `OIDCConfig`: issuer_url, client_id, audience, jwks_uri
- `JWTMiddleware`: validates Bearer JWT tokens from OIDC providers
- Coexists with API key auth — try JWT first, fall back to API key
- `/api/auth/me` endpoint returns current user/tenant context
- Config via environment: `AGENTOPTIMIZE_OIDC_ISSUER`, `AGENTOPTIMIZE_OIDC_CLIENT_ID`

---

## 3. Persistent Storage Upgrade (Postgres / ClickHouse)

### What
Abstract storage behind an interface so the same code works with SQLite (pilot), Postgres (production), and ClickHouse (analytics at scale).

### Design
```
StorageBackend (abstract)
  ├── SqliteBackend (current, embedded, free)
  ├── PostgresBackend (production, managed)
  └── ClickHouseBackend (analytics, high-volume traces)
```

- `AGENTOPTIMIZE_DB_BACKEND=sqlite|postgres|clickhouse`
- `AGENTOPTIMIZE_DB_URL=postgresql://...` or `clickhouse://...`
- Postgres via asyncpg for async queries
- ClickHouse via clickhouse-connect for analytical trace queries
- SQLite remains the zero-config default
- Migration tool: `agent-optimize migrate` CLI command

### Priority
- Postgres first (covers all use cases up to ~10M traces)
- ClickHouse later (when trace volumes exceed Postgres comfort zone)

---

## 4. Prometheus Metrics Export

### What
Expose `/metrics` endpoint for Prometheus scraping so the system can observe itself.

### Metrics
**Business metrics:**
- `agentoptimize_traces_ingested_total` (counter)
- `agentoptimize_trace_cost_dollars` (histogram)
- `agentoptimize_waste_detected_dollars` (histogram)
- `agentoptimize_recommendations_total` (gauge, by status)
- `agentoptimize_savings_identified_dollars` (gauge)
- `agentoptimize_savings_verified_dollars` (gauge)

**Autopilot metrics:**
- `agentoptimize_autopilot_decisions_total` (counter, by outcome)
- `agentoptimize_routing_decisions_total` (counter, by complexity)
- `agentoptimize_verification_skip_rate` (gauge)

**System metrics:**
- `agentoptimize_request_duration_seconds` (histogram, by endpoint)
- `agentoptimize_request_total` (counter, by status code)
- `agentoptimize_traces_stored` (gauge)

### Implementation
- Use `prometheus_client` library (standard, zero deps beyond the lib)
- Middleware to track request duration/count
- Background task to refresh business metrics periodically
- Grafana dashboard template included

---

## 5. Customer Onboarding Flow & Documentation Site

### What
A docs site with getting-started guides, API reference, and an in-app onboarding flow.

### Docs Site
- Markdown-based, built with a static generator
- Sections: Getting Started, API Reference, Detectors, Evaluators, Autopilot, Deployment
- Hosted from the same container at `/docs/guide` (or separate deploy)

### In-App Onboarding
- `/api/onboarding/status` — tracks setup progress per tenant
- Checklist: connect traces → view first opportunity → generate recommendations → run replay → deploy
- First-run detection: show setup wizard when no traces exist
- Sample trace generator: `POST /api/onboarding/seed-demo` sends synthetic traces

### Implementation
- Onboarding API with progress tracking
- Demo seed endpoint for instant gratification
- Docs as Markdown files rendered by the dashboard
