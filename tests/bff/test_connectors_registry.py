"""CONN-1 — the registry-driven connector surface.

The connector panel is no longer hardcoded to "StoryWorld admin API". The shell reads
``GET /v1/connectors`` (the ingest-capable subset of ``plugins.tool_plugins()`` — declaration
driven, License-gated, secrets never returned) and ingests through a generic
``POST /v1/connector/ingest`` that dispatches by ``connector_id`` to a per-connector adapter.
Adding a connector is a manifest entry (+ an adapter, if it pulls) — never a UI edit.

  * A1 — ``/v1/connectors`` lists ``storyworld_admin`` (declared in the narrative pack's
    ``tools.json``) with its label + default_base_url and NO secret; the JUTE connector
    (``etlp_jute`` — a transform engine, not an ingest source) is NOT listed.
  * A2 — ``/v1/connector/ingest {connector_id: storyworld_admin}`` dispatches to the StoryWorld
    adapter and returns the same shape as the legacy route (the bespoke pull is untouched).
  * A3 — an unknown ``connector_id`` is a clean 400 (no adapter), nothing written.
  * A4 — the legacy ``/v1/connector/storyworld/ingest`` route still works (back-compat).

All $0/offline: only ``StoryWorldAdminClient`` is mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_synthetic_session.json"
_SECRET = "sw-secret-do-not-leak-CONN1"


@pytest.fixture()
def ws_env(tmp_path, monkeypatch):
    # active_pack() reads LITHRIM_BENCH_PACK at call time → pin narrative so the pack's
    # tools.json (storyworld_admin) is in tool_plugins().
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "narrative")
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    try:
        ws = ws_mod.create_workspace("conn1", pack="narrative", seed=False)
        ws_mod.set_active_workspace(ws.name)
        ws.dir.mkdir(parents=True, exist_ok=True)
        (ws.dir / ".connector_env").write_text(f"STORYWORLD_API_KEY={_SECRET}\n")
        (ws.dir / "connector.json").write_text(
            json.dumps({"base_url": "https://storyworld-api.example.test"})
        )
        yield ws_mod, ws
    finally:
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _install_fake_storyworld(monkeypatch, detail):
    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def list_sessions(self, limit=50, offset=0):
            if detail is None:
                return {"items": [], "total": 0}
            return {"items": [{"id": detail.get("id", "sess_real_001")}], "total": 1}

        def get_session(self, session_id):
            return detail

    monkeypatch.setattr("lithrim_bench.verification.StoryWorldAdminClient", FakeClient)


def test_connectors_list_lists_ingest_sources_only_no_secret(ws_env):
    """A1: the declared ingest connector (storyworld_admin) is listed with label +
    default_base_url and NO secret; the JUTE transform engine is NOT listed."""
    client = TestClient(bff.app)
    resp = client.get("/v1/connectors")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    conns = body["connectors"]
    by_id = {c["connector_id"]: c for c in conns}

    assert "storyworld_admin" in by_id, by_id
    sw = by_id["storyworld_admin"]
    assert sw["label"] == "StoryWorld admin API", sw
    assert "default_base_url" in sw
    # no secret/key field is ever projected
    blob = json.dumps(body)
    assert "x_api_key" not in blob and "api_key" not in blob, blob

    # the JUTE connector is a transform engine, not an ingest source → excluded
    assert "etlp_jute" not in by_id, by_id


def test_connectors_list_follows_active_workspace_pack_not_process_env(ws_env, monkeypatch):
    """A1b: the list reflects the ACTIVE WORKSPACE's pack, not the BFF process env — a narrative
    workspace served through a differently-pinned process still sees its connectors. (The BFF
    binds one pack at import but serves multi-pack workspaces.)"""
    # simulate a process pinned to a different pack than the active (narrative) workspace
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "healthcare")
    client = TestClient(bff.app)
    resp = client.get("/v1/connectors")
    assert resp.status_code == 200, resp.text
    ids = {c["connector_id"] for c in resp.json()["connectors"]}
    assert "storyworld_admin" in ids, ids


def test_connector_ingest_dispatches_to_storyworld(ws_env, monkeypatch):
    """A2: the generic route dispatches to the StoryWorld adapter (same shape as the legacy route)."""
    _ws_mod, ws = ws_env
    detail = json.loads(_FIXTURE.read_text())
    _install_fake_storyworld(monkeypatch, detail)
    client = TestClient(bff.app)

    resp = client.post(
        "/v1/connector/ingest", json={"connector_id": "storyworld_admin", "limit": 50}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3, body
    assert body["sessions"] == 1, body
    assert body["errors_trapped"] == 0, body
    assert set(["count", "sessions", "cases", "errors_trapped"]).issubset(body), body
    assert (ws.out_dir / "ingested_cases.jsonl").exists()


def test_connector_ingest_unknown_id_is_clean_400(ws_env):
    """A3: an unregistered connector_id → 400, nothing written."""
    _ws_mod, ws = ws_env
    client = TestClient(bff.app)
    resp = client.post("/v1/connector/ingest", json={"connector_id": "nope_not_real"})
    assert resp.status_code == 400, resp.text
    assert not (ws.out_dir / "ingested_cases.jsonl").exists()


def test_legacy_storyworld_route_still_works(ws_env, monkeypatch):
    """A4: the legacy /v1/connector/storyworld/ingest route still ingests (back-compat delegator)."""
    _ws_mod, ws = ws_env
    detail = json.loads(_FIXTURE.read_text())
    _install_fake_storyworld(monkeypatch, detail)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 3, resp.text
