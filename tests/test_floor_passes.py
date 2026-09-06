"""FLOOR-PASSES-1 — a satisfied floor is EVIDENCE, and the record must carry it.

``GroundedResult.floor_blocks`` records a floor that VIOLATED (a BLOCK injected) or was
INCONCLUSIVE; a floor that was SATISFIED (``conforms is True``) was a no-op and left no trace
(``harness/grounding.py`` docstring: "not recorded"). So a PASS could never prove a check ran,
and ``coverage.floor_backstopped`` was False on every PASS that no suppress contract touched,
even when a deterministic floor examined the artifact and found it clean.

This adds ``floor_passes`` (the satisfied floors, with their evidence) as a PURELY ADDITIVE,
read-only field next to ``floor_blocks``, and lets a PASS count as floor-backstopped when at
least one floor pass is recorded. ``active`` / ``suppressed`` / ``verdict`` / ``floor_blocks``
/ ``verdict_no_floor`` are byte-identical to before (the invariance guard); the frozen
consensus seam is untouched.

Written FIRST (RED): ``GroundedResult`` has no ``floor_passes`` field, ``composite`` does not
surface it, and a clean PASS under a satisfied floor is stamped ``floor_backstopped=False``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import from_dict  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402

_SEV = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}


def _flag(code):
    return {
        "flag": code,
        "category": "fidelity",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
        "owner_roles": ["reviewer"],
        "tier": "TIER_1",
        "gradeable": True,
    }


# a deterministic, pure-stdlib core floor (value_presence, match=any): the source raised a
# refusal; the artifact must record it in some accepted form.
_FLOOR_ONT = {
    "ontology_version": "floor_passes_test_v1",
    "domain": "generic",
    "flags": [_flag("MISSING_CONTEXT")],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "MISSING_CONTEXT",
            "question": "Is the refusal spoken in the source preserved in the artifact?",
            "contract_type": "value_presence",
            "version": "value-presence/test-1",
            "params": {
                "value_regex": r"refused|declined|declining",
                "source_path": "transcript",
                "match": "any",
                "inject_flag_code": "MISSING_CONTEXT",
                "inject_severity": "HIGH",
                "artifact_kind": "note",
            },
        }
    ],
    "severity_map": _SEV,
}

_NO_CONTRACT_ONT = {**_FLOOR_ONT, "verification_contracts": []}


def _council_pass():
    return {
        "verdict": "PASS",
        "findings": [],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "PASS"}]},
    }


_TRANSCRIPT = "Clinician: the booster is due. Patient: I refused it last time and I am declining again."
_KEPT = {
    "transcript": _TRANSCRIPT,
    "artifacts": [{"type": "note", "content": "Patient declined the booster; refusal documented."}],
}
_ERASED = {
    "transcript": _TRANSCRIPT,
    "artifacts": [{"type": "note", "content": "Routine visit. No acute concerns."}],
}
_NO_SOURCE = {"artifacts": [{"type": "note", "content": "Routine visit."}]}


def test_satisfied_floor_is_recorded_as_a_floor_pass():
    """A1: the floor examined the artifact and found it conforming → the pass is RECORDED with
    its evidence, and ``floor_blocks`` stays empty exactly as before."""
    g = ground(_council_pass(), _KEPT, ontology=from_dict(_FLOOR_ONT))
    assert g.verdict == "PASS"
    assert g.floor_blocks == []
    assert len(g.floor_passes) == 1
    p = g.floor_passes[0]
    assert p["decl"].contract_type == "value_presence"
    assert p["result"].conforms is True
    assert p["result"].evidence.get("concept_in_artifact") is True


def test_a_pass_with_a_floor_pass_is_floor_backstopped():
    """A2: the deterministic layer materially supported this PASS — the stamp says so."""
    g = ground(_council_pass(), _KEPT, ontology=from_dict(_FLOOR_ONT))
    assert g.coverage["floor_backstopped"] is True
    assert g.coverage["floor_passes"] == 1


def test_a_judge_only_pass_is_still_not_backstopped():
    """A3 (the invariant that must NOT move): no contract ran → a PASS rests on judges alone."""
    g = ground(_council_pass(), _KEPT, ontology=from_dict(_NO_CONTRACT_ONT))
    assert g.verdict == "PASS"
    assert g.floor_passes == []
    assert g.coverage["floor_backstopped"] is False


def test_a_violating_floor_still_blocks_and_records_no_pass():
    """A4: the FLOOR direction is untouched — the erased refusal injects the BLOCK, and nothing
    lands in ``floor_passes``."""
    g = ground(_council_pass(), _ERASED, ontology=from_dict(_FLOOR_ONT))
    assert g.verdict == "BLOCK"
    assert g.verdict_no_floor == "PASS"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is not None
    assert g.floor_passes == []
    assert g.coverage["floor_backstopped"] is True


def test_an_inconclusive_floor_is_neither_a_pass_nor_a_block():
    """A5: no source text → the floor cannot decide → surfaced in ``floor_blocks`` as
    inconclusive, NOT counted as a pass, and the PASS is NOT backstopped (never by silence)."""
    g = ground(_council_pass(), _NO_SOURCE, ontology=from_dict(_FLOOR_ONT))
    assert g.verdict == "PASS"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is None
    assert g.floor_passes == []
    assert g.coverage["floor_backstopped"] is False


def test_composite_surfaces_floor_passes():
    """A6: the audit record carries the passes (flag, contract_type, contract, evidence) and a
    count, so a report can show WHICH check cleared the case."""
    comp = composite(ground(_council_pass(), _KEPT, ontology=from_dict(_FLOOR_ONT)))
    assert comp["floor_pass_count"] == 1
    entry = comp["floor_passes"][0]
    assert entry["flag"] == "MISSING_CONTEXT"
    assert entry["contract_type"] == "value_presence"
    assert entry["contract"] == "value-presence/test-1"
    assert entry["conforms"] is True
    assert entry["evidence"]["concept_in_artifact"] is True
    assert comp["floor_backstopped"] is True


def test_invariance_of_the_grade_fields():
    """A7 (invariance guard): the grade-bearing fields on a satisfied-floor PASS are exactly what
    they were before the addition — nothing in the grade digest moved."""
    g = ground(_council_pass(), _KEPT, ontology=from_dict(_FLOOR_ONT))
    assert g.active == []
    assert g.suppressed == []
    assert g.verdict == "PASS"
    assert g.verdict_no_floor == "PASS"
    assert g.floor_blocks == []


# ── REVIEW-STATE-1: the grounded block persists the passes and the coverage too ─────────


def test_grounded_block_carries_floor_passes_and_coverage():
    """The `grounded` block is the run-blob/audit shape (LAYER0-READ-1). It carried only the
    blocks, so a stored run could show what a check contradicted but never what it confirmed.
    Parity with composite(): floor_passes (with evidence) and coverage ride the same block."""
    _SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    import run_eval  # noqa: E402

    g = ground(_council_pass(), _KEPT, ontology=from_dict(_FLOOR_ONT))
    block = run_eval._grounded_block(g)
    assert block["coverage"]["floor_backstopped"] is True
    assert block["coverage"]["floor_passes"] == 1
    (p,) = block["floor_passes"]
    assert p["contract_type"] == "value_presence" and p["conforms"] is True
    assert p["evidence"], "a recorded pass carries the evidence the check produced"
