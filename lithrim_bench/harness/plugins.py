"""The unified plugin registry — the single *declared* Core/Pro boundary (Plugin Phase-1).

This module formalizes the bench's three pre-existing ad-hoc registries onto one typed
manifest (``SPEC_PLUGIN_ARCHITECTURE`` Phase-1 — a **pure refactor, no new features**):

- the **pack** loaders (``harness/pack.py`` — already manifest-driven; :class:`PackManifest`
  validates the existing ``packs/<id>/pack.json``);
- the **contract** registry (``harness/grounding.py`` ``_CONTRACT_EXECUTORS`` + the pack-floors
  merge — enumerated as ``kind: contract`` plugins by :func:`grounding.contract_plugins`);
- the **provider** registry (``runtime/council/judges_dspy.py`` ``build_judge_lm`` — Azure +
  BYO-Claude declared here as ``kind: provider`` plugins; the per-role deployment *binding*
  stays in core, PACK-2c — infra ∉ a domain pack).

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
    judges: list[str] = Field(default_factory=list)


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
)


def provider_plugins() -> list[PluginManifest]:
    """The judge-LM provider plugins (Azure default + BYO-Claude). These DECLARE the providers
    for the boundary + provenance; the binding stays core (``judges_dspy._ROLE_DEPLOYMENT``)."""
    return list(_PROVIDER_PLUGINS)


def resolve_provider_id(selector: str, global_provider: str, *, byo_values: frozenset[str]) -> str:
    """Route a ``build_judge_lm`` selector to a provider-plugin id — the BYOC-1 selection, now
    manifest-mediated (was a bare set-membership inlined in ``build_judge_lm``). **Byte-identical**:
    the same boolean as before, with ``byo_values`` threaded in from the caller's
    ``byo_claude_lm.BYO_CLAUDE_MODEL_VALUES`` so this module stays ``dspy``-free."""
    if selector in byo_values or global_provider in byo_values:
        return "byo_claude"
    return "azure_openai"


def provenance_snapshot(license: License | None = None) -> dict[str, Any]:
    """The loaded-plugin set for run-provenance (D5): the active pack (``kind: pack``) + its
    contract plugins (``kind: contract``, core ∪ pack) + the provider plugins, each filtered by
    ``license`` (default permit-all). Returns a plain dict; default-safe (callers default the
    provenance field to ``[]``/``None`` on replay/no-op stores).

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
    ]
    permitted = [p for p in plugins if not is_gated(p.tier) or license.permits(p.id)]
    return {
        "active_pack": active,
        "pack_tier": manifest.tier,
        "plugins": [p.model_dump() for p in permitted],
    }
