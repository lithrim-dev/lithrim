"""OTEL-INGEST-1 through the front door: an OTLP trace export previews as native cases (no mapper),
commits verbatim with the span record intact, and a KPI contract then blocks a span through the
floor with no judge involved."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lithrim_bench.harness.audit import Actor

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

from tests.verification.test_otel_ingest import EVENTED, HTTP, LLM, NO_OUTPUT, export  # noqa: E402


class _NeverConstructed:
    def __init__(self, *_a, **_k):
        raise AssertionError("an OTel export must never touch the JUTE mapper")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", _NeverConstructed)
    from lithrim_bench.harness import workspace as ws_mod

    ws = SimpleNamespace(
        name="otel_test",
        pack="_core",
        out_dir=tmp_path / "ws" / "out",
        collections_db=tmp_path / "ws" / "collections.sqlite",
        config_db=tmp_path / "ws" / "config.sqlite",
        ontology_dir=tmp_path / "ws" / "ontology",
        dir=tmp_path / "ws",
    )
    monkeypatch.setattr(ws_mod, "get_active_workspace", lambda *a, **k: ws)
    ctx = bff._build_tool_context(
        req_agent="ws0_default",
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )
    return ctx, ws


def test_preview_and_commit_take_the_native_path_with_the_span_record(env):
    ctx, ws = env
    raw = json.dumps(export([LLM, EVENTED, NO_OUTPUT, HTTP]))
    prev = ctx.ingest_preview(raw=raw, fmt="auto", filename="traces.json", agent="ws0_default")
    assert prev["fmt"] == "otel" and prev["native"] is True and prev["count"] == 2
    assert prev["columns"] == ["spans=4", "llm_spans=3", "cases=2", "skipped_no_output=1"]
    assert prev["sample_cases"][0]["source_kind"] == "record"
    assert not (ws.out_dir / "ingested_cases.jsonl").exists(), "preview writes nothing"
    res = ctx.ingest_commit(
        approved_template=None, raw=raw, fmt="auto", filename="traces.json", agent="ws0_default"
    )
    assert res["count"] == 2 and res["native"] is True
    rows = [
        json.loads(line) for line in (ws.out_dir / "ingested_cases.jsonl").read_text().splitlines()
    ]
    by_id = {r["case_id"]: r for r in rows}
    rec = json.loads(by_id["otel_0123456789abcdef_aa11"]["transcript"])
    assert rec["gen_ai"]["usage"]["output_tokens"] == 260 and rec["service"] == "checkout-assistant"
    assert (
        by_id["otel_0123456789abcdef_bb22"]["artifacts"][0]["content"]
        == "assistant: Refund issued."
    )


def test_a_kpi_contract_blocks_a_span_from_the_export_before_any_judge(env):
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.ontology import from_dict

    ctx, ws = env
    ctx.ingest_commit(
        approved_template=None,
        raw=json.dumps(export([LLM, EVENTED])),
        fmt="auto",
        filename="t.json",
        agent="ws0_default",
    )
    rows = {
        json.loads(ln)["case_id"]: json.loads(ln)
        for ln in (ws.out_dir / "ingested_cases.jsonl").read_text().splitlines()
    }
    ont = from_dict(
        {
            "ontology_version": "otel_kpi_v1",
            "domain": "generic",
            "questions": [],
            "flags": [
                {
                    "flag": "KPI_BREACH",
                    "category": "kpi",
                    "definition": "",
                    "when_to_use": "",
                    "when_NOT_to_use": "",
                    "owner_roles": ["reviewer"],
                    "tier": "TIER_1",
                    "gradeable": True,
                }
            ],
            "verification_contracts": [
                {
                    "flag_code": "KPI_BREACH",
                    "question": "Did the call succeed?",
                    "contract_type": "field_in_set",
                    "version": "kpi/1",
                    "params": {
                        "field": "status.code",
                        "allowed": ["OK"],
                        "inject_flag_code": "KPI_BREACH",
                        "inject_severity": "HIGH",
                        "artifact_kind": "llm_response",
                    },
                },
                {
                    "flag_code": "KPI_BREACH",
                    "question": "Under the token budget?",
                    "contract_type": "kpi_threshold",
                    "version": "kpi/1",
                    "params": {
                        "field": "gen_ai.usage.output_tokens",
                        "op": "<=",
                        "value": 100,
                        "inject_flag_code": "KPI_BREACH",
                        "inject_severity": "HIGH",
                        "artifact_kind": "llm_response",
                    },
                },
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
                "block_at_or_above": 0.5,
                "warn_above": 0.0,
            },
        }
    )
    council = {
        "verdict": "PASS",
        "findings": [],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "PASS"}]},
    }
    ok_span = ground(
        council, rows["otel_0123456789abcdef_aa11"], ontology=ont
    )  # OK status, 260 tokens
    err_span = ground(
        council, rows["otel_0123456789abcdef_bb22"], ontology=ont
    )  # ERROR status, 12 tokens
    assert ok_span.verdict == "BLOCK" and [
        b["decl"].contract_type for b in ok_span.floor_blocks if b["injected_finding"]
    ] == ["kpi_threshold"]
    assert err_span.verdict == "BLOCK" and [
        b["decl"].contract_type for b in err_span.floor_blocks if b["injected_finding"]
    ] == ["field_in_set"]
    assert (
        ok_span.floor_blocks[0]["result"].evidence["actual"] == 260
        if ok_span.floor_blocks[0]["injected_finding"]
        else True
    )
