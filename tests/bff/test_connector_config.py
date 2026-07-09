"""NARR-6 P1a — ``POST /v1/connector/config`` (the StoryWorld connector config endpoint).

The owner-decided secret hygiene (§8.2): the ``x-api-key`` is written ONLY to a gitignored
``out/workspaces/<active>/.connector_env`` (mirrors ``grade.py:_load_env``), and ``base_url`` +
``last_tested`` persist to a gitignored ``connector.json`` sidecar (NOT the Workspace dataclass,
NOT SQLite, NOT the response). The endpoint runs a READ-ONLY Test (GET
``/api/admin/sessions?limit=1``) via an injected ``StoryWorldAdminClient`` so the green bar is
$0/offline (no live Azure call):

  * A1 — a clean 200 Test → ``.connector_env`` written (key present), ``connector.json`` carries
    ``base_url`` only, the key is NOT in the JSON response and NOT in any SQLite DB.
  * A2 — a 401 Test → the auth status is surfaced and the key is NOT written (non-vacuous vs A1).

Requires the ``[bff]`` extra (fastapi). Pack-independent (no healthcare reads); uses a tmp_path
workspace so nothing touches the real ``out/`` tree.
"""

from __future__ import annotations

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


@pytest.fixture()
def ws_env(tmp_path, monkeypatch):
    """Point the workspaces tree at tmp_path + force the module to honor it, returning the
    active workspace so the test can read its on-disk .connector_env / connector.json."""
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    try:
        ws = ws_mod.create_workspace("narr6_conn", pack="narrative", seed=False)
        ws_mod.set_active_workspace(ws.name)
        yield ws_mod, ws
    finally:
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _install_fake_client(monkeypatch, *, status, ok):
    """Patch StoryWorldAdminClient so test_connection() returns a canned status (no live call)."""

    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def test_connection(self):
            return {"status": status, "ok": ok}

    monkeypatch.setattr("lithrim_bench.verification.StoryWorldAdminClient", FakeClient)


def test_connector_config_clean_test_writes_key_only_to_connector_env(ws_env, monkeypatch):
    """A1: a clean 200 Test → .connector_env holds the key; connector.json holds base_url only;
    the key never appears in the response or in any *.sqlite file."""
    ws_mod, ws = ws_env
    _install_fake_client(monkeypatch, status=200, ok=True)
    client = TestClient(bff.app)

    secret = "sw-secret-DEADBEEF-do-not-leak"
    base_url = "https://storyworld-api.example.test"
    resp = client.post(
        "/v1/connector/config",
        json={"connector_id": "storyworld_admin", "base_url": base_url, "x_api_key": secret},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == 200
    assert body["base_url"] == base_url
    assert body["last_tested"]
    # the key NEVER round-trips in the response
    assert secret not in resp.text

    env_file = ws.dir / ".connector_env"
    assert env_file.exists(), "the key was not written to .connector_env"
    env_text = env_file.read_text()
    assert f"STORYWORLD_API_KEY={secret}" in env_text

    sidecar = ws.dir / "connector.json"
    assert sidecar.exists()
    sidecar_text = sidecar.read_text()
    assert base_url in sidecar_text
    assert secret not in sidecar_text, "the key leaked into the connector.json sidecar"

    # the key never reaches SQLite (the config plane)
    for db in ws.dir.rglob("*.sqlite"):
        assert secret.encode() not in db.read_bytes()


def test_connector_config_failed_test_surfaces_auth_and_does_not_write_key(ws_env, monkeypatch):
    """A2 (non-vacuity): a 401 Test → the auth status is surfaced and the key is NOT written —
    proving the A1 write is conditional on a clean Test."""
    ws_mod, ws = ws_env
    _install_fake_client(monkeypatch, status=401, ok=False)
    client = TestClient(bff.app)

    secret = "sw-secret-SHOULD-NOT-PERSIST"
    resp = client.post(
        "/v1/connector/config",
        json={
            "connector_id": "storyworld_admin",
            "base_url": "https://storyworld-api.example.test",
            "x_api_key": secret,
        },
    )
    # the endpoint surfaces the failing status (4xx) and does not 500
    assert resp.status_code in (200, 400, 401, 502), resp.text
    body = resp.json()
    # whether returned as a status field or an error detail, the 401 is visible
    assert "401" in resp.text or body.get("status") == 401

    env_file = ws.dir / ".connector_env"
    if env_file.exists():
        assert secret not in env_file.read_text(), "the key was written despite a failed Test"
    assert secret not in resp.text
