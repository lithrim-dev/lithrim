"""Active-pack resolution — the core loads its ontology + taxonomy from a *pack*,
not a hardcoded clinical path (healthcare-realm-as-pack, layer 1a).

A **pack** is a domain bundle: a manifest (``packs/<id>/pack.json``) that names the
pack's ontology + taxonomy (flags) + judges. The core resolves the **active pack**
(default ``healthcare``; override via ``LITHRIM_BENCH_PACK``) and reads the
ontology/taxonomy paths from its manifest — so the core itself carries no clinical
content path. ``harness/ontology.py`` and ``taxonomy.py`` resolve their defaults
through here; relocating the clinical realm into ``packs/healthcare/`` is what makes
the core↔domain boundary grep-verifiable (no ``clinical_v1`` literal in the core).

The **taxonomy source-of-truth** (healthcare-realm-as-pack, layer 1b): the FROZEN council
reads its 3 tier sets FROM the active pack's snapshot via :func:`pack_tiers` (the PACK-2
inline-``__import__`` carve-out in ``compliance_council.py``), so
``packs/<id>/taxonomy_snapshot.json`` is the **single source of truth** — not a council
hardcode. :func:`council_known_codes` therefore reads the SAME snapshot (a self-consistency
value, no longer an AST parse of the council's literals), and
:func:`assert_pack_council_consistent` is now a cheap self-consistency no-op; the genuine
council⇄snapshot equivalence (that the *imported* council resolved the same set) is pinned in
the ``[council]``-env layer-1b test.

Layer 2b extends the flip to the **Tier-1 owner-map**: the council resolves ``_TIER1_OWNERS``
FROM the snapshot via :func:`pack_tier1_owners` (the same inline-``__import__`` carve-out), so
the consensus one-strike owner-map is pack-resolved too. :func:`council_roster` therefore reads
its owner roles from the snapshot; the AST-parse-no-import technique survives only for the
``CouncilModel`` roster names (still a council literal — un-freezing that infra roster + the
``judge_metric.LENS_BY_ROLE`` lenses is a later, separate cut).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
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
    """The council's ``KNOWN_TAXONOMY_CODES`` (TIER_1|2|3 union).

    Post layer-1b the council reads its taxonomy FROM the active pack (:func:`pack_tiers`),
    so "the council's known codes" ARE the pack snapshot's codes — read here directly from
    the snapshot (no ``openai``, no council import; the core OSS env stays dependency-light).
    The genuine council⇄snapshot equivalence — that the *imported* council resolved the SAME
    set — is pinned in the ``[council]``-env layer-1b test. (Pre-1b this AST-parsed the
    council's literal tier sets; once those became ``pack_tiers()`` subscripts a
    ``literal_eval`` would raise, so the re-point is atomic with the council carve-out.)"""
    return _pack_taxonomy_codes(active_pack())


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


def pack_tiers(pack: str | None = None) -> dict[str, frozenset[str]]:
    """The active (or named) pack's 3 taxonomy tier sets, keyed by the council's tier-set
    names (``TIER_1_NEVER_EVENTS`` / ``TIER_2_HIGH_RISK`` / ``TIER_3_MEDIUM``), read straight
    from the snapshot ``tiers``.

    This is the layer-1b source-of-truth flip: the FROZEN council resolves its tier sets from
    HERE (``compliance_council.py`` inline ``__import__`` carve-out) instead of carrying a
    hardcoded literal copy — so the pack snapshot is the single source of truth. Ungated and
    stdlib-only ON PURPOSE: the council imports this during its OWN module import, so calling
    the consistency gate (or :mod:`lithrim_bench.taxonomy`, which resolves a *gated* path at
    its module import) from here would re-enter; reading the snapshot directly keeps it
    acyclic and ``import lithrim_bench.harness.pack`` heavy-dep-free (no ``openai``)."""
    snap = json.loads(_resolve(_manifest(pack or active_pack())["flags_ref"]).read_text())
    return {name: frozenset(snap["tiers"][name]) for name in _COUNCIL_TIER_NAMES}


def pack_tier1_owners(pack: str | None = None) -> dict[str, frozenset[str]]:
    """The active (or named) pack's Tier-1 ownership map (``code -> {owning judge roles}``),
    read straight from the snapshot ``tier1_owners``.

    This is the layer-2b source-of-truth flip — the owner-map twin of :func:`pack_tiers`: the
    FROZEN council resolves ``_TIER1_OWNERS`` from HERE (``compliance_council.py`` inline
    ``__import__`` carve-out) instead of carrying a hardcoded literal copy, so the consensus
    one-strike owner-map lives in ``packs/<id>/taxonomy_snapshot.json``. Ungated and stdlib-only
    ON PURPOSE for the SAME reason as :func:`pack_tiers`: the council imports this during its OWN
    module import, so any gated/heavy path would re-enter; a direct snapshot read stays acyclic
    and ``import lithrim_bench.harness.pack`` heavy-dep-free (no ``openai``)."""
    snap = json.loads(_resolve(_manifest(pack or active_pack())["flags_ref"]).read_text())
    return {code: frozenset(owners) for code, owners in snap["tier1_owners"].items()}


def pack_taxonomy_codes(pack: str | None = None) -> frozenset[str]:
    """The active (or named) pack's full taxonomy code set (the TIER_1|2|3 union)."""
    return frozenset().union(*pack_tiers(pack).values())


def _pack_taxonomy_codes(pack: str) -> frozenset[str]:
    """Private union accessor, kept for the consistency gate + :func:`council_known_codes`."""
    return pack_taxonomy_codes(pack)


@lru_cache(maxsize=8)
def assert_pack_council_consistent(pack: str) -> None:
    """A cheap self-consistency no-op, retained on the ontology/taxonomy resolution path.

    Pre-1b this asserted the pack's codes ⊆ the council's HARDCODED ``KNOWN_TAXONOMY_CODES``
    (the bridge that let the council stay frozen). Post-1b the council reads its codes FROM
    the pack (:func:`council_known_codes` now returns the active pack's snapshot codes), so
    for the active pack this is ``codes ⊆ codes`` — vacuously true. It is kept (not deleted)
    so the resolution path keeps its fail-closed shape; the genuine council⇄snapshot
    equivalence is pinned in the ``[council]``-env layer-1b test. Cached; runs once per pack."""
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
    """Every judge role the frozen council knows: the ``CouncilModel(name=…, prompt_role=…)``
    roster (AST-parsed from the council source — no import) UNION the Tier-1 owner roles.

    The roster names (across both the v2 and v1 branches → risk/policy/faithfulness/behavior)
    are still AST-collected from the frozen source (it stays a literal). The owner roles (which
    carry the dormant ``source_message_judge``) now come FROM the active pack's snapshot via
    :func:`pack_tier1_owners` — post-layer-2b ``_TIER1_OWNERS`` is no longer a council literal
    (the carve-out resolves it from the pack), so AST-eval'ing it would raise; the value is
    0-delta (the snapshot owner-map == the former literal). Both legs are ``openai``-free, so
    this still runs in the core (no-import) env — the authoritative "known role" set the judges
    gate checks against."""
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
    for owners in pack_tier1_owners().values():
        roles.update(owners)
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


# ─────────────────────────── the generators layer (PACK-5a) ───────────────────────────
# Layer 5a is the FIRST packs-as-GENERATION step: the clinical scribe DATASET-GENERATION
# realm (the scribe synthesizers + injectors + the ``SCRIBE_PACK`` recipe) relocates OUT of
# the domain-agnostic engine into the pack's ``generators`` package, behind this registration
# interface. This UNIFIES the two "pack" concepts — ``lithrim_bench.packs.PACKS`` (per-agent
# generation recipes) ⊕ ``packs/healthcare/`` (eval-config) — so a pack is now data + grading
# + generation. ``lithrim_bench.packs.active_packs()`` merges the package's ``PACKS`` over the
# core's non-scribe recipes LAZILY (on first generation use), so the dependency points
# pack→core only and there is no import cycle. A pack with no ``generators`` declaration
# degrades cleanly to ``None`` (the core generates with its remaining core recipes alone).
# The relocation is a MOVE: the ``InjectionRecipe`` (the by-construction label) is byte-
# verbatim, so the scribe corpus regenerates byte-identical.


def load_pack_generators(pack: str | None = None) -> ModuleType | None:
    """Importlib-load the active (or named) pack's ``generators`` package, or ``None`` if the
    pack declares no ``generators`` (cached; loaded once per pack per process).

    The package exposes the pack's recipe-registration dict (``PACKS``) + its re-exported
    injectors/synthesizers; ``lithrim_bench.packs.active_packs()`` merges its ``PACKS`` into
    the core recipe set. Loaded by FILE PATH from the manifest — never by ``import packs.*`` —
    so the core resolves the pack's code through the manifest, exactly as it resolves the
    ``floors`` module and the ontology/prompts paths. Unlike ``floors`` (a single module),
    ``generators`` is a multi-file PACKAGE (the relocated modules import sibling helpers
    relatively), so it is loaded with ``submodule_search_locations`` + a ``sys.modules``
    registration that lets those intra-package relative imports resolve.
    """
    return _load_pack_generators(pack or active_pack())


@lru_cache(maxsize=8)
def _load_pack_generators(pack: str) -> ModuleType | None:
    """The cached loader, keyed on the RESOLVED pack id — so ``load_pack_generators()`` and
    ``load_pack_generators("healthcare")`` return the SAME package object (one identity)."""
    ref = _manifest(pack).get("generators")
    if not ref:
        return None
    path = _resolve(ref)
    mod_name = f"lithrim_bench_pack_{pack}_generators"
    spec = importlib.util.spec_from_file_location(
        mod_name, path, submodule_search_locations=[str(path.parent)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load pack generators package for {pack!r} from {path}")
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec so the package's intra-package relative imports resolve against
    # this synthetic package name + its ``__path__`` (= submodule_search_locations).
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
