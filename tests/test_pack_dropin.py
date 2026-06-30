"""PACK-DROPIN-1 — a dropped-in pack's portable ``seed_agents`` are seeded into the config DB.

The CE loads packs from a drop-in volume/path (``LITHRIM_BENCH_PACKS_DIR``). Empty drop-in →
clean ``_core`` CE (``seed_config_db`` seeds ONLY the committed core agent). Drop a pack folder
whose ``pack.json`` declares ``seed_agents`` → its portable agents are ALSO seeded, with their
``ontology_path`` resolved to wherever the pack is dropped (never a stale ``packs/<x>`` literal).

The contract this build DEFINES (the pack-side build conforms):
  - ``pack.json`` gains an OPTIONAL ``"seed_agents": ["agents/<name>.json"]`` (pack-relative).
  - Each seed-agent JSON uses LOGICAL refs: an ``ontology_ref`` + a pack-relative ``dataset``.
  - The seed sets ``ontology_path = pack_ontology_path(pack)`` (valid in the CURRENT env) and
    resolves pack-relative ``dataset.source``/``baseline`` against the pack ROOT.
  - A seed-agent whose name collides with an existing agent is SKIPPED (never clobbers core).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_fake_pack(
    packs_dir: Path,
    pack_id: str,
    *,
    seed_agents: list[str] | None,
    agent_name: str = "fake_default",
) -> Path:
    """Build a minimal DISCOVERABLE pack under ``packs_dir/<pack_id>``: a ``pack.json`` (optionally
    declaring ``seed_agents``), a tiny ontology, and (when declared) a portable agent JSON using a
    LOGICAL ``ontology_ref`` + pack-relative dataset refs. Returns the pack root."""
    root = packs_dir / pack_id
    (root / "agents").mkdir(parents=True, exist_ok=True)
    (root / "ontology.json").write_text(json.dumps({"id": f"{pack_id}/1", "flags": []}))
    manifest = {
        "pack_id": pack_id,
        "version": "0.1.0",
        "tier": "core",
        "domain": pack_id,
        "ontology": "ontology.json",
        "flags_ref": "taxonomy_snapshot.json",
        "council_roles": "council_roles",
        "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
    }
    if seed_agents is not None:
        manifest["seed_agents"] = seed_agents
        for ref in seed_agents:
            (root / ref).parent.mkdir(parents=True, exist_ok=True)
            (root / ref).write_text(
                json.dumps(
                    {
                        "name": agent_name,
                        "eval_profile": {
                            "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
                            "council_config": {},
                            "ontology_ref": f"{pack_id}/1",
                            # NO ontology_path: the seed resolves it to the CURRENT env.
                            "tools": [],
                            "kb_bindings": {},
                            "severity_map_ref": f"ontology:{pack_id}/1",
                        },
                        "dataset": {
                            "case_id": f"{pack_id}_case",
                            "source": "examples/case.jsonl",
                            "baseline": "examples/baseline.json",
                            "mode": "replay",
                        },
                    }
                )
            )
    (root / "council_roles").mkdir(exist_ok=True)
    (root / "pack.json").write_text(json.dumps(manifest))
    return root


@pytest.fixture
def clean_pack_caches():
    """Bust the lru_cache'd pack-root/manifest caches so a tmp packs-dir is seen fresh."""
    from lithrim_bench.harness import pack as pack_mod

    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()
    yield
    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()


def test_a_no_pack_seeds_only_core(tmp_path, monkeypatch, clean_pack_caches):
    """A: with NO discoverable drop-in pack, ``seed_config_db`` seeds ONLY the committed core
    agent — the clean-by-construction CE default is unchanged."""
    from lithrim_bench.harness.config import list_agents, seed_config_db

    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path / "empty"))  # no pack subdirs
    (tmp_path / "empty").mkdir()
    db = tmp_path / "cfg.sqlite"

    names = seed_config_db(db_path=db)

    assert names == ["ws0_default"]
    assert list_agents(db_path=db) == ["ws0_default"]


def test_seed_is_idempotent_no_rewrite_on_reseed(tmp_path, monkeypatch, clean_pack_caches):
    """POSTGRES-DEADLOCK-FIX: re-running ``seed_config_db`` writes NOTHING once seeded. Under the
    Postgres plane the local sqlite ``db_path`` never exists, so the BFF re-seeds on EVERY request;
    the prior unconditional ``save_agent`` re-archived every agent each time and two concurrent
    requests deadlocked on ``agents_history``. The idempotent seed skips already-present agents, so
    the re-seed calls ``save_agent`` ZERO times — no archive, no concurrent-write race."""
    from lithrim_bench.harness import config as cfg

    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    db = tmp_path / "cfg.sqlite"

    assert "ws0_default" in cfg.seed_config_db(db_path=db)  # first seed creates the core agent

    calls: list[int] = []
    monkeypatch.setattr(cfg, "save_agent", lambda *a, **k: calls.append(1))
    second = cfg.seed_config_db(db_path=db)  # re-seed (what every request does under Postgres)

    assert calls == []  # NO save_agent on re-seed → no archive_prior → no deadlock
    assert cfg.list_agents(db_path=db) == ["ws0_default"]
    assert second == ["ws0_default"]  # returns the existing set, seeded nothing new


def test_b_dropin_pack_agent_seeded_with_resolved_ontology(
    tmp_path, monkeypatch, clean_pack_caches
):
    """B: a FAKE drop-in pack declaring ``seed_agents`` on a tmp PACKS_DIR → its agent is ALSO
    seeded, and its ``ontology_path`` resolves to the tmp pack's ontology (NOT a stale path)."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.config import list_agents, load_agent, seed_config_db

    packs_dir = tmp_path / "dropin"
    pack_root = _write_fake_pack(
        packs_dir, "dropin_demo", seed_agents=["agents/dropin_default.json"]
    )
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(packs_dir))
    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()
    db = tmp_path / "cfg.sqlite"

    names = seed_config_db(db_path=db)

    assert "ws0_default" in names  # the core seed still runs first
    assert "fake_default" in names  # the pack's portable agent was seeded too
    assert set(list_agents(db_path=db)) == {"ws0_default", "fake_default"}

    agent = load_agent("fake_default", db_path=db)
    resolved = Path(agent.eval_profile.ontology_path)
    assert resolved.is_absolute()
    assert resolved == (pack_root / "ontology.json").resolve()
    assert "packs/dropin_demo" not in agent.eval_profile.ontology_path  # not a stale literal
    # pack-relative dataset refs resolve against the dropped pack root
    assert Path(agent.dataset.source) == (pack_root / "examples" / "case.jsonl").resolve()
    assert Path(agent.dataset.baseline) == (pack_root / "examples" / "baseline.json").resolve()


def test_c_seed_agent_named_ws0_default_is_skipped(tmp_path, monkeypatch, clean_pack_caches):
    """C: a seed-agent whose name collides with the core ``ws0_default`` is SKIPPED — the pack
    NEVER clobbers the committed core seed."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.config import load_agent, seed_config_db

    packs_dir = tmp_path / "dropin"
    _write_fake_pack(
        packs_dir,
        "clobber_demo",
        seed_agents=["agents/ws0_default.json"],
        agent_name="ws0_default",  # the collision
    )
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(packs_dir))
    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()
    db = tmp_path / "cfg.sqlite"

    seed_config_db(db_path=db)

    # ws0_default survives as the CORE seed (its committed ontology_path), not the pack's.
    core = load_agent("ws0_default", db_path=db)
    assert core.eval_profile.ontology_path == "packs/_core/ontology.json"


def test_d_get_packs_lists_core_and_dropin_marks_active(tmp_path, monkeypatch, clean_pack_caches):
    """D: ``GET /v1/packs`` lists ``_core`` (bare-CE) + the fake drop-in pack when discoverable,
    and marks the active pack."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness import workspace as W

    # Isolate WORKSPACES_DIR so the active workspace is the clean `_core` default — NOT a non-_core
    # workspace another suite test switched to in the shared real out/workspaces (the active marker
    # would otherwise be ordering-dependent). Mirrors test_workspace.py's ``ws_root`` fixture.
    monkeypatch.setattr(W, "WORKSPACES_DIR", tmp_path / "workspaces")

    packs_dir = tmp_path / "dropin"
    _write_fake_pack(packs_dir, "dropin_demo", seed_agents=["agents/dropin_default.json"])
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(packs_dir))
    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()

    _bff = REPO_ROOT / "apps" / "bff"
    if str(_bff) not in sys.path:
        sys.path.insert(0, str(_bff))
    import app as bff
    from fastapi.testclient import TestClient

    body = TestClient(bff.app).get("/v1/packs").json()
    ids = {p["id"] for p in body["packs"]}
    assert {"_core", "dropin_demo"} <= ids

    by_id = {p["id"]: p for p in body["packs"]}
    assert by_id["_core"]["active"] is True  # the bare-CE active pack is marked
    assert by_id["dropin_demo"]["active"] is False
    assert body["active"] == "_core"  # back-compat top-level marker retained
