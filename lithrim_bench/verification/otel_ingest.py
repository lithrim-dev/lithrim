"""OTEL-INGEST-1: an OpenTelemetry trace export (OTLP/JSON) as eval cases.

One case per LLM span: the span's input (the prompt, the messages) is the transcript, its output
(the completion, the choice) is the graded artifact, and the span's own attributes, resource
attributes, duration and status are the STRUCTURED RECORD the deterministic floor checks against
(``source_kind: record``, the record as JSON at ``transcript``), so a KPI contract (latency,
tokens, status, model) can be proven before any judge runs.

Which spans are LLM spans: any span carrying a ``gen_ai.*`` attribute (the OpenTelemetry GenAI
semantic conventions), an OpenInference ``openinference.span.kind = LLM``, or ``llm.*``
attributes. Prompt and completion resolve from the conventions in order: ``gen_ai.prompt`` /
``gen_ai.completion``, ``gen_ai.input.messages`` / ``gen_ai.output.messages``, OpenInference
``input.value`` / ``output.value``, ``llm.prompts`` / ``llm.completions``, then the span events
(``gen_ai.content.prompt`` / ``gen_ai.content.completion``, ``gen_ai.user.message`` /
``gen_ai.choice`` and kin). A span with no output is not a case (nothing to grade) and is
counted, never fabricated. Dotted attribute keys nest (``gen_ai.usage.output_tokens`` becomes
``record["gen_ai"]["usage"]["output_tokens"]``) so a KPI field is a dotted path. Ingested
traces are UNLABELED by construction (``expected_safety_flags: []``, ``injection_recipe: null``).
Pure stdlib, deterministic.
"""

from __future__ import annotations

import json
from typing import Any

_PROMPT_KEYS = ("gen_ai.prompt", "gen_ai.input.messages", "input.value", "llm.prompts", "gen_ai.request.messages")
_COMPLETION_KEYS = ("gen_ai.completion", "gen_ai.output.messages", "output.value", "llm.completions", "gen_ai.response.messages")
_PROMPT_EVENTS = ("gen_ai.content.prompt", "gen_ai.system.message", "gen_ai.user.message")
_COMPLETION_EVENTS = ("gen_ai.content.completion", "gen_ai.choice", "gen_ai.assistant.message")
_STATUS = {0: "UNSET", 1: "OK", 2: "ERROR", "STATUS_CODE_UNSET": "UNSET", "STATUS_CODE_OK": "OK", "STATUS_CODE_ERROR": "ERROR"}


def is_otlp_trace(obj: Any) -> bool:
    """An OTLP/JSON trace export: ``{"resourceSpans": [...]}`` (also the ``resource_spans``
    snake-case spelling some exporters write)."""
    return isinstance(obj, dict) and isinstance(obj.get("resourceSpans", obj.get("resource_spans")), list)


def _any_value(v: Any) -> Any:
    """An OTLP ``AnyValue`` as a plain Python value (intValue rides as a string in JSON)."""
    if not isinstance(v, dict):
        return v
    if "stringValue" in v:
        return v["stringValue"]
    if "intValue" in v:
        try:
            return int(v["intValue"])
        except (TypeError, ValueError):
            return v["intValue"]
    if "doubleValue" in v:
        return v["doubleValue"]
    if "boolValue" in v:
        return bool(v["boolValue"])
    if "arrayValue" in v:
        return [_any_value(x) for x in (v["arrayValue"] or {}).get("values", [])]
    if "kvlistValue" in v:
        return _attributes((v["kvlistValue"] or {}).get("values", []))
    if "bytesValue" in v:
        return v["bytesValue"]
    return v


def _attributes(items: Any) -> dict:
    """OTLP ``[{key, value}]`` (or an already-flat dict) as a flat ``{key: value}`` dict."""
    if isinstance(items, dict):
        return {str(k): _any_value(v) for k, v in items.items()}
    out: dict = {}
    for kv in items or []:
        if isinstance(kv, dict) and "key" in kv:
            out[str(kv["key"])] = _any_value(kv.get("value"))
    return out


def nest(flat: dict) -> dict:
    """Dotted keys nested (``a.b.c`` -> ``{"a": {"b": {"c": v}}}``); a key that would need to be
    both a leaf and a branch keeps its flat spelling instead (never silently overwritten)."""
    out: dict = {}
    for key in sorted(flat, key=lambda k: (k.count("."), k)):
        parts = str(key).split(".")
        cur = out
        ok = True
        for part in parts[:-1]:
            nxt = cur.get(part)
            if nxt is None:
                nxt = cur[part] = {}
            elif not isinstance(nxt, dict):
                ok = False
                break
            cur = nxt
        if ok and not isinstance(cur.get(parts[-1]), dict):
            cur[parts[-1]] = flat[key]
        else:
            out[str(key)] = flat[key]
    return out


def _text(value: Any) -> str:
    """Prompt/completion content as text: a string as is; a list of messages as ``role: content``
    lines; anything else as compact JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return _text(json.loads(s))
            except (TypeError, ValueError):
                return s
        return s
    if isinstance(value, list):
        lines = []
        for m in value:
            if isinstance(m, dict):
                role = m.get("role") or m.get("author") or ""
                content = m.get("content")
                if content is None and isinstance(m.get("message"), dict):
                    role = role or m["message"].get("role", "")
                    content = m["message"].get("content")
                if isinstance(content, list):
                    content = " ".join(
                        str(c.get("text") if isinstance(c, dict) else c) for c in content
                    )
                lines.append(f"{role}: {content}" if role else str(content))
            else:
                lines.append(str(m))
        return "\n".join(x for x in lines if x)
    if isinstance(value, dict):
        if "content" in value:
            return _text([value])
        return json.dumps(value, sort_keys=True)
    return str(value)


def _first(attrs: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if attrs.get(k) not in (None, ""):
            return attrs[k]
    return None


def _from_events(events: list[dict], names: tuple[str, ...]) -> str:
    parts = []
    for ev in events:
        if ev.get("name") not in names:
            continue
        a = ev.get("attributes") or {}
        val = _first(a, ("gen_ai.completion", "gen_ai.prompt", "message", "content", "gen_ai.event.content"))
        if val is None and a:
            val = a
        if val is not None:
            parts.append(_text(val))
    return "\n".join(p for p in parts if p)


def _is_llm_span(attrs: dict) -> bool:
    if any(str(k).startswith(("gen_ai.", "llm.")) for k in attrs):
        return True
    return str(attrs.get("openinference.span.kind") or "").upper() == "LLM"


def _ns(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def spans_from_otlp(obj: dict) -> list[dict]:
    """Every span in the export as a flat dict: ids, name, kind, times, status, the span's
    attributes (flat), the resource attributes (flat), the scope name, and the events."""
    out: list[dict] = []
    for rs in obj.get("resourceSpans", obj.get("resource_spans")) or []:
        resource = _attributes(((rs.get("resource") or {}).get("attributes")) or [])
        for ss in rs.get("scopeSpans", rs.get("scope_spans", rs.get("instrumentationLibrarySpans"))) or []:
            scope = (ss.get("scope") or ss.get("instrumentationLibrary") or {}).get("name")
            for sp in ss.get("spans") or []:
                attrs = _attributes(sp.get("attributes") or [])
                events = [
                    {"name": ev.get("name"), "attributes": _attributes(ev.get("attributes") or []), "time_unix_nano": ev.get("timeUnixNano")}
                    for ev in (sp.get("events") or [])
                    if isinstance(ev, dict)
                ]
                start, end = _ns(sp.get("startTimeUnixNano")), _ns(sp.get("endTimeUnixNano"))
                status = sp.get("status") or {}
                code = status.get("code")
                out.append(
                    {
                        "trace_id": str(sp.get("traceId") or sp.get("trace_id") or ""),
                        "span_id": str(sp.get("spanId") or sp.get("span_id") or ""),
                        "parent_span_id": str(sp.get("parentSpanId") or sp.get("parent_span_id") or ""),
                        "name": sp.get("name"),
                        "kind": sp.get("kind"),
                        "start_time_unix_nano": start,
                        "end_time_unix_nano": end,
                        "duration_ms": (end - start) / 1e6 if start is not None and end is not None else None,
                        "status": {"code": _STATUS.get(code, code if code is not None else "UNSET"), "message": status.get("message")},
                        "attributes": attrs,
                        "resource": resource,
                        "scope": scope,
                        "events": events,
                    }
                )
    return out


def cases_from_otlp(obj: dict) -> dict:
    """The export as native eval cases (one per LLM span with an output) plus the honest counts:
    ``{"cases": [...], "spans": n, "llm_spans": n, "skipped_no_output": n}``."""
    spans = spans_from_otlp(obj)
    cases: list[dict] = []
    llm = skipped = 0
    for sp in spans:
        attrs = sp["attributes"]
        if not _is_llm_span(attrs):
            continue
        llm += 1
        prompt = _text(_first(attrs, _PROMPT_KEYS)) or _from_events(sp["events"], _PROMPT_EVENTS)
        completion = _text(_first(attrs, _COMPLETION_KEYS)) or _from_events(sp["events"], _COMPLETION_EVENTS)
        if not completion.strip():
            skipped += 1
            continue
        model = _first(attrs, ("gen_ai.response.model", "gen_ai.request.model", "llm.model_name", "llm.model"))
        service = sp["resource"].get("service.name")
        record = {
            "trace_id": sp["trace_id"],
            "span_id": sp["span_id"],
            "parent_span_id": sp["parent_span_id"] or None,
            "name": sp["name"],
            "kind": sp["kind"],
            "service": service,
            "scope": sp["scope"],
            "duration_ms": sp["duration_ms"],
            "status": sp["status"],
            "input": prompt,
            "output": completion,
            "resource": nest(sp["resource"]),
            **nest(attrs),
        }
        record_json = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        case_id = f"otel_{sp['trace_id'][:16] or 'trace'}_{sp['span_id'] or len(cases)}"
        cases.append(
            {
                "case_id": case_id,
                "artifacts": [
                    {
                        "type": "llm_response",
                        "content": completion,
                        "metadata": {"model": model, "finish_reason": _first(attrs, ("gen_ai.response.finish_reasons", "llm.finish_reason")), "source": service},
                    }
                ],
                "transcript": record_json,
                "context": record_json,
                "context_kind": "otel_span",
                "source_kind": "record",
                "expected_safety_flags": [],
                "injection_recipe": None,
                "ground_truth_basis": None,
                "model": model,
                "source": service,
                "otel": {"trace_id": sp["trace_id"], "span_id": sp["span_id"], "service": service, "name": sp["name"], "model": model},
            }
        )
    return {"cases": cases, "spans": len(spans), "llm_spans": llm, "skipped_no_output": skipped}
