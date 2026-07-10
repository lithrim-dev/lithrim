"""WS-6d: real SQLite provenance store (retire Mongo) — D4 / A1–A3.

A1 (real SQLite persistence): ``SqliteProvenanceStore.save`` persists a
    ``PipelineProvenance`` through the stdlib doc-shim; ``find_by_id`` round-trips
    it (no Mongo, no new dep). Default-deps (pydantic only, no openai).
A2 (eval-isolation invariant): re-running the same case writes a fresh uuid4
    ``pipeline_run_id`` -> distinct, non-colliding rows; persisting the same
    ``pipeline_run_id`` twice upserts to one row (the doc-shim's idempotent
    ``ON CONFLICT(id) DO UPDATE``). Default-deps.
A3 (frozen contract — the load-bearing gate): the in-process grade record is
    byte-identical with ``SqliteProvenanceStore`` vs a Null store. Persistence is a
    pure fire-and-forget side-effect behind ``save``; the returned ``PipelineResult``
    dict is unchanged save the inherently per-run fields (``pipeline_run_id`` /
    ``timestamp`` / ``duration_ms``), which a NoOp-vs-NoOp control proves are the
    *only* run-to-run nondeterminism — so the on-vs-off equality is not an artifact
    of over-stripping. Needs ``openai`` (the grade_inprocess import chain), so it is
    function-level ``importorskip``-gated: runs on debuglithrim, skips on default
    deps (A1/A2 still run).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lithrim_bench.harness.collections import PIPELINE_RUNS
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.picklist import load_case
from lithrim_bench.runtime.pipeline.models import (
    Finding,
    JudgeVote,
    PipelineProvenance,
    StageResult,
)
from lithrim_bench.runtime.pipeline.provenance import (
    NoOpProvenanceStore,
    SqliteProvenanceStore,
)
from tests._house_fixture import HOUSE_CASE_ID as _CASE_ID
from tests._house_fixture import HOUSE_CASE_PATH as _CASE_SRC

_REPO = Path(__file__).resolve().parents[1]

# Inherently per-run (unseeded) fields — vary between any two evaluate() calls,
# persistence on or off. The A3 control run proves this set is exhaustive.
_NONDET = {"pipeline_run_id", "timestamp", "duration_ms"}


def _prov(run_id: str, *, org_id: str = "orgX", **over) -> PipelineProvenance:
    fields = {
        "pipeline_run_id": run_id,
        "org_id": org_id,
        "timestamp": datetime(2026, 6, 2, tzinfo=timezone.utc),
        "request_hash": "h1",
        "stages_executed": ["semantic", "verdict"],
    }
    fields.update(over)
    return PipelineProvenance(**fields)


# ── A1 ──────────────────────────────────────────────────────────────────────


def test_a1_save_then_find_by_id_round_trips(tmp_path):
    store = SqliteProvenanceStore(db_path=tmp_path / "prov.sqlite")
    prov = _prov("run-A", org_id="orgX")

    asyncio.run(store.save(prov, agent_id="agent-7"))
    got = asyncio.run(store.find_by_id("run-A"))

    # Full round-trip fidelity: the persisted doc IS the json-mode model dump plus
    # the orchestrator-supplied ``agent_id`` extra field (no schema drift).
    assert got == {**prov.model_dump(mode="json"), "agent_id": "agent-7"}


def test_a1_save_without_agent_id_omits_the_field(tmp_path):
    store = SqliteProvenanceStore(db_path=tmp_path / "prov.sqlite")
    asyncio.run(store.save(_prov("run-B")))
    got = asyncio.run(store.find_by_id("run-B"))
    assert got is not None and "agent_id" not in got


def test_a1_noop_and_missing_id_return_none(tmp_path):
    store = SqliteProvenanceStore(db_path=tmp_path / "prov.sqlite")
    assert asyncio.run(store.find_by_id("never-saved")) is None
    # NoOp persists nothing and its read path is always None (the hermetic default).
    asyncio.run(NoOpProvenanceStore().save(_prov("run-C"), agent_id="x"))
    assert asyncio.run(NoOpProvenanceStore().find_by_id("run-C")) is None


# ── A2 (eval-isolation invariant) ─────────────────────────────────────────────


def test_a2_distinct_run_ids_write_distinct_rows(tmp_path):
    db = tmp_path / "prov.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    # Two evaluate()s of the same case get two fresh uuid4 pipeline_run_ids.
    asyncio.run(store.save(_prov("run-1", org_id="orgZ")))
    asyncio.run(store.save(_prov("run-2", org_id="orgZ")))

    assert len(PIPELINE_RUNS.find_by_fk("orgZ", db_path=db)) == 2
    assert asyncio.run(store.find_by_id("run-1")) is not None
    assert asyncio.run(store.find_by_id("run-2")) is not None


def test_a2_same_run_id_upserts_to_one_row(tmp_path):
    db = tmp_path / "prov.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    asyncio.run(store.save(_prov("run-X", org_id="orgZ", request_hash="h1")))
    asyncio.run(store.save(_prov("run-X", org_id="orgZ", request_hash="h2")))

    rows = PIPELINE_RUNS.find_by_fk("orgZ", db_path=db)
    assert len(rows) == 1  # upsert, not append
    assert asyncio.run(store.find_by_id("run-X"))["request_hash"] == "h2"  # last write wins


# ── A3 (frozen contract — the load-bearing gate) ──────────────────────────────


def _fake_semantic_stage():
    """A deterministic council stand-in so the orchestrator runs with no Azure call
    and the only run-to-run variance is the unseeded provenance fields."""

    async def _stage(_request):
        sr = StageResult(
            status="BLOCK",
            findings=[
                Finding(
                    type="semantic",
                    severity="HIGH",
                    code="FABRICATED_HISTORY",
                    detail="FABRICATED_HISTORY (judges=1)",
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

    return _stage


def _strip_nondet(obj):
    """Recursively drop the inherently per-run keys so two runs are comparable."""
    if isinstance(obj, dict):
        return {k: _strip_nondet(v) for k, v in obj.items() if k not in _NONDET}
    if isinstance(obj, list):
        return [_strip_nondet(x) for x in obj]
    return obj


def test_a3_grade_record_byte_identical_persistence_on_vs_off(tmp_path):
    pytest.importorskip("openai")  # grade_inprocess -> LocalPipelineBackend -> council
    pytest.importorskip("tenacity")

    case = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert case is not None, f"case {_CASE_ID} not found in {_CASE_SRC}"
    stage = _fake_semantic_stage()

    db = tmp_path / "a3.sqlite"
    sqlite_store = SqliteProvenanceStore(db_path=db)

    r_sqlite = grade_inprocess(case, semantic_stage=stage, provenance_store=sqlite_store)
    r_noop = grade_inprocess(case, semantic_stage=stage, provenance_store=NoOpProvenanceStore())
    r_noop2 = grade_inprocess(case, semantic_stage=stage, provenance_store=NoOpProvenanceStore())

    # The A3 claim: persistence does not change the deterministic grade record.
    assert json.dumps(_strip_nondet(r_sqlite), sort_keys=True) == json.dumps(
        _strip_nondet(r_noop), sort_keys=True
    )
    # Control: two Null-store runs match after the same strip -> _NONDET is exactly
    # the run-to-run nondeterminism, so the equality above is not an over-strip
    # artifact. And the raw dicts DO differ (the runs are real, not memoised).
    assert json.dumps(_strip_nondet(r_noop), sort_keys=True) == json.dumps(
        _strip_nondet(r_noop2), sort_keys=True
    )
    assert r_sqlite != r_noop

    # The side-effect actually happened on the Sqlite path (so we compared on-vs-off,
    # not off-vs-off): exactly one row, keyed on the run's pipeline_run_id.
    run_id = r_sqlite["provenance"]["pipeline_run_id"]
    assert len(PIPELINE_RUNS.find_by_fk("local", db_path=db)) == 1
    assert asyncio.run(sqlite_store.find_by_id(run_id)) is not None
