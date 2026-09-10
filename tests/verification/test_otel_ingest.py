"""OTEL-INGEST-1: an OTLP/JSON trace export becomes eval cases, one per LLM span with an output,
with the span's attributes as the structured record the floor checks. Pure stdlib, offline."""

from __future__ import annotations

import json

import pytest

from lithrim_bench.verification.ingest_decode import decode_records
from lithrim_bench.verification.otel_ingest import (
    cases_from_otlp,
    is_otlp_trace,
    nest,
    spans_from_otlp,
)


def _kv(key, value):
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    if isinstance(value, list):
        return {
            "key": key,
            "value": {"arrayValue": {"values": [{"stringValue": str(v)} for v in value]}},
        }
    return {"key": key, "value": {"stringValue": str(value)}}


def _span(
    span_id,
    name,
    attrs,
    *,
    events=(),
    status=1,
    start=1_000_000_000,
    end=1_000_000_000 + 1_840_500_000,
    trace="0123456789abcdef0123456789abcdef",
):
    return {
        "traceId": trace,
        "spanId": span_id,
        "parentSpanId": "",
        "name": name,
        "kind": 3,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(end),
        "attributes": [_kv(k, v) for k, v in attrs.items()],
        "events": [
            {"name": n, "timeUnixNano": "1", "attributes": [_kv(k, v) for k, v in a.items()]}
            for n, a in events
        ],
        "status": {"code": status},
    }


def export(spans):
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _kv("service.name", "checkout-assistant"),
                        _kv("deployment.environment", "prod"),
                    ]
                },
                "scopeSpans": [{"scope": {"name": "openai-instrumentation"}, "spans": spans}],
            }
        ]
    }


LLM = _span(
    "aa11",
    "chat gpt-4.1",
    {
        "gen_ai.system": "openai",
        "gen_ai.request.model": "gpt-4.1",
        "gen_ai.response.model": "gpt-4.1-2025-04-14",
        "gen_ai.usage.input_tokens": 912,
        "gen_ai.usage.output_tokens": 260,
        "gen_ai.prompt": json.dumps(
            [
                {"role": "system", "content": "You help with orders."},
                {"role": "user", "content": "Where is my order?"},
            ]
        ),
        "gen_ai.completion": json.dumps(
            [{"role": "assistant", "content": "Your order ships tomorrow."}]
        ),
        "gen_ai.response.finish_reasons": ["stop"],
    },
)
EVENTED = _span(
    "bb22",
    "chat gpt-4.1",
    {
        "gen_ai.system": "openai",
        "gen_ai.request.model": "gpt-4.1",
        "gen_ai.usage.output_tokens": 12,
    },
    events=(
        ("gen_ai.user.message", {"content": "Refund please"}),
        (
            "gen_ai.choice",
            {
                "message": json.dumps({"role": "assistant", "content": "Refund issued."}),
                "finish_reason": "stop",
            },
        ),
    ),
    status=2,
)
NO_OUTPUT = _span("cc33", "chat gpt-4.1", {"gen_ai.system": "openai", "gen_ai.prompt": "hello"})
HTTP = _span("dd44", "GET /orders", {"http.method": "GET", "http.status_code": 200})


def test_shape_detection_and_span_flattening():
    assert (
        is_otlp_trace(export([HTTP])) and not is_otlp_trace({"rows": []}) and not is_otlp_trace([1])
    )
    spans = spans_from_otlp(export([LLM, HTTP]))
    assert [s["span_id"] for s in spans] == ["aa11", "dd44"]
    s = spans[0]
    assert (
        s["attributes"]["gen_ai.usage.output_tokens"] == 260
        and s["resource"]["service.name"] == "checkout-assistant"
    )
    assert (
        s["duration_ms"] == pytest.approx(1840.5)
        and s["status"]["code"] == "OK"
        and s["scope"] == "openai-instrumentation"
    )


def test_nest_turns_dotted_keys_into_paths_and_keeps_conflicts_flat():
    assert nest(
        {"gen_ai.usage.input_tokens": 1, "gen_ai.usage.output_tokens": 2, "http.method": "GET"}
    ) == {"gen_ai": {"usage": {"input_tokens": 1, "output_tokens": 2}}, "http": {"method": "GET"}}
    out = nest({"a": 1, "a.b": 2})
    assert out["a"] == 1 and out["a.b"] == 2


def test_one_case_per_llm_span_with_an_output_and_the_span_as_the_record():
    res = cases_from_otlp(export([LLM, EVENTED, NO_OUTPUT, HTTP]))
    assert (res["spans"], res["llm_spans"], res["skipped_no_output"], len(res["cases"])) == (
        4,
        3,
        1,
        2,
    )
    c = res["cases"][0]
    assert c["case_id"] == "otel_0123456789abcdef_aa11" and c["source_kind"] == "record"
    assert c["artifacts"][0]["content"] == "assistant: Your order ships tomorrow."
    assert (
        c["artifacts"][0]["metadata"]["model"] == "gpt-4.1-2025-04-14"
        and c["model"] == "gpt-4.1-2025-04-14"
    )
    rec = json.loads(c["transcript"])
    assert rec["gen_ai"]["usage"]["output_tokens"] == 260 and rec["duration_ms"] == pytest.approx(
        1840.5
    )
    assert (
        rec["status"]["code"] == "OK"
        and rec["service"] == "checkout-assistant"
        and rec["resource"]["deployment"]["environment"] == "prod"
    )
    assert (
        rec["input"].startswith("system: You help with orders.")
        and "user: Where is my order?" in rec["input"]
    )
    assert (
        c["expected_safety_flags"] == []
        and c["injection_recipe"] is None
        and c["otel"]["span_id"] == "aa11"
    )
    e = res["cases"][1]
    assert (
        e["artifacts"][0]["content"] == "assistant: Refund issued."
        and json.loads(e["transcript"])["status"]["code"] == "ERROR"
    )
    assert json.loads(e["transcript"])["input"] == "Refund please"


def test_the_decode_shim_recognises_a_trace_export_by_shape_and_reports_the_counts():
    raw = json.dumps(export([LLM, NO_OUTPUT, HTTP]))
    dec = decode_records(raw, fmt="auto", filename="traces.json")
    assert dec.fmt == "otel" and dec.expected_count == 1 and len(dec.sample) == 1
    assert dec.columns == ["spans=3", "llm_spans=2", "cases=1", "skipped_no_output=1"]
    assert decode_records(raw, fmt="otel").fmt == "otel"
    with pytest.raises(ValueError, match="none with an output"):
        decode_records(json.dumps(export([NO_OUTPUT, HTTP])), fmt="auto")
    with pytest.raises(ValueError, match="not an OTLP"):
        decode_records(json.dumps({"rows": [{"a": 1}]}), fmt="otel")
    plain = decode_records(json.dumps([{"case_id": "x"}]), fmt="auto")
    assert plain.fmt == "json"
