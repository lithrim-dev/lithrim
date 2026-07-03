"""PACK-OVERLAY-1 — UI-authored judge/criterion identity must survive container recreation.

Diagnosis (CONFIRMED live 2026-07-03, isolated lithrim-validate stack): the sanctioned authoring
writers — ``harness.criterion.splice_gradeable_criterion`` and
``harness.judge_authoring.splice_production_judge`` + ``write_role_prompt`` — target the ACTIVE
PACK ROOT via ``pack._pack_ref``. In Docker that is ``/app/packs/_core/`` — the bff container's
image WRITABLE LAYER, not the ``lithrim_out`` volume — so a ``docker compose up`` that recreates
the container silently reverts every authored criterion/judge while the workspace DB / ontology
overlays / bindings on ``/app/out`` survive. The next grade then 500s:
``FileNotFoundError: no council role prompt for '<authored_role>'``
(``runtime/council/judge_assignment.load_role_prompt``).

The fix (option a, the principled one): a VOLUME-BACKED PACK OVERLAY above the PACK-DIST-1
discovery seam. ``LITHRIM_BENCH_PACK_OVERLAY_DIR`` names a STATE dir (compose:
``/app/out/pack_overlay`` on the ``lithrim_out`` volume); ``pack._pack_ref`` layers
``<overlay>/<pack_id>/`` over the discovered pack root for the two MUTABLE refs only
(``flags_ref`` + ``council_roles``), materializing the pack's seed copy-on-first-resolve. The
audited writers then read AND write the volume copy; the image pack dir is never mutated. Env
unset (the default, incl. this dev suite) → resolution byte-identical to today (the zero-delta
posture, same as the License permit-all default). The frozen council is untouched: its
``_ROLE_PROMPTS_DIR`` import-time carve-out already resolves through ``pack_prompts_path()``,
and its inline ``__import__`` tier/lens/roster reads already flow through ``_pack_ref`` — the
overlay swap happens entirely above the seam.

Also pinned here (in passing, same incident report): ``CouncilRosterRequest`` must reject
unknown body fields — a POST with a misspelled roster field returned 200 and silently CLEARED
the reviewer roster (``body.roster`` defaulted to ``None`` = "clear the override").
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY_ENV = "LITHRIM_BENCH_PACK_OVERLAY_DIR"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))


def _clear_pack_caches() -> None:
    """A recreated container is a FRESH PROCESS — every lru cache is cold. Clearing them all is
    the in-process equivalent (plus it isolates the throwaway pack between tests)."""
    from lithrim_bench.harness import pack as pack_mod

    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    pack_mod.assert_pack_council_consistent.cache_clear()
    pack_mod.assert_pack_judges_consistent.cache_clear()


@pytest.fixture
def image_pack(tmp_path, monkeypatch):
    """A throwaway tier:core pack (a copy of ``packs/_core``) living in a tmp 'image layer' dir,
    plus a PRISTINE copy to revert to (= what a recreated container's image layer holds). Yields
    ``(pack_id, image_dir, pristine_dir)``."""
    image_base = tmp_path / "image_packs"
    pack_dir = image_base / "overlaypack"
    shutil.copytree(REPO_ROOT / "packs" / "_core", pack_dir)
    manifest = json.loads((pack_dir / "pack.json").read_text())
    manifest["pack_id"] = "overlaypack"
    (pack_dir / "pack.json").write_text(json.dumps(manifest, indent=2))
    pristine = tmp_path / "pristine_pack"
    shutil.copytree(pack_dir, pristine)
    existing = os.environ.get("LITHRIM_BENCH_PACKS_DIR", "")
    monkeypatch.setenv(
        "LITHRIM_BENCH_PACKS_DIR",
        str(image_base) + (os.pathsep + existing if existing else ""),
    )
    _clear_pack_caches()
    yield "overlaypack", pack_dir, pristine
    _clear_pack_caches()


@pytest.fixture
def overlay_dir(tmp_path, monkeypatch):
    """The tmp 'volume' the overlay lives on (compose: /app/out/pack_overlay on lithrim_out)."""
    vol = tmp_path / "volume" / "pack_overlay"
    monkeypatch.setenv(OVERLAY_ENV, str(vol))
    return vol


# ── A0 — env unset (the default): resolution is byte-identical to today ──────────────


def test_overlay_disabled_resolution_is_unchanged(image_pack, monkeypatch):
    from lithrim_bench.harness import pack as pack_mod

    pack, pack_dir, _ = image_pack
    monkeypatch.delenv(OVERLAY_ENV, raising=False)
    assert pack_mod._pack_ref(pack, "flags_ref") == pack_dir / "taxonomy_snapshot.json"
    assert pack_mod._pack_ref(pack, "council_roles") == pack_dir / "council_roles"


# ── A1 — an authored write targets the VOLUME overlay; the image pack stays pristine ──


def test_overlay_write_leaves_image_pack_pristine(image_pack, overlay_dir):
    from lithrim_bench.harness import criterion as crit

    pack, pack_dir, _ = image_pack
    image_snap_before = (pack_dir / "taxonomy_snapshot.json").read_bytes()
    crit.splice_gradeable_criterion(pack, "AUTHORED_CHECK", "TIER_2", "risk_judge")
    # state/image separation: the image layer is DATA the container loads, never state it writes
    assert (pack_dir / "taxonomy_snapshot.json").read_bytes() == image_snap_before
    overlay_snap = json.loads((overlay_dir / pack / "taxonomy_snapshot.json").read_text())
    assert "AUTHORED_CHECK" in overlay_snap["tiers"]["TIER_2_HIGH_RISK"]
    assert "AUTHORED_CHECK" in overlay_snap["lenses"]["risk_judge"]


def test_role_prompt_write_targets_overlay(image_pack, overlay_dir):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    pack, pack_dir, _ = image_pack
    crit_seed = "generalist_reviewer: raise only its assigned lens."
    # a prompt write for an EXISTING role (PUT /v1/judges/{role} role_prompt path)
    ja.write_role_prompt(pack, "risk_judge", crit_seed)
    assert not (pack_dir / "council_roles" / "risk_judge.txt").read_text().startswith(crit_seed)
    assert (overlay_dir / pack / "council_roles" / "risk_judge.txt").read_text().strip() == crit_seed
    # and the read path resolves the SAME overlay copy
    prompts = pack_mod.pack_prompts_path(pack)
    assert prompts == overlay_dir / pack / "council_roles"


# ── A2 — the prompts dir materializes the pack SEED (whole-dir copy-on-first-resolve) ──


def test_prompts_dir_materializes_seed_prompts(image_pack, overlay_dir):
    from lithrim_bench.harness import pack as pack_mod

    pack, pack_dir, _ = image_pack
    prompts = pack_mod.pack_prompts_path(pack)
    assert prompts == overlay_dir / pack / "council_roles"
    # every seed role prompt is present + byte-identical (the council globs this ONE dir; a
    # partial overlay would drop seed roles from the roster gate)
    seed = {p.name: p.read_bytes() for p in (pack_dir / "council_roles").glob("*.txt")}
    assert seed  # non-vacuous: _core ships the trio seeds
    for name, body in seed.items():
        assert (prompts / name).read_bytes() == body


# ── A3 — THE incident: authored criterion+judge survive an image-layer reversion ──────


def test_authored_identity_survives_image_layer_reversion(image_pack, overlay_dir):
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.runtime.council.judge_assignment import load_role_prompt

    pack, pack_dir, pristine = image_pack
    # author, exactly what POST /v1/criterion then POST /v1/judges do (splice + prompt seed)
    crit.splice_gradeable_criterion(pack, "AUTHORED_CHECK", "TIER_2", "risk_judge")
    ja.splice_production_judge(pack, "authored_judge", ["AUTHORED_CHECK"], [])
    prompt_text = "authored_judge: raise only its assigned lens, grounded in an evidence span."
    ja.write_role_prompt(pack, "authored_judge", prompt_text)

    # `docker compose up` recreates the container: the image layer REVERTS to the shipped pack;
    # the volume (overlay) survives; the new process starts with cold caches.
    shutil.rmtree(pack_dir)
    shutil.copytree(pristine, pack_dir)
    _clear_pack_caches()

    # the grade path resolves the authored identity from the surviving overlay
    assert "authored_judge" in pack_mod.pack_production_judges(pack)
    assert "AUTHORED_CHECK" in pack_mod.pack_taxonomy_codes(pack)
    assert "AUTHORED_CHECK" in pack_mod.pack_lenses(pack)["authored_judge"]
    prompts = pack_mod.pack_prompts_path(pack)  # judges-consistency gate passes too
    assert load_role_prompt("authored_judge", prompts_dir=prompts) == prompt_text
    # the seed roles still resolve (the overlay is a full copy, not a partial shadow)
    assert load_role_prompt("risk_judge", prompts_dir=prompts)


# ── A4 — rollback (restore_snapshot) hits the overlay too, never the image ────────────


def test_restore_snapshot_targets_overlay(image_pack, overlay_dir):
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import pack as pack_mod

    pack, pack_dir, _ = image_pack
    image_before = (pack_dir / "taxonomy_snapshot.json").read_bytes()
    before, _after = crit.splice_gradeable_criterion(pack, "AUTHORED_CHECK", "T2", "risk_judge")
    crit.restore_snapshot(pack, before)  # the BFF's post-splice-failure atomicity backstop
    assert "AUTHORED_CHECK" not in pack_mod.pack_taxonomy_codes(pack)
    assert (pack_dir / "taxonomy_snapshot.json").read_bytes() == image_before


# ── B — CouncilRosterRequest: a misspelled field must 422, never silently clear ───────


@pytest.fixture
def roster_client(tmp_path, monkeypatch, image_pack):
    """A hermetic BFF client whose active workspace is pinned to the throwaway pack."""
    import app as bff
    from fastapi.testclient import TestClient

    from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

    pack, _pack_dir, _ = image_pack
    db = tmp_path / "bench_config.sqlite"
    ag = Agent(
        name="roster_test",
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={},
            ontology_ref="core/1",
            ontology_path=str(REPO_ROOT / "packs" / "_core" / "ontology.json"),
            tools=(),
            kb_bindings={},
            severity_map_ref="ontology:core/1",
        ),
        dataset=Dataset(case_id="c1", source="unused.jsonl", baseline="unused.json"),
    )
    save_agent(ag, db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="overlay_ws", pack=pack),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_council_roster_request_rejects_unknown_fields():
    import app as bff
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        bff.CouncilRosterRequest(agent="roster_test", rosterr=["risk_judge"])


def test_misspelled_roster_field_is_422_not_a_silent_clear(roster_client):
    r = roster_client.post(
        "/v1/council/roster", json={"agent": "roster_test", "roster": ["risk_judge"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["reviewer_roster"] == ["risk_judge"]
    # the incident shape: a misspelled field parsed as {roster: None} → 200 + roster CLEARED
    r2 = roster_client.post(
        "/v1/council/roster", json={"agent": "roster_test", "rosterr": ["risk_judge"]}
    )
    assert r2.status_code == 422, r2.text
    r3 = roster_client.get("/v1/council/roster", params={"agent": "roster_test"})
    assert r3.json()["reviewer_roster"] == ["risk_judge"]  # NOT cleared
