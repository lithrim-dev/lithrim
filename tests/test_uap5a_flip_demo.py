"""UAP-5a A4 (offline half): the by-construction demo case FLIPS with authoring.

The demo case ``bench_uap5a_flip_demo_dosage_drift_*`` carries a subtle WRONG_DOSAGE
drift (300 MG -> 450 MG, 1.5x — a real Tier-1 defect, owner risk_judge). Authoring a
judge by assigning the WRONG_DOSAGE lens to risk_judge must be CONSEQUENTIAL: the
in-process council, built as the authored DSPy trio, votes reject where the default
trio does not. We prove it $0/offline with injected per-role predictors that key off
the AUTHORED REFINEMENT marker (the section ``render_role_questions`` appends ONLY
when a role carries an assignment):

  * unassigned -> no marker -> every judge approves -> verdict NOT reject
  * assigned   -> risk_judge's prompt carries the marker -> it BLOCKs -> the Tier-1
                  one-strike floor drives the composite to reject (the FLIP)

This is the deterministic half of A4. The LIVE composite flip on the real paid trio
is the cost-gated attestation recorded in the session log. The construction is honest
(``package_case`` enforces D1/D3; lint green): the case truly contains the defect, so
the base trio's miss is a calibration false-negative the authoring corrects — never a
manufactured flip.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.harness.grade import grade_inprocess  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage  # noqa: E402
from lithrim_bench.runtime.council.judge_assignment import render_role_questions  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_CASE_ID = "bench_uap5a_flip_demo_dosage_drift_84ee8f1e7442"
_CASE_SRC = _REPO / "examples" / "uap5a_flip_demo.jsonl"
_MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="
_FLAG = "WRONG_DOSAGE"


def _recording_predictors(captured: dict, flag: str):
    def make(role):
        def _p(*, role_key_questions: str = "", **_kw):
            captured[role] = role_key_questions
            if _MARKER in role_key_questions:
                return {
                    "decision": "reject",
                    "findings": [{"taxonomy_code": flag, "evidence_spans": [{"quote": "450MG", "turn_ids": []}]}],
                }
            return {"decision": "approve", "findings": []}

        return _p

    return {role: make(role) for role in V2_ROLES}


def _case():
    c = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert c is not None, f"case {_CASE_ID} not found in {_CASE_SRC}"
    return c


def test_demo_case_flips_non_reject_to_reject_on_assignment():
    ont = load_ontology()
    case = _case()

    cap0: dict = {}
    stage0 = build_authored_semantic_stage(
        ontology=ont, assignments=None, predictors=_recording_predictors(cap0, _FLAG)
    )
    r0 = grade_inprocess(case, semantic_stage=stage0)
    comp0 = composite(ground(r0, case, ontology=ont))
    assert comp0["verdict"] != "reject"  # base trio: non-reject
    assert all(v["vote"] != "BLOCK" for v in r0["semantic"]["judge_votes"])

    cap1: dict = {}
    stage1 = build_authored_semantic_stage(
        ontology=ont,
        assignments={"risk_judge": [_FLAG]},
        predictors=_recording_predictors(cap1, _FLAG),
    )
    r1 = grade_inprocess(case, semantic_stage=stage1)
    comp1 = composite(ground(r1, case, ontology=ont))
    assert comp1["verdict"] == "reject"  # THE FLIP

    risk = next(v for v in r1["semantic"]["judge_votes"] if v["judge_role"] == "risk_judge")
    assert risk["vote"] == "BLOCK"
    assert _FLAG in risk["findings"]
    others = [v for v in r1["semantic"]["judge_votes"] if v["judge_role"] != "risk_judge"]
    assert all(v["vote"] != "BLOCK" for v in others)  # only the authored judge moved


def test_demo_case_preview_matches_the_authored_prompt():
    """Preview↔live parity on the demo case: the judge votes on EXACTLY the prompt the
    $0 GET /v1/judges/{role}?assigned_flags= JudgeEditor preview returns."""
    ont = load_ontology()
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont, assignments={"risk_judge": [_FLAG]}, predictors=_recording_predictors(cap, _FLAG)
    )
    grade_inprocess(_case(), semantic_stage=stage)

    preview = render_role_questions(ont, "risk_judge", assigned_flags=[_FLAG])
    assert cap["risk_judge"] == preview
    assert _MARKER in preview and _FLAG in preview
    assert _MARKER not in cap["policy_judge"]
