"""KPI-FLOOR-1: deterministic record-field checks a user pins against their own KPIs before any
judge runs — ``kpi_threshold`` (a numeric field vs a bound or a range) and ``field_in_set`` (a
field vs an allowed set). Record-field checks, so the tri-state is: the comparison holds →
CONFORMS (a recorded floor pass); it fails → VIOLATION (the floor injects the pinned flag, the
expected and actual values named); the field absent, non-numeric, no record, or a prose source
→ INCONCLUSIVE (unknown is never a violation, and never a silent pass). Pure stdlib, offline."""

from __future__ import annotations

import json

import pytest

from lithrim_bench.harness.grounding import floor_executors, ground, validate_contract_params
from lithrim_bench.harness.ontology import VerificationContractDecl, from_dict
from lithrim_bench.verification import (
    STRUCTURAL_CONFORMANCE,
    TOOL_FIELD_IN_SET,
    TOOL_KPI_THRESHOLD,
    Claim,
    FieldInSetTool,
    KpiThresholdTool,
    VerificationSpec,
)

_RECORD = {
    "service": "checkout-assistant",
    "duration_ms": 1840.5,
    "status": {"code": "OK"},
    "gen_ai": {
        "usage": {"input_tokens": 912, "output_tokens": 260},
        "request": {"model": "gpt-4.1"},
    },
    "note": "n/a",
}


def _case(record=_RECORD, *, source_kind="record", artifact="The order ships tomorrow."):
    return {
        "case_id": "c1",
        "source_kind": source_kind,
        "transcript": json.dumps(record),
        "artifacts": [{"type": "llm_response", "content": artifact}],
    }


def _spec(tool, reference, version="kpi/test-1"):
    return VerificationSpec(
        tool=tool, applies_to_flags=("KPI_BREACH",), locus="", reference=reference, version=version
    )


def _claim(case):
    return Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code="KPI_BREACH",
        subject=case["artifacts"][0]["content"],
        locus="",
        source=case,
    )


# ── registration ──────────────────────────────────────────────────────────────
def test_both_floors_are_core_and_lift_only_their_knobs():
    fe = floor_executors("_core")
    assert fe["kpi_threshold"].tool_factory(None).name == TOOL_KPI_THRESHOLD
    assert fe["field_in_set"].tool_factory(None).name == TOOL_FIELD_IN_SET
    ref = fe["kpi_threshold"].reference_builder(
        {"field": "duration_ms", "op": "<=", "value": 2000, "inject_flag_code": "X", "junk": 1}
    )
    assert ref == {"field": "duration_ms", "op": "<=", "value": 2000}
    ref = fe["field_in_set"].reference_builder(
        {"field": "status.code", "allowed": ["OK"], "mode": "in"}
    )
    assert ref == {"field": "status.code", "allowed": ["OK"], "mode": "in"}


# ── kpi_threshold ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "ref, conforms",
    [
        ({"field": "duration_ms", "op": "<=", "value": 2000}, True),
        ({"field": "duration_ms", "op": "<", "value": 1000}, False),
        ({"field": "gen_ai.usage.output_tokens", "op": ">=", "value": 200}, True),
        ({"field": "gen_ai.usage.output_tokens", "op": "between", "min": 300, "max": 500}, False),
        ({"field": "gen_ai.usage.input_tokens", "op": "==", "value": 912}, True),
        ({"field": "gen_ai.usage.input_tokens", "op": "!=", "value": 912}, False),
    ],
)
def test_threshold_decides_on_the_record_field(ref, conforms):
    r = KpiThresholdTool().verify(_claim(_case()), _spec(TOOL_KPI_THRESHOLD, ref))
    assert r.conforms is conforms
    assert r.manifest["deterministic"] is True and r.evidence["field"] == ref["field"]
    if conforms is False:
        assert "actual" in r.evidence and r.evidence["missing"]


def test_threshold_is_unknown_when_it_cannot_decide():
    absent = KpiThresholdTool().verify(
        _claim(_case()),
        _spec(TOOL_KPI_THRESHOLD, {"field": "gen_ai.usage.total_tokens", "op": "<=", "value": 1}),
    )
    assert absent.conforms is None and "absent" in absent.evidence["reason"]
    text = KpiThresholdTool().verify(
        _claim(_case()), _spec(TOOL_KPI_THRESHOLD, {"field": "note", "op": "<=", "value": 1})
    )
    assert text.conforms is None and "not numeric" in text.evidence["reason"]
    prose = KpiThresholdTool().verify(
        _claim(_case(source_kind="prose")),
        _spec(TOOL_KPI_THRESHOLD, {"field": "duration_ms", "op": "<=", "value": 1}),
    )
    assert prose.conforms is None and "prose" in prose.evidence["reason"]
    not_json = _case()
    not_json["transcript"] = "just words"
    assert (
        KpiThresholdTool()
        .verify(_claim(not_json), _spec(TOOL_KPI_THRESHOLD, {"field": "x", "op": "<", "value": 1}))
        .conforms
        is None
    )


def test_threshold_can_read_a_json_artifact_instead_of_the_source():
    case = _case(artifact=json.dumps({"score": 0.42}))
    ref = {"field": "score", "op": ">=", "value": 0.5, "target": "artifact"}
    r = KpiThresholdTool().verify(_claim(case), _spec(TOOL_KPI_THRESHOLD, ref))
    assert r.conforms is False and r.evidence["actual"] == 0.42


def test_threshold_refuses_a_malformed_pin_at_author_time():
    with pytest.raises(ValueError):
        KpiThresholdTool.expected({"op": "~", "value": 1})
    with pytest.raises(ValueError):
        KpiThresholdTool.expected({"op": "between", "min": 5, "max": 1})
    with pytest.raises(ValueError):
        KpiThresholdTool.expected({"op": "<=", "value": "many"})
    with pytest.raises(ValueError):  # the spec's required keys
        _spec(TOOL_KPI_THRESHOLD, {"field": "x"})


# ── field_in_set ──────────────────────────────────────────────────────────────
def test_field_in_set_decides_case_insensitively_and_both_ways():
    ok = FieldInSetTool().verify(
        _claim(_case()),
        _spec(TOOL_FIELD_IN_SET, {"field": "status.code", "allowed": ["ok", "UNSET"]}),
    )
    assert ok.conforms is True
    bad = FieldInSetTool().verify(
        _claim(_case()),
        _spec(TOOL_FIELD_IN_SET, {"field": "gen_ai.request.model", "allowed": ["gpt-4o"]}),
    )
    assert bad.conforms is False and bad.evidence["actual"] == "gpt-4.1"
    strict = FieldInSetTool().verify(
        _claim(_case()),
        _spec(
            TOOL_FIELD_IN_SET,
            {"field": "status.code", "allowed": ["ok"], "case_insensitive": False},
        ),
    )
    assert strict.conforms is False
    not_in = FieldInSetTool().verify(
        _claim(_case()),
        _spec(TOOL_FIELD_IN_SET, {"field": "status.code", "allowed": ["ERROR"], "mode": "not_in"}),
    )
    assert not_in.conforms is True
    absent = FieldInSetTool().verify(
        _claim(_case()), _spec(TOOL_FIELD_IN_SET, {"field": "status.detail", "allowed": ["x"]})
    )
    assert absent.conforms is None
    with pytest.raises(ValueError):
        FieldInSetTool.allowed({"field": "x", "allowed": []})


# ── through ground(): the floor injects, passes, or abstains ─────────────────
_SEV = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}


def _flag(code):
    return {
        "flag": code,
        "category": "kpi",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
        "owner_roles": ["reviewer"],
        "tier": "TIER_1",
        "gradeable": True,
    }


def _ont(contract_type, params):
    return from_dict(
        {
            "ontology_version": "kpi_test_v1",
            "domain": "generic",
            "flags": [_flag("KPI_BREACH")],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "KPI_BREACH",
                    "question": "Does the span meet the KPI?",
                    "contract_type": contract_type,
                    "version": "kpi/test-1",
                    "params": {
                        "inject_flag_code": "KPI_BREACH",
                        "inject_severity": "HIGH",
                        "artifact_kind": "llm_response",
                        **params,
                    },
                }
            ],
            "severity_map": _SEV,
        }
    )


def _council_pass():
    return {
        "verdict": "PASS",
        "findings": [],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "PASS"}]},
    }


def test_ground_blocks_a_latency_kpi_breach_the_judges_never_saw():
    g = ground(
        _council_pass(),
        _case(),
        ontology=_ont("kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 1000}),
    )
    assert g.verdict == "BLOCK" and g.verdict_no_floor == "PASS"
    fb = g.floor_blocks[0]
    assert fb["injected_finding"]["code"] == "KPI_BREACH"
    assert (
        fb["result"].evidence["actual"] == 1840.5 and fb["result"].evidence["expected"] == "<= 1000"
    )
    assert g.coverage["floor_backstopped"] is True


def test_ground_records_a_pass_when_the_kpi_holds_and_abstains_when_unknown():
    g = ground(
        _council_pass(),
        _case(),
        ontology=_ont("field_in_set", {"field": "status.code", "allowed": ["OK"]}),
    )
    assert g.verdict == "PASS" and g.floor_blocks == [] and len(g.floor_passes) == 1
    g2 = ground(
        _council_pass(),
        _case(source_kind="prose"),
        ontology=_ont("kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 1}),
    )
    assert g2.verdict == "PASS"
    assert [b for b in g2.floor_blocks if b["injected_finding"] is None], (
        "surfaced as inconclusive, never flipped"
    )


def test_validate_contract_params_gates_a_bad_pin_before_it_can_reach_a_grade():
    good = VerificationContractDecl(
        flag_code="KPI_BREACH",
        question="q",
        contract_type="kpi_threshold",
        version="v1",
        params={
            "field": "duration_ms",
            "op": "<=",
            "value": 1000,
            "inject_flag_code": "KPI_BREACH",
            "inject_severity": "HIGH",
            "artifact_kind": "x",
        },
    )
    validate_contract_params(good, pack="_core")
    bad = VerificationContractDecl(
        flag_code="KPI_BREACH",
        question="q",
        contract_type="kpi_threshold",
        version="v1",
        params={
            "field": "duration_ms",
            "inject_flag_code": "KPI_BREACH",
            "inject_severity": "HIGH",
            "artifact_kind": "x",
        },
    )
    with pytest.raises(ValueError):
        validate_contract_params(bad, pack="_core")
