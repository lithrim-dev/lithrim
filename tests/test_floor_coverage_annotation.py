"""FLOOR-COVERAGE-1 — per-verdict floor-coverage provenance.

The live reproduction (out/launch_trailer/VALIDATION.md) surfaced the F10-shaped
residual: the judges over-fired ``FABRICATED_CLAIM`` on a CLEAN control, no bound
contract could touch it, and the verdict flipped to a false-BLOCK that the record
presents *identically* to a grounded verdict. The honesty moat was silent exactly
where it is weakest.

This closes that at the verdict layer: ``ground()`` labels every surviving finding
with a coverage tag (``grounded`` / ``cleared`` / ``declined`` / ``unrefuted`` /
``judge_only`` / ``reference`` / ``null``) and stamps the verdict with
``floor_backstopped`` — False when a BLOCK rests solely on judge-only findings the
deterministic floor never grounded.

The annotation is PURELY DERIVED and ADDITIVE: ``active`` / ``suppressed`` /
``verdict`` / ``floor_blocks`` are byte-identical to the pre-annotation ``ground()``
(the invariance guard). It never touches the frozen consensus seam.

Written FIRST (RED): ``GroundedResult`` has no ``coverage`` field and ``composite``
does not surface it yet, so ``g.coverage`` raises ``AttributeError`` and
``composite(g)["coverage"]`` raises ``KeyError``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grounding import floor_executors, ground  # noqa: E402
from lithrim_bench.harness.ontology import from_dict  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402

_SEV = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}


def _flag(code, category="fidelity"):
    return {
        "flag": code,
        "category": category,
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
        "owner_roles": ["reviewer"],
        "tier": "TIER_1",
        "gradeable": True,
    }


# ── judge-only ontology: a gradeable flag with NO verification contract (the live-failure shape) ──

_JUDGE_ONLY_ONT = {
    "ontology_version": "coverage_test_judge_only_v1",
    "domain": "generic",
    "flags": [_flag("FABRICATED_CLAIM")],
    "questions": [],
    "verification_contracts": [],
    "severity_map": _SEV,
}


def _council_block():
    return {
        "verdict": "BLOCK",
        "findings": [{"code": "FABRICATED_CLAIM", "severity": "HIGH"}],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "BLOCK"}]},
    }


def test_judge_only_block_is_not_floor_backstopped():
    """THE live failure (cv_mts_001): a coded BLOCK-driver with no bound contract is judge_only,
    and the verdict is stamped floor_backstopped=False — no deterministic backstop for the reject."""
    g = ground(_council_block(), {"transcript": "t"}, ontology=from_dict(_JUDGE_ONLY_ONT))
    assert g.verdict == "BLOCK"
    cov = g.coverage
    assert cov["judge_only"] >= 1
    assert cov["grounded"] == 0 and cov["cleared"] == 0
    assert cov["floor_backstopped"] is False
    # the per-finding audit tags the surviving driver honestly
    tags = {(pf["code"], pf["coverage"]) for pf in cov["per_finding"]}
    assert ("FABRICATED_CLAIM", "judge_only") in tags


# ── suppress ontology: terminology_subsumption over a faked MCP terminology server ($0/offline) ──

_CONCEPTS = {"alzheimer's disease": 26929004, "dementia": 52448006, "hypertension": 38341003}
_IS_A = {(26929004, 52448006)}  # Alzheimer's is-a Dementia


class _FakeTerminology:
    def __init__(self, *a, **k):
        pass

    def call_tool(self, name, args):
        if name == "search":
            code = _CONCEPTS.get(str(args.get("query", "")).strip().lower())
            return [{"conceptId": code}] if code else []
        if name == "subsumed_by":
            pair = (args.get("concept_id"), args.get("subsumer_id"))
            return {"subsumedBy": pair in _IS_A or args.get("concept_id") == args.get("subsumer_id")}
        raise AssertionError(f"unexpected tool op {name}")

    def close(self):
        pass


def _wire_fakes(monkeypatch):
    from lithrim_bench.harness import plugins
    from lithrim_bench.verification import mcp_client

    monkeypatch.setattr(
        plugins, "resolve_tool",
        lambda tool_id: SimpleNamespace(service={"mcp": {"command": "fake", "args": []}}),
    )
    monkeypatch.setattr(mcp_client, "McpStdioClient", _FakeTerminology)


_SUB_ONT = {
    "ontology_version": "coverage_test_subsumption_v1",
    "domain": "generic",
    "flags": [_flag("FABRICATED_CLAIM")],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "FABRICATED_CLAIM",
            "question": "is the flagged term grounded in the record?",
            "contract_type": "terminology_subsumption",
            "version": "test/1",
            "params": {"tool": "my_terminology", "record_path": "record.conditions"},
        }
    ],
    "severity_map": _SEV,
}


def _council_block_with_span(quote="Alzheimer's disease"):
    return {
        "verdict": "BLOCK",
        "findings": [{"code": "FABRICATED_CLAIM", "severity": "HIGH"}],
        "semantic": {
            "judge_votes": [{"judge_role": "reviewer", "vote": "BLOCK"}],
            "evidence": [{"violation_code": "FABRICATED_CLAIM", "spans": [{"quote": quote}]}],
        },
    }


def test_suppress_cleared_finding_is_backstopped(monkeypatch):
    """A suppress contract disproves the flagged term (Alzheimer's ⊑ Dementia) → the finding is
    'cleared', the block flips PASS, and floor_backstopped=True (the floor materially cleared it)."""
    _wire_fakes(monkeypatch)
    case = {"transcript": "t", "record": {"conditions": ["Dementia", "Hypertension"]}}
    g = ground(_council_block_with_span(), case, ontology=from_dict(_SUB_ONT))
    assert g.verdict == "PASS"
    cov = g.coverage
    assert cov["cleared"] == 1 and cov["cleared"] == len(g.suppressed)
    assert cov["floor_backstopped"] is True
    assert ("FABRICATED_CLAIM", "cleared") in {
        (pf["code"], pf["coverage"]) for pf in cov["per_finding"]
    }


def test_bound_but_unrefuted_finding_is_not_backstopped(monkeypatch):
    """A suppress contract EXISTS for the code and ran, but the term is not subsumed (record lacks
    Dementia) → the finding STANDS as 'unrefuted' (distinct from judge_only: a contract examined it),
    the BLOCK holds, and it is NOT floor_backstopped (a suppress no-clear is not block support)."""
    _wire_fakes(monkeypatch)
    case = {"transcript": "t", "record": {"conditions": ["Hypertension"]}}
    g = ground(_council_block_with_span(), case, ontology=from_dict(_SUB_ONT))
    assert g.verdict == "BLOCK"
    cov = g.coverage
    assert cov["unrefuted"] >= 1
    assert cov["judge_only"] == 0
    assert cov["floor_backstopped"] is False


# ── structural floor: value_presence injects a BLOCK the council missed → 'grounded' ──

_VP_ONT = {
    "ontology_version": "coverage_test_value_presence_v1",
    "domain": "generic",
    "flags": [_flag("VALUE_DROPPED", category="completeness")],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "VALUE_DROPPED",
            "question": "is every value spoken in the transcript preserved in the note?",
            "contract_type": "value_presence",
            "version": "v1",
            "params": {
                "value_regex": r"refused|declining|declined",
                "source_path": "transcript",
                "match": "any",
                "inject_flag_code": "VALUE_DROPPED",
                "inject_severity": "HIGH",
            },
        }
    ],
    "severity_map": _SEV,
}
_TRANSCRIPT = (
    "Clinician: Your tetanus booster is due today. "
    "Patient: I refused the tetanus shot last time and I'm declining it again."
)
_SOAP_ERASED = "ASSESSMENT: Adult preventive visit, no acute concerns. PLAN: Continue current meds."
_COUNCIL_PASS = {
    "verdict": "PASS",
    "findings": [],
    "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "PASS"}]},
}


@pytest.mark.skipif(
    "value_presence" not in floor_executors(),
    reason="value_presence floor not registered under the active pack",
)
def test_floor_injected_block_is_grounded_and_backstopped():
    """A structural floor injects the BLOCK the council missed → the injected driver is 'grounded'
    and the verdict IS floor_backstopped (deterministic support for the reject)."""
    case = {"artifacts": [{"type": "scribe_soap", "content": _SOAP_ERASED}], "transcript": _TRANSCRIPT}
    g = ground(_COUNCIL_PASS, case, ontology=from_dict(_VP_ONT))
    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"
    cov = g.coverage
    assert cov["grounded"] >= 1
    assert cov["floor_backstopped"] is True
    assert ("VALUE_DROPPED", "grounded") in {
        (pf["code"], pf["coverage"]) for pf in cov["per_finding"]
    }


# ── INVARIANCE GUARD: coverage is purely derived — active/suppressed/verdict untouched ──


def test_coverage_is_purely_derived_and_conserved(monkeypatch):
    """The annotation must NOT perturb the grade: findings are never mutated in place, the verdict
    is still a pure rescore of active, and every finding is classified exactly once (conservation)."""
    _wire_fakes(monkeypatch)
    case = {"transcript": "t", "record": {"conditions": ["Dementia", "Hypertension"]}}
    ont = from_dict(_SUB_ONT)
    g = ground(_council_block_with_span(), case, ontology=ont)

    # no coverage key leaked into the graded finding dicts (not annotated in place)
    for f in g.active:
        assert "coverage" not in f and "_coverage" not in f
    for s in g.suppressed:
        assert "coverage" not in s["finding"]

    # verdict is still a pure rescore of active (unchanged by the annotation)
    assert g.verdict == ont.severity_map.rescore(g.active)

    # conservation: every active finding falls in exactly one active bucket
    cov = g.coverage
    active_buckets = (
        cov["grounded"] + cov["declined"] + cov["unrefuted"] + cov["judge_only"] + cov["null"]
    )
    assert active_buckets == len(g.active)
    assert cov["cleared"] == len(g.suppressed)
    assert cov["reference"] == len(g.skipped_non_gradeable)


def test_composite_surfaces_coverage_and_backstop():
    """The report seam (composite) carries the coverage summary + the floor_backstopped headline so
    the record/UI can mark a verdict with no deterministic backstop."""
    g = ground(_council_block(), {"transcript": "t"}, ontology=from_dict(_JUDGE_ONLY_ONT))
    comp = composite(g)
    assert comp["floor_backstopped"] is False
    assert comp["coverage"]["judge_only"] >= 1
    assert comp["coverage"]["grounded"] == 0
