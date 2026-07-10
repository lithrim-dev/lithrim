"""Workspaces — the switchable domain-setup boundary (the multitenancy primitive).

A workspace is a directory holding its own config plane (config.sqlite / collections /
ontology / out) + a pinned pack. Switching repoints every store. The schema carries an
``owner`` slot so a hosted layer gates access per workspace without a model change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import workspace as W
from lithrim_bench.harness.config import list_agents

REPO_ROOT = Path(__file__).resolve().parents[1]


def _expected_default_agents() -> list[str]:
    """The default workspace's EXACT seeded set: the committed core ``ws0_default`` PLUS every
    discoverable pack's declared ``seed_agents`` (PACK-DROPIN-1 / PACK-PORTABLE, pack b973867).
    Bare CE (no discoverable pack declaring ``seed_agents``) reduces to ``["ws0_default"]``."""
    from lithrim_bench.harness.pack import discover_packs, pack_root

    names = {"ws0_default"}
    for entry in discover_packs():
        root = pack_root(entry["id"])
        try:
            manifest = json.loads((root / "pack.json").read_text())
        except (OSError, ValueError):
            continue
        for ref in manifest.get("seed_agents") or []:
            try:
                names.add(json.loads((root / ref).read_text())["name"])
            except (OSError, ValueError, KeyError):
                continue
    return sorted(names)


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
    # the default workspace seeds the blank CE default agent + every discoverable pack's
    # declared seed agents (PACK-DROPIN-1) — bare CE stays exactly ["ws0_default"]
    assert list_agents(db_path=ws.config_db) == _expected_default_agents()
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


def test_fresh_workspace_starts_empty_default_keeps_ws0(ws_root):
    """A created workspace is EMPTY ('create your first agent') — only the default carries
    the seeded ws0_default. The committed template stays available as the clone source."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff
    from fastapi.testclient import TestClient

    c = TestClient(bff.app)
    seeded = _expected_default_agents()  # ws0_default + discoverable packs' seed agents
    assert c.get("/v1/agents").json()["agents"] == seeded  # the default workspace
    c.post("/v1/workspaces", json={"name": "fresh", "pack": "_core"})
    c.post("/v1/workspace", json={"name": "fresh"})
    assert c.get("/v1/agents").json()["agents"] == []  # EMPTY — the isolation is visible
    assert c.get("/v1/agent/template").json()["name"] == "ws0_default"  # clone source still there
    c.post("/v1/workspace", json={"name": "default"})
    assert c.get("/v1/agents").json()["agents"] == seeded  # default unchanged


def test_grade_subprocess_binds_the_workspace_pack(ws_root, monkeypatch):
    """PACK-WS: the council-bound grade spawns run_eval with LITHRIM_BENCH_PACK=<workspace
    pack> + its packs_dir (so the frozen council binds the workspace's domain), and parses
    the __GRADE_JSON__ record back. Mocked subprocess — no real grade."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff

    captured = {}

    class _Proc:
        returncode = 0
        stdout = 'log noise\n__GRADE_JSON__{"verdict": "PASS", "n": 1}\ntrailing'
        stderr = ""

    monkeypatch.setattr(
        bff.subprocess, "run", lambda cmd, **kw: (captured.update(cmd=cmd, env=kw.get("env")), _Proc())[1]
    )
    ws = W.create_workspace("hc", pack="healthcare", packs_dir="/ext/packs")
    rec = bff._grade_via_subprocess(
        agent_name="ws0_default", config_db="/cfg.sqlite", ontology_path="/ont.json",
        collections_db="/coll.sqlite", out_dir="/out", live=False, in_process=True, ws=ws,
    )
    assert rec == {"verdict": "PASS", "n": 1}  # parsed past the noise + trailing lines
    assert captured["env"]["LITHRIM_BENCH_PACK"] == "healthcare"
    assert captured["env"]["LITHRIM_BENCH_PACKS_DIR"] == "/ext/packs"
    assert "--in-process" in captured["cmd"]
    assert "/ont.json" in captured["cmd"] and "/cfg.sqlite" in captured["cmd"]


def test_discover_packs_and_selectable_filter(ws_root):
    """P3: discoverable packs are what a workspace can pin; GET /v1/packs shows the selectable
    DOMAINS (tier core|pro, non-fixture) — 'install a pack' = make it discoverable."""
    from lithrim_bench.harness.pack import discover_packs

    ids = {p["id"] for p in discover_packs()}
    assert {"_core", "support_ticket_qa"} <= ids  # in-repo CE domains
    assert "_tiers_fixture" in ids  # discover is UNfiltered (the endpoint filters)

    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff
    from fastapi.testclient import TestClient

    body = TestClient(bff.app).get("/v1/packs").json()
    sel = {p["id"] for p in body["packs"]}
    assert {"_core", "support_ticket_qa"} <= sel
    assert "_tiers_fixture" not in sel and "story_audit" not in sel  # fixtures + demo filtered
    assert body["active"] == "_core"


def test_pack_bound_agent_template_and_cases(ws_root, monkeypatch):
    """P3-c: a workspace pinning a discoverable pack gets an agent template bound to THAT pack's
    ontology + a case, and the pack's cases are listable; the default _core workspace falls back
    to the committed blank. Needs the healthcare pack checked out (skip-when-absent)."""
    sib = REPO_ROOT.parent / "lithrim-pack-healthcare"
    if not (sib / "healthcare" / "pack.json").is_file():
        pytest.skip("healthcare pack not checked out")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(sib))
    from lithrim_bench.harness import pack as pack_mod

    pack_mod._pack_root.cache_clear()

    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff
    from fastapi.testclient import TestClient

    c = TestClient(bff.app)
    c.post("/v1/workspaces", json={"name": "clinical", "pack": "healthcare"})
    c.post("/v1/workspace", json={"name": "clinical"})
    t = c.get("/v1/agent/template").json()
    assert t["name"] == "healthcare_default"
    assert "healthcare" in t["eval_profile"]["ontology_path"]  # bound to the PACK ontology
    assert t["dataset"]["case_id"]  # a seed case from the pack's corpora
    cases = c.get("/v1/packs/healthcare/cases").json()["cases"]
    assert len(cases) > 0 and all("case_id" in x for x in cases)

    c.post("/v1/workspace", json={"name": "default"})  # _core → the committed blank
    assert c.get("/v1/agent/template").json()["name"] == "ws0_default"
