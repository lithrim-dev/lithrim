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
import importlib.util
import json
import os
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "packs"
DEFAULT_PACK = "healthcare"
_COUNCIL_SOURCE = REPO_ROOT / "lithrim_bench" / "runtime" / "council" / "compliance_council.py"
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


# ─────────────────────────── the judges layer (PACK-2) ───────────────────────────
# Layer 2 relocates the clinical council role prompts (``council_roles/*.txt``) into the
# pack. The frozen council still globs the prompt files itself, so its ``_ROLE_PROMPTS_DIR``
# is repointed here via an AUTHORIZED path-only carve-out — the same shape as the codes
# gate above: a textual (AST-parse, no-import) bridge keeps the council frozen while the
# domain content lives in the pack. Un-hardcoding the roster/lenses themselves is layer 2b.


@lru_cache(maxsize=1)
def council_roster() -> frozenset[str]:
    """Every judge role the frozen council knows, AST-parsed from its source — no import.

    The union of the ``CouncilModel(name=…, prompt_role=…)`` roster (across both the v2
    and v1 branches → risk/policy/faithfulness/behavior) and the ``_TIER1_OWNERS`` owner
    sets (which carry the dormant ``source_message_judge``). This is the authoritative
    "known role" set the judges gate checks against — the same no-import technique as
    :func:`council_known_codes`."""
    tree = ast.parse(_COUNCIL_SOURCE.read_text())
    roles: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CouncilModel"
        ):
            for kw in node.keywords:
                if kw.arg in ("name", "prompt_role") and isinstance(kw.value, ast.Constant):
                    roles.add(kw.value.value)
    for node in tree.body:
        # ``_TIER1_OWNERS: Dict[str, set] = {…}`` is an annotated assignment.
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "_TIER1_OWNERS" for t in targets):
            for owners in ast.literal_eval(node.value).values():
                roles.update(owners)
            break
    else:
        raise KeyError(f"'_TIER1_OWNERS' not found in council source {_COUNCIL_SOURCE}")
    return frozenset(roles)


def assert_judges_known(
    declared: Iterable[str],
    prompt_stems: Iterable[str],
    *,
    roster: frozenset[str] | None = None,
    pack: str = "<pack>",
) -> None:
    """The pure judges-consistency check (no disk I/O), so the fail-closed path is
    test-pinnable on crafted sets without writing a bad pack to disk (A3, non-vacuous):

      (i)  every declared judge is a council-known role,
      (ii) every declared judge has a relocated prompt file,
      (iii) no relocated ``.txt`` is for a non-roster role.
    """
    roster = council_roster() if roster is None else roster
    declared = list(declared)
    stems = set(prompt_stems)
    unknown = sorted(set(declared) - roster)
    if unknown:
        raise PackConsistencyError(
            f"pack {pack!r} declares judges not in the frozen council roster: {unknown}"
        )
    missing = sorted(set(declared) - stems)
    if missing:
        raise PackConsistencyError(
            f"pack {pack!r} declares judges with no council-role prompt file: {missing}"
        )
    stray = sorted(stems - roster)
    if stray:
        raise PackConsistencyError(
            f"pack {pack!r} carries council-role prompt(s) for unknown role(s): {stray}"
        )


@lru_cache(maxsize=8)
def assert_pack_judges_consistent(pack: str) -> None:
    """Assert the pack's declared judges have relocated prompts ∧ ⊆ the frozen council
    roster, and that no relocated prompt is for a non-roster role (cached; runs once per
    pack on first prompts resolution). The bridge that lets the council stay frozen while
    its role prompts live in the pack."""
    prompts_dir = _resolve(_manifest(pack)["council_roles"])
    stems = [p.stem for p in prompts_dir.glob("*.txt")]
    assert_judges_known(_manifest(pack)["judges"], stems, pack=pack)


def pack_prompts_path(pack: str | None = None) -> Path:
    """The active (or named) pack's council-role-prompts dir, gated for judge-consistency."""
    pack = pack or active_pack()
    assert_pack_judges_consistent(pack)
    return _resolve(_manifest(pack)["council_roles"])


# ─────────────────────────── the floors layer (PACK-3) ───────────────────────────
# Layer 3 is the FIRST packs-as-CODE step: the clinical grounding *executors* relocate
# OUT of the core into the pack's ``floors`` module, behind this registration interface.
# The module is importlib-loaded from the manifest's ``floors`` path (so the core carries
# no clinical-executor import) and cached. ``harness/grounding.py`` merges the module's
# ``SUPPRESS_EXECUTORS`` / ``FLOOR_EXECUTORS`` dicts into its generic registries LAZILY
# (on first grounding use) — the dependency points pack→core only, so there is no import
# cycle. A pack with no ``floors`` declaration degrades cleanly to ``None`` (the core
# engine runs with its generic executors alone). Un-freezing the council is layer 2b/1b.


def load_pack_floors(pack: str | None = None) -> ModuleType | None:
    """Importlib-load the active (or named) pack's ``floors`` module, or ``None`` if the
    pack declares no ``floors`` (cached; loaded once per pack per process).

    The module exposes the pack's executor-registration dicts (``SUPPRESS_EXECUTORS`` /
    ``FLOOR_EXECUTORS``); ``harness.grounding`` merges them into its generic registries.
    Loaded by file path from the manifest — never by package import — so the core resolves
    the pack's code through the manifest, exactly as it resolves the ontology/prompts paths.
    """
    return _load_pack_floors(pack or active_pack())


@lru_cache(maxsize=8)
def _load_pack_floors(pack: str) -> ModuleType | None:
    """The cached loader, keyed on the RESOLVED pack id — so ``load_pack_floors()`` and
    ``load_pack_floors("healthcare")`` return the SAME module object (one class identity;
    ``isinstance`` across the engine and callers holds)."""
    ref = _manifest(pack).get("floors")
    if not ref:
        return None
    path = _resolve(ref)
    spec = importlib.util.spec_from_file_location(f"lithrim_bench_pack_{pack}_floors", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load pack floors module for {pack!r} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
