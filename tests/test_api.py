"""API contract tests — verify endpoint shapes and status codes."""



class TestHealthEndpoints:
    def test_health(self, app_client):
        resp = app_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_status(self, app_client):
        resp = app_client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces_stored" in data
        assert "detectors" in data
        assert len(data["detectors"]) == 7


class TestTraceEndpoints:
    def test_list_empty(self, app_client):
        resp = app_client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["traces"] == []

    def test_get_nonexistent(self, app_client):
        resp = app_client.get("/api/traces/does-not-exist")
        assert resp.status_code == 404

    def test_ingest_and_query(self, app_client):
        """Full pipeline: ingest OTLP trace → query it back."""
        # Send an OTLP trace
        otlp_payload = {
            "resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "test"}}]},
                "scopeSpans": [{
                    "scope": {},
                    "spans": [{
                        "traceId": "abc123",
                        "spanId": "span1",
                        "name": "chat",
                        "startTimeUnixNano": "1700000000000000000",
                        "endTimeUnixNano": "1700000001000000000",
                        "status": {"code": 1},
                        "attributes": [
                            {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
                            {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 500}},
                            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 100}},
                        ],
                    }],
                }],
            }],
        }
        ingest_resp = app_client.post("/v1/traces", json=otlp_payload)
        assert ingest_resp.status_code == 200

        # Query traces
        list_resp = app_client.get("/api/traces")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["count"] == 1
        assert data["traces"][0]["trace_id"] == "abc123"

        # Get trace detail
        detail_resp = app_client.get("/api/traces/abc123")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["trace_id"] == "abc123"
        assert len(detail["spans"]) == 1
        assert detail["spans"][0]["model_call"]["model"] == "gpt-4o"

        # Get cost breakdown
        cost_resp = app_client.get("/api/traces/abc123/cost")
        assert cost_resp.status_code == 200
        cost = cost_resp.json()
        assert "by_model" in cost
        assert cost["total_cost"] > 0

        # Get waste report
        waste_resp = app_client.get("/api/traces/abc123/waste")
        assert waste_resp.status_code == 200
        waste = waste_resp.json()
        assert "efficiency_score" in waste


class TestDashboardEndpoints:
    def test_opportunities_empty(self, app_client):
        resp = app_client.get("/api/dashboard/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ai_spend_monthly"] == 0.0

    def test_stats_empty(self, app_client):
        resp = app_client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["traces"] == 0

    def test_runs_empty(self, app_client):
        resp = app_client.get("/api/dashboard/runs")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_models(self, app_client):
        resp = app_client.get("/api/dashboard/models")
        assert resp.status_code == 200
        assert "catalog_models" in resp.json()

    def test_tools(self, app_client):
        resp = app_client.get("/api/dashboard/tools")
        assert resp.status_code == 200


class TestRecommendationEndpoints:
    def test_list_empty(self, app_client):
        resp = app_client.get("/api/recommendations")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_stats_empty(self, app_client):
        resp = app_client.get("/api/recommendations/stats")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_nonexistent(self, app_client):
        resp = app_client.get("/api/recommendations/does-not-exist")
        assert resp.status_code == 404

    def test_generate_empty(self, app_client):
        resp = app_client.post("/api/recommendations/generate", json={})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestExperimentEndpoints:
    def test_list_empty(self, app_client):
        resp = app_client.get("/api/experiments")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_get_nonexistent(self, app_client):
        resp = app_client.get("/api/experiments/does-not-exist")
        assert resp.status_code == 404


class TestValidationEndpoints:
    def test_evaluators(self, app_client):
        resp = app_client.get("/api/validation/evaluators")
        assert resp.status_code == 200
        assert len(resp.json()["evaluators"]) == 6

    def test_proofs_empty(self, app_client):
        resp = app_client.get("/api/validation/proofs")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_canaries_empty(self, app_client):
        resp = app_client.get("/api/validation/canaries")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestAutopilotEndpoints:
    def test_status(self, app_client):
        resp = app_client.get("/api/autopilot/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "off"
        assert "constraints" in data

    def test_set_mode(self, app_client):
        resp = app_client.post("/api/autopilot/mode", json={"mode": "suggest"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "suggest"

    def test_routing_stats(self, app_client):
        resp = app_client.get("/api/autopilot/route/stats")
        assert resp.status_code == 200
        assert resp.json()["total_routed"] == 0

    def test_route_request(self, app_client):
        # Need to enable routing in constraints first
        app_client.post("/api/autopilot/mode", json={"mode": "suggest"})

        resp = app_client.post("/api/autopilot/route", json={
            "original_model": "gpt-4o",
            "input_tokens": 500,
            "output_tokens_estimate": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "selected_model" in data
        assert data["complexity"] == "low"

    def test_verify_request(self, app_client):
        resp = app_client.post("/api/autopilot/verify", json={
            "risk_score": 0.3,
            "model_confidence": 0.95,
        })
        assert resp.status_code == 200
        assert resp.json()["should_verify"] is False

    def test_verify_high_risk(self, app_client):
        resp = app_client.post("/api/autopilot/verify", json={
            "risk_score": 0.9,
            "model_confidence": 0.5,
        })
        assert resp.status_code == 200
        assert resp.json()["should_verify"] is True

    def test_recover_request(self, app_client):
        resp = app_client.post("/api/autopilot/recover", json={
            "failure_type": "infrastructure",
            "failed_tool": "api_call",
            "retry_count": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["strategy"] == "retry_same"

    def test_decisions_empty(self, app_client):
        resp = app_client.get("/api/autopilot/decisions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_policies_empty(self, app_client):
        resp = app_client.get("/api/autopilot/policies")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_recovery_rules(self, app_client):
        resp = app_client.get("/api/autopilot/recover/rules")
        assert resp.status_code == 200
        assert resp.json()["count"] == 3  # 3 default rules
