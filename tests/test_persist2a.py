"""PERSIST-2a: versioned provenance blob (SQLite temporal) + replay-from-provenance
+ freshness guard. A1–A6 (driver §5), written RED before the implementation.

A1 (append-only versioning; S-BS-68 fixed)
    - distinct ``pipeline_run_id`` grades for the same ``(agent, case_id)`` are RETAINED
      as versions (the live table stays append-only — WS-6d ``test_a2`` is preserved).
    - a SAME-id re-insert (the S-BS-72 withstands re-embed / replay re-run) archives the
      prior row into ``pipeline_runs_history`` with its ``created_at`` PRESERVED, and the
      live row keeps first-write ``created_at`` (the S-BS-68 last-write-wins fix, scoped to
      the PIPELINE_RUNS tier).
A2 (addressability)
    ``latest_for(agent, case_id)`` returns the head; ``list_versions`` returns all versions
    newest-first; ``case_id`` is persisted on the blob (absent before this phase). NoOp →
    None/[].
A3 (shape adapter)
    ``provenance_to_result(blob)`` reconstructs a ``PipelineResult``-shaped dict from the
    persisted ``provenance`` sub-tree that ``ground``/``composite`` consume to the SAME
    composite the original baseline grounds to.
A4 (replay-from-provenance — the aha)
    with ``dataset.baseline is None``, ``run_eval.run`` resolves the persisted head →
    adapts → returns a $0 replay (no ``SystemExit``) whose composite matches the captured
    grade.
A5 (freshness guard)
    a head carries a grade signature; when the current config's signature differs the head
    is STALE → replay-resolve surfaces the re-grade path instead of serving it (drift-aware
    default).
A6 (frozen contract / moat)
    versioning is a pure side-effect scoped to the provenance tier (the four config
    collections are untouched); the in_process record is byte-identical store on/off; the
    consensus seam is 0-delta vs ``acc4973``.

A3/A4/A5 use the neutral in-repo ``_core`` house fixture (default-deps, pack-free,
hermetic). A6's byte-identical gate needs ``openai`` (the grade_inprocess chain), so it is
``importorskip``-gated like WS-6d A3.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lithrim_bench.harness.collections import COLLECTIONS, PIPELINE_RUNS
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.replay import (
    grade_signature,
    is_fresh,
    provenance_to_result,
)
from lithrim_bench.harness.report import composite
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
from tests._house_fixture import (
    HOUSE_BASELINE_PATH,
    HOUSE_CASE_ID,
    HOUSE_CASE_PATH,
    HOUSE_ONTOLOGY_PATH,
    house_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402


def _prov(run_id: str, *, org_id: str = "orgX", verdict: str = "WARN", **over) -> PipelineProvenance:
    """A minimal valid provenance whose ``stage_results['semantic']`` carries the
    evidence ``ground()`` reads (so the adapter has something to promote)."""
    semantic = StageResult(
        status="WARN",
        findings=[Finding(type="semantic", severity="LOW", code="X", detail="X (judges=1)")],
        evidence=[{"violation_code": "X", "judge": "j", "spans": [{"quote": "q", "turn_ids": []}]}],
        judge_votes=[JudgeVote(judge_role="j", vote="WARN", confidence=0.5, model="m", findings=["X"])],
    )
    fields = {
        "pipeline_run_id": run_id,
        "org_id": org_id,
        "timestamp": datetime(2026, 6, 18, tzinfo=timezone.utc),
        "request_hash": "h",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": semantic},
        "verdict": verdict,
        "gate_decision": "pass",
        "findings": [],
    }
    fields.update(over)
    return PipelineProvenance(**fields)


def _live_row(db: Path, run_id: str):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT created_at, json FROM pipeline_runs WHERE id = ?", (run_id,)
        ).fetchone()
    finally:
        conn.close()


def _history_rows(db: Path) -> list[dict]:
    """The ``pipeline_runs_history`` archive rows; [] when the table does not exist yet
    (the RED state — so the assertion fails cleanly, not with an OperationalError)."""
    conn = sqlite3.connect(db)
    try:
        try:
            rows = conn.execute(
                "SELECT original_id, json, created_at FROM pipeline_runs_history ORDER BY hist_id"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()
    return [{"original_id": r[0], "json": r[1], "created_at": r[2]} for r in rows]


def _agent_no_baseline(name: str = "persist2a_test"):
    """The neutral house agent with ``baseline=None`` — an ingested/live-only case whose
    only $0 path is replay-from-provenance."""
    agent = house_agent()
    ds = dataclasses.replace(agent.dataset, baseline=None)
    return dataclasses.replace(agent, name=name, dataset=ds)


def _ontology_dict() -> dict:
    return json.loads(HOUSE_ONTOLOGY_PATH.read_text())


# ── A1 (append-only versioning; S-BS-68 fixed) ────────────────────────────────


def test_provenance_versions_are_append_only(tmp_path):
    db = tmp_path / "prov.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    asyncio.run(store.save(_prov("run-1", verdict="WARN"), agent_id="ag", case_id="c1"))
    asyncio.run(store.save(_prov("run-2", verdict="BLOCK"), agent_id="ag", case_id="c1"))

    versions = asyncio.run(store.list_versions("ag", "c1"))
    assert [v["pipeline_run_id"] for v in versions] == ["run-2", "run-1"]  # newest-first, both kept
    # the live table is NOT collapsed (WS-6d isolation invariant preserved)
    assert asyncio.run(store.find_by_id("run-1")) is not None
    assert asyncio.run(store.find_by_id("run-2")) is not None


def test_same_id_reinsert_archives_prior_and_preserves_created_at(tmp_path):
    db = tmp_path / "prov.sqlite"
    doc_v1 = _prov("R", verdict="WARN").model_dump(mode="json")
    PIPELINE_RUNS.insert(doc_v1, db_path=db)
    created_1, _ = _live_row(db, "R")
    assert _history_rows(db) == []  # nothing archived on the first write

    doc_v2 = _prov("R", verdict="BLOCK").model_dump(mode="json")
    PIPELINE_RUNS.insert(doc_v2, db_path=db)

    # the live row is updated to v2 BUT keeps its first-write created_at (S-BS-68 fixed)
    created_2, live_json = _live_row(db, "R")
    assert json.loads(live_json)["verdict"] == "BLOCK"
    assert created_2 == created_1

    # the prior version is archived, created_at PRESERVED (not re-stamped)
    hist = _history_rows(db)
    assert len(hist) == 1
    assert hist[0]["original_id"] == "R"
    assert json.loads(hist[0]["json"])["verdict"] == "WARN"
    assert hist[0]["created_at"] == created_1


# ── A2 (addressability) ───────────────────────────────────────────────────────


def test_latest_for_and_list_versions_address_by_agent_case(tmp_path):
    db = tmp_path / "prov.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    asyncio.run(store.save(_prov("r1"), agent_id="ag", case_id="c1"))
    asyncio.run(store.save(_prov("r2"), agent_id="ag", case_id="c1"))
    asyncio.run(store.save(_prov("r3"), agent_id="ag", case_id="c2"))

    head = asyncio.run(store.latest_for("ag", "c1"))
    assert head["pipeline_run_id"] == "r2"
    assert head["case_id"] == "c1"  # case_id persisted + addressable (absent before this phase)
    assert head["agent_id"] == "ag"

    assert [v["pipeline_run_id"] for v in asyncio.run(store.list_versions("ag", "c1"))] == ["r2", "r1"]
    assert [v["pipeline_run_id"] for v in asyncio.run(store.list_versions("ag", "c2"))] == ["r3"]
    assert asyncio.run(store.latest_for("ag", "nope")) is None

    assert asyncio.run(NoOpProvenanceStore().latest_for("ag", "c1")) is None
    assert asyncio.run(NoOpProvenanceStore().list_versions("ag", "c1")) == []


# ── A3 (shape adapter) ────────────────────────────────────────────────────────


def test_provenance_to_result_round_trips():
    baseline = json.loads(HOUSE_BASELINE_PATH.read_text())
    blob = baseline["provenance"]
    adapted = provenance_to_result(blob)

    assert adapted["verdict"] == blob["verdict"]
    assert adapted["gate_decision"] == blob["gate_decision"]
    assert adapted["findings"] == blob["findings"]
    assert adapted["semantic"] == blob["stage_results"]["semantic"]
    assert adapted["provenance"] == blob

    case = load_case(HOUSE_CASE_ID, source=str(HOUSE_CASE_PATH))
    ontology = load_ontology(HOUSE_ONTOLOGY_PATH)
    c_orig = composite(ground(baseline, case, ontology=ontology))
    c_adapt = composite(ground(adapted, case, ontology=ontology))
    assert json.dumps(c_adapt, sort_keys=True) == json.dumps(c_orig, sort_keys=True)


# ── A4 (replay-from-provenance — the aha) ─────────────────────────────────────


def test_replay_resolves_from_persisted_head(tmp_path):
    db = tmp_path / "collections.sqlite"
    agent = _agent_no_baseline()
    ontology = load_ontology(HOUSE_ONTOLOGY_PATH)
    case = load_case(HOUSE_CASE_ID, source=str(HOUSE_CASE_PATH))
    baseline = json.loads(HOUSE_BASELINE_PATH.read_text())

    # persist a head exactly as run_eval would stamp it: addressable + a FRESH signature
    blob = dict(baseline["provenance"])
    blob["agent_id"] = agent.name
    blob["case_id"] = agent.dataset.case_id
    blob["grade_signature"] = grade_signature(
        _ontology_dict(), assignments=None, models=None,
        council_config=agent.eval_profile.council_config,
    )
    PIPELINE_RUNS.insert(blob, db_path=db)

    record = run_eval.run(agent, collections_db=db, out_dir=tmp_path / "out")

    assert record["provenance"]["grade_path"] == "replay"  # $0, no SystemExit
    c_expected = composite(ground(baseline, case, ontology=ontology))
    assert record["composite"]["verdict"] == c_expected["verdict"]
    assert record["composite"]["score"] == c_expected["score"]
    # RUNTRAIL-1 (append-with-lineage): replay-from-provenance no longer REUSES the head's
    # pipeline_run_id (that was the idempotent-overwrite behavior this cycle reverses). It
    # mints a FRESH id and stamps replay_of = the captured head it was derived from, so the
    # re-grade appends a distinct audit row rather than overwriting the head.
    assert record["result"]["provenance"]["pipeline_run_id"] != blob["pipeline_run_id"]
    assert record["result"]["provenance"]["replay_of"] == blob["pipeline_run_id"]


# ── A5 (freshness guard) ──────────────────────────────────────────────────────


def test_replay_refuses_a_stale_head_on_config_drift(tmp_path):
    db = tmp_path / "collections.sqlite"
    agent = _agent_no_baseline()
    baseline = json.loads(HOUSE_BASELINE_PATH.read_text())

    blob = dict(baseline["provenance"])
    blob["agent_id"] = agent.name
    blob["case_id"] = agent.dataset.case_id
    blob["grade_signature"] = "STALE-SIGNATURE-FROM-A-DIFFERENT-CONFIG"  # ≠ current
    PIPELINE_RUNS.insert(blob, db_path=db)

    with pytest.raises(SystemExit, match="config changed"):
        run_eval.run(agent, collections_db=db, out_dir=tmp_path / "out")


def test_is_fresh_is_a_swappable_drift_aware_predicate():
    fresh = {"grade_signature": "abc"}
    assert is_fresh(fresh, "abc") is True
    assert is_fresh(fresh, "xyz") is False
    assert is_fresh({}, "abc") is False  # an un-signed head is never fresh


# ── A6 (frozen contract / moat) ───────────────────────────────────────────────


def test_versioning_is_scoped_to_the_provenance_tier():
    assert PIPELINE_RUNS.versioned is True
    for c in COLLECTIONS:  # the four M1 config/report collections — untouched (PERSIST-2b)
        assert c.versioned is False, f"{c.name} must not be versioned in 2a"


def test_consensus_seam_is_zero_delta_vs_acc4973():
    from tests._seam_freeze import assert_compliance_council_carveouts_only

    assert_compliance_council_carveouts_only(REPO_ROOT)  # the canonical acc4973 moat pin


def test_frozen_contract_record_identical(tmp_path):
    pytest.importorskip("openai")  # grade_inprocess -> LocalPipelineBackend -> council
    pytest.importorskip("tenacity")
    from lithrim_bench.harness.grade import grade_inprocess

    case = load_case(HOUSE_CASE_ID, source=str(HOUSE_CASE_PATH))
    assert case is not None

    async def _stage(_request):
        sr = StageResult(
            status="BLOCK",
            findings=[Finding(type="semantic", severity="HIGH", code="FABRICATED_CLAIM", detail="d")],
            evidence=[{"violation_code": "FABRICATED_CLAIM", "judge": "faithfulness_judge", "spans": []}],
            judge_votes=[
                JudgeVote(judge_role="faithfulness_judge", vote="BLOCK", confidence=0.9, model="m", findings=["FABRICATED_CLAIM"])
            ],
        )
        return sr, {"council_config": {"mode": "full"}}

    nondet = {"pipeline_run_id", "timestamp", "duration_ms"}

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in nondet}
        if isinstance(o, list):
            return [strip(x) for x in o]
        return o

    db = tmp_path / "a6.sqlite"
    r_sqlite = grade_inprocess(case, semantic_stage=_stage, provenance_store=SqliteProvenanceStore(db_path=db))
    r_noop = grade_inprocess(case, semantic_stage=_stage, provenance_store=NoOpProvenanceStore())

    # versioning is a pure side-effect: the returned record is byte-identical store on/off
    assert json.dumps(strip(r_sqlite), sort_keys=True) == json.dumps(strip(r_noop), sort_keys=True)
