"""LAYER0-READ-1 — the read layer serves post-floor truth.

The persisted PipelineProvenance blob carried only the PRE-floor verdict/findings, so
every read surface (/v1/runs, /v1/runs/{id}/audit) was blind to the grounding floor —
the exact hole behind the 2026-07-01 "floor dormant" mis-diagnosis. This cycle folds the
grounded block into the blob at the existing post-save patch seam (`_enrich_run_blob`,
above the frozen consensus) and projects it ADDITIVELY in the read API (existing keys
byte-unchanged — blob `verdict` is pipeline-domain approve/reject while the grounded
verdict is composite-domain BLOCK/WARN/PASS, so the headline is never silently swapped;
the post-floor truth rides labeled `grounded*` fields).

Hermetic + $0 (the test-pattern of test_run_audit_trail_grade_path.py): replay grades the
house fixture end-to-end; the in_process fold is proven at the unit level against the SAME
store seam `run()` calls; the read projections are pure-function tests.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore
from tests._house_fixture import house_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402

_GROUNDED = {
    "verdict": "BLOCK",
    "original_verdict": "WARN",
    "active": [{"code": "FABRICATED_CLAIM"}],
    "suppressed": [
        {
            "code": "HALLUCINATED_DETAIL",
            "contract": "snomed-subsumption/v1",
            "disproved": True,
            "matched_token": "migraine",
            "evidence": ["37796009"],
            "reason": "documented condition subsumes the flagged term",
        }
    ],
    "ungrounded": [],
    "skipped_non_gradeable": [],
    "floor_blocks": [],
}


def _seed_blob(db, run_id: str) -> None:
    asyncio.run(
        SqliteProvenanceStore(db_path=db).save_blob(
            {"pipeline_run_id": run_id, "verdict": "reject", "findings": []}
        )
    )


# ── L1: the post-save patch stamps the grounded block (in_process unit level) ──────────
def test_l1_enrich_stamps_grounded_block(tmp_path):
    db = tmp_path / "collections.sqlite"
    _seed_blob(db, "run-l1")
    run_eval._enrich_run_blob(
        "run-l1",
        [],
        in_process=True,
        case_id="c1",
        agent_id="a1",
        grade_sig="sig",
        grade_path="in_process",
        collections_db=db,
        grounded_block=_GROUNDED,
    )
    blob = asyncio.run(SqliteProvenanceStore(db_path=db).find_by_id("run-l1"))
    assert blob["grounded"] == _GROUNDED


# ── L2: the replay path folds grounded end-to-end ($0 house fixture) ────────────────────
def test_l2_replay_blob_carries_grounded(tmp_path):
    db = tmp_path / "collections.sqlite"
    agent = house_agent()
    rec = run_eval.run(agent, collections_db=db, out_dir=tmp_path / "o")
    run_id = rec["result"]["provenance"]["pipeline_run_id"]
    blob = asyncio.run(SqliteProvenanceStore(db_path=db).find_by_id(run_id))
    assert blob is not None
    g = blob.get("grounded")
    assert g is not None, "a replay blob must carry the grounded block (the read-trust fold)"
    # the blob's grounded block == the API record's grounded block (single source shape)
    assert g["verdict"] == rec["grounded"]["verdict"]
    assert g["suppressed"] == rec["grounded"]["suppressed"]
    assert [f.get("code") for f in g["active"]] == [
        f.get("code") for f in rec["grounded"]["active"]
    ]


# ── L3/L4: the read projections (pure) ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def bff():
    _BFF = REPO_ROOT / "apps" / "bff"
    if str(_BFF) not in sys.path:
        sys.path.insert(0, str(_BFF))
    pytest.importorskip("fastapi")
    import app as bff_mod

    return bff_mod


def _doc(with_grounded: bool) -> dict:
    doc = {
        "pipeline_run_id": "r1",
        "verdict": "reject",
        "gate_decision": "escalate",
        "agent_id": "a1",
        "case_id": "c1",
        "timestamp": "2026-07-02T00:00:00Z",
        "findings": [{"code": "HALLUCINATED_DETAIL"}, {"code": "FABRICATED_CLAIM"}],
        "stage_results": {"semantic": {"judge_votes": []}},
    }
    if with_grounded:
        doc["grounded"] = _GROUNDED
    return doc


def test_l3_audit_projects_grounded_additively(bff):
    report = bff._run_audit_report(_doc(True), "r1")
    assert report["verdict"] == "reject"  # existing key untouched (pipeline domain)
    assert report["grounded_verdict"] == "BLOCK"
    g = report["grounded"]
    assert g["original_verdict"] == "WARN"
    assert [f["code"] for f in g["active"]] == ["FABRICATED_CLAIM"]
    assert g["suppressed"][0]["contract"] == "snomed-subsumption/v1"
    assert g["suppressed"][0]["disproved"] is True


def test_l3_audit_legacy_blob_unchanged(bff):
    legacy = bff._run_audit_report(_doc(False), "r1")
    assert legacy["verdict"] == "reject"
    assert legacy["findings"] == [{"code": "HALLUCINATED_DETAIL"}, {"code": "FABRICATED_CLAIM"}]
    assert legacy["grounded"] is None
    assert legacy["grounded_verdict"] is None


def test_l4_run_summary_dual(bff):
    row = bff._run_summary(_doc(True))
    assert row["verdict"] == "reject"
    assert row["grounded_verdict"] == "BLOCK"
    assert row["floor_suppressed"] == 1
    legacy = bff._run_summary(_doc(False))
    assert legacy["verdict"] == "reject"
    assert legacy["grounded_verdict"] is None
    assert legacy["floor_suppressed"] is None


# ── L5: token-usage capture (cost_tokens root fix) — the UNFROZEN sampling seam ─────────
# NOT Judge.forward: ``class Judge`` is byte-frozen vs acc4973 (tests/_seam_freeze.py), so
# the capture lives in sampling.judge_call and the authored stage folds it onto the seam
# dict — the exact placement pattern the sampling telemetry already uses.
class _FakeLM:
    def __init__(self):
        self.history: list[dict] = []


class _FakePredict:
    """A predictor whose call appends a litellm-shaped history entry to its LM."""

    def __init__(self, usage=None):
        self.lm = _FakeLM()
        self._usage = usage

    def __call__(self, **kwargs):
        entry = {}
        if self._usage is not None:
            entry["usage"] = self._usage
        self.lm.history.append(entry)
        return {"decision": "approve", "findings": [], "reason": "ok"}


def test_l5_judge_call_captures_usage_from_lm_history_delta():
    from lithrim_bench.runtime.council.sampling import judge_call

    fake = _FakePredict({"prompt_tokens": 120, "completion_tokens": 30})
    jr = judge_call("t", model=None, k=1, artifact="a", predict=fake)
    assert jr.usage == {"input_tokens": 120, "output_tokens": 30}


def test_l5_no_usage_means_none_and_no_seam_key():
    from lithrim_bench.runtime.council.sampling import judge_call

    jr = judge_call("t", model=None, k=1, artifact="a", predict=_FakePredict(None))
    assert jr.usage is None


def test_l5_authored_evaluator_folds_usage_onto_seam_dicts():
    """Mirror of test_authored_evaluator_carries_sampling_telemetry: a JudgeResult with
    usage reaches every per-judge seam dict, where the frozen stages.py cost sum reads it."""
    from lithrim_bench.harness.pack import pack_production_judges
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator
    from lithrim_bench.runtime.council.sampling import JudgeResult

    roles = list(pack_production_judges())
    block = JudgeResult(
        score_mean=1.0, score_variance=0.0, scores_raw=[1.0], k=1,
        rationale="r", decision="approve", findings=[], _raw_response=None,
        usage={"input_tokens": 200, "output_tokens": 40},
    )
    predictors = {r: (lambda **kw: block) for r in roles}
    evaluator = build_authored_evaluator(
        ontology=None, assignments=None, predictors=predictors, apply_gate=False
    )
    out = evaluator({"call_context": {"transcript": "t"}, "artifacts": [{"content": "a"}]})
    models = out["models"]
    assert models, "expected at least one per-judge seam dict"
    for m in models:
        assert m["usage"] == {"input_tokens": 200, "output_tokens": 40}


# ── L5 critic close-out (coverage gaps a-c from the cold critique) ───────────────────────
def test_l5_usage_captured_on_k_gt_1_and_degenerate_branches():
    from lithrim_bench.runtime.council.sampling import judge_call

    # (a) the k>1 return still stamps usage
    fake = _FakePredict({"prompt_tokens": 300, "completion_tokens": 60})
    jr = judge_call("t", model=None, k=3, artifact="a", predict=fake)
    assert jr.usage == {"input_tokens": 300, "output_tokens": 60}

    # (a) the degenerate all-empty return stamps usage too — the failed call still spent
    class _EmptyDecision(_FakePredict):
        def __call__(self, **kwargs):
            self.lm.history.append({"usage": self._usage})
            return {"decision": "", "findings": []}

    jr2 = judge_call(
        "t", model=None, k=3, artifact="a",
        predict=_EmptyDecision({"prompt_tokens": 50, "completion_tokens": 5}),
    )
    assert jr2.k == 0 and jr2.usage == {"input_tokens": 50, "output_tokens": 5}


def test_l5_fold_usage_never_clobbers_and_never_fabricates():
    from lithrim_bench.runtime.council.authored_stage import _fold_usage
    from lithrim_bench.runtime.council.sampling import JudgeResult

    jr = JudgeResult(
        score_mean=1.0, score_variance=0.0, scores_raw=[1.0], k=1,
        usage={"input_tokens": 9, "output_tokens": 9},
    )
    # (b) a pre-existing usage on the seam dict survives the fold
    r = {"model": "risk_judge", "usage": {"input_tokens": 1, "output_tokens": 2}}
    _fold_usage(r, jr)
    assert r["usage"] == {"input_tokens": 1, "output_tokens": 2}
    # and absent JudgeResult usage never fabricates a key
    r2 = {"model": "risk_judge"}
    _fold_usage(r2, JudgeResult(score_mean=1.0, score_variance=0.0))
    assert "usage" not in r2


def test_l5_usage_delta_tolerates_non_dict_history_entries():
    from lithrim_bench.runtime.council.sampling import _usage_delta

    class _LM:
        history = [
            "a-string-entry",
            {"usage": {"prompt_tokens": 10, "completion_tokens": 2}},
            {"no_usage_key": True},
        ]

    # (c) mixed-shape history: no raise, only dict entries with usage summed
    assert _usage_delta(_LM(), 0) == {"input_tokens": 10, "output_tokens": 2}
