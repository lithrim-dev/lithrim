"""Contract-preservation + grade-wire tests for the in-process v2 council
(WS-6c-AGENTIC, D2/D4 → A2/A3).

THE D2 CONTRACT MAP (the divergence note). The in-process spine is the
``pipeline/`` PRIMITIVE recompose (structural → semantic → artifact → verdict),
NOT a 1:1 port of the backend's 7-node ``compliance_workflow``. It calls
``council.evaluate()`` ONCE and uses the council's authoritative
``_apply_consensus`` directly. So the §4/§5 behavior contracts classify as
follows (each checked against ``compliance_workflow.py`` @ mvp-ready):

  - Council concurrency semaphore (§4#3): APPLIES — lives in the frozen council
    (``COMPLIANCE_COUNCIL_MAX_CONCURRENT_LLM``, ``compliance_council.py:58``),
    ported verbatim, survives.
  - Eval isolation (§4#4): seed-determinism honored via ``eval_mode`` + the
    ``run:local:case:<id>`` conversation_id (``local_pipeline.py``); the
    ``::eval::`` context_hash upsert is MOOT in-process (``NoOpProvenanceStore`` —
    no persistence this cycle; the real repository is WS-6d).
  - Two-phase disposition (§4#1): lives INSIDE the frozen ``_apply_consensus``;
    the workflow's preliminary→recompute is a defensive WRAPPER the primitive
    legitimately does not replicate (no ``_determine_disposition`` /
    ``_recompute_*`` exist in the bench council — confirmed by grep).
  - Gate safety policy (§5: P0-3 artifact-guard / FAST PATH / regex): WORKFLOW
    WRAPPER, SAFELY ABSENT. The backend gate (``compliance_workflow.py:785``) can
    ONLY approve-without-council; reject/needs_review always defer; an artifact
    present is forced to needs_review (``:767-780``, always-escalate). The
    primitive ALWAYS runs the full council, so "artifacts always escalate / gate
    can only approve" is VACUOUSLY satisfied → backend strictness <= bench
    strictness; no by-construction defect-pack case exists where the backend
    BLOCKS and the bench passes. Adding the gate would INTRODUCE the
    approve-without-council false-negative this HARD GATE exists to prevent.
    (Verified from source by the WS-6c-AGENTIC adjudication workflow, VD.)
  - Fatal vs non-fatal (§4#2, re-derived from the live 7 nodes — the stale §4
    names check_hipaa_compliance/evaluate_artifacts do NOT exist): the workflow
    routes to ``handle_error`` on ``state["status"] == "failed"``, set by
    ``run_council:1016`` / ``extract_evidence:1053`` / ``store_report:1496``;
    best-effort (swallow + log) by ``run_safety_prescreening``,
    ``run_confidence_gate:844``, and the HIPAA/clinical/medication sub-queries in
    ``retrieve_context``. The primitive uses its OWN error model (stage exception →
    WARN + ``council_error=True``; orchestrator/stages, shipped since M1/WS-0) — a
    DELIBERATE bench divergence, not a port gap.
  - Lockstep recompute (§5): MOOT — no divergent recompute path in-process; the
    primitive uses the authoritative ``_apply_consensus`` (byte-frozen, A4).

BACK-PORTING CAVEAT: the safe-direction divergence holds ONLY because the bench
always runs the full council. The gap would become real if someone later ports
the always-council expectation back into the backend WHILE keeping the fast
confidence gate — then a gate-approve could skip a council reject the bench
would catch. Keep the two coupled.

THE REGRESSION ORACLE (D4 / A2). The no-verdict-drift proof feeds the captured
live ``:8002`` v2 baseline's council output back through the in-process recompose
and asserts the verdict + composite + the S-BS-7 suppression reproduce. This
isolates RECOMPOSE fidelity from LLM non-determinism (the live-trio reproduction
is spot-checked by the single A5 live call). The only baseline↔in-process delta
is STAGE COVERAGE (in-process is semantic-only; the live baseline also ran
structural/artifact) — a documented milestone-scope delta, NOT a v1→v2 or
recompose-drift delta (the captured baseline is itself v2).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# grade_inprocess constructs LocalPipelineBackend → the council (openai/tenacity).
pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.harness.grade import grade_inprocess  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402
from lithrim_bench.runtime.pipeline.models import (  # noqa: E402
    Finding,
    JudgeVote,
    StageResult,
)

_REPO = Path(__file__).resolve().parents[4]
_CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
_BASELINE = _REPO / "tests" / "fixtures" / "ws0" / f"baseline.{_CASE_ID}.json"
_CASE_SRC = _REPO / "tests" / "fixtures" / "ws0" / f"case.{_CASE_ID}.jsonl"


def _baseline() -> dict:
    return json.loads(_BASELINE.read_text())


def _case() -> dict:
    c = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert c is not None, f"case {_CASE_ID} not found in {_CASE_SRC}"
    return c


def _semantic_stage_from(baseline: dict):
    """A fake semantic stage that REPLAYS the baseline's council output, so the
    in-process recompose runs on the exact live council result — isolating
    recompose fidelity from LLM non-determinism."""
    sem = baseline["semantic"]

    async def _stage(_request):
        sr = StageResult(
            status=sem["status"],
            findings=[Finding(**f) for f in sem.get("findings", [])],
            evidence=sem.get("evidence", []),
            judge_votes=[JudgeVote(**v) for v in (sem.get("judge_votes") or [])],
        )
        return sr, {"council_config": {"mode": "full", "replayed": True}}

    return _stage


def test_inprocess_dict_shape_matches_baseline_keys():
    """The grade_inprocess dict has the SAME top-level keys as the captured
    :8002 baseline — the frozen-seam shape that keeps ground/composite path-
    agnostic (§6/§7)."""
    base = _baseline()
    result = grade_inprocess(_case(), semantic_stage=_semantic_stage_from(base))
    assert set(result.keys()) == set(base.keys())
    assert set(result["semantic"]).issuperset(
        {"status", "findings", "evidence", "judge_votes"}
    )


def test_inprocess_reproduces_baseline_semantic_and_composite_verdict():
    """D4/A2: replaying the live baseline's council output through the in-process
    recompose reproduces verdict + gate_decision + composite + the S-BS-7
    suppression — the recompose introduces no verdict drift."""
    base = _baseline()
    case = _case()
    ont = load_ontology()

    result = grade_inprocess(case, semantic_stage=_semantic_stage_from(base))

    # worst-of (semantic-only) reproduces the baseline's semantic verdict; the
    # gate_decision derivation matches too.
    assert result["verdict"] == base["semantic"]["status"]  # BLOCK
    assert result["gate_decision"] == base["gate_decision"]  # escalate

    g_in = ground(result, case, ontology=ont)
    g_base = ground(base, case, ontology=ont)
    c_in = composite(g_in)
    c_base = composite(g_base)

    assert c_in["verdict"] == c_base["verdict"] == "reject"
    assert "FABRICATED_HISTORY" in c_in["active_findings"]
    # the S-BS-7 confident false positive is suppressed on the in-process path too
    suppressed = {s["finding"].get("code") for s in g_in.suppressed}
    assert "MEDICATION_NOT_IN_TRANSCRIPT" in suppressed


def test_inprocess_flows_through_ground_composite_offline():
    """A3 plumbing: a fresh in-process result flows ground→composite unchanged,
    deterministically and with no Azure call."""
    case = _case()

    async def _fake(_request):
        sr = StageResult(
            status="BLOCK",
            findings=[
                Finding(
                    type="semantic",
                    severity="HIGH",
                    code="FABRICATED_HISTORY",
                    detail="FABRICATED_HISTORY (judges=2)",
                )
            ],
            evidence=[
                {
                    "violation_code": "FABRICATED_HISTORY",
                    "judge": "faithfulness_judge",
                    "spans": [{"quote": "q", "turn_ids": []}],
                }
            ],
            judge_votes=[
                JudgeVote(
                    judge_role="faithfulness_judge",
                    vote="BLOCK",
                    confidence=0.99,
                    model="llama",
                    findings=["FABRICATED_HISTORY"],
                )
            ],
        )
        return sr, {"council_config": {"mode": "full"}}

    result = grade_inprocess(case, semantic_stage=_fake)
    c = composite(ground(result, case, ontology=load_ontology()))
    assert c["verdict"] == "reject"
    assert "FABRICATED_HISTORY" in c["active_findings"]
