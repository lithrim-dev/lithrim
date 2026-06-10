"""Pack definitions: per-agent recipe for synthesis + injection.

A PackDefinition bundles the per-agent variations (transcript shape,
artifact shape, applicable injectors) behind one identifier. The pack
generator dispatches on the `--pack` flag; new agent types add a new
PackDefinition entry rather than a new generator script.

PACK-5a (healthcare-realm-as-pack, layer 5a) relocated the SCRIBE recipe OUT of this
core module into the active pack's ``generators`` package: the PackDefinition *class*
stays core (the generic recipe shape), but the scribe *instance* — with its
synthesizers + injectors — moved. ``active_packs()`` resolves the full recipe set: the
core's remaining non-scribe recipes merged with the active pack's relocated generators
(``harness.pack.load_pack_generators``). The other 4 agent-types stay core until 5b.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .encounter_spec import EncounterSpec
from .injectors import (
    CODING_INJECTORS,
    SCHEDULING_INJECTORS,
    TRIAGE_INJECTORS,
    DefectInjector,
)
from .synthesizers.coding_artifact import synthesize_coding_artifact
from .synthesizers.coding_transcript import synthesize_coding_transcript
from .synthesizers.scheduling_artifact import synthesize_scheduling_artifact
from .synthesizers.scheduling_transcript import synthesize_scheduling_transcript
from .synthesizers.triage_artifact import synthesize_triage_artifact
from .synthesizers.triage_transcript import synthesize_triage_transcript

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


SCHEDULING_PACK = PackDefinition(
    name="scheduling_v1",
    agent_type="scheduling",
    transcript_fn=synthesize_scheduling_transcript,
    artifact_fn=synthesize_scheduling_artifact,
    injectors=SCHEDULING_INJECTORS,
)

CODING_PACK = PackDefinition(
    name="coding_v1",
    agent_type="coding",
    transcript_fn=synthesize_coding_transcript,
    artifact_fn=synthesize_coding_artifact,
    injectors=CODING_INJECTORS,
)

TRIAGE_PACK = PackDefinition(
    name="triage_v1",
    agent_type="triage",
    transcript_fn=synthesize_triage_transcript,
    artifact_fn=synthesize_triage_artifact,
    injectors=TRIAGE_INJECTORS,
)

# The non-scribe CORE recipes. The scribe recipe (``scribe_v1``) relocated into the active
# pack's ``generators`` package (PACK-5a); ``active_packs()`` merges it back over these.
_CORE_PACKS: dict[str, PackDefinition] = {
    SCHEDULING_PACK.name: SCHEDULING_PACK,
    CODING_PACK.name: CODING_PACK,
    TRIAGE_PACK.name: TRIAGE_PACK,
}


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
    """The active pack's full recipe set: the core's non-scribe recipes ⊕ the pack's
    relocated generators (``load_pack_generators(active_pack()).PACKS``). Cached on the
    resolved pack id. A pack with no ``generators`` declaration yields just the core
    recipes (the scribe recipe absent — there is no core fallback for it post-5a)."""
    from .harness.pack import active_pack

    return _active_packs(active_pack())
