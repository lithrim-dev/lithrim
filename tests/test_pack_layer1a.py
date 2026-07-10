"""PACK-1 layer-1a — the core loads its ontology + taxonomy from the active
`healthcare` pack, not a hardcoded clinical path (healthcare-realm-as-pack).

The verifiable boundary (D5/A1): the CORE package + the config seeds carry no
clinical content path; the only residual old-path strings in ``scripts/`` are
``taxonomy_snapshot`` PROVENANCE LABELS stamped into already-committed corpora (a
documented carve-out — those are output metadata recording where the snapshot lived
at build time, not live load dependencies; the live ``load_taxonomy()`` resolves via
the pack). The consistency gate (D4/A3) kept the loaded pack council-compatible while the
council still owned a hardcoded ``KNOWN_TAXONOMY_CODES`` copy; **layer 1b flipped that** — the
council now reads its codes FROM the pack (``pack.pack_tiers``), so ``council_known_codes()``
reads the same snapshot and the gate is a self-consistency no-op (see ``test_pack_layer1b``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lithrim_bench.harness import pack
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.taxonomy import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parents[1]

# The two clinical content paths that relocated into the pack. Both slash-string and
# Path-segment forms, so a re-introduced hardcode in either style is caught.
_OLD_NEEDLES = (
    "data/ontology/clinical_v1.json",
    "taxonomy/taxonomy_snapshot.json",
    '"data" / "ontology" / "clinical_v1.json"',
    '"taxonomy" / "taxonomy_snapshot.json"',
)


def _hits(root: Path) -> list[str]:
    out: list[str] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in {".py", ".json"} or "__pycache__" in f.parts:
            continue
        try:
            text = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(n in line for n in _OLD_NEEDLES):
                out.append(f"{f.relative_to(REPO_ROOT)}:{i}: {line.strip()}")
    return out


# ───────────────────────────── D5 / A1 — the boundary ─────────────────────────────
def test_core_package_carries_no_clinical_content_path():
    """``lithrim_bench/`` (the core) names no relocated clinical path — the live load
    resolves via the active pack. EXCLUDES this test file's own needles by location."""
    hits = _hits(REPO_ROOT / "lithrim_bench")
    assert hits == [], "core package still hardcodes a relocated clinical path:\n" + "\n".join(hits)


def test_config_seeds_carry_no_old_ontology_path():
    """The agent seeds reference the pack ontology, not the old clinical path."""
    hits = _hits(REPO_ROOT / "data" / "config")
    assert hits == [], "a config seed still hardcodes the old ontology path:\n" + "\n".join(hits)


def test_scripts_live_load_path_is_clean():
    """In ``scripts/`` the ONLY permitted residual old-path strings are the
    ``taxonomy_snapshot`` provenance LABELS (documented carve-out). Any other residual
    (i.e. a live load path) fails — keeping this guard non-vacuous."""
    residual = [h for h in _hits(REPO_ROOT / "scripts") if "taxonomy_snapshot" not in h]
    assert residual == [], "a script still hardcodes a relocated clinical LOAD path:\n" + "\n".join(
        residual
    )


# ───────────────────────── active-pack resolution (D1/D3) ─────────────────────────
def test_active_pack_defaults_to_healthcare():
    assert pack.active_pack() == "healthcare"
    assert pack.pack_ontology_path().name == "ontology.json"
    assert pack.pack_ontology_path().parent.name == "healthcare"
    assert pack.pack_taxonomy_path().name == "taxonomy_snapshot.json"
    assert pack.pack_ontology_path().exists()
    assert pack.pack_taxonomy_path().exists()


# PACK-DIST-2 D5: test_core_defaults_resolve_through_the_pack relocated (GENERICIZED) to the pack
# repo (tests/test_pack_layer1a_relocated.py) — it asserted the literal 'packs/healthcare' in the
# resolved paths, STALE once the pack lives outside the CE tree; the pack version asserts resolution
# to pack._pack_root('healthcare')/… instead. The generic boundary funcs + NEEDS_PACK funcs stay.


# ─────────────────────────── A2 — byte-behavior identity ───────────────────────────
def test_loaded_ontology_is_the_clinical_domain():
    ont = load_ontology()
    assert ont.ontology_version == "clinical/1"
    assert ont.domain == "clinical"
    # the gradeable set is exactly the frozen council's known codes (19).
    assert {f.flag for f in ont.gradeable_flags()} == set(pack.council_known_codes())


def test_loaded_taxonomy_matches_the_council():
    tax = load_taxonomy()
    assert set(tax.known_codes) == set(pack.council_known_codes())


# ─────────────────── D4 / A3 — the consistency gate (non-vacuous) ───────────────────
def test_healthcare_pack_is_council_consistent():
    # does not raise; the council's frozen set is the real 19 codes.
    pack.assert_pack_council_consistent("healthcare")
    assert len(pack.council_known_codes()) == 19


def test_gate_fails_closed_on_an_unknown_code():
    known = set(pack.council_known_codes())
    # a subset of real codes passes…
    pack.assert_codes_known(frozenset(list(known)[:3]))
    # …an out-of-council code fails closed.
    with pytest.raises(pack.PackConsistencyError) as ei:
        pack.assert_codes_known(known | {"NOT_A_REAL_TAXONOMY_CODE"})
    assert "NOT_A_REAL_TAXONOMY_CODE" in str(ei.value)


def test_council_codes_resolve_from_the_pack_without_importing_openai():
    """``council_known_codes()`` resolves the taxonomy with no council import and no
    ``openai`` — so it runs in the core (no-openai) env. Post layer-1b the council reads its
    codes FROM the pack, so this reads the SAME snapshot directly (it no longer AST-parses the
    council's literals — those are now ``pack_tiers()`` subscripts a ``literal_eval`` would
    reject). The green run with openai absent is itself the proof; here we pin that it yields
    real codes (not an empty/vacuous set)."""
    codes = pack.council_known_codes()
    assert "WRONG_DOSAGE" in codes and "MISSING_ALLERGY" in codes


def _clear_known_codes_cache() -> None:
    """Clear whatever cache backs ``council_known_codes`` — the function itself pre-fix
    (``@lru_cache`` on the argless accessor), the pack-keyed helper post-fix. Agnostic so the
    regression below is RED on the stale code and GREEN on the keyed fix without an edit."""
    for name in ("council_known_codes", "_council_known_codes"):
        cache_clear = getattr(getattr(pack, name, None), "cache_clear", None)
        if cache_clear:
            cache_clear()


def test_council_known_codes_tracks_active_pack_flip(monkeypatch):
    """REGRESSION (S-BS-156): ``council_known_codes()`` MUST follow ``active_pack()`` WITHIN a
    process. The ``maxsize=1`` cache returned the first-resolved pack's codes forever, so an
    in-process pack flip (the BFF serving a healthcare flag op after first resolving the neutral
    ``_core`` default) mis-fired ``assert_pack_council_consistent`` — healthcare's 19 codes
    checked against the stale 8 ``_core`` codes → ``PackConsistencyError``. Keyed by pack, the
    flip resolves live."""
    _clear_known_codes_cache()
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "_core")
    core_codes = pack.council_known_codes()
    assert "WRONG_DOSAGE" not in core_codes  # the neutral pack carries no clinical codes

    monkeypatch.setenv("LITHRIM_BENCH_PACK", "healthcare")
    flipped = pack.council_known_codes()
    assert flipped == pack._pack_taxonomy_codes("healthcare")  # tracks the flip, not stale _core
    assert "WRONG_DOSAGE" in flipped and len(flipped) == 19
    _clear_known_codes_cache()
