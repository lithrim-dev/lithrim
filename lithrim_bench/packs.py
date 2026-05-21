"""Pack definitions: per-agent recipe for synthesis + injection.

A PackDefinition bundles the per-agent variations (transcript shape,
artifact shape, applicable injectors) behind one identifier. The pack
generator dispatches on the `--pack` flag; new agent types add a new
PackDefinition entry rather than a new generator script.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .encounter_spec import EncounterSpec
from .injectors import (
    CODING_INJECTORS,
    SCHEDULING_INJECTORS,
    SCRIBE_INJECTORS,
    TRIAGE_INJECTORS,
    DefectInjector,
)
from .synthesizers.coding_artifact import synthesize_coding_artifact
from .synthesizers.coding_transcript import synthesize_coding_transcript
from .synthesizers.scheduling_artifact import synthesize_scheduling_artifact
from .synthesizers.scheduling_transcript import synthesize_scheduling_transcript
from .synthesizers.scribe_artifact import synthesize_scribe_artifact
from .synthesizers.transcript import synthesize_scribe_transcript
from .synthesizers.triage_artifact import synthesize_triage_artifact
from .synthesizers.triage_transcript import synthesize_triage_transcript

TranscriptFn = Callable[[EncounterSpec], str]
ArtifactFn = Callable[[EncounterSpec], list[dict[str, Any]] | dict[str, Any]]


def _wrap_single(fn: Callable[[EncounterSpec], dict[str, Any]]) -> ArtifactFn:
    def _inner(spec: EncounterSpec) -> list[dict[str, Any]]:
        return [fn(spec)]

    return _inner


@dataclass(frozen=True)
class PackDefinition:
    name: str
    agent_type: str
    transcript_fn: TranscriptFn
    artifact_fn: ArtifactFn
    injectors: list[type[DefectInjector]]
    requires_active_medication: bool = False


SCRIBE_PACK = PackDefinition(
    name="scribe_v1",
    agent_type="scribe",
    transcript_fn=synthesize_scribe_transcript,
    artifact_fn=_wrap_single(synthesize_scribe_artifact),
    injectors=SCRIBE_INJECTORS,
    requires_active_medication=True,
)

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

PACKS: dict[str, PackDefinition] = {
    SCRIBE_PACK.name: SCRIBE_PACK,
    SCHEDULING_PACK.name: SCHEDULING_PACK,
    CODING_PACK.name: CODING_PACK,
    TRIAGE_PACK.name: TRIAGE_PACK,
}
