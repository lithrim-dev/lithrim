"""The unified plugin registry — the single *declared* Core/Pro boundary (Plugin Phase-1).

This module formalizes the bench's three pre-existing ad-hoc registries onto one typed
manifest (``SPEC_PLUGIN_ARCHITECTURE`` Phase-1 — a **pure refactor, no new features**):

- the **pack** loaders (``harness/pack.py`` — already manifest-driven; :class:`PackManifest`
  validates the existing ``packs/<id>/pack.json``);
- the **contract** registry (``harness/grounding.py`` ``_CONTRACT_EXECUTORS`` + the pack-floors
  merge — enumerated as ``kind: contract`` plugins by :func:`grounding.contract_plugins`);
- the **provider** registry (``runtime/council/judges_dspy.py`` ``build_judge_lm`` — Azure +
  BYO-Claude declared here as ``kind: provider`` plugins; the per-role deployment *binding*
  stays in core, PACK-2c — infra ∉ a domain pack);
- the **tool** registry (TOOL-1 — configurable connector/capability declarations: the JUTE
  connector + a pack's ``tools.json``, enumerated as ``kind: tool`` plugins by
  :func:`tool_plugins`; declaration-only — execution stays in ``verification``/``grounding``).

It is kept **stdlib + pydantic-core only** (no ``openai``/``dspy``/``httpx``) so the
dependency-light core importers (``signals``/``withstands``/``judge_metric``) are unaffected —
the heavier ``pack``/``grounding`` reads in :func:`provenance_snapshot` are lazy.

The Core/Pro line is a single auditable field: ``tier``. Only ``tier: pro`` is license-gated
(:data:`TIER_GATED`); ``core`` and the bench fixtures (``fixture``/``demo``) always load. The
Phase-1 default is **permit-all** (:class:`License`) so grading is byte-identical; the
fail-closed deny path (a denied ``pro`` plugin/pack is *absent*, not stubbed — the S-BS-90
deny-hook posture) is the non-vacuity lever + the substrate for Phase-3 enforcement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# The manifest vocabulary (SPEC §1 KINDS, §2 transports, §4 tiering). ``frontend`` is declared
# for completeness but DEFERRED to post-CHATBIND-2 (it needs the runtime trigger channel).
Kind = Literal["contract", "provider", "importer", "tool", "frontend", "pack"]
# Four tier values exist in the live manifests (core×2, pro, fixture×2, demo) — the schema
# admits all four; only ``pro`` is gated (the spec's ``{core, pro}`` was the shipping subset).
Tier = Literal["core", "pro", "fixture", "demo"]
Transport = Literal["in_process", "service"]

# The tiers that require a license to load. ``core``/``fixture``/``demo`` are never gated.
TIER_GATED: frozenset[str] = frozenset({"pro"})


def is_gated(tier: str) -> bool:
    """True iff a plugin/pack of this ``tier`` requires a license (only ``pro`` today)."""
    return tier in TIER_GATED


class PluginManifest(BaseModel):
    """One plugin's declared identity — the atomic Core/Pro boundary record (SPEC §Data
    Contracts). ``extra='forbid'`` makes it a real contract: a typo'd field fails fast."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Kind
    tier: Tier = "core"
    transport: Transport = "in_process"
    version: str = "0.0.0"
    implements: str | None = None
    contract_types: list[str] = Field(default_factory=list)
    service: dict[str, Any] | None = None
    requires_license: bool = False


class PackManifest(BaseModel):
    """The validated shape of ``packs/<id>/pack.json`` — the ``kind: pack`` plugin (a manifest
    bundling ontology + taxonomy/flags + judges + the optional floors/generators code modules).
    ``extra='forbid'`` pins the contract; the six existing manifests validate as-is (A1)."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str
    version: str = "0.0.0"
    tier: Tier = "core"
    domain: str = ""
    ontology: str
    flags_ref: str
    council_roles: str
    floors: str | None = None
    generators: str | None = None
    tools: str | None = None  # TOOL-1: ref to a ``tools.json`` (the pack's kind:tool declarations)
    # IMPORTER-1: refs to ``kind: importer`` manifests (one JSON object each) — the declared
    # bridge between a foreign dataset's vocabulary and this pack's taxonomy.
    importers: list[str] = Field(default_factory=list)
    judges: list[str] = Field(default_factory=list)
    # The pack-relative agent JSONs the CE seeds into the rail (packs-dropin/README.md). Optional;
    # a pack with none declares an empty list. Without this field PackManifest (extra='forbid')
    # rejected every pack that ships seed_agents (e.g. healthcare) → provenance_snapshot() threw.
    seed_agents: list[str] = Field(default_factory=list)


def validate_pack_manifest(raw: dict[str, Any]) -> PackManifest:
    """Validate a raw ``pack.json`` dict into a typed :class:`PackManifest`."""
    return PackManifest.model_validate(raw)


@dataclass(frozen=True)
class License:
    """The Phase-1 load-time license. :meth:`permits` decides whether a *gated* (``tier: pro``)
    plugin/pack registers; ``core``/fixtures are never gated.

    Phase-1 default is **permit-all** (so grading is byte-identical), overridable via
    ``LITHRIM_BENCH_LICENSE`` (the fail-closed proof + the Phase-3 enforcement substrate). A
    denied plugin is **absent**, not stubbed — the S-BS-90 deny-hook posture.
    """

    mode: Literal["permit-all", "deny-all", "allowlist", "denylist"] = "permit-all"
    ids: frozenset[str] = frozenset()

    def permits(self, plugin_id: str) -> bool:
        if self.mode == "permit-all":
            return True
        if self.mode == "deny-all":
            return False
        if self.mode == "allowlist":
            return plugin_id in self.ids
        return plugin_id not in self.ids  # denylist

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> License:
        """Build the license from ``LITHRIM_BENCH_LICENSE`` (unset/empty → permit-all).

        Grammar: ``permit-all`` | ``deny-all`` (or ``deny``) | ``allowlist:a,b`` |
        ``denylist:a,b``. An unparseable value raises (fail-loud at construction, not a
        silent ambiguous runtime path)."""
        spec = (env if env is not None else os.environ).get("LITHRIM_BENCH_LICENSE", "").strip()
        if not spec or spec == "permit-all":
            return cls("permit-all")
        if spec in ("deny-all", "deny"):
            return cls("deny-all")
        for mode in ("allowlist", "denylist"):
            prefix = mode + ":"
            if spec.startswith(prefix):
                ids = frozenset(p.strip() for p in spec[len(prefix) :].split(",") if p.strip())
                return cls(mode, ids)  # type: ignore[arg-type]
        raise ValueError(
            f"unparseable LITHRIM_BENCH_LICENSE={spec!r} "
            "(expected: permit-all | deny-all | allowlist:a,b | denylist:a,b)"
        )


def default_license() -> License:
    """The process license — permit-all unless ``LITHRIM_BENCH_LICENSE`` overrides."""
    return License.from_env()


# ── the importer registry (IMPORTER-1) — a foreign dataset's vocabulary as a kind:importer plugin ──
# A ``kind: importer`` plugin DECLARES how a dataset's labels, verdict rule, and untyped
# predictions map onto the pack's taxonomy. Consumed at the EDGES only (ingest, scoring,
# export); the council's DSPy signature never sees a dataset term. A dataset term with no code
# fails admissibility at ingest (never silently dropped). A second dataset is a second manifest.
class ImporterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["importer"] = "importer"
    tier: Tier = "core"
    version: str = "0.0.0"
    implements: str = "importer.dataset_vocabulary"
    dataset: str
    citation: str | None = None
    license: str | None = None
    # dataset label term -> taxonomy code (the inbound map; ingest applies it)
    label_types: dict[str, str]
    # dataset facets carried as case metadata, not codes (e.g. RAGTruth's Evident/Subtle)
    metadata_fields: dict[str, Any] = Field(default_factory=dict)
    # the verdict equivalence, stated in both vocabularies (the write-up footnote)
    verdict_rule: dict[str, str] = Field(default_factory=dict)
    # how an untyped dataset-side prediction (e.g. the paper's typeless span list) is named
    untyped_prediction_class: str = "prediction (untyped)"
    admissibility: str = "a dataset label term with no taxonomy code fails ingest"
    # ENGINE-CLEAN-1: where an imported case keeps its dataset source id (the unit the optimizer
    # keeps train/held-out disjoint on) and its gold evidence spans, as dotted paths into the
    # case. Optional; a case with no manifest behind it uses the neutral top-level
    # ``source_id`` / ``gold_spans`` (see ``case_source_id`` / ``case_gold_spans``).
    source_id_path: str | None = None
    gold_spans_path: str | None = None

    def code_for(self, label_type: str) -> str:
        """The taxonomy code for a dataset label term; a term with no code is an admissibility
        failure (``LookupError``), never a silent drop."""
        try:
            return self.label_types[label_type]
        except KeyError:
            raise LookupError(
                f"importer {self.id!r}: dataset label {label_type!r} has no taxonomy code "
                f"(declared: {sorted(self.label_types)})"
            ) from None

    def terms_for(self, code: str) -> list[str]:
        """The dataset terms a taxonomy code stands for (the outbound map; scoring/export)."""
        return sorted(t for t, c in self.label_types.items() if c == code)


def importer_plugins(pack: str | None = None) -> list[ImporterManifest]:
    """The dataset importers a pack declares (``pack.json`` ``importers`` refs), validated and
    defaulting to the pack's tier. ``pack`` defaults to the active pack. Lazy pack import."""
    from lithrim_bench.harness import pack as _pack

    active = pack or _pack.active_pack()
    pack_tier = _pack._manifest(active).get("tier", "core")
    return [
        ImporterManifest.model_validate({**raw, "kind": "importer", "tier": raw.get("tier", pack_tier)})
        for raw in _pack.load_pack_importers(active)
    ]


def importer_vocabulary(dataset: str, *, pack: str | None = None) -> ImporterManifest:
    """The declared vocabulary for ``dataset`` in the active (or named) pack; fails closed
    (``LookupError``) when no manifest declares it — never an implicit mapping."""
    for m in importer_plugins(pack):
        if m.dataset == dataset:
            return m
    raise LookupError(
        f"no kind:importer manifest declares dataset {dataset!r} in pack "
        f"{pack or 'active'!r}; add one under the pack's `importers` refs"
    )


def _dig(obj: Any, path: str | None) -> Any:
    if not path:
        return None
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _case_field(case: Any, top_level: str, path_attr: str, pack: str | None) -> Any:
    """ENGINE-CLEAN-1: read a case field the engine needs but a dataset may keep anywhere.
    Every importer manifest of the pack is tried at its declared path first (a case shaped by
    that importer resolves there); the neutral top-level key is the fallback, so a corpus with
    no manifest behind it still works. Empty values count as absent; ``None`` when nowhere."""
    if not isinstance(case, dict):
        return None
    try:
        manifests = importer_plugins(pack)
    except (FileNotFoundError, LookupError, ValueError):
        manifests = []
    for m in manifests:
        value = _dig(case, getattr(m, path_attr))
        if value not in (None, "", [], {}):
            return value
    value = case.get(top_level)
    return None if value in (None, "", [], {}) else value


def case_source_id(case: Any, *, pack: str | None = None) -> str | None:
    """The dataset source id a case was generated from (``source_id_path`` of the pack's importer
    manifests, else top-level ``source_id``); ``None`` when the case carries none."""
    value = _case_field(case, "source_id", "source_id_path", pack)
    return None if value is None else str(value)


def case_gold_spans(case: Any, *, pack: str | None = None) -> list | None:
    """The human gold evidence spans on a labeled case (``gold_spans_path`` of the pack's importer
    manifests, else top-level ``gold_spans``); ``None`` when the case carries none."""
    value = _case_field(case, "gold_spans", "gold_spans_path", pack)
    return list(value) if isinstance(value, list) else None


# ── the provider registry (D4) — Azure + BYO-Claude as kind:provider plugins ──────────────
# Static because the provider SET is fixed (BYOC-1 added byo_claude); the per-role DEPLOYMENT
# binding stays in core (``judges_dspy._ROLE_DEPLOYMENT`` — PACK-2c, infra ∉ a domain pack).
# Azure reaches a remote API (``service``); BYO-Claude shells out to a local ``claude -p``
# (``in_process``).
_PROVIDER_PLUGINS: tuple[PluginManifest, ...] = (
    PluginManifest(
        id="azure_openai",
        kind="provider",
        tier="core",
        transport="service",
        implements="council.judge_lm",
    ),
    PluginManifest(
        id="byo_claude",
        kind="provider",
        tier="core",
        transport="in_process",
        implements="council.judge_lm",
    ),
    # F8-PROVIDER: a purpose-built eval reward model (Composo wire shape) in the commodity judge
    # slot — score→verdict mapped deterministically in the sampling layer
    # (``runtime/council/reward_lm.py``); bound per-role like any provider
    # (``LITHRIM_LLM_PROVIDER_<ROLE>=composo``).
    PluginManifest(
        id="composo",
        kind="provider",
        tier="core",
        transport="service",
        implements="council.judge_lm",
    ),
)


def provider_plugins() -> list[PluginManifest]:
    """The judge-LM provider plugins (Azure default + BYO-Claude + the composo reward model).
    These DECLARE the providers for the boundary + provenance; the binding stays core
    (``judges_dspy._ROLE_DEPLOYMENT`` / the per-role env binding)."""
    return list(_PROVIDER_PLUGINS)


def resolve_provider_id(selector: str, global_provider: str, *, byo_values: frozenset[str]) -> str:
    """Route a ``build_judge_lm`` selector to a provider-plugin id — the BYOC-1 selection, now
    manifest-mediated (was a bare set-membership inlined in ``build_judge_lm``). **Byte-identical**:
    the same boolean as before, with ``byo_values`` threaded in from the caller's
    ``byo_claude_lm.BYO_CLAUDE_MODEL_VALUES`` so this module stays ``dspy``-free."""
    if selector in byo_values or global_provider in byo_values:
        return "byo_claude"
    return "azure_openai"


# ── the tool registry (TOOL-1) — connectors/capabilities as kind:tool plugins ──────────────
# A ``kind: tool`` plugin DECLARES a configurable capability the eval can reach — an MCP server,
# an HTTP/API connector, a KB-query endpoint, a terminology service, or an in-process builtin —
# with its ``transport`` (in_process | service), a ``service`` config blob, and its ``tier``. The
# ``implements`` slot names the sub-kind (``tool.mcp_server`` / ``tool.api_connector`` /
# ``tool.kb_query`` / ``tool.terminology`` / ``tool.builtin``), mirroring how a contract uses
# ``grounding.suppress`` / ``grounding.floor``. Like every other kind this is DECLARATION-ONLY:
# the registry records + tier-gates tools; EXECUTION stays in ``verification/tools.py`` +
# ``harness/grounding.py`` (a tool is USED by a flag's ``verification_contract`` criterion). The
# CE/Pro split is the single ``tier`` field — core tools (the JUTE connector) always load; a pack's
# tools inherit the pack tier (so the healthcare KB/terminology tools come out ``pro``), gated by
# the same License. "Configure any MCP / custom / API tool" = a manifest entry (this core tuple or
# a pack ``tools.json``), ZERO engine edits (the open/closed property — TOOL-2 ships the Pro tools).
#
# NOTE (namespace): the legacy ``verification/spec.py`` ``TOOL_*`` ids ({in_row, kb_rag, record_rag,
# structural_jute, jute_gen, dosage_grounding}) and the grounding ``contract_type`` keys overlap but
# are NOT yet unified with the ``kind: tool`` id space — a deliberate deferral (a hard merge would
# touch the ``contract_type`` keys ontologies reference). TOOL-1 declares the connector capabilities;
# the existing contract executors stay enumerated as ``kind: contract``.
_CORE_TOOL_PLUGINS: tuple[PluginManifest, ...] = (
    PluginManifest(
        id="etlp_jute",
        kind="tool",
        tier="core",
        transport="service",
        implements="tool.api_connector",
        service={"default_base_url": "http://localhost:3031"},
    ),
    # CONN-WEBSEARCH-1: the web-search reference connector (community release, §4). The executor
    # is NON-AUTHORITATIVE BY CONSTRUCTION (always ``conforms=None``; it attaches evidence, never
    # clears/raises a finding) — see ``grounding.WebSearchGrounding`` / ``verification.WebSearchTool``.
    # config only here; the API key rides env (``LITHRIM_WEB_SEARCH_API_KEY``), never the manifest.
    PluginManifest(
        id="web_search",
        kind="tool",
        tier="core",
        transport="service",
        implements="tool.mcp_server",
        service={"default_base_url": "http://localhost:8585"},
    ),
)


def etlp_jute_default_base_url() -> str:
    """The JUTE mapper (:3031) default base URL — the SINGLE source of the default, declared on the
    ``etlp_jute`` plugin manifest. The mapper is an opt-in add-on (a separate ``../etlp-mapper``
    service); callers resolve the live URL from ``LITHRIM_JUTE_URL`` and fall back HERE so the
    default lives in one place. A plain lookup — no env, no logging."""
    for p in _CORE_TOOL_PLUGINS:
        if p.id == "etlp_jute":
            return (p.service or {}).get("default_base_url", "http://localhost:3031")
    return "http://localhost:3031"


def tool_plugins(pack: str | None = None) -> list[PluginManifest]:
    """The tool registry (core ∪ a pack) as ``kind: tool`` plugins — the TOOL-1 declaration layer.
    Core tools are the static :data:`_CORE_TOOL_PLUGINS` (the JUTE connector, all-Core); a pack
    contributes tools DATA-ONLY via its manifest ``tools`` ref (a ``tools.json`` list of manifest
    dicts), each forced to ``kind='tool'`` and defaulting to the pack's tier. Mirrors
    :func:`provider_plugins` (static core) ⊕ the pack-floors fold in
    :func:`grounding.contract_plugins` (pack-contributed). ``pack`` defaults to the active pack;
    pass it explicitly to enumerate a specific workspace's pack from a differently-pinned process
    (CONN-1 — the BFF process binds one pack but serves multi-pack workspaces). ``pack`` (the
    module) is imported lazily so this module stays dependency-light."""
    out: list[PluginManifest] = list(_CORE_TOOL_PLUGINS)
    from lithrim_bench.harness import pack as _pack

    active = pack or _pack.active_pack()
    pack_tier = _pack._manifest(active).get("tier", "core")
    for raw in _pack.load_pack_tools(active) or ():
        out.append(
            PluginManifest.model_validate(
                {**raw, "kind": "tool", "tier": raw.get("tier", pack_tier)}
            )
        )
    return out


def resolve_tool(
    tool_id: str,
    *,
    pack: str | None = None,
    workspace_db: Any = None,
    workspace_id: str | None = None,
    license: License | None = None,
) -> PluginManifest | None:
    """Resolve a tool id to its manifest at grade time (TOOL-AUTHOR-1 Stage 2): a workspace's
    **authored** tool wins, else the active pack ∪ core :func:`tool_plugins`, else ``None``.
    License-gated — a ``tier: pro`` tool is ABSENT (``None``) under a denying license, never
    stubbed (the S-BS-90 posture). The workspace defaults to the active workspace (the in-process
    grade has it); pass ``workspace_db``/``workspace_id`` explicitly for an off-process resolve.
    Lazy imports keep this module dependency-light + cycle-free."""
    lic = license or default_license()

    def _gated_out(m: PluginManifest) -> bool:
        return is_gated(m.tier) and not lic.permits(m.id)

    # (1) authored, per-workspace
    wdb, wid = workspace_db, workspace_id
    if wdb is None or wid is None:
        try:
            from lithrim_bench.harness import workspace as _ws

            aws = _ws.get_active_workspace()
            wdb = wdb or getattr(aws, "config_db", None)
            wid = wid or getattr(aws, "name", None)
        except Exception:  # noqa: BLE001 — no active workspace (a bare resolve) → skip authored
            pass
    if wdb is not None and wid is not None:
        try:
            from lithrim_bench.harness import tools_store

            row = tools_store.load_tool(tool_id, db_path=wdb, workspace_id=wid)
        except Exception:  # noqa: BLE001 — store unavailable → fall through to declared
            row = None
        if row:
            m = PluginManifest.model_validate({**row["manifest"], "kind": "tool"})
            return None if _gated_out(m) else m

    # (2) the active pack ∪ core declared registry
    for m in tool_plugins(pack):
        if m.id == tool_id:
            return None if _gated_out(m) else m
    return None


def provenance_snapshot(license: License | None = None) -> dict[str, Any]:
    """The loaded-plugin set for run-provenance (D5): the active pack (``kind: pack``) + its
    contract plugins (``kind: contract``, core ∪ pack) + the provider plugins + the tool plugins
    (``kind: tool``, core ∪ pack — TOOL-1), each filtered by ``license`` (default permit-all).
    Returns a plain dict; default-safe (callers default the provenance field to ``[]``/``None``
    on replay/no-op stores).

    ``pack`` + ``grounding`` are imported LAZILY (both stdlib at import) so this module stays
    dependency-light for the core importers."""
    license = license or default_license()
    from lithrim_bench.harness import grounding
    from lithrim_bench.harness import pack as _pack

    active = _pack.active_pack()
    manifest = validate_pack_manifest(_pack._manifest(active))
    plugins: list[PluginManifest] = [
        PluginManifest(
            id=manifest.pack_id,
            kind="pack",
            tier=manifest.tier,
            transport="in_process",
            implements="pack",
        ),
        *grounding.contract_plugins(),
        *provider_plugins(),
        *tool_plugins(),
    ]
    permitted = [p for p in plugins if not is_gated(p.tier) or license.permits(p.id)]
    # REL-OPS-1 O4: the last bind-time model-binding check (role → model id + dated flag),
    # recorded by ``model_policy.check_model_bindings`` at council construction. ``None``
    # when no council was bound this process (structural-only / replay) — default-safe.
    from lithrim_bench.harness import model_policy

    return {
        "active_pack": active,
        "pack_tier": manifest.tier,
        "plugins": [p.model_dump() for p in permitted],
        "model_bindings": model_policy.last_model_bindings(),
    }
