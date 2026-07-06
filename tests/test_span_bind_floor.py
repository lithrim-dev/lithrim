"""SPAN-BIND-1 — the SNOMED-subsumption floor is SPAN-bound, not flag-code-bound.

A history-subsumption oracle may clear a finding ONLY when a flagged evidence span quotes a
documented PMH item. Binding on the flag CODE alone let a PMH-subsumption pass clear a
FABRICATED_CLAIM whose span was a fabricated exam/plan detail, flipping true-reject cases to
PASS (measured live on clinverdict_mts: cv_mts_104 / cv_mts_105, sole gold FABRICATED_CLAIM on
off-PMH spans, wrongly suppressed → PASS). This pins the fix: off-PMH span ⇒ finding STANDS;
on-PMH span ⇒ suppressed as before; no span ⇒ STANDS (never clear by silence).

The pack lives in the drop-in tree; skip cleanly when it (or its deps) is not on the path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DROPIN = REPO_ROOT / "packs-dropin"

pytestmark = pytest.mark.skipif(
    not (DROPIN / "clinverdict" / "floors.py").exists(),
    reason="clinverdict drop-in pack not present",
)


@pytest.fixture()
def floor(monkeypatch):
    import sys

    if str(DROPIN) not in sys.path:
        sys.path.insert(0, str(DROPIN))
    F = pytest.importorskip("clinverdict.floors")
    from lithrim_bench.harness.ontology import VerificationContractDecl

    # Stub the terminology transport so the ON-PMH (positive) path grounds every item without a
    # live Hermes MCP server. The OFF-PMH / no-span paths short-circuit BEFORE the client is
    # built — they need no stub, which is itself the point (out-of-scope findings cost no RPC).
    monkeypatch.setattr(
        F, "_terminology_client", lambda p: type("X", (), {"close": lambda s: None})()
    )
    monkeypatch.setattr(F, "_resolve_code", lambda cl, t: 111)
    monkeypatch.setattr(F, "_grounded_by_code", lambda cl, it, codes: True)

    decl = VerificationContractDecl(
        flag_code="FABRICATED_CLAIM",
        question="q",
        contract_type="snomed_subsumption",
        params={"oracle_path": "patient_profile.conditions", "tool": "hermes_snomed"},
        version="v1",
    )
    return F.SnomedSubsumptionGrounding(decl)


def _case(pmh_item: str):
    soap = f"S: cramps.\nPMH:\n  - {pmh_item}\nA/P: plan.\n"
    docref = json.dumps(
        {"resourceType": "DocumentReference", "content": [{"attachment": {"data": soap}}]}
    )
    return {
        "artifacts": [{"type": "note", "content": docref}],
        "patient_profile": {"conditions": [pmh_item]},
    }


def _finding(*quotes: str):
    return {
        "code": "FABRICATED_CLAIM",
        "_evidence_spans": [{"quote": q} for q in quotes],
    }


PMH = "Human immunodeficiency virus infection"


def test_off_pmh_span_is_not_suppressed(floor):
    """The regression that flipped cv_mts_104/105: a fabricated EXAM detail cleared because the
    PMH happened to be subsumed. The span points away from the history ⇒ finding STANDS."""
    v = floor.check(
        _finding("Neurological exam notable for diminished patellar reflexes bilaterally."),
        _case(PMH),
    )
    assert v.disproved is False
    assert "does not quote a documented PMH item" in v.reason


def test_on_pmh_span_is_suppressed(floor):
    """The designed win: the judge flagged the documented history itself, and it is grounded by
    subsumption ⇒ the false alarm is disproved."""
    v = floor.check(_finding(f"PMH:  - {PMH}"), _case(PMH))
    assert v.disproved is True
    assert "subsumed-by a record concept" in (v.evidence or "")


def test_no_span_is_not_suppressed(floor):
    """Conservative: a finding with no evidence span cannot be confirmed as history-scoped, so
    the history oracle never clears it by silence."""
    v = floor.check(_finding(), _case(PMH))
    assert v.disproved is False


def test_off_pmh_span_makes_no_terminology_call(floor, monkeypatch):
    """The gate short-circuits above the MCP seam: an out-of-scope finding must not resolve any
    SNOMED code (both correctness AND cost)."""
    import clinverdict.floors as F

    called = {"n": 0}

    def _boom(p):
        called["n"] += 1
        raise AssertionError("terminology client must not be built for an off-PMH span")

    monkeypatch.setattr(F, "_terminology_client", _boom)
    v = floor.check(_finding("Positive Phalen's test bilaterally."), _case(PMH))
    assert v.disproved is False
    assert called["n"] == 0
