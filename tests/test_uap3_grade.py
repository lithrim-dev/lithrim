"""UAP-3 / S-BS-63: the authored→flip — an authored judge re-votes with its authored
lens through the in-process grade.

THE LOAD-BEARING TEST (A1). Authoring a judge (assigning an ontology flag lens) must
be CONSEQUENTIAL: the in-process council, built as the authored DSPy trio
(``build_authored_semantic_stage``), votes differently than the default-config trio.
We prove it $0/offline with injected per-role predictors that key off the AUTHORED
REFINEMENT marker — the section ``render_role_questions`` appends ONLY when a role
carries an assignment. So:

  * unassigned  → no marker in any role prompt → every judge approves → verdict NOT reject
  * assigned    → the assigned role's prompt carries the marker → that judge BLOCKs →
                  the Tier-1 safety floor drives the composite verdict to reject (the FLIP)

PREVIEW↔LIVE PARITY (refinement #2): the predictor records the exact
``role_key_questions`` each judge actually voted on; we assert it is byte-equal to
``render_role_questions(ontology, role, assigned_flags=…)`` — the SAME render the $0
``GET /v1/judges/{role}?assigned_flags=`` JudgeEditor preview returns. So the prompt
the SME previews IS the prompt the live judge grades on; the preview is not a separate
approximation.

The frozen consensus seam (``_apply_consensus`` + the per-judge seam dict +
``judges_dspy`` + ``judge_metric``) is byte-0-delta this cycle — verified by the A2
``git diff`` acceptance check over the full set (recorded in the session log), not
re-run here (a git-diff-in-pytest would pin against a cycle-specific parent).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# build_authored_semantic_stage → build_trio (dspy) + ComplianceCouncil (openai).
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
_CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
_CASE_SRC = _REPO / "tests" / "fixtures" / "ws0" / f"case.{_CASE_ID}.jsonl"

_MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="
_ASSIGNED_FLAG = "WRONG_DOSAGE"  # a risk_judge Tier-1 lens code


def _case():
    c = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert c is not None, f"case {_CASE_ID} not found in {_CASE_SRC}"
    return c


def _recording_predictors(captured: dict, flag: str):
    """Per-role predictors that record the role_key_questions they were fed, and BLOCK
    (emitting ``flag``) iff the authored-refinement marker is present — i.e. iff the
    role carries an assignment. Pure dict-returning callables; no dspy / no network."""

    def make(role):
        def _p(*, role_key_questions: str = "", **_kw):
            captured[role] = role_key_questions
            if _MARKER in role_key_questions:
                return {
                    "decision": "reject",
                    "findings": [
                        {"taxonomy_code": flag, "evidence_spans": [{"quote": "x", "turn_ids": []}]}
                    ],
                }
            return {"decision": "approve", "findings": []}

        return _p

    return {role: make(role) for role in V2_ROLES}


def test_authored_assignment_flips_the_in_process_verdict():
    """The headline (A1): assigning WRONG_DOSAGE to risk_judge flips the composite
    verdict from non-reject (default trio) to reject (authored trio), $0/offline."""
    ont = load_ontology()
    case = _case()

    # default (no authoring) → no marker → every judge approves → NOT reject
    cap0: dict = {}
    stage0 = build_authored_semantic_stage(
        ontology=ont, assignments=None, predictors=_recording_predictors(cap0, _ASSIGNED_FLAG)
    )
    r0 = grade_inprocess(case, semantic_stage=stage0)
    comp0 = composite(ground(r0, case, ontology=ont))
    assert comp0["verdict"] != "reject"
    assert all(v["vote"] != "BLOCK" for v in r0["semantic"]["judge_votes"])

    # authored: assign the lens to risk_judge → that judge BLOCKs → composite reject
    cap1: dict = {}
    stage1 = build_authored_semantic_stage(
        ontology=ont,
        assignments={"risk_judge": [_ASSIGNED_FLAG]},
        predictors=_recording_predictors(cap1, _ASSIGNED_FLAG),
    )
    r1 = grade_inprocess(case, semantic_stage=stage1)
    comp1 = composite(ground(r1, case, ontology=ont))
    assert comp1["verdict"] == "reject"  # THE FLIP

    risk_vote = next(v for v in r1["semantic"]["judge_votes"] if v["judge_role"] == "risk_judge")
    assert risk_vote["vote"] == "BLOCK"
    assert _ASSIGNED_FLAG in risk_vote["findings"]
    # the OTHER roles, unassigned, did not flip → the move is the authoring, not the case
    others = [v for v in r1["semantic"]["judge_votes"] if v["judge_role"] != "risk_judge"]
    assert all(v["vote"] != "BLOCK" for v in others)


def test_authored_prompt_matches_the_judge_editor_preview():
    """Preview↔live parity: the prompt the live judge votes on is byte-equal to the
    render the $0 GET /v1/judges/{role}?assigned_flags= preview returns — anchored on
    the SAME render_role_questions call, so the preview is not a separate approximation."""
    ont = load_ontology()
    case = _case()
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments={"risk_judge": [_ASSIGNED_FLAG]},
        predictors=_recording_predictors(cap, _ASSIGNED_FLAG),
    )
    grade_inprocess(case, semantic_stage=stage)

    preview = render_role_questions(ont, "risk_judge", assigned_flags=[_ASSIGNED_FLAG])
    assert cap["risk_judge"] == preview  # the judge voted on EXACTLY the previewed prompt
    assert _MARKER in preview and _ASSIGNED_FLAG in preview
    # an unassigned role's prompt is the seed base (no marker) — back-compat parity
    assert _MARKER not in cap["policy_judge"]
    assert cap["policy_judge"] == render_role_questions(ont, "policy_judge")


class _Sentinel(Exception):
    """Short-circuits run() right after the grade dispatch built its stage — so the
    test never makes a paid grade call ($0)."""


def test_no_assignment_in_process_path_builds_authored_stage_not_default_council(
    tmp_path, monkeypatch
):
    """D4 (CE-PACK-6b-ROUTE): run_eval's in-process dispatch with NO assignments builds
    the AUTHORED stage from the FULL PACK LENS — it never falls through to
    ``semantic_stage=None`` (the legacy ``ComplianceCouncil.build_prompt`` default
    council). $0/offline: the authored-stage builder + grade_inprocess are stubbed so no
    Azure call fires; we only assert the routing.

    ``build_prompt`` was DELETED in CE-PACK-6b-CLEAN (the authored DSPy stage is the single
    live prompt source); this test pins that the in-process path builds the authored stage
    (never ``semantic_stage=None``, the slot the legacy default council used to fill)."""
    import sys as _sys

    import lithrim_bench.runtime.council.authored_stage as authored_mod
    from lithrim_bench.harness.config import load_agent, seed_config_db
    from lithrim_bench.harness.pack import pack_lenses, pack_production_judges

    if str(_REPO / "scripts") not in _sys.path:
        _sys.path.insert(0, str(_REPO / "scripts"))
    import run_eval

    db = tmp_path / "config.sqlite"
    seed_config_db(db_path=db)
    agent = load_agent("ws0_default", db_path=db)

    captured: dict = {}

    def _fake_build_authored_semantic_stage(*, assignments=None, **_kw):
        captured["assignments"] = assignments
        return "STAGE_SENTINEL"  # a non-None stage object

    def _fake_grade_inprocess(case, *, semantic_stage=None, **_kw):
        captured["semantic_stage"] = semantic_stage
        raise _Sentinel  # stop before any real grade / persistence

    monkeypatch.setattr(
        authored_mod, "build_authored_semantic_stage", _fake_build_authored_semantic_stage
    )
    monkeypatch.setattr(run_eval, "grade_inprocess", _fake_grade_inprocess)

    with pytest.raises(_Sentinel):
        run_eval.run(agent, in_process=True, assignments=None, collections_db=db)

    # the authored stage was built (never None) → the deleted build_prompt default council
    # cannot be reached on the in-process path
    assert captured["semantic_stage"] == "STAGE_SENTINEL"
    assert captured["semantic_stage"] is not None

    # and the no-assignment default is the FULL PACK LENS over the production roster
    lenses = pack_lenses()
    expected = {role: sorted(lenses[role]) for role in pack_production_judges() if role in lenses}
    assert captured["assignments"] == expected
    assert captured["assignments"], "the default lens must be non-empty"
