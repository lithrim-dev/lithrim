"""Acceptance suite for the agent↔pack readiness preflight (readiness.py).

The preflight exists to kill one silent failure: the council votes with the PACK lens but
``ground()`` reads its verification-contract set from the AGENT ontology — so a pack-declared
floor whose contract is absent from the agent ontology silently never fires (no error, verdict
stands). See ``agent-ontology-vs-pack-contract-split`` (memory) + the design doc.

These tests exercise the PURE function only: hand-built ``Ontology`` fixtures, an injected
``resolve_tool``, an explicit ``registered_executors``/``raiseable_codes`` set. No BFF, no pack
on disk, no network, ``$0``.
"""

from __future__ import annotations

from lithrim_bench.harness import readiness
from lithrim_bench.harness.ontology import from_dict

_SEVERITY_MAP = {"weights": {"high": 1.0, "medium": 0.5, "low": 0.1}, "block_at_or_above": 1.0, "warn_above": 0.0}


def _flag(code: str, gradeable: bool = True) -> dict:
    return {
        "flag": code,
        "category": "faithfulness",
        "definition": f"{code} definition",
        "when_to_use": "x",
        "when_NOT_to_use": "y",
        "owner_roles": ["faithfulness_judge"],
        "tier": "tier_1",
        "gradeable": gradeable,
    }


def _contract(flag_code: str, contract_type: str, tool: str | None = None) -> dict:
    params: dict = {"oracle_path": "patient_profile.conditions"}
    if tool is not None:
        params["tool"] = tool
    return {
        "flag_code": flag_code,
        "question": f"is {flag_code} grounded?",
        "contract_type": contract_type,
        "params": params,
        "version": "1",
    }


def _ont(flag_codes: list[str], contracts: list[dict]):
    return from_dict(
        {
            "ontology_version": "test/1",
            "domain": "test",
            "flags": [_flag(c) for c in flag_codes],
            "verification_contracts": contracts,
            "severity_map": _SEVERITY_MAP,
        }
    )


def _assess(*, agent, pack_ont, executors, resolve_tool, raiseable, source="committed", pack="clinverdict", agent_name="ws0_default"):
    return readiness.assess_agent_pack_readiness(
        agent_ontology=agent,
        ontology_source=source,
        pack=pack,
        agent_name=agent_name,
        pack_ontology=pack_ont,
        registered_executors=frozenset(executors),
        resolve_tool=resolve_tool,
        raiseable_codes=frozenset(raiseable),
    )


def _tool_present(_tool_id):  # a resolve_tool that finds every tool
    return {"id": _tool_id, "kind": "tool"}


def _tool_absent(_tool_id):  # a resolve_tool that finds nothing (undeclared / tier-denied)
    return None


# ── C1: CONTRACT_COVERAGE (the headline catch — the anchor bug) ────────────────────────


def test_c1_missing_pack_contract_is_error_and_not_ok():
    """The anchor bug: pack declares snomed_subsumption, the (_core-shaped) agent has none."""
    pack_ont = _ont(
        ["FABRICATED_CLAIM", "HALLUCINATED_DETAIL"],
        [_contract("FABRICATED_CLAIM", "snomed_subsumption", tool="hermes_snomed"),
         _contract("HALLUCINATED_DETAIL", "snomed_subsumption", tool="hermes_snomed")],
    )
    agent = _ont(["FABRICATED_CLAIM"], [])  # neutral agent: zero contracts

    report = _assess(
        agent=agent, pack_ont=pack_ont,
        executors={"snomed_subsumption"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"},
    )

    assert report.ok is False
    cov = [f for f in report.findings if f.check == "CONTRACT_COVERAGE"]
    assert len(cov) == 2
    assert all(f.severity == "ERROR" for f in cov)
    assert any("FABRICATED_CLAIM" in (f.code or "") for f in cov)
    assert any("HALLUCINATED_DETAIL" in (f.code or "") for f in cov)


def test_c1_aligned_agent_is_ok():
    contracts = [_contract("FABRICATED_CLAIM", "snomed_subsumption", tool="hermes_snomed")]
    pack_ont = _ont(["FABRICATED_CLAIM"], contracts)
    agent = _ont(["FABRICATED_CLAIM"], contracts)

    report = _assess(
        agent=agent, pack_ont=pack_ont,
        executors={"snomed_subsumption"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )

    assert report.ok is True
    assert report.findings == ()


def test_c1_contract_chain_on_one_code_is_covered():
    """LAYER2 composition: a flag_code may declare a CHAIN of contracts. An agent whose
    chain matches the pack's chain is COVERED — the old {flag_code: contract} dict kept only
    the last-declared and false-alarmed the rest as missing (the live clinverdict_mts modal
    warning, 2026-07-02: 3 contracts on HALLUCINATED_DETAIL -> 2 phantom ERRORs)."""
    chain = [
        _contract("HALLUCINATED_DETAIL", "snomed_subsumption", tool="hermes_snomed"),
        _contract("HALLUCINATED_DETAIL", "observation_form"),
        _contract("HALLUCINATED_DETAIL", "evidence_presence"),
    ]
    report = _assess(
        agent=_ont(["HALLUCINATED_DETAIL"], chain),
        pack_ont=_ont(["HALLUCINATED_DETAIL"], chain),
        executors={"snomed_subsumption", "observation_form", "evidence_presence"},
        resolve_tool=_tool_present, raiseable={"HALLUCINATED_DETAIL"},
    )
    assert [f for f in report.findings if f.check == "CONTRACT_COVERAGE"] == []
    assert report.ok is True


def test_c1_missing_link_in_a_chain_is_still_flagged():
    """Non-vacuity: the chain-aware match must still catch a genuinely missing pair —
    the agent carries only 2 of the pack's 3 chain links."""
    pack_chain = [
        _contract("HALLUCINATED_DETAIL", "snomed_subsumption", tool="hermes_snomed"),
        _contract("HALLUCINATED_DETAIL", "observation_form"),
        _contract("HALLUCINATED_DETAIL", "evidence_presence"),
    ]
    report = _assess(
        agent=_ont(["HALLUCINATED_DETAIL"], pack_chain[:2]),
        pack_ont=_ont(["HALLUCINATED_DETAIL"], pack_chain),
        executors={"snomed_subsumption", "observation_form", "evidence_presence"},
        resolve_tool=_tool_present, raiseable={"HALLUCINATED_DETAIL"},
    )
    cov = [f for f in report.findings if f.check == "CONTRACT_COVERAGE"]
    assert len(cov) == 1
    assert cov[0].code == "evidence_presence(HALLUCINATED_DETAIL)"


def test_c1_wrong_contract_type_is_error():
    """Same flag_code but a different contract_type is NOT coverage."""
    pack_ont = _ont(["FABRICATED_CLAIM"], [_contract("FABRICATED_CLAIM", "snomed_subsumption")])
    agent = _ont(["FABRICATED_CLAIM"], [_contract("FABRICATED_CLAIM", "presence_check")])

    report = _assess(
        agent=agent, pack_ont=pack_ont,
        executors={"snomed_subsumption", "presence_check"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )
    assert report.ok is False
    assert any(f.check == "CONTRACT_COVERAGE" for f in report.findings)


# ── C3: EXECUTOR_PRESENCE ──────────────────────────────────────────────────────────────


def test_c3_unregistered_executor_is_error():
    agent = _ont(["FABRICATED_CLAIM"], [_contract("FABRICATED_CLAIM", "bogus_type")])
    report = _assess(
        agent=agent, pack_ont=None,
        executors={"snomed_subsumption"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )
    assert report.ok is False
    ep = [f for f in report.findings if f.check == "EXECUTOR_PRESENCE"]
    assert ep and ep[0].severity == "ERROR" and ep[0].code == "bogus_type"


# ── C2: TOOL_REACHABILITY ──────────────────────────────────────────────────────────────


def test_c2_unreachable_tool_is_error():
    contracts = [_contract("FABRICATED_CLAIM", "snomed_subsumption", tool="hermes_snomed")]
    agent = _ont(["FABRICATED_CLAIM"], contracts)
    report = _assess(
        agent=agent, pack_ont=_ont(["FABRICATED_CLAIM"], contracts),
        executors={"snomed_subsumption"}, resolve_tool=_tool_absent,
        raiseable={"FABRICATED_CLAIM"},
    )
    assert report.ok is False
    tr = [f for f in report.findings if f.check == "TOOL_REACHABILITY"]
    assert tr and tr[0].severity == "ERROR" and tr[0].code == "hermes_snomed"


def test_c2_no_tool_param_is_not_checked():
    contracts = [_contract("FABRICATED_CLAIM", "source_grounding")]  # no params.tool
    agent = _ont(["FABRICATED_CLAIM"], contracts)
    report = _assess(
        agent=agent, pack_ont=_ont(["FABRICATED_CLAIM"], contracts),
        executors={"source_grounding"}, resolve_tool=_tool_absent,
        raiseable={"FABRICATED_CLAIM"},
    )
    assert not any(f.check == "TOOL_REACHABILITY" for f in report.findings)


# ── C4: CONTRACT_FLAG_VALIDITY (WARN) ──────────────────────────────────────────────────


def test_c4_contract_keyed_to_unraiseable_flag_is_warn():
    # agent declares a contract on a flag it does NOT declare / no judge can raise
    agent = _ont(["FABRICATED_CLAIM"], [_contract("GHOST_CODE", "presence_check")])
    report = _assess(
        agent=agent, pack_ont=None,
        executors={"presence_check"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )
    warns = [f for f in report.findings if f.check == "CONTRACT_FLAG_VALIDITY"]
    assert warns and warns[0].severity == "WARN" and warns[0].code == "GHOST_CODE"
    # a WARN alone does not fail readiness
    assert report.ok is True


# ── C5: LENS_VS_CONTRACT_GAP (WARN) ────────────────────────────────────────────────────


def test_c5_raiseable_fabrication_code_without_floor_is_warn():
    agent = _ont(["FABRICATED_CLAIM"], [])
    report = _assess(
        agent=agent, pack_ont=None,  # no pack ontology → C1 silent; C5 still fires
        executors=set(), resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"},
    )
    gaps = [f for f in report.findings if f.check == "LENS_VS_CONTRACT_GAP"]
    assert {g.code for g in gaps} == {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"}
    assert all(g.severity == "WARN" for g in gaps)
    assert report.ok is True


def test_c5_no_gap_when_floor_present():
    contracts = [_contract("FABRICATED_CLAIM", "snomed_subsumption", tool="hermes_snomed")]
    agent = _ont(["FABRICATED_CLAIM"], contracts)
    report = _assess(
        agent=agent, pack_ont=_ont(["FABRICATED_CLAIM"], contracts),
        executors={"snomed_subsumption"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )
    assert not any(f.check == "LENS_VS_CONTRACT_GAP" for f in report.findings)


# ── report shape ───────────────────────────────────────────────────────────────────────


def test_report_to_dict_is_json_shaped():
    agent = _ont(["FABRICATED_CLAIM"], [])
    pack_ont = _ont(["FABRICATED_CLAIM"], [_contract("FABRICATED_CLAIM", "snomed_subsumption")])
    report = _assess(
        agent=agent, pack_ont=pack_ont,
        executors={"snomed_subsumption"}, resolve_tool=_tool_present,
        raiseable={"FABRICATED_CLAIM"},
    )
    d = report.to_dict()
    assert d["ok"] is False
    assert d["pack"] == "clinverdict"
    assert d["agent"] == "ws0_default"
    assert d["ontology_source"] == "committed"
    assert isinstance(d["findings"], list) and d["findings"]
    f0 = d["findings"][0]
    assert set(f0) == {"check", "severity", "code", "message", "remediation"}
