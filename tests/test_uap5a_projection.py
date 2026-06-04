"""UAP-5a D2 / S-BS-66: the authored in_process path projects a LEGIBLE per-judge audit.

The regression this guards: before the fix, the injected (authored DSPy) branch fed
``_judge_votes_from_models`` an empty ``model_lookup`` and a ``["injected"]`` roster,
and the per-judge seam dict carries no ``summary``/``rationale``. So a live authored
run's ``council.votes`` + ``/v1/runs/{id}/audit`` came back with empty ``model`` +
empty ``reason`` + a roster of ``["injected"]`` — the flip was not READABLE (the A8
smoke finding). ``judge_role`` / ``vote`` / ``findings`` were already populated.

The fix is mapping-layer only (``stages.py``; the frozen consensus seam +
``judges_dspy`` + ``judge_metric`` + seeds are byte-0-delta — the A2 ``git diff``
check in the session log). This proves the projection at $0 via injected predictors;
the LIVE attestation (a real in_process run through the same surface) is recorded in
the session log per the cost gate.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.harness.grade import grade_inprocess  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_CASE_ID = "bench_uap5a_flip_demo_dosage_drift_84ee8f1e7442"
_CASE_SRC = _REPO / "examples" / "uap5a_flip_demo.jsonl"
_MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="
_FLAG = "WRONG_DOSAGE"


def _blocking_predictors(flag: str):
    """Per-role predictors that BLOCK (emit ``flag``) iff the authored-refinement
    marker is present — i.e. iff the role carries an assignment. No dspy / no network."""

    def make(_role):
        def _p(*, role_key_questions: str = "", **_kw):
            if _MARKER in role_key_questions:
                return {
                    "decision": "reject",
                    "findings": [{"taxonomy_code": flag, "evidence_spans": [{"quote": "450MG", "turn_ids": []}]}],
                }
            return {"decision": "approve", "findings": []}

        return _p

    return {role: make(role) for role in V2_ROLES}


def test_injected_path_projects_non_empty_model_reason_and_roster():
    ont = load_ontology()
    case = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert case is not None

    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments={"risk_judge": [_FLAG]},
        predictors=_blocking_predictors(_FLAG),
    )
    r = grade_inprocess(case, semantic_stage=stage)
    votes = r["semantic"]["judge_votes"]
    by_role = {v["judge_role"]: v for v in votes}

    # role/vote/findings were always populated — guard they stay populated (no regression).
    assert set(by_role) == set(V2_ROLES)
    risk = by_role["risk_judge"]
    assert risk["vote"] == "BLOCK"
    assert _FLAG in risk["findings"]

    # S-BS-66: model is no longer blank — it falls back to the seam's role name.
    assert all(v["model"] for v in votes), [v["model"] for v in votes]
    assert risk["model"] == "risk_judge"

    # S-BS-66: the BLOCKing judge carries a synthesized one-line reason (decision + codes);
    # a clean approve stays empty (nothing to justify).
    assert risk["reason"]
    assert _FLAG in risk["reason"]
    assert by_role["policy_judge"]["reason"] == ""

    # S-BS-66: the provenance roster is the real trio, not ["injected"].
    roster = (r.get("provenance") or {}).get("council_config", {}).get("judges")
    assert roster == list(V2_ROLES), roster
