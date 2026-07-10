"""NARR-5-CRIT-a — the sanctioned gradeable-criterion snapshot writer (harness level).

``harness.criterion.splice_gradeable_criterion`` is the FIRST audited writer above the
CLAUDE.md "never hand-edit the snapshot" invariant (owner sign-off 2026-06-21). It splices a
new gradeable code into a tier:core pack's taxonomy snapshot so the existing admissibility gate
then passes for it. These tests exercise the writer DIRECTLY on a throwaway copy of ``packs/_core``
(no BFF, no repo-source mutation): the happy paths (T2 + T1), the four rejections (each must write
NOTHING), the tier aliasing, and the cache clear. The moat/council is never imported here.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_pack(tmp_path: Path, name: str, tier: str = "core") -> str:
    """Copy ``packs/_core`` into ``tmp_path/<name>`` with the given tier; return the pack id."""
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "packs" / "_core", dst)
    manifest = json.loads((dst / "pack.json").read_text())
    manifest["pack_id"] = name
    manifest["tier"] = tier
    (dst / "pack.json").write_text(json.dumps(manifest, indent=2))
    return name


@pytest.fixture
def core_pack(tmp_path, monkeypatch):
    """A discoverable throwaway tier:core pack (a copy of _core) — the writer's test vehicle."""
    from lithrim_bench.harness import pack as pack_mod

    name = _make_pack(tmp_path, "corepack", tier="core")
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


# ── A1 — splice a Tier-2 criterion: tiers + lenses updated, tier1_owners untouched ──


def test_splice_tier2_updates_tiers_and_lenses(core_pack):
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import pack as pack_mod

    before, after = crit.splice_gradeable_criterion(
        core_pack, "EVERY_DOSE_IN_SOAP", "TIER_2", "faithfulness_judge"
    )
    assert "EVERY_DOSE_IN_SOAP" not in before["tiers"]["TIER_2_HIGH_RISK"]
    snap = _snapshot(core_pack)
    assert "EVERY_DOSE_IN_SOAP" in snap["tiers"]["TIER_2_HIGH_RISK"]
    assert "EVERY_DOSE_IN_SOAP" in snap["lenses"]["faithfulness_judge"]
    # a T2 criterion does NOT touch the one-strike T1 owner-map
    assert "EVERY_DOSE_IN_SOAP" not in snap.get("tier1_owners", {})
    # the live accessors + the cache reflect it immediately (cache cleared by the writer)
    assert "EVERY_DOSE_IN_SOAP" in pack_mod.pack_taxonomy_codes(core_pack)
    assert "EVERY_DOSE_IN_SOAP" in pack_mod.pack_lenses(core_pack)["faithfulness_judge"]
    # the after dict mirrors the persisted snapshot
    assert after["tiers"]["TIER_2_HIGH_RISK"] == snap["tiers"]["TIER_2_HIGH_RISK"]


# ── A2 — splice a Tier-1 criterion: tier1_owners gains the one-strike owner ──


def test_splice_tier1_sets_tier1_owner(core_pack):
    from lithrim_bench.harness import criterion as crit

    crit.splice_gradeable_criterion(core_pack, "PATIENT_HARM_OMITTED", "T1", "risk_judge")
    snap = _snapshot(core_pack)
    assert "PATIENT_HARM_OMITTED" in snap["tiers"]["TIER_1_NEVER_EVENTS"]
    assert "PATIENT_HARM_OMITTED" in snap["lenses"]["risk_judge"]
    assert snap["tier1_owners"]["PATIENT_HARM_OMITTED"] == ["risk_judge"]


# ── A3 — a non-production-judge owner is rejected WITHOUT writing ──


def test_unknown_owner_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import criterion as crit

    snap_before = _snapshot(core_pack)
    with pytest.raises(crit.UnknownOwnerError):
        crit.splice_gradeable_criterion(core_pack, "X_CODE", "TIER_2", "not_a_real_judge")
    assert _snapshot(core_pack) == snap_before  # rejection wrote nothing


# ── A4 — a duplicate code is a 409-class rejection, no write ──


def test_duplicate_code_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import criterion as crit

    snap_before = _snapshot(core_pack)
    with pytest.raises(crit.DuplicateCriterionError):
        crit.splice_gradeable_criterion(core_pack, "STYLE_VIOLATION", "TIER_3", "policy_judge")
    assert _snapshot(core_pack) == snap_before


# ── A5 — a tier:pro pack is refused (its snapshot is a backend re-snapshot) ──


def test_non_core_pack_rejected(tmp_path, monkeypatch):
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import pack as pack_mod

    name = _make_pack(tmp_path, "propack", tier="pro")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path))
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    snap_before = _snapshot(name)
    with pytest.raises(crit.NonCorePackError):
        crit.splice_gradeable_criterion(name, "X_CODE", "TIER_2", "faithfulness_judge")
    assert _snapshot(name) == snap_before
    pack_mod._pack_root.cache_clear()


# ── A6 — bad tier rejected; the alias resolution is correct ──


def test_bad_tier_rejected_and_aliases(core_pack):
    from lithrim_bench.harness import criterion as crit

    snap_before = _snapshot(core_pack)
    with pytest.raises(crit.BadTierError):
        crit.splice_gradeable_criterion(core_pack, "X_CODE", "TIER_9", "policy_judge")
    assert _snapshot(core_pack) == snap_before

    assert crit.resolve_tier_name("T2") == "TIER_2_HIGH_RISK"
    assert crit.resolve_tier_name("TIER_2") == "TIER_2_HIGH_RISK"
    assert crit.resolve_tier_name("TIER_2_HIGH_RISK") == "TIER_2_HIGH_RISK"
    assert crit.short_tier_name("TIER_2_HIGH_RISK") == "TIER_2"
    assert crit.short_tier_name("T1") == "TIER_1"


# ── A8 (F1) — a malformed/empty code is refused WITHOUT writing (contract-of-record guard) ──


def test_malformed_code_rejected_and_no_write(core_pack):
    from lithrim_bench.harness import criterion as crit

    snap_before = _snapshot(core_pack)
    for bad in ["", "   ", "lower_case", "a;DROP", "9LEADS_DIGIT", "HAS SPACE", "Mixed_Case"]:
        with pytest.raises(crit.BadCodeError):
            crit.splice_gradeable_criterion(core_pack, bad, "TIER_2", "policy_judge")
    assert _snapshot(core_pack) == snap_before  # not one bad code leaked into the snapshot


# ── A7 — restore_snapshot rolls the splice back (the BFF atomicity backstop) ──


def test_restore_snapshot_rolls_back(core_pack):
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import pack as pack_mod

    before, _ = crit.splice_gradeable_criterion(core_pack, "TMP_CODE", "TIER_2", "policy_judge")
    assert "TMP_CODE" in pack_mod.pack_taxonomy_codes(core_pack)
    crit.restore_snapshot(core_pack, before)
    assert "TMP_CODE" not in pack_mod.pack_taxonomy_codes(core_pack)
    assert _snapshot(core_pack) == before


def test_rollback_is_byte_faithful(core_pack):
    """Live A-LIVE NIT (F6-followup): a content-identical rollback leaves the snapshot file
    BYTE-identical — ensure_ascii=False preserves the raw unicode the snapshot stores, so a
    splice-then-restore is a true no-op (no spurious git-dirty / re-escaped em-dashes)."""
    from lithrim_bench.harness import criterion as crit
    from lithrim_bench.harness import pack as pack_mod

    snap_path = pack_mod._pack_ref(core_pack, "flags_ref")
    original = snap_path.read_bytes()
    before, _ = crit.splice_gradeable_criterion(core_pack, "TMP_CODE", "TIER_2", "policy_judge")
    crit.restore_snapshot(core_pack, before)
    assert snap_path.read_bytes() == original  # byte-faithful: no reformat, no re-escaping
    assert "\\u" not in snap_path.read_text()  # raw unicode preserved, not ASCII-escaped
