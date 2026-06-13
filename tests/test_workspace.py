"""Workspaces — the switchable domain-setup boundary (the multitenancy primitive).

A workspace is a directory holding its own config plane (config.sqlite / collections /
ontology / out) + a pinned pack. Switching repoints every store. The schema carries an
``owner`` slot so a hosted layer gates access per workspace without a model change.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import workspace as W
from lithrim_bench.harness.config import list_agents

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ws_root(tmp_path, monkeypatch):
    """Point WORKSPACES_DIR at a tmp dir — every store + the active pointer derive from it."""
    d = tmp_path / "workspaces"
    monkeypatch.setattr(W, "WORKSPACES_DIR", d)
    return d


def test_default_workspace_self_heals_and_seeds_clean(ws_root):
    ws = W.get_active_workspace()
    assert ws.name == "default" and ws.pack == "_core"
    assert ws.config_db.is_file()
    # the default workspace seeds the blank CE default agent — nothing clinical
    assert list_agents(db_path=ws.config_db) == ["ws0_default"]
    assert W.list_workspaces() == ["default"]
    assert W.active_workspace_name() == "default"


def test_create_switch_list_and_guards(ws_root):
    W.get_active_workspace()  # materialize default
    hc = W.create_workspace("team-b", pack="healthcare", actor="b@x", owner="org-42")
    assert hc.pack == "healthcare" and hc.owner == "org-42"
    assert set(W.list_workspaces()) == {"default", "team-b"}

    assert W.set_active_workspace("team-b").pack == "healthcare"
    assert W.active_workspace_name() == "team-b"
    assert W.set_active_workspace("default").name == "default"

    with pytest.raises(FileExistsError):
        W.create_workspace("default")
    with pytest.raises(ValueError):
        W.create_workspace("bad name!")
    with pytest.raises(FileNotFoundError):
        W.set_active_workspace("ghost")


def test_every_store_is_workspace_scoped(ws_root):
    a = W.get_active_workspace()
    b = W.create_workspace("other", pack="_core")
    # each store lives under its own workspace dir — switching moves ALL of them together
    for ws in (a, b):
        for p in (ws.config_db, ws.collections_db, ws.ontology_dir, ws.out_dir):
            assert ws.dir in p.parents or p == ws.dir
    assert a.config_db != b.config_db
    assert a.collections_db != b.collections_db
    assert a.ontology_dir != b.ontology_dir


def test_owner_slot_is_persisted_but_ignored_locally(ws_root):
    """The auth seam: owner round-trips in the manifest (a hosted layer reads it); the
    local runtime never gates on it."""
    W.get_active_workspace()
    W.create_workspace("tenant-x", owner="acme@cloud")
    assert W.read_workspace("tenant-x").owner == "acme@cloud"
    assert W.read_workspace("tenant-x").to_public()["owner"] == "acme@cloud"


def test_bff_workspace_endpoints(ws_root):
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff
    from fastapi.testclient import TestClient

    c = TestClient(bff.app)
    body = c.get("/v1/workspaces").json()
    assert body["active"] == "default"
    assert [w["name"] for w in body["workspaces"]] == ["default"]
    assert body["workspaces"][0]["pack"] == "_core"

    assert c.post("/v1/workspaces", json={"name": "w2", "pack": "_core"}).status_code == 200
    assert c.post("/v1/workspace", json={"name": "w2"}).json()["active"] == "w2"
    assert c.get("/v1/workspaces").json()["active"] == "w2"
    assert c.post("/v1/workspace", json={"name": "ghost"}).status_code == 404
    assert c.post("/v1/workspaces", json={"name": "default"}).status_code == 400
