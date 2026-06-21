"""GRADE-GUARD-1 — a malformed verification_contract must NEVER 500 a grade.

The live A-LIVE surfaced it: a leftover ``presence_check`` authored with the inert default params
(``{"source": ...}``, no ``med_source``) crashed the ENTIRE grade with a cryptic ``KeyError`` at
contract construction (``ground()`` builds all suppress contracts eagerly, before grading findings).
Two guards, both written RED first:

  * B1 (grade-time, defense): ``ground()`` SKIP-LOGS a contract that fails to build/run (into a new
    ``GroundedResult.skipped_malformed`` bucket — surfaced, never silent) instead of crashing — the
    same "never silently drop, never abort the grade" discipline as the S-BS-8/10 skip-logging.
  * B2 (author-time, prevention): ``validate_contract_params(decl)`` dry-constructs the contract and
    raises a clear ``ValueError`` on malformed params — the FAUTH-2 gate calls it so a bad contract
    is rejected (422) at author time, never persisted to detonate at grade time.

``presence_check`` is a CORE suppress executor (always registered), so these run pack-agnostic.
"""

from __future__ import annotations

import pytest

from lithrim_bench.harness.ontology import VerificationContractDecl, from_dict

_CASE = {"artifacts": [{"type": "x", "content": "the artifact text"}], "transcript": "t"}
_COUNCIL = {"verdict": "PASS", "findings": [], "semantic": {}}


def _ont(params: dict, contract_type: str = "presence_check"):
    return from_dict(
        {
            "ontology_version": "grade_guard_test",
            "domain": "test",
            "flags": [
                {"flag": "X", "category": "c", "definition": "", "when_to_use": "",
                 "when_NOT_to_use": "", "owner_roles": ["risk_judge"], "tier": "TIER_1", "gradeable": True}
            ],
            "questions": [],
            "verification_contracts": [
                {"flag_code": "X", "contract_type": contract_type, "question": "q",
                 "version": "v1", "params": params}
            ],
            "severity_map": {"weights": {"HIGH": 1.0, "MEDIUM": 0.5}, "block_at_or_above": 0.5, "warn_above": 0.0},
        }
    )


# ── B1 — ground() skip-logs a malformed contract instead of crashing ──


def test_ground_skiplogs_malformed_contract_instead_of_crashing():
    from lithrim_bench.harness.grounding import ground

    ont = _ont({"source": "response.claims"})  # the inert default — MISSING med_source/dosage_regex
    g = ground(_COUNCIL, _CASE, ontology=ont)  # MUST NOT raise (parent: KeyError 'med_source')
    assert any(s["decl"].flag_code == "X" for s in g.skipped_malformed)
    assert "med_source" in g.skipped_malformed[0]["error"]
    assert g.verdict in ("PASS", "WARN", "BLOCK")  # the grade COMPLETED


def test_ground_valid_presence_check_is_not_skiplogged():
    from lithrim_bench.harness.grounding import ground

    ont = _ont({"med_source": "transcript", "dosage_regex": r"\b\d+\b"})  # well-formed
    g = ground(_COUNCIL, _CASE, ontology=ont)
    assert g.skipped_malformed == []  # a valid contract builds; nothing skip-logged


def test_ground_skiplogs_malformed_floor_contract_instead_of_crashing():
    """B1 covers the FLOOR branch too (not just the suppress build): a malformed core floor
    (``structural_jute`` with empty params) raises ``KeyError: 'service'`` INSIDE the floor loop —
    it MUST skip-log (``stage='floor'``) and let the grade complete, the same as the suppress-side
    ``med_source`` KeyError. Without the floor try/except this would 500 the grade."""
    from lithrim_bench.harness.grounding import ground

    g = ground(_COUNCIL, _CASE, ontology=_ont({}, contract_type="structural_jute"))  # MUST NOT raise
    floor_skips = [s for s in g.skipped_malformed if s["stage"] == "floor"]
    assert floor_skips, f"expected a floor-stage skip-log, got {g.skipped_malformed}"
    assert floor_skips[0]["decl"].flag_code == "X"
    assert g.verdict in ("PASS", "WARN", "BLOCK")  # the grade COMPLETED


# ── B2 — validate_contract_params rejects malformed params at author time ──


def test_validate_contract_params_rejects_and_passes():
    from lithrim_bench.harness.grounding import validate_contract_params

    bad = VerificationContractDecl(
        flag_code="X", question="q", contract_type="presence_check",
        params={"source": "response.claims"}, version="v1",
    )
    with pytest.raises(ValueError) as ei:
        validate_contract_params(bad)
    assert "presence_check" in str(ei.value) and "med_source" in str(ei.value)

    good = VerificationContractDecl(
        flag_code="X", question="q", contract_type="presence_check",
        params={"med_source": "transcript", "dosage_regex": r"\b\d+\b"}, version="v1",
    )
    validate_contract_params(good)  # no raise


def test_validate_contract_params_rejects_malformed_core_floor():
    """A core FLOOR type (structural_jute) with empty params fails its reference build → rejected."""
    from lithrim_bench.harness.grounding import validate_contract_params

    bad = VerificationContractDecl(
        flag_code="X", question="q", contract_type="structural_jute", params={}, version="v1",
    )
    with pytest.raises(ValueError):
        validate_contract_params(bad)
