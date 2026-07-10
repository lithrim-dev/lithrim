"""PHASE2-A — the sanctioned production-judge authoring writer (harness level).

``harness.judge_authoring.splice_production_judge`` is the STRUCTURAL TWIN of
``harness.criterion.splice_gradeable_criterion`` (the gradeable-code snapshot writer, owner
sign-off 2026-06-21): the SECOND audited writer above the CLAUDE.md "never hand-edit the
snapshot" invariant (owner sign-off 2026-06-25, the §8 arbitrary-judges probe discharged). It
splices a new ``production_judges`` role + its ``lenses[role]`` + (for owned codes) the
``tier1_owners`` entries into a tier:core pack's taxonomy snapshot, behind an author-time
by-construction admissibility gate (roster≥2, lens non-empty, codes ∈ taxonomy, owner↔emit).

These tests exercise the writer DIRECTLY on a throwaway copy of ``packs/support_ticket_qa`` (a
genuinely independent tier:core pack — its own ontology + council_roles + snapshot, no
``packs/healthcare/`` reuse): the happy path (A), the admissibility rejections (B–E, each must
write NOTHING), the atomicity backstop (F), the role-prompt seed (G), and the wall-#4 relaxation
(H — a newly spliced ``production_judges`` role is roster-known, a still-unknown role still
FAILS). The moat/council is never imported here.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_pack(tmp_path: Path, name: str, tier: str = "core") -> str:
    """Copy ``packs/support_ticket_qa`` into ``tmp_path/<name>`` with the given tier; return the
    pack id. support_ticket_qa is the writable tier:core fixture — a genuinely independent pack
    with its own taxonomy/lenses/tier1_owners (no healthcare reuse)."""
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "packs" / "support_ticket_qa", dst)
    manifest = json.loads((dst / "pack.json").read_text())
    manifest["pack_id"] = name
    manifest["tier"] = tier
    (dst / "pack.json").write_text(json.dumps(manifest, indent=2))
    return name


@pytest.fixture
def core_pack(tmp_path, monkeypatch):
    """A discoverable throwaway tier:core pack (a copy of support_ticket_qa) — the writer's vehicle."""
    from lithrim_bench.harness import pack as pack_mod

    name = _make_pack(tmp_path, "corejudgepack", tier="core")
    existing = os.environ.get("LITHRIM_BENCH_PACKS_DIR", "")
    monkeypatch.setenv(
        "LITHRIM_BENCH_PACKS_DIR", str(tmp_path) + (os.pathsep + existing if existing else "")
    )
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    yield name
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()


def _snapshot(pack: str) -> dict:
    from lithrim_bench.harness import pack as pack_mod

    return json.loads(pack_mod._pack_ref(pack, "flags_ref").read_text())


# ── A — splice a new production judge: production_judges + lenses + tier1_owners updated ──


def test_splice_adds_role_lens_and_owners(core_pack):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    # CONTRADICTS_THREAD + UNRESOLVED_ISSUE are in the support_ticket_qa taxonomy; own one of them.
    before, after = ja.splice_production_judge(
        core_pack,
        "escalation_judge",
        lens_codes=["CONTRADICTS_THREAD", "UNRESOLVED_ISSUE"],
        owned_codes=["UNRESOLVED_ISSUE"],
    )
    # before is the pristine snapshot — the new role is absent
    assert "escalation_judge" not in before["production_judges"]
    assert "escalation_judge" not in before["lenses"]

    snap = _snapshot(core_pack)
    # production_judges gains the role (appended → order preserved)
    assert snap["production_judges"][-1] == "escalation_judge"
    assert "escalation_judge" in snap["production_judges"]
    # lenses[role] = sorted(lens_codes)
    assert snap["lenses"]["escalation_judge"] == ["CONTRADICTS_THREAD", "UNRESOLVED_ISSUE"]
    # tier1_owners[code] gains the role for each owned code
    assert "escalation_judge" in snap["tier1_owners"]["UNRESOLVED_ISSUE"]
    # a non-owned lens code does NOT gain a tier1_owners entry
    assert "CONTRADICTS_THREAD" not in snap["tier1_owners"]

    # the live accessors + caches reflect it immediately (the writer cleared them)
    assert "escalation_judge" in pack_mod.pack_production_judges(core_pack)
    assert pack_mod.pack_lenses(core_pack)["escalation_judge"] == frozenset(
        {"CONTRADICTS_THREAD", "UNRESOLVED_ISSUE"}
    )
    assert "escalation_judge" in pack_mod.pack_tier1_owners(core_pack)["UNRESOLVED_ISSUE"]
    # the after dict mirrors the persisted snapshot
    assert after["production_judges"] == snap["production_judges"]
    assert after["lenses"]["escalation_judge"] == snap["lenses"]["escalation_judge"]


# ── B — owner ⊄ lens (the inert-owner guard): rejected WITHOUT writing ──


def test_owned_not_subset_of_lens_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import judge_authoring as ja

    snap_before = _snapshot(core_pack)
    with pytest.raises(ja.InertOwnerError):
        ja.splice_production_judge(
            core_pack,
            "triage_judge",
            lens_codes=["CONTRADICTS_THREAD"],
            owned_codes=["UNRESOLVED_ISSUE"],  # owns a code it cannot emit → inert owner
        )
    assert _snapshot(core_pack) == snap_before  # rejection wrote nothing


# ── C — a code ∉ the pack taxonomy: rejected WITHOUT writing ──


def test_code_outside_taxonomy_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import judge_authoring as ja

    snap_before = _snapshot(core_pack)
    with pytest.raises(ja.UnknownCodeError):
        ja.splice_production_judge(
            core_pack,
            "triage_judge",
            lens_codes=["NOT_A_REAL_CODE"],
            owned_codes=[],
        )
    assert _snapshot(core_pack) == snap_before


# ── D — a non-core (tier:pro) pack: the NonCorePackError twin, no write ──


def test_non_core_pack_rejected_and_no_write(tmp_path, monkeypatch):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    name = _make_pack(tmp_path, "projudgepack", tier="pro")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path))
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    snap_before = _snapshot(name)
    with pytest.raises(ja.NonCorePackError):
        ja.splice_production_judge(
            name,
            "triage_judge",
            lens_codes=["CONTRADICTS_THREAD"],
            owned_codes=[],
        )
    assert _snapshot(name) == snap_before
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()


# ── E — a role-id colliding with an existing production_judges entry: rejected, no write ──


def test_role_id_collision_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import judge_authoring as ja

    snap_before = _snapshot(core_pack)
    with pytest.raises(ja.RoleCollisionError):
        ja.splice_production_judge(
            core_pack,
            "risk_judge",  # already in production_judges
            lens_codes=["CONTRADICTS_THREAD"],
            owned_codes=[],
        )
    assert _snapshot(core_pack) == snap_before


def test_malformed_role_id_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import judge_authoring as ja

    snap_before = _snapshot(core_pack)
    for bad in ["", "   ", "UpperCase", "has space", "9leads_digit", "bad;DROP", "Mixed_Judge"]:
        with pytest.raises(ja.BadRoleIdError):
            ja.splice_production_judge(
                core_pack, bad, lens_codes=["CONTRADICTS_THREAD"], owned_codes=[]
            )
    assert _snapshot(core_pack) == snap_before


def test_empty_lens_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import judge_authoring as ja

    snap_before = _snapshot(core_pack)
    with pytest.raises(ja.EmptyLensError):
        ja.splice_production_judge(core_pack, "triage_judge", lens_codes=[], owned_codes=[])
    assert _snapshot(core_pack) == snap_before


# ── F — ATOMIC: a failure AFTER the snapshot write leaves the snapshot RESTORED ──


def test_restore_snapshot_rolls_back(core_pack):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    before, _ = ja.splice_production_judge(
        core_pack, "triage_judge", lens_codes=["CONTRADICTS_THREAD"], owned_codes=[]
    )
    assert "triage_judge" in pack_mod.pack_production_judges(core_pack)
    ja.restore_snapshot(core_pack, before)
    assert "triage_judge" not in pack_mod.pack_production_judges(core_pack)
    assert _snapshot(core_pack) == before


def test_rollback_is_byte_faithful(core_pack):
    """A content-identical rollback leaves the snapshot file BYTE-identical (ensure_ascii=False)."""
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    snap_path = pack_mod._pack_ref(core_pack, "flags_ref")
    original = snap_path.read_bytes()
    before, _ = ja.splice_production_judge(
        core_pack, "triage_judge", lens_codes=["CONTRADICTS_THREAD"], owned_codes=[]
    )
    ja.restore_snapshot(core_pack, before)
    assert snap_path.read_bytes() == original


# ── G — write_role_prompt creates council_roles/<role>.txt ──


def test_write_role_prompt_creates_seed(core_pack):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    ja.write_role_prompt(core_pack, "escalation_judge", "You verify escalation policy.")
    prompts_dir = pack_mod._pack_ref(core_pack, "council_roles")
    seed = prompts_dir / "escalation_judge.txt"
    assert seed.is_file()
    assert seed.read_text().strip() == "You verify escalation policy."


def test_write_role_prompt_rejects_non_core(tmp_path, monkeypatch):
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    name = _make_pack(tmp_path, "proprompt", tier="pro")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path))
    pack_mod._pack_root.cache_clear()
    with pytest.raises(ja.NonCorePackError):
        ja.write_role_prompt(name, "escalation_judge", "x")
    pack_mod._pack_root.cache_clear()


# ── H — wall-#4 relaxation: a spliced production_judges role is roster-known; non-vacuous ──


def test_wall4_relaxation_admits_spliced_role(core_pack):
    """After splicing a new ``production_judges`` role (+ its prompt seed), the pack's judge-
    consistency gate PASSES for that role — the active pack's ``production_judges`` is now
    roster-known. NON-VACUOUS: a role NOT in production_judges (and not on the canonical roster)
    still FAILS."""
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    ja.splice_production_judge(
        core_pack,
        "escalation_judge",
        lens_codes=["CONTRADICTS_THREAD", "UNRESOLVED_ISSUE"],
        owned_codes=["UNRESOLVED_ISSUE"],
    )
    ja.write_role_prompt(core_pack, "escalation_judge", "You verify escalations.")
    # add the new role to the manifest's declared judges (the pack now runs it)
    manifest_path = pack_mod._pack_root(core_pack) / "pack.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["judges"] = [*manifest["judges"], "escalation_judge"]
    manifest_path.write_text(json.dumps(manifest, indent=2))
    pack_mod._manifest.cache_clear()
    pack_mod.assert_pack_judges_consistent.cache_clear()

    # PASSES: the spliced production-judge role is now roster-known for THIS pack.
    pack_mod.assert_pack_judges_consistent(core_pack)

    # NON-VACUOUS: a still-unknown role (declared but never spliced, off the canonical roster)
    # still fails the pure gate against this pack's relaxed roster. prompt_stems is EMPTY so ONLY
    # the declared-∉-roster leg can raise — otherwise the stray-prompt leg would mask a regression
    # in the fail-closed leg (critic P2A Q3, sharpening test H's targeting).
    roster = pack_mod.council_roster() | set(pack_mod.pack_production_judges(core_pack))
    assert "escalation_judge" in roster  # the relaxation added it
    with pytest.raises(pack_mod.PackConsistencyError) as ei:
        pack_mod.assert_judges_known(
            ["never_spliced_judge"], [], roster=frozenset(roster)
        )
    assert "never_spliced_judge" in str(ei.value)


def test_wall4_canonical_roster_unchanged_for_existing_packs(core_pack):
    """The relaxation is ADDITIVE: ``council_roster()`` (the canonical AST ∪ DEFAULT_PACK-owner
    set) is UNCHANGED — the spliced role lives only in the ACTIVE pack's production_judges, not
    in the council's intrinsic roster (so existing pack-consistency stays intact)."""
    from lithrim_bench.harness import judge_authoring as ja
    from lithrim_bench.harness import pack as pack_mod

    canonical_before = set(pack_mod.council_roster())
    ja.splice_production_judge(
        core_pack,
        "escalation_judge",
        lens_codes=["CONTRADICTS_THREAD"],
        owned_codes=[],
    )
    assert "escalation_judge" not in canonical_before
    assert set(pack_mod.council_roster()) == canonical_before  # canonical roster untouched
