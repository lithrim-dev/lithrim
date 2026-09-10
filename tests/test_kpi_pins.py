"""KPI-PINS-1: the fixes the v0.1.27 published-image test found.

1. A malformed KPI pin (unknown op, missing or non-numeric bound, reversed range, empty or
   non-list allowed set, unknown mode) is refused at AUTHOR time, as docs/KPI_CONTRACTS.md says,
   instead of being accepted and then skipped as malformed at grade time (the KPI silently never
   ran). The spec validates it, so the author gate and the grade share one rule.
3. KPI contracts stack per flag, one per field: pinning a KPI never displaces a flag's other
   checks, a second field appends, and a new version of the same KPI (same flag, type and field)
   replaces its predecessor, so a flag never runs two versions of one check. An ordinary
   contract keeps the existing rule (re-saving a flag replaces its contract) and never displaces
   a KPI contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent
from lithrim_bench.harness.grounding import validate_contract_params
from lithrim_bench.harness.ontology import VerificationContractDecl
from lithrim_bench.verification import TOOL_FIELD_IN_SET, TOOL_KPI_THRESHOLD, VerificationSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
_BASE = {
    "inject_flag_code": "UNSUPPORTED_ASSERTION",
    "inject_severity": "HIGH",
    "artifact_kind": "llm_response",
}


def _decl(ctype, params, version="v1", flag="UNSUPPORTED_ASSERTION"):
    return VerificationContractDecl(
        flag_code=flag,
        question="q",
        contract_type=ctype,
        version=version,
        params={**params, **_BASE},
    )


# ── 1. author-time refusal ────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "ctype, params, why",
    [
        ("kpi_threshold", {"field": "duration_ms", "op": "<="}, "value"),
        ("kpi_threshold", {"field": "duration_ms", "op": "<=", "value": "fast"}, "value"),
        ("kpi_threshold", {"field": "duration_ms", "op": "~", "value": 1}, "op"),
        ("kpi_threshold", {"field": "x", "op": "between", "min": 5, "max": 1}, "min"),
        ("kpi_threshold", {"field": "x", "op": "between", "min": 5}, "max"),
        ("kpi_threshold", {"field": "", "op": "<=", "value": 1}, "field"),
        ("field_in_set", {"field": "status.code", "allowed": []}, "allowed"),
        ("field_in_set", {"field": "status.code", "allowed": "OK"}, "allowed"),
        ("field_in_set", {"field": "status.code", "allowed": ["OK"], "mode": "maybe"}, "mode"),
        (
            "field_in_set",
            {"field": "status.code", "allowed": ["OK"], "target": "elsewhere"},
            "target",
        ),
    ],
)
def test_a_malformed_kpi_pin_is_refused_when_authored(ctype, params, why):
    with pytest.raises(ValueError, match=why):
        validate_contract_params(_decl(ctype, params), pack="_core")


def test_well_formed_kpi_pins_pass_the_author_gate():
    validate_contract_params(
        _decl("kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 2000}), pack="_core"
    )
    validate_contract_params(
        _decl("kpi_threshold", {"field": "t", "op": "between", "min": "20", "max": 800}),
        pack="_core",
    )
    validate_contract_params(
        _decl("field_in_set", {"field": "status.code", "allowed": ["OK"], "mode": "not_in"}),
        pack="_core",
    )


def test_the_spec_is_the_one_rule_the_grade_also_applies():
    with pytest.raises(ValueError, match="op"):
        VerificationSpec(
            tool=TOOL_KPI_THRESHOLD,
            applies_to_flags=("X",),
            locus="",
            reference={"field": "a", "op": "=~", "value": 1},
        )
    with pytest.raises(ValueError, match="allowed"):
        VerificationSpec(
            tool=TOOL_FIELD_IN_SET,
            applies_to_flags=("X",),
            locus="",
            reference={"field": "a", "allowed": []},
        )


# ── 3. KPI contracts stack per flag, identity without version ────────────────
AGENT = "kpi_pins_agent"
CORE_ONT = REPO_ROOT / "packs" / "_core" / "ontology.json"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff

    from lithrim_bench.harness import workspace as _workspace

    monkeypatch.setattr(
        _workspace,
        "get_active_workspace",
        lambda: _workspace.Workspace(name="default", pack="_core"),
    )
    db = tmp_path / "config.sqlite"
    save_agent(
        Agent(
            name=AGENT,
            eval_profile=EvalProfile(
                judges=("risk_judge",),
                council_config={},
                ontology_ref="_core/1",
                ontology_path=str(CORE_ONT),
                tools=(),
                kb_bindings={},
                severity_map_ref="ontology:_core/1",
            ),
            dataset=Dataset(case_id="c", source="s", baseline="b"),
        ),
        db_path=db,
    )
    workdir = tmp_path / "ont"
    c = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=workdir,
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test"),
        x_actor=None,
    )
    return c, workdir


def _contracts(workdir, flag):
    hits = list(Path(workdir).rglob("*.json"))
    docs = [json.loads(p.read_text()) for p in hits]
    ont = next(d for d in docs if isinstance(d, dict) and "verification_contracts" in d)
    return [
        (c["contract_type"], (c.get("params") or {}).get("field"), c["version"])
        for c in ont["verification_contracts"]
        if c["flag_code"] == flag
    ]


def _pin(c, ctype, params, version, flag="SOURCE_CONTRADICTION"):
    return c.put_grounding_contract(
        flag_code=flag,
        contract_type=ctype,
        question=f"{ctype} {params.get('field')}",
        version=version,
        agent=AGENT,
        params={
            **params,
            "inject_flag_code": flag,
            "inject_severity": "HIGH",
            "artifact_kind": "llm_response",
        },
    )


def test_kpi_pins_stack_per_field_and_never_displace_other_checks(ctx):
    c, workdir = ctx
    r1 = _pin(c, "kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 2000}, "latency/1")
    assert r1["replaced"] is False
    after = _contracts(workdir, "SOURCE_CONTRADICTION")
    assert ("value_grounding", None, "value-grounding/3") in after, "the pack's own check stays"
    assert ("kpi_threshold", "duration_ms", "latency/1") in after
    r2 = _pin(
        c,
        "kpi_threshold",
        {"field": "gen_ai.usage.output_tokens", "op": "between", "min": 20, "max": 800},
        "tokens/1",
    )
    assert r2["replaced"] is False
    r3 = _pin(c, "field_in_set", {"field": "status.code", "allowed": ["OK"]}, "status/1")
    assert r3["replaced"] is False
    kpis = [
        x
        for x in _contracts(workdir, "SOURCE_CONTRADICTION")
        if x[0] in ("kpi_threshold", "field_in_set")
    ]
    assert sorted(kpis) == [
        ("field_in_set", "status.code", "status/1"),
        ("kpi_threshold", "duration_ms", "latency/1"),
        ("kpi_threshold", "gen_ai.usage.output_tokens", "tokens/1"),
    ]


def test_a_new_version_of_the_same_kpi_replaces_its_predecessor(ctx):
    c, workdir = ctx
    _pin(c, "kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 2000}, "latency/1")
    r = _pin(c, "kpi_threshold", {"field": "duration_ms", "op": "<=", "value": 1500}, "latency/2")
    assert r["replaced"] is True
    latency = [x for x in _contracts(workdir, "SOURCE_CONTRADICTION") if x[1] == "duration_ms"]
    assert latency == [("kpi_threshold", "duration_ms", "latency/2")], (
        "one version of one check, never both"
    )


def test_an_ordinary_contract_keeps_replace_by_flag_and_never_displaces_a_kpi(ctx):
    c, workdir = ctx
    _pin(
        c,
        "kpi_threshold",
        {"field": "duration_ms", "op": "<=", "value": 2000},
        "latency/1",
        flag="FABRICATED_CLAIM",
    )
    r = c.put_grounding_contract(
        flag_code="FABRICATED_CLAIM",
        contract_type="source_grounding",
        params={"source_path": "transcript"},
        question="grounded?",
        version="source-grounding/2",
        agent=AGENT,
    )
    assert r["replaced"] is True, "the flag's existing ordinary check is replaced, as before"
    got = _contracts(workdir, "FABRICATED_CLAIM")
    assert ("source_grounding", None, "source-grounding/2") in got
    assert ("kpi_threshold", "duration_ms", "latency/1") in got
    assert sum(1 for x in got if x[0] == "source_grounding") == 1
