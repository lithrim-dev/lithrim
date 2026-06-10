"""Pack definitions: per-agent recipe for synthesis + injection.

A PackDefinition bundles the per-agent variations (transcript shape,
artifact shape, applicable injectors) behind one identifier. The pack
generator dispatches on the `--pack` flag; new agent types add a new
PackDefinition entry rather than a new generator script.

PACK-5a/5b (healthcare-realm-as-pack) relocated ALL the per-agent recipes OUT of this
core module into the active pack's ``generators`` package: the PackDefinition *class*
stays core (the generic recipe shape), but every recipe *instance* — scribe (5a) and
hl7_adt / coding / scheduling / triage (5b) — with its synthesizers + injectors moved.
``_CORE_PACKS`` is now empty; ``active_packs()`` resolves the full recipe set entirely
from the active pack (``harness.pack.load_pack_generators``). The dependency points
pack → core only (the relocated recipes import core primitives), loaded lazily so there
is no import cycle.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .encounter_spec import EncounterSpec
from .injectors import DefectInjector

TranscriptFn = Callable[[EncounterSpec], str]
ArtifactFn = Callable[[EncounterSpec], list[dict[str, Any]] | dict[str, Any]]


@dataclass(frozen=True)
class PackDefinition:
    name: str
    agent_type: str
    transcript_fn: TranscriptFn
    artifact_fn: ArtifactFn
    injectors: list[type[DefectInjector]]
    requires_active_medication: bool = False


# PACK-5b emptied the core recipe set: ALL agent-types (scribe / hl7_adt / coding /
# scheduling / triage) relocated into the active pack's ``generators`` package.
# ``_CORE_PACKS`` is now empty and ``active_packs()`` resolves the full recipe set from the
# pack (``load_pack_generators``). The ``PackDefinition`` class + ``active_packs()`` stay
# core — the generic recipe shape + the resolver. A pack with no ``generators`` declaration
# degrades to ``{}`` (there is no core recipe fallback post-5b).
_CORE_PACKS: dict[str, PackDefinition] = {}


@lru_cache(maxsize=8)
def _active_packs(pack: str) -> dict[str, PackDefinition]:
    """The cached merge, keyed on the RESOLVED pack id. The pack generators load lazily —
    by which point this core module is fully imported — so the dependency points pack→core
    and there is no import cycle."""
    from .harness.pack import load_pack_generators

    merged = dict(_CORE_PACKS)
    module = load_pack_generators(pack)
    if module is not None:
        merged.update(getattr(module, "PACKS", {}))
    return merged


def active_packs() -> dict[str, PackDefinition]:
    """The active pack's full recipe set, resolved entirely from the pack
    (``load_pack_generators(active_pack()).PACKS``) — PACK-5b emptied ``_CORE_PACKS``,
    so there are no core recipes to merge. Cached on the resolved pack id. A pack with
    no ``generators`` declaration degrades to ``{}`` (no core fallback)."""
    from .harness.pack import active_pack

    return _active_packs(active_pack())
