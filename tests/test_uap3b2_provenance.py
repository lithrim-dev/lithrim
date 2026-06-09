"""UAP-3b-2 — S-BS-72: the withstands ruling embedded in the run-PROVENANCE blob
(stream-2, ``GET /v1/runs/{id}/audit``), plus the re-pinned frozen-seam 0-delta and
the A5 by-construction guard.

The S-BS-72 integration test is dspy/openai-gated (the authored trio's seam), $0 via
injected per-role predictors (no Azure call) + an injected ``SqliteProvenanceStore``
(a tmp doc-shim DB). The frozen + guard + BFF-projection tests run on default deps /
the [bff] extra.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.runtime.council.withstands import apply_withstands_gate

from ._seam_freeze import (
    assert_clinical_ontology_seam_frozen,
    assert_compliance_council_prompts_dir_relocated_only,
    assert_council_roles_relocated_only,
    assert_judges_dspy_consensus_seam_frozen,
    assert_seed_ontology_path_relocated_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"

# the exhibit FP: a Tier-1 code OUTSIDE risk_judge's lens, sole-owned by policy_judge.
_FP_CODE = "PHI_DISCLOSURE_PRE_VERIFICATION"
_FP_ROLE = "risk_judge"
_CLEAN_CASE_ID = "bench_scribe_v1_clean_negative_aaecd73c3bcf"
_CLEAN_CASE_SRC = REPO_ROOT / "examples" / "proof_case.jsonl"


def _seam(role: str, decision: str, codes: list[str]) -> dict:
    return {
        "model": role,
        "decision": decision,
        "confidence": 0.9,
        "findings": [
            {"taxonomy_code": c, "evidence_spans": [{"quote": "x", "turn_ids": []}]} for c in codes
        ],
        "errors": [],
    }


def _clean_case() -> dict:
    return {
        "transcript": "Agent verified identity first, then discussed the visit.",
        "artifacts": [{"content": "n"}],
    }


# ─────────────────────────── frozen + A5 guard (default deps) ───────────────────────


def test_frozen_seam_zero_delta():
    """A4 — the D2 provenance work + the D3 entity surface add ZERO lines to the frozen
    consensus seam + the per-judge seam + the metric + the committed seeds.

    BYOC-1: judges_dspy.py is no longer whole-file-pinned — ``build_judge_lm`` +
    ``build_trio`` are the authorized provider-seam change (driver A6). Its CONSENSUS seam
    is instead asserted byte-frozen by :func:`assert_judges_dspy_consensus_seam_frozen`."""
    # PACK-2: compliance_council.py is no longer whole-file-pinned — the live council
    # globs the role prompts itself, so relocating council_roles/ into the pack required
    # an AUTHORIZED path-only carve-out of its _ROLE_PROMPTS_DIR; and council_roles/ itself
    # relocated. Both are asserted by the carve-out guards below. judge_metric.py stays
    # whole-file-frozen (the lenses are 2b).
    frozen = [
        "lithrim_bench/runtime/council/judge_metric.py",
    ]
    out = subprocess.run(
        ["git", "diff", "acc4973", "HEAD", "--", *frozen],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout == "", f"frozen seam drifted:\n{out.stdout[:2000]}"
    assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)
    assert_compliance_council_prompts_dir_relocated_only(REPO_ROOT)
    assert_council_roles_relocated_only(REPO_ROOT)
    # PACK-1: ws0_default.json is no longer whole-file-pinned — the healthcare-pack
    # relocation gives it a behavior-preserving, path-ONLY ontology_path update; every
    # other field stays byte-frozen vs acc4973 (asserted precisely here).
    assert_seed_ontology_path_relocated_only(REPO_ROOT, "data/config/agents/ws0_default.json")
    # clinical_v1.json's consensus/owner seam stays frozen; only verification_contracts
    # may grow additively (GROUND-FLOOR-1's record_presence contract).
    assert_clinical_ontology_seam_frozen(REPO_ROOT)


def test_gate_cannot_relabel_true_case():
    """A5 (re-pinned) — a genuinely-correct in-lens finding is NEVER suppressed: risk
    raises WRONG_DOSAGE (its own Tier-1 lens code), it withstands, verdict stays
    reject. The S-BS-72/A6 work does not weaken the by-construction invariant."""
    ont = load_ontology()
    results = [
        _seam("risk_judge", "reject", ["WRONG_DOSAGE"]),
        _seam("policy_judge", "approve", []),
        _seam("faithfulness_judge", "approve", []),
    ]
    corrected, decisions = apply_withstands_gate(results, ontology=ont, case=_clean_case())
    assert [f["taxonomy_code"] for f in corrected[0]["findings"]] == ["WRONG_DOSAGE"]
    assert corrected[0]["decision"] == "reject"
    assert decisions[0].decision == "withstand"


# ─────────────────────────── S-BS-72 blob embed (dspy/openai-gated) ─────────────────


def _fp_predictors(roles):
    def make(role):
        def _p(*, role_key_questions: str = "", **_kw):
            if role == _FP_ROLE:
                return {
                    "decision": "reject",
                    "findings": [
                        {"taxonomy_code": _FP_CODE, "evidence_spans": [{"quote": "x", "turn_ids": []}]}
                    ],
                }
            return {"decision": "approve", "findings": []}

        return _p

    return {role: make(role) for role in roles}


def test_S_BS_72_provenance_blob_carries_withstands_ruling(tmp_path):
    """A2 — a graded in_process run's SqliteProvenanceStore blob carries the per-judge
    withstands ruling ``{role, signals_weighed, decision, what_failed}``, so
    ``GET /v1/runs/{id}/audit`` (stream-2) shows it. $0: injected predictors (no Azure)
    + an injected tmp store. The real grade_inprocess saves the blob; run_eval's
    post-save embed patches it; find_by_id reads it back."""
    pytest.importorskip("dspy")
    pytest.importorskip("openai")
    from lithrim_bench.harness.collections import PIPELINE_RUNS
    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.picklist import load_case
    from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
    from lithrim_bench.runtime.council.judges_dspy import V2_ROLES
    from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore

    if str(REPO_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval

    db = tmp_path / "coll.sqlite"
    ont = load_ontology()
    case = load_case(_CLEAN_CASE_ID, source=str(_CLEAN_CASE_SRC))
    assert case is not None

    sink: list = []
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_fp_predictors(V2_ROLES),
        apply_gate=True,
        decisions_sink=sink,
    )
    result = grade_inprocess(
        case, semantic_stage=stage, provenance_store=SqliteProvenanceStore(db_path=db)
    )
    run_id = (result.get("provenance") or {}).get("pipeline_run_id")
    assert run_id, "in_process run must carry a pipeline_run_id"
    assert sink, "the gate must have run pre-consensus (non-empty sink)"

    # before the embed the blob has no withstands ruling (the orchestrator save is FP-blind).
    pre = PIPELINE_RUNS.get(run_id, db_path=db)
    assert pre is not None and "withstands_decisions" not in pre

    run_eval._embed_withstands_in_blob(run_id, sink, in_process=True, collections_db=db)

    blob = PIPELINE_RUNS.get(run_id, db_path=db)
    assert blob is not None
    rulings = blob["withstands_decisions"]
    assert len(rulings) == len(sink)
    risk_ruling = next(r for r in rulings if r["role"] == _FP_ROLE)
    assert set(risk_ruling) == {"role", "signals_weighed", "decision", "what_failed"}
    assert set(risk_ruling["signals_weighed"]) == {"ontology_rules", "validator_outputs"}
    assert risk_ruling["decision"] == "corrected"  # the out-of-lens FP was corrected
    # the row id + fk are preserved across the re-insert (same doc round-trips).
    assert blob.get("pipeline_run_id") == run_id


# ─────────────────────────── BFF projection ([bff] extra) ───────────────────────────


def test_run_audit_report_projects_withstands():
    """The §2B stream-2 report surfaces the embedded ruling (a 1-line projection); a
    non-gated run (no key) degrades to an empty list, never a KeyError."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    if str(REPO_ROOT / "apps" / "bff") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "apps" / "bff"))
    import app as bff

    doc = {
        "verdict": "approve",
        "stage_results": {"semantic": {"judge_votes": []}},
        "withstands_decisions": [
            {"role": "risk_judge", "signals_weighed": {}, "decision": "corrected", "what_failed": []}
        ],
    }
    report = bff._run_audit_report(doc, "run-x")
    assert report["withstands"] == doc["withstands_decisions"]
    # a run with no ruling → empty list (back-compat).
    assert bff._run_audit_report({"stage_results": {}}, "run-y")["withstands"] == []
