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
    ``::eval::`` context_hash upsert is MOOT in-process — it is a
    ``store_report``/COMPLIANCE_REPORT concern the primitive never invokes, and
    provenance-store eval-isolation comes from ``pipeline_run_id`` uniqueness per run
    (the real SQLite repository landed in WS-6d / SqliteProvenanceStore).
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
import os
from datetime import date
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

# A5 live grade-wire (option-B addendum): the real v2 trio over grade_inprocess.
_DROP_ALLERGY_CASE_ID = "bench_scribe_v1_drop_allergy_805205594117"


def _ws0_dir() -> Path:
    """PACK-DIST-2 C2: the ws0 baseline + case + a5 fixture live with the healthcare pack
    (``../lithrim-pack-healthcare/fixtures/ws0/``), not in the CE tree. Resolve via the
    discovery seam; ``pytest.skip`` in a bare CE checkout (every reader here is NEEDS_PACK /
    Azure-gated). Self-contained — matches the vendored conftest's inline-discovery
    convention rather than importing the ``tests`` package from this subtree."""
    from lithrim_bench.harness import pack as _pack

    try:
        return _pack._pack_root("healthcare").parent / "fixtures" / "ws0"
    except FileNotFoundError:
        pytest.skip(
            "PACK-DIST-1: healthcare pack not discoverable (bare CE checkout) — the ws0 "
            "fixture lives with the pack; set LITHRIM_BENCH_PACKS_DIR or install "
            "lithrim-pack-healthcare"
        )


def _proof_case() -> Path:
    """The A5 live proof_case (relocated with the pack — PACK-DIST-1). Resolve via discovery;
    used only by the Azure-gated live smoke (default-skipped)."""
    from lithrim_bench.harness import pack as _pack

    try:
        return _pack._pack_root("healthcare").parent / "examples" / "proof_case.jsonl"
    except FileNotFoundError:
        pytest.skip("PACK-DIST-1: healthcare pack not discoverable — proof_case lives with the pack")
_AZURE_READY = os.environ.get("LITHRIM_LLM_PROVIDER") == "azure" and all(
    os.environ.get(k)
    for k in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3",
        "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
    )
)


def _baseline() -> dict:
    return json.loads((_ws0_dir() / f"baseline.{_CASE_ID}.json").read_text())


def _case() -> dict:
    case_src = _ws0_dir() / f"case.{_CASE_ID}.jsonl"
    c = load_case(_CASE_ID, source=str(case_src))
    assert c is not None, f"case {_CASE_ID} not found in {case_src}"
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
    agnostic (§6/§7). ``case_outcome`` (the named-outcome axis on
    ``PipelineResult``, additive at fc6d7ad) post-dates the pinned baseline, so
    the FULL exact contract is baseline-keys ∪ {case_outcome} — still equality,
    never a subset check."""
    base = _baseline()
    result = grade_inprocess(_case(), semantic_stage=_semantic_stage_from(base))
    assert set(result.keys()) == set(base.keys()) | {"case_outcome"}
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


@pytest.mark.skipif(
    not _AZURE_READY,
    reason="live grade_inprocess smoke: set LITHRIM_LLM_PROVIDER=azure + AZURE_OPENAI_* (separate go)",
)
def test_v2_trio_grade_inprocess_live():
    """A5: the REAL v2 trio scores proof_case:drop_allergy through grade_inprocess
    end-to-end (NO stage injection) -> reject. This is the in-suite real-council
    grade-wire coverage (S-BS-35b / critic C6) — every other test here injects a
    stage. Default-skips ($0); runs only with the Azure env (one explicit go). With
    WS6C_A5_CAPTURE=1 it writes the on-disk evidence fixture BEFORE asserting, so
    the artifact survives even a borderline assert.

    The recipe label is MISSING_ALLERGY but the live judges emit FABRICATED_ALLERGY
    / FABRICATED_HISTORY / HALLUCINATED_DETAIL / ... (the RECOMPOSITION_PLAN_ws6
    §8 risk-6 recipe!=emitted-code calibration signal), so the assertion is at the
    robust VERDICT level (reject), NOT the code level. The MISSING_ALLERGY
    one-strike is proven OFFLINE in test_consensus.py, not on this live run.
    """
    from lithrim_bench.runtime.council import llm_provider

    llm_provider.reset_clients()  # drop any client cached by the offline tests
    proof_case = _proof_case()
    case = load_case(_DROP_ALLERGY_CASE_ID, source=str(proof_case))
    assert case is not None, f"{_DROP_ALLERGY_CASE_ID} not in {proof_case}"

    result = grade_inprocess(case)  # LIVE: real v2 trio, no semantic_stage injection
    grounded = ground(result, case, ontology=load_ontology())
    comp = composite(grounded)

    votes = result["semantic"]["judge_votes"]
    per_judge = [
        {
            "judge_role": v["judge_role"],
            "model": v["model"],
            "decision": v["vote"],
            "confidence": v["confidence"],
            "finding_codes": v["findings"],
            # JudgeVote collapses per-judge errors; the aggregate is council_error below.
            "errors": [],
        }
        for v in votes
    ]

    if os.environ.get("WS6C_A5_CAPTURE") == "1":
        artifact = {
            "_meta": {
                "captured_by": "WS-6c-AGENTIC A5 (option-B addendum)",
                "captured_at": date.today().isoformat(),
                "case_id": _DROP_ALLERGY_CASE_ID,
                "case_source": "examples/proof_case.jsonl",
                "expected_safety_flags": case.get("expected_safety_flags"),
                "path": "grade_inprocess (in-process v2 trio, semantic-only, NoOpProvenanceStore)",
                "council_version": "v2",
                "note": (
                    "recipe label MISSING_ALLERGY != live emitted codes "
                    "(FABRICATED_*/HALLUCINATED_*) — the RECOMPOSITION_PLAN_ws6 §8 "
                    "risk-6 calibration signal. The MISSING_ALLERGY one-strike is "
                    "proven OFFLINE (test_consensus.py), not on this live run."
                ),
            },
            "verdict": result["verdict"],
            "gate_decision": result["gate_decision"],
            "composite_verdict": comp["verdict"],
            "composite_active_findings": comp["active_findings"],
            "council_error": result["provenance"].get("council_error"),
            "per_judge": per_judge,
            "cost_tokens": result["provenance"].get("cost_tokens"),
        }
        (_ws0_dir() / "a5_live.drop_allergy.json").write_text(
            json.dumps(artifact, indent=2) + "\n"
        )

    # Robust verdict-level assertions: the grade-wire works live; the defect rejects.
    assert result["verdict"] == "BLOCK"
    assert comp["verdict"] == "reject"
    by_role = {v["judge_role"]: v for v in votes}
    assert len(by_role) == 3, "the live v2 trio must produce 3 judge votes"
    # Mistral (policy_judge) exposes no logprobs -> confidence None, never synthesized.
    assert by_role["policy_judge"]["confidence"] is None
