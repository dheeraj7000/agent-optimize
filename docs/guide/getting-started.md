# Getting Started with AgentOptimize

## 1. Install and run

```bash
pip install -e ".[dev]"
agent-optimize serve
```

Open http://localhost:8080 to see the dashboard.

## 2. Seed demo data (optional)

If you don't have traces yet, seed some demo data:

```bash
curl -X POST http://localhost:8080/api/onboarding/seed-demo \
  -H "Content-Type: application/json" \
  -d '{"count": 30}'
```

## 3. Connect your agent traces

Point your OpenTelemetry SDK or collector at:

```
POST http://localhost:8080/v1/traces
```

Any OTel-compatible agent framework works: OpenAI Agents, LangGraph, CrewAI, or custom Python.

### Example: Python OTel SDK

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:8080/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
```

### Example: OTel Collector config

```yaml
exporters:
  otlphttp:
    endpoint: "http://localhost:8080"
```

## 4. View opportunities

Open the dashboard at http://localhost:8080. The Overview page shows:
- Total AI spend
- Identified waste
- Optimization potential
- Ranked opportunities by category

## 5. Generate recommendations

Click "Generate" on the Recommendations page, or:

```bash
curl -X POST http://localhost:8080/api/recommendations/generate \
  -H "Content-Type: application/json" \
  -d '{}'
```

Each recommendation includes impact projections, confidence scores, evidence, and action items.

## 6. Review and act

1. **Accept** recommendations you want to pursue
2. **Run a replay experiment** to validate savings
3. **Deploy** the change
4. **Verify** that post-deploy metrics confirm savings
5. **Enable autopilot** (suggest mode first) for automated routing decisions

## 7. Enable autopilot

```bash
# Start with "suggest" mode (recommendations only, no auto-apply)
curl -X POST http://localhost:8080/api/autopilot/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "suggest"}'
```

## 8. Set up webhooks (optional)

Get notified on Slack or PagerDuty when the system detects regressions:

```bash
curl -X POST http://localhost:8080/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/services/...",
    "events": ["canary.regressed", "autopilot.decision.blocked"],
    "name": "Slack alerts"
  }'
```

## 9. Production deployment

```bash
# Fly.io (~$2/month)
fly launch --copy-config && fly deploy

# Or self-hosted Docker
docker build -f Dockerfile.production -t agentoptimize .
docker run -d -p 8080:8080 \
  -v ./data:/data \
  -e AGENTOPTIMIZE_DB_PATH=/data/agentoptimize.db \
  agentoptimize
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTOPTIMIZE_DB_PATH` | (none) | SQLite path. Omit for in-memory. |
| `AGENTOPTIMIZE_DB_BACKEND` | `sqlite` | `sqlite`, `postgres` |
| `AGENTOPTIMIZE_DB_URL` | (none) | Postgres connection URL |
| `AGENTOPTIMIZE_API_KEY_REQUIRED` | `false` | Enable API key auth |
| `AGENTOPTIMIZE_LOG_FORMAT` | `console` | `console` or `json` |
| `AGENTOPTIMIZE_OIDC_ISSUER` | (none) | OIDC provider issuer URL |
| `AGENTOPTIMIZE_OIDC_CLIENT_ID` | (none) | OIDC client ID |
