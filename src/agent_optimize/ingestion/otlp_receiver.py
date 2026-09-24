"""OTLP HTTP receiver: authenticates through middleware and stamps tenant ownership."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Request, Response

from agent_optimize.ingestion.normalizer import TraceNormalizer

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["otlp"])


def _extract_spans_from_otlp(payload: dict[str, Any]) -> list[dict[str, Any]]:
    all_spans: list[dict[str, Any]] = []
    for resource_span in payload.get("resourceSpans", []):
        resource_attrs = _flatten_attrs(resource_span.get("resource", {}).get("attributes", []))
        for scope_span in resource_span.get("scopeSpans", []):
            scope_attrs = _flatten_attrs(scope_span.get("scope", {}).get("attributes", []))
            for span in scope_span.get("spans", []):
                span_attrs = _flatten_attrs(span.get("attributes", []))
                all_spans.append({
                    "traceId": span.get("traceId", ""),
                    "spanId": span.get("spanId", str(uuid.uuid4())),
                    "parentSpanId": span.get("parentSpanId"),
                    "name": span.get("name", ""),
                    "startTimeUnixNano": _parse_nano(span.get("startTimeUnixNano", 0)),
                    "endTimeUnixNano": _parse_nano(span.get("endTimeUnixNano", 0)),
                    "status": span.get("status", {}),
                    "attributes": {**resource_attrs, **scope_attrs, **span_attrs},
                })
    return all_spans


def _flatten_attrs(attrs: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(attrs, dict):
        return attrs
    result: dict[str, Any] = {}
    for attr in attrs:
        key, value_obj = attr.get("key", ""), attr.get("value", {})
        if isinstance(value_obj, dict):
            for vtype in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if vtype in value_obj:
                    result[key] = value_obj[vtype]
                    break
            else:
                if "arrayValue" in value_obj:
                    result[key] = [v.get("stringValue", v) for v in value_obj["arrayValue"].get("values", [])]
                else:
                    result[key] = value_obj
        else:
            result[key] = value_obj
    return result


def _parse_nano(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


_normalizer = TraceNormalizer(capture_content=False)
_on_trace_callback: Any = None


def set_trace_callback(callback: Any) -> None:
    global _on_trace_callback
    _on_trace_callback = callback


def set_normalizer(normalizer: TraceNormalizer) -> None:
    global _normalizer
    _normalizer = normalizer


@router.post("/traces")
async def receive_traces(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        logger.warning("otlp_receiver.invalid_json")
        return Response(status_code=400, content='{"error":"invalid JSON"}')
    if not isinstance(payload, dict):
        return Response(status_code=400, content='{"error":"invalid JSON body"}')
    raw_spans = _extract_spans_from_otlp(payload)
    if not raw_spans:
        return Response(status_code=200, content="{}")
    traces_map: dict[str, list[dict[str, Any]]] = {}
    for span in raw_spans:
        traces_map.setdefault(span.get("traceId", "unknown"), []).append(span)

    tenant_id = getattr(request.state, "tenant_id", None)
    authenticated = getattr(request.state, "authenticated", False)
    ingested_count = 0
    for trace_id, spans in traces_map.items():
        trace = _normalizer.normalize_trace(spans)
        if trace and authenticated:
            trace.tenant_id = tenant_id
        if trace and _on_trace_callback:
            try:
                await _on_trace_callback(trace)
            except Exception:
                logger.exception("otlp_receiver.callback_error", trace_id=trace_id)
        if trace:
            ingested_count += 1
    logger.info("otlp_receiver.ingested", spans=len(raw_spans), traces=ingested_count)
    return Response(status_code=200, content="{}")
