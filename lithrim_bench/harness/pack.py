"""Active-pack resolution — the core loads its ontology + taxonomy from a *pack*,
not a hardcoded clinical path (healthcare-realm-as-pack, layer 1a).

A **pack** is a domain bundle: a manifest (``packs/<id>/pack.json``) that names the
pack's ontology + taxonomy (flags) + judges. The core resolves the **active pack**
(default ``healthcare``; override via ``LITHRIM_BENCH_PACK``) and reads the
ontology/taxonomy paths from its manifest — so the core itself carries no clinical
content path. ``harness/ontology.py`` and ``taxonomy.py`` resolve their defaults
through here; relocating the clinical realm into ``packs/healthcare/`` is what makes
the core↔domain boundary grep-verifiable (no ``clinical_v1`` literal in the core).

The **consistency gate** (:func:`assert_pack_council_consistent`) bridges to the
still-FROZEN council: it asserts the loaded pack's taxonomy codes are a subset of the
council's ``KNOWN_TAXONOMY_CODES`` while that set stays hardcoded in the frozen
``compliance_council.py`` (un-freezing it is layer 1b). The council's codes are read
by AST-parsing its source — NOT by importing it: the core (OSS) env has no ``openai``,
so ``import ...compliance_council`` fails there; a textual parse is dependency-free and
read-only (the same technique ``scripts/seed_ontology.py`` uses).
"""

from __future__ import annotations

import ast
import json
import os
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "packs"
DEFAULT_PACK = "healthcare"
_COUNCIL_SOURCE = (
    REPO_ROOT / "lithrim_bench" / "runtime" / "council" / "compliance_council.py"
)
_COUNCIL_TIER_NAMES = ("TIER_1_NEVER_EVENTS", "TIER_2_HIGH_RISK", "TIER_3_MEDIUM")


class PackConsistencyError(RuntimeError):
    """A loaded pack declares taxonomy codes the frozen council does not know.

    Fail-closed: a pack whose codes are not ⊆ ``KNOWN_TAXONOMY_CODES`` would be scored
    by a council that discards them before consensus, so it does not load (this is the
    1a bridge that lets the council stay frozen — 1b removes the gate by reading the
    council's codes FROM the pack).
    """


def active_pack() -> str:
    """The active pack id. Default ``healthcare``; override via ``LITHRIM_BENCH_PACK``."""
    return os.environ.get("LITHRIM_BENCH_PACK") or DEFAULT_PACK


@lru_cache(maxsize=8)
def _manifest(pack: str) -> dict:
    path = PACKS_DIR / pack / "pack.json"
    if not path.exists():
        raise FileNotFoundError(f"pack manifest not found: {path}")
    return json.loads(path.read_text())


def _resolve(ref: str) -> Path:
    p = Path(ref)
    return p if p.is_absolute() else REPO_ROOT / p


@lru_cache(maxsize=1)
def council_known_codes() -> frozenset[str]:
    """The frozen council's ``KNOWN_TAXONOMY_CODES`` (TIER_1|2|3), AST-parsed from
    source — no import (``openai`` is absent in the core env)."""
    tree = ast.parse(_COUNCIL_SOURCE.read_text())
    codes: set[str] = set()
    for name in _COUNCIL_TIER_NAMES:
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets
            ):
                codes.update(ast.literal_eval(node.value))
                break
        else:
            raise KeyError(f"{name!r} not found in council source {_COUNCIL_SOURCE}")
    return frozenset(codes)


def assert_codes_known(codes: frozenset[str] | set[str], *, pack: str = "<pack>") -> None:
    """Fail-closed iff ``codes`` is not ⊆ the frozen council's known codes.

    The pure check, separated from disk I/O so the fail-closed path is test-pinnable
    on a crafted code set without writing a bad pack to disk (A3, non-vacuous)."""
    extra = frozenset(codes) - council_known_codes()
    if extra:
        raise PackConsistencyError(
            f"pack {pack!r} declares taxonomy codes not in the frozen council "
            f"KNOWN_TAXONOMY_CODES: {sorted(extra)}"
        )


def _pack_taxonomy_codes(pack: str) -> frozenset[str]:
    snap = json.loads(_resolve(_manifest(pack)["flags_ref"]).read_text())
    codes: set[str] = set()
    for tier in snap["tiers"].values():
        codes.update(tier)
    return frozenset(codes)


@lru_cache(maxsize=8)
def assert_pack_council_consistent(pack: str) -> None:
    """Assert the pack's taxonomy codes ⊆ the frozen council's known codes (cached;
    runs once per pack per process, on first ontology/taxonomy resolution)."""
    assert_codes_known(_pack_taxonomy_codes(pack), pack=pack)


def pack_ontology_path(pack: str | None = None) -> Path:
    """The active (or named) pack's ontology JSON path, gated for council-consistency."""
    pack = pack or active_pack()
    assert_pack_council_consistent(pack)
    return _resolve(_manifest(pack)["ontology"])


def pack_taxonomy_path(pack: str | None = None) -> Path:
    """The active (or named) pack's taxonomy-snapshot path, gated for council-consistency."""
    pack = pack or active_pack()
    assert_pack_council_consistent(pack)
    return _resolve(_manifest(pack)["flags_ref"])
