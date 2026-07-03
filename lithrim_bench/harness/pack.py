"""Active-pack resolution — the core loads its ontology + taxonomy from a *pack*,
not a hardcoded clinical path (healthcare-realm-as-pack, layer 1a).

A **pack** is a domain bundle: a manifest (``packs/<id>/pack.json``) that names the
pack's ontology + taxonomy (flags) + judges. The core resolves the **active pack**
(default the neutral ``_core`` pack — CE-PACK-NEUTRAL-DEFAULT; override via
``LITHRIM_BENCH_PACK`` to a domain pack such as ``healthcare``) and reads the
ontology/taxonomy paths from its manifest — so the core itself carries no clinical
content path AND boots standalone with no Pro pack on disk. ``harness/ontology.py`` and ``taxonomy.py`` resolve their defaults
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

Layer 2b extends the flip to the **Tier-1 owner-map**: the council resolves its *runtime*
``_TIER1_OWNERS`` FROM the ACTIVE pack's snapshot via :func:`pack_tier1_owners` (the same
inline-``__import__`` carve-out), so the consensus one-strike owner-map is pack-resolved too.
:func:`council_roster` (the council's *validation* identity, against which packs are checked) reads
its owner roles from the council's CANONICAL (``DEFAULT_PACK``) snapshot — pack-INDEPENDENT, so a
fixture pack that overrides the owner-map DATA cannot mutate the roster. The AST-parse-no-import
technique survives only for the ``CouncilModel`` roster names (still a council literal — un-freezing
that infra roster + the ``judge_metric.LENS_BY_ROLE`` lenses is a later, separate cut).
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "packs"
DEFAULT_PACK = "_core"
_COUNCIL_SOURCE = REPO_ROOT / "lithrim_bench" / "runtime" / "council" / "compliance_council.py"
_COUNCIL_TIER_NAMES = ("TIER_1_NEVER_EVENTS", "TIER_2_HIGH_RISK", "TIER_3_MEDIUM")

# PACK-DIST-1: the external pack discovery seam. A pack id resolves to a ROOT dir (the dir
# holding its ``pack.json``) by SEARCHING, in order: (1) an installed entry point in the
# ``lithrim_bench.packs`` group (the pip-installable / idiomatic path — a Pro pack ships as
# its own wheel, NOT inside the OSS core), (2) ``LITHRIM_BENCH_PACKS_DIR`` (one or more
# external dirs, ``os.pathsep``-joined — the dev / airgap path), (3) the in-repo ``packs/``
# (the final fallback — the CE sample packs + fixtures). This is what lets the clinical
# ``healthcare`` realm live OUTSIDE this repo while the core still loads it. Stdlib-only.
_PACK_EP_GROUP = "lithrim_bench.packs"
_PACKS_DIR_ENV = "LITHRIM_BENCH_PACKS_DIR"

# PACK-OVERLAY-1: the volume-backed pack overlay. The sanctioned authoring writers
# (``harness.criterion`` / ``harness.judge_authoring``) mutate a tier:core pack's taxonomy
# snapshot + ``council_roles/`` — but the discovered pack root may be EPHEMERAL (in Docker,
# ``/app/packs/_core`` is the container's image writable layer, reverted on every recreation
# while the ``/app/out`` volume survives — the 2026-07-03 lithrim-validate incident: authored
# judges vanished and the next grade 500'd on the missing role prompt). When
# ``LITHRIM_BENCH_PACK_OVERLAY_DIR`` names a STATE dir (compose: ``/app/out/pack_overlay``),
# the two MUTABLE manifest refs resolve through ``<overlay>/<pack_id>/`` instead, materializing
# the pack's seed copy-on-first-resolve — so reads AND writes hit the volume and the image pack
# stays pristine DATA. Env unset (the default) → resolution byte-identical to before (the same
# zero-delta posture as the License permit-all default). Entirely ABOVE the frozen-council seam:
# the council's ``_ROLE_PROMPTS_DIR`` carve-out and inline ``__import__`` tier/lens/roster reads
# already flow through ``pack_prompts_path()`` / ``_pack_ref``, which is where the swap lives.
_OVERLAY_DIR_ENV = "LITHRIM_BENCH_PACK_OVERLAY_DIR"
_OVERLAY_KEYS = frozenset({"flags_ref", "council_roles"})


class PackConsistencyError(RuntimeError):
    """A loaded pack declares taxonomy codes the frozen council does not know.

    Fail-closed: a pack whose codes are not ⊆ ``KNOWN_TAXONOMY_CODES`` would be scored
    by a council that discards them before consensus, so it does not load (this is the
    1a bridge that lets the council stay frozen — 1b removes the gate by reading the
    council's codes FROM the pack).
    """


class PackLicenseError(RuntimeError):
    """A ``tier: pro`` pack is resolved under a license that does not permit it.

    Fail-closed (Plugin Phase-1, D2): a Pro pack the operator is not entitled to does NOT
    load — it is *absent*, not stubbed (the S-BS-90 deny-hook posture). The Phase-1 default
    is permit-all (``LITHRIM_BENCH_LICENSE`` unset), so this never fires for an existing pack
    and grading is byte-identical; the deny path is the gate's non-vacuity lever.
    """


def active_pack() -> str:
    """The active pack id. Default the neutral ``_core`` pack; override via ``LITHRIM_BENCH_PACK``."""
    return os.environ.get("LITHRIM_BENCH_PACK") or DEFAULT_PACK


def _external_pack_dirs() -> list[Path]:
    """The ``LITHRIM_BENCH_PACKS_DIR`` search dirs (``os.pathsep``-joined), in order; empty
    when unset. Each dir is expected to contain ``<pack_id>/pack.json`` subdirs."""
    raw = os.environ.get(_PACKS_DIR_ENV, "")
    return [Path(d) for d in raw.split(os.pathsep) if d]


def _entry_point_root(ep: importlib.metadata.EntryPoint) -> Path | None:
    """The on-disk root dir of an installed pack entry point (the dir holding its ``pack.json``),
    or ``None`` if it cannot be resolved. The entry point names a trivial importable module/package
    whose dir IS the pack payload; importing it is cheap (it must NOT pull the floors/generators,
    which load lazily by path)."""
    try:
        module = ep.load()
    except Exception:
        return None
    file = getattr(module, "__file__", None)
    return Path(file).resolve().parent if file else None


@lru_cache(maxsize=8)
def _pack_root(pack: str) -> Path:
    """Resolve a pack id to its ROOT dir (the dir holding ``pack.json``) via the PACK-DIST-1
    discovery search: installed entry point → ``LITHRIM_BENCH_PACKS_DIR`` → in-repo ``packs/``.
    Fail-closed (``FileNotFoundError``) when the pack is discoverable nowhere — never a silent
    fallback (A4). Cached per resolved id (one root per pack per process)."""
    # (1) installed entry points (a separately-distributed Pro pack wheel).
    try:
        eps = importlib.metadata.entry_points(group=_PACK_EP_GROUP)
    except TypeError:  # pragma: no cover - <3.10 SelectableGroups shape
        eps = importlib.metadata.entry_points().get(_PACK_EP_GROUP, [])
    for ep in eps:
        if ep.name == pack:
            root = _entry_point_root(ep)
            if root is not None and (root / "pack.json").exists():
                return root
    # (2) LITHRIM_BENCH_PACKS_DIR external dirs (dev / airgap).
    for base in _external_pack_dirs():
        cand = base / pack
        if (cand / "pack.json").exists():
            return cand
    # (3) in-repo packs/ (CE sample packs + fixtures).
    cand = PACKS_DIR / pack
    if (cand / "pack.json").exists():
        return cand
    raise FileNotFoundError(
        f"pack {pack!r} not found via entry points, {_PACKS_DIR_ENV}, or {PACKS_DIR}"
    )


def pack_root(pack: str | None = None) -> Path:
    """The ROOT dir of the active (or named) discoverable pack — the dir holding its ``pack.json``,
    resolved via the PACK-DIST-1 discovery search (entry point → ``LITHRIM_BENCH_PACKS_DIR`` →
    in-repo ``packs/``). The public accessor for callers that need to resolve a pack-relative DATA
    ref against the dropped pack's location (PACK-DROPIN-1: ``seed_config_db`` resolving a portable
    seed-agent's pack-relative dataset). Raises ``FileNotFoundError`` if the pack is undiscoverable."""
    return _pack_root(pack or active_pack())


def discover_packs() -> list[dict]:
    """Every DISCOVERABLE pack — the union of installed entry points, ``LITHRIM_BENCH_PACKS_DIR``
    dirs, and the in-repo ``packs/`` — deduped by id (first-wins, matching ``_pack_root``'s
    resolution order). Each entry: ``{id, tier, domain, version, source}``. 'Installing a pack'
    in the product == making it discoverable here (pip-install the wheel, or point PACKS_DIR at
    it). Unfiltered — callers pick the selectable domains (e.g. tier in {core, pro}, non-fixture)."""
    seen: dict[str, dict] = {}

    def _add(pack_id: str, root: Path, source: str) -> None:
        if pack_id in seen or not (root / "pack.json").is_file():
            return
        try:
            m = json.loads((root / "pack.json").read_text())
        except (OSError, ValueError):
            return
        seen[pack_id] = {
            "id": pack_id,
            "tier": m.get("tier", "core"),
            "domain": m.get("domain"),
            "version": m.get("version"),
            "source": source,
        }

    try:
        eps = importlib.metadata.entry_points(group=_PACK_EP_GROUP)
    except TypeError:  # pragma: no cover - <3.10 SelectableGroups shape
        eps = importlib.metadata.entry_points().get(_PACK_EP_GROUP, [])
    for ep in eps:
        root = _entry_point_root(ep)
        if root is not None:
            _add(ep.name, root, "entry_point")
    for base in _external_pack_dirs():
        if base.is_dir():
            for cand in sorted(base.iterdir()):
                _add(cand.name, cand, "packs_dir")
    if PACKS_DIR.is_dir():
        for cand in sorted(PACKS_DIR.iterdir()):
            _add(cand.name, cand, "in_repo")
    return sorted(seen.values(), key=lambda p: p["id"])


def pack_corpora_dir(pack: str) -> Path | None:
    """The dir holding a pack's by-construction case corpora (``*.jsonl``), or ``None``.
    Convention (until a manifest ``corpora`` field formalizes it): ``<pack_root>/examples``,
    then the sibling ``<pack_root>/../examples`` (the external-pack-repo layout)."""
    root = _pack_root(pack)
    for cand in (root / "examples", root.parent / "examples"):
        if cand.is_dir() and any(cand.glob("*.jsonl")):
            return cand
    return None


def pack_cases(pack: str, *, limit: int = 200) -> list[dict]:
    """The pack's by-construction cases, flattened across its corpora. Each:
    ``{case_id, source (abs jsonl), corpus, expected_safety_flags, clean_negative}``. Empty
    when the pack ships no corpora dir."""
    cdir = pack_corpora_dir(pack)
    if cdir is None:
        return []
    out: list[dict] = []
    for jf in sorted(cdir.glob("*.jsonl")):
        try:
            with jf.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    cid = row.get("case_id")
                    if not cid:
                        continue
                    out.append(
                        {
                            "case_id": cid,
                            "source": str(jf),
                            "corpus": jf.stem,
                            "expected_safety_flags": row.get("expected_safety_flags") or [],
                            "clean_negative": bool(row.get("clean_negative")),
                        }
                    )
                    if len(out) >= limit:
                        return out
        except (OSError, ValueError):
            continue
    return out


@lru_cache(maxsize=8)
def _manifest(pack: str) -> dict:
    return json.loads((_pack_root(pack) / "pack.json").read_text())


def _resolve_ref(pack: str, ref: str) -> Path:
    """Resolve a manifest ref (``ontology`` / ``flags_ref`` / ``council_roles`` / ``floors`` /
    ``generators``) for ``pack``. A bare/pack-root-relative ref (the PACK-DIST-1 form, e.g.
    ``ontology.json``) resolves against the pack's discovered ROOT — so the pack is relocatable
    (in-repo OR external). A legacy ``packs/<id>/...`` REPO_ROOT-relative ref still resolves
    against REPO_ROOT (back-compat for any cross-pack reuse); an absolute ref is taken as-is."""
    p = Path(ref)
    if p.is_absolute():
        return p
    if ref.startswith("packs/"):
        return REPO_ROOT / p
    return _pack_root(pack) / p


def _materialize_overlay(seed: Path, dest: Path) -> None:
    """Copy the pack's seed ref (file or dir) to its overlay location, atomically (temp-in-dir +
    ``os.replace``) so a concurrent resolver never sees a partial copy. No seed on disk → nothing
    to materialize (the writer creates the ref; ``write_role_prompt`` already mkdirs)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if seed.is_dir():
        tmp = Path(tempfile.mkdtemp(dir=dest.parent, prefix=f".tmp_{dest.name}_"))
        shutil.copytree(seed, tmp, dirs_exist_ok=True)
    elif seed.is_file():
        fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".tmp_{dest.name}_")
        os.close(fd)
        tmp = Path(tmp_name)
        shutil.copy2(seed, tmp)
    else:
        return
    try:
        os.replace(tmp, dest)
    except OSError:
        if not dest.exists():
            raise
        # a concurrent resolver materialized the same seed first — discard ours
        if tmp.is_dir():
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            tmp.unlink(missing_ok=True)


def _overlay_ref(pack: str, key: str, seed: Path) -> Path | None:
    """The overlay path for a MUTABLE manifest ref (PACK-OVERLAY-1), seed-materialized on first
    resolve; ``None`` when the overlay is disabled (env unset) or ``key`` is not overlay-managed
    (immutable refs — ontology/floors/generators/tools — always resolve to the pack root)."""
    raw = os.environ.get(_OVERLAY_DIR_ENV, "")
    if not raw or key not in _OVERLAY_KEYS:
        return None
    dest = Path(raw) / pack / seed.name
    if not dest.exists():
        _materialize_overlay(seed, dest)
    return dest


def _pack_ref(pack: str, key: str) -> Path:
    """The resolved path of a REQUIRED manifest ref (``key`` must be present). The two MUTABLE
    refs (``flags_ref`` + ``council_roles``) resolve through the volume-backed overlay when
    ``LITHRIM_BENCH_PACK_OVERLAY_DIR`` is set (PACK-OVERLAY-1) — so the audited authoring writers,
    which read and write via this resolver, survive an ephemeral pack root."""
    seed = _resolve_ref(pack, _manifest(pack)[key])
    overlay = _overlay_ref(pack, key, seed)
    return seed if overlay is None else overlay


@lru_cache(maxsize=8)
def _council_known_codes(pack: str) -> frozenset[str]:
    """Pack-keyed cache backing :func:`council_known_codes` — mirrors the per-pack caches on
    :func:`assert_pack_council_consistent` / :func:`assert_pack_judges_consistent`. Keyed by
    pack (not ``maxsize=1`` argless) so an in-process ``active_pack()`` flip resolves the right
    snapshot instead of returning the first-resolved pack's codes forever (S-BS-156: the BFF
    resolving a healthcare flag op after first caching the neutral ``_core`` default fired a
    spurious ``PackConsistencyError``; collection order decided the poison)."""
    return _pack_taxonomy_codes(pack)


def council_known_codes() -> frozenset[str]:
    """The council's ``KNOWN_TAXONOMY_CODES`` (TIER_1|2|3 union).

    Post layer-1b the council reads its taxonomy FROM the active pack (:func:`pack_tiers`),
    so "the council's known codes" ARE the pack snapshot's codes — read here directly from
    the snapshot (no ``openai``, no council import; the core OSS env stays dependency-light).
    The genuine council⇄snapshot equivalence — that the *imported* council resolved the SAME
    set — is pinned in the ``[council]``-env layer-1b test. (Pre-1b this AST-parsed the
    council's literal tier sets; once those became ``pack_tiers()`` subscripts a
    ``literal_eval`` would raise, so the re-point is atomic with the council carve-out.)

    Cached per-resolved-pack (:func:`_council_known_codes`), NOT ``maxsize=1`` over the argless
    call — the latter went stale across an in-process active-pack flip (S-BS-156)."""
    return _council_known_codes(active_pack())


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
    snap = json.loads(_pack_ref(pack or active_pack(), "flags_ref").read_text())
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
    snap = json.loads(_pack_ref(pack or active_pack(), "flags_ref").read_text())
    return {code: frozenset(owners) for code, owners in snap["tier1_owners"].items()}


def pack_lenses(pack: str | None = None) -> dict[str, frozenset[str]]:
    """The active (or named) pack's per-role lens authority (``role -> {codes the role may
    assert}``), read straight from the snapshot ``lenses``.

    This is the PACK-2c source-of-truth flip for the MOAT authority — the lens twin of
    :func:`pack_tier1_owners`: ``judge_metric.LENS_BY_ROLE`` resolves from HERE (a
    ``judge_metric.py`` inline ``__import__``) instead of carrying hardcoded ``frozenset``
    literals, so the per-role "codes you may raise" the withstands-gate scope-checks
    (``withstands.py`` ``code not in lens``) lives in ``packs/<id>/taxonomy_snapshot.json``.
    Ungated and stdlib-only ON PURPOSE for the SAME reason as :func:`pack_tier1_owners`:
    ``judge_metric`` is imported by ``signals``/``withstands`` on the dependency-light core,
    so a gated/heavy path would pull in deps it must not — a direct snapshot read stays
    ``openai``-free."""
    snap = json.loads(_pack_ref(pack or active_pack(), "flags_ref").read_text())
    return {role: frozenset(codes) for role, codes in snap["lenses"].items()}


def pack_production_judges(pack: str | None = None) -> list[str]:
    """The active (or named) pack's roster IDENTITY — the ordered list of judges that run,
    read straight from the snapshot ``production_judges``.

    This is the PACK-2c source-of-truth flip for the roster: the FROZEN council builds its v2
    roster by iterating THIS list (``compliance_council.py`` inline ``__import__`` carve-out)
    and binding each identity to its CORE-side deployment (provider/model/Azure id/capability
    flags stay in core — infra ∉ a domain pack), instead of inlining the role NAMES in the
    ``CouncilModel(...)`` constructors. Order is load-bearing (it is the roster order). Ungated
    and stdlib-only ON PURPOSE — the council imports this during its OWN module import, so any
    gated/heavy path would re-enter; a direct snapshot read stays acyclic and ``openai``-free."""
    snap = json.loads(_pack_ref(pack or active_pack(), "flags_ref").read_text())
    return list(snap["production_judges"])


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


def assert_pack_licensed(pack: str, license=None) -> None:
    """Fail-closed iff ``pack`` is ``tier: pro`` and the license denies it — the Plugin Phase-1
    load-time gate (D2). The Phase-1 default is permit-all (:func:`plugins.default_license`,
    ``LITHRIM_BENCH_LICENSE`` unset), so this never fires for an existing pack and grading is
    byte-identical; under a deny license a Pro pack does NOT load (raises :class:`PackLicenseError`).

    **R-GUARD (load-bearing):** called ONLY from the ontology/taxonomy/prompts ``*_path``
    resolvers — ABOVE the frozen-council seam — and NEVER from :func:`pack_tiers` /
    :func:`pack_tier1_owners` / :func:`pack_lenses` / :func:`pack_production_judges`, which the
    FROZEN council resolves via inline ``__import__`` during its OWN module import and which are
    deliberately ungated + stdlib-only (gating them would re-enter the council's import). Denial
    still fails closed correctly: the council importing tier *data* is harmless; the grade raises
    here when it resolves the denied pack's ontology/prompts. ``plugins`` is imported LAZILY so
    ``import harness.pack`` stays dependency-light (no ``openai``)."""
    from lithrim_bench.harness import plugins

    tier = _manifest(pack).get("tier", "core")
    if not plugins.is_gated(tier):
        return
    lic = license or plugins.default_license()
    if not lic.permits(pack):
        raise PackLicenseError(
            f"pack {pack!r} (tier={tier!r}) is not permitted by the active license "
            "(LITHRIM_BENCH_LICENSE); it does not load — fail-closed, not stubbed."
        )


def pack_ontology_path(pack: str | None = None, *, check_consistency: bool = True) -> Path:
    """The active (or named) pack's ontology JSON path, gated for license + (optionally)
    council-consistency. ``check_consistency=False`` skips the codes-⊆-KNOWN gate — for
    resolving a NON-active pack's ontology PATH (e.g. the BFF building a pack-bound agent
    template while a different pack is active); the gate still fires for real at GRADE time,
    where the subprocess binds that pack so its codes match the council. The license gate
    (R-GUARD: on the ``*_path`` resolvers) is never skipped."""
    pack = pack or active_pack()
    assert_pack_licensed(pack)
    if check_consistency:
        assert_pack_council_consistent(pack)
    return _pack_ref(pack, "ontology")


def pack_taxonomy_path(pack: str | None = None) -> Path:
    """The active (or named) pack's taxonomy-snapshot path, gated for license + council-consistency."""
    pack = pack or active_pack()
    assert_pack_licensed(pack)
    assert_pack_council_consistent(pack)
    return _pack_ref(pack, "flags_ref")


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

    This is the council's INTRINSIC roster — its IDENTITY, against which ANY active pack's declared
    judges + relocated ``council_roles`` prompts are validated (the judges gate). It is therefore
    **pack-independent**: the names are AST-collected from the frozen source (still a literal); the
    owner roles (which carry the dormant ``source_message_judge``) come from the council's CANONICAL
    pack snapshot (:func:`pack_tier1_owners` of ``DEFAULT_PACK``), NOT the active pack. Post-layer-2b
    ``_TIER1_OWNERS`` is no longer a council literal (the carve-out resolves the council's *runtime*
    owner-map from the ACTIVE pack), so AST-eval'ing it would raise — but the ROSTER must stay
    canonical: a fixture/alternate pack that overrides the owner-map DATA (e.g. ``_tiers_fixture``'s
    sentinel) must NOT mutate the council's known-role set, else its reused canonical ``council_roles``
    prompts would fail the gate. The value is 0-delta with the pre-2b literal (``DEFAULT_PACK``'s
    owner-map == the former council literal). Both legs are ``openai``-free, so this runs in the core
    (no-import) env."""
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
    for owners in pack_tier1_owners(DEFAULT_PACK).values():
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
    """Assert the pack's declared judges have relocated prompts ∧ ⊆ the council roster, and that
    no relocated prompt is for a non-roster role (cached; runs once per pack on first prompts
    resolution). The bridge that lets the council stay frozen while its role prompts live in the
    pack.

    **Wall-#4 relaxation (PHASE2-A, ADDITIVE).** The roster checked here is the canonical
    :func:`council_roster` (the AST-parsed ``CouncilModel`` names ∪ ``DEFAULT_PACK`` owner roles)
    UNION the ACTIVE pack's own ``production_judges`` — so a self-authored production judge spliced
    into THIS pack's snapshot (``harness.judge_authoring.splice_production_judge``) is roster-known
    for THIS pack. This matches the PACK-2c source-of-truth flips: the snapshot ``production_judges``
    already IS the runtime roster authority the frozen council iterates (:func:`pack_production_judges`),
    so its entries are roster-known by definition. It is purely ADDITIVE — the canonical leg is
    unchanged, so every existing pack (declared judges ⊆ the canonical roster) still validates
    exactly as before; :func:`council_roster` itself stays pack-independent (untouched), and the
    pure :func:`assert_judges_known` with an explicit ``roster=`` still fails closed on an unknown
    role (non-vacuous).

    **GENERALIST-1 (ADDITIVE).** The roster ALSO unions the pack's own ``lenses`` roles
    (:func:`pack_lenses`) — a role the pack DECLARES with a lens + a Tier-1 owner entry + a relocated
    prompt is a pack-declared reviewer, roster-known FOR THIS PACK, even when it is NOT a panel member
    (``production_judges``). This lets a pack ship an OPT-IN single-reviewer role (e.g. a generalist
    carrying the full-coverage lens) that runs ONLY via an explicit ``reviewer_roster`` override, never
    inflating the default panel. Still additive — every production judge already has a lens, so existing
    packs' rosters are unchanged; a stray prompt for a role with NO lens declaration still fails closed."""
    prompts_dir = _pack_ref(pack, "council_roles")
    stems = [p.stem for p in prompts_dir.glob("*.txt")]
    roster = (
        council_roster()
        | frozenset(pack_production_judges(pack))
        | frozenset(pack_lenses(pack))
    )
    assert_judges_known(_manifest(pack)["judges"], stems, roster=roster, pack=pack)


def pack_prompts_path(pack: str | None = None) -> Path:
    """The active (or named) pack's council-role-prompts dir, gated for license + judge-consistency."""
    pack = pack or active_pack()
    assert_pack_licensed(pack)
    assert_pack_judges_consistent(pack)
    return _pack_ref(pack, "council_roles")


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
    path = _resolve_ref(pack, ref)
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
    path = _resolve_ref(pack, ref)
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


# ─────────────────────────── the tool registry (TOOL-1) ───────────────────────────
# A pack contributes TOOLS (configurable connector/capability declarations — MCP servers, API
# connectors, KB-query/terminology endpoints) DATA-ONLY via its manifest ``tools`` ref: a
# ``tools.json`` holding a JSON list of plugin-manifest dicts. Unlike ``floors``/``generators``
# (CODE modules), tools are pure DECLARATIONS — no import, no execution here. ``harness/plugins.py``
# ``tool_plugins()`` validates them into ``kind: tool`` ``PluginManifest`` entries + tier-gates
# them; a tool is USED by a flag's ``verification_contract`` criterion (TOOL-2). Loaded by FILE
# PATH from the manifest (relocatable, exactly like the other refs). A pack with no ``tools``
# declaration degrades cleanly to ``None``.


def load_pack_tools(pack: str | None = None) -> tuple[dict, ...] | None:
    """Read the active (or named) pack's ``tools.json`` (a list of tool-manifest dicts), or
    ``None`` if the pack declares no ``tools`` (cached per pack per process). DATA only — the
    declarations are validated + tier-gated by ``harness/plugins.py`` ``tool_plugins()``."""
    return _load_pack_tools(pack or active_pack())


@lru_cache(maxsize=8)
def _load_pack_tools(pack: str) -> tuple[dict, ...] | None:
    """The cached loader, keyed on the RESOLVED pack id. Returns an immutable tuple so callers
    can't mutate the cached declarations (``tool_plugins`` copies each dict before validating)."""
    ref = _manifest(pack).get("tools")
    if not ref:
        return None
    raw = json.loads(_resolve_ref(pack, ref).read_text())
    if not isinstance(raw, list):
        raise ValueError(f"pack {pack!r} tools.json must be a JSON list, got {type(raw).__name__}")
    return tuple(raw)
