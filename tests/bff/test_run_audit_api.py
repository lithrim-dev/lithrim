"""RUNTRAIL-6 — the run audit READ-API surfaces lineage + history + rehydrate (BFF layer).

The read-surface complement to the persistence work (RUNTRAIL-1/2/4): the blob carries
`replay_of` and the store exposes `list_history`/`rehydrate`, but the read API dropped them.
SPEC_RUN_AUDIT_TRAIL.md §2 (the trail is the consumable record), §3 (lineage: `replay_of`),
§4 (rehydrate from the blob alone, no model call).

`grade_path` is deliberately OUT of scope here (RUNTRAIL-7, a persist-layer cycle): the
persisted PipelineProvenance blob does NOT carry `grade_path` — it lives only in the
non-persisted API record. This cycle surfaces only what the blob actually holds.

Hermetic + $0: TestClient + a tmp `collections_db`, blobs persisted through the SAME store
factory the BFF reads through (mirror of `test_cohort_audit_trail.py`). No network, no model.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _blob(run_id: str, *, replay_of: str | None = None, verdict: str = "approve") -> dict:
    """A minimal persisted-blob shape: the PipelineProvenance dump + the extra doc fields the
    grade path stamps. `replay_of` is top-level (None = authoritative)."""
    return {
        "pipeline_run_id": run_id,
        "replay_of": replay_of,
        "agent_id": "audit_agent",
        "case_id": "audit_case",
        "timestamp": "2026-06-30T00:00:00+00:00",
        "verdict": verdict,
        "gate_decision": "pass",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": {"judge_votes": [], "evidence": []}},
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    collections_db = tmp_path / "coll.sqlite"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    try:
        yield TestClient(bff.app), collections_db
    finally:
        bff.app.dependency_overrides.clear()


def _save(collections_db: Path, blob: dict) -> None:
    run_coro(provenance_store_for(collections_db).save_blob(blob))


# --------------------------------------------------------------------------- #
# A1 — GET /v1/runs/{id}/audit includes replay_of
# --------------------------------------------------------------------------- #
def test_audit_includes_replay_of_for_replay_run(client):
    cli, collections_db = client
    baseline = str(uuid.uuid4())
    replay = str(uuid.uuid4())
    _save(collections_db, _blob(baseline))
    _save(collections_db, _blob(replay, replay_of=baseline))

    res = cli.get(f"/v1/runs/{replay}/audit")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "replay_of" in body, "audit report must carry the replay_of lineage key"
    assert body["replay_of"] == baseline


def test_audit_replay_of_key_present_null_for_authoritative(client):
    cli, collections_db = client
    rid = str(uuid.uuid4())
    _save(collections_db, _blob(rid))

    body = cli.get(f"/v1/runs/{rid}/audit").json()
    assert "replay_of" in body, "key must be present even for an authoritative grade"
    assert body["replay_of"] is None


# --------------------------------------------------------------------------- #
# A2 — GET /v1/runs rows include replay_of
# --------------------------------------------------------------------------- #
def test_runs_list_rows_include_replay_of(client):
    cli, collections_db = client
    baseline = str(uuid.uuid4())
    replay = str(uuid.uuid4())
    _save(collections_db, _blob(baseline))
    _save(collections_db, _blob(replay, replay_of=baseline))

    rows = cli.get("/v1/runs").json()["runs"]
    by_id = {r["run_id"]: r for r in rows}
    assert "replay_of" in by_id[baseline]
    assert by_id[baseline]["replay_of"] is None
    assert by_id[replay]["replay_of"] == baseline


# --------------------------------------------------------------------------- #
# A3 — /history + /rehydrate
# --------------------------------------------------------------------------- #
def test_history_returns_archived_prior_versions_newest_first(client):
    cli, collections_db = client
    rid = str(uuid.uuid4())
    # same id re-saved -> the prior version is copy-on-write archived into _history.
    _save(collections_db, _blob(rid, verdict="approve"))
    _save(collections_db, _blob(rid, verdict="block"))

    res = cli.get(f"/v1/runs/{rid}/history")
    assert res.status_code == 200, res.text
    history = res.json()["history"]
    assert isinstance(history, list)
    assert len(history) == 1, "one re-save archives exactly one prior version"
    assert history[0]["verdict"] == "approve"


def test_history_empty_list_for_known_unsuperseded_run(client):
    cli, collections_db = client
    rid = str(uuid.uuid4())
    _save(collections_db, _blob(rid))

    res = cli.get(f"/v1/runs/{rid}/history")
    assert res.status_code == 200, res.text
    assert res.json()["history"] == []


def test_rehydrate_reconstructs_verdict_no_model_call(client):
    cli, collections_db = client
    rid = str(uuid.uuid4())
    _save(collections_db, _blob(rid, verdict="block"))

    res = cli.get(f"/v1/runs/{rid}/rehydrate")
    assert res.status_code == 200, res.text
    assert res.json()["verdict"] == "block"


def test_rehydrate_unknown_id_404(client):
    cli, _ = client
    res = cli.get(f"/v1/runs/{uuid.uuid4()}/rehydrate")
    assert res.status_code == 404, res.text


def test_history_unknown_id_404(client):
    cli, _ = client
    res = cli.get(f"/v1/runs/{uuid.uuid4()}/history")
    assert res.status_code == 404, res.text
