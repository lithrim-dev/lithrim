"""Healthcare pack — the scribe DATASET-GENERATION recipe (PACK-5a, layer 5a).

PACK-1/2 moved DATA (ontology/taxonomy, role prompts); PACK-3 moved the first CODE
(the clinical grounding executors → ``floors.py``). Layer 5a moves the *generation*
realm: the scribe synthesizers + injectors + the ``SCRIBE_PACK`` recipe relocate OUT of
the domain-agnostic engine into this package, behind the pack generator-registration
interface (``harness.pack.load_pack_generators``). This **unifies the two "pack" words**:
``lithrim_bench.packs.PACKS`` (per-agent generation recipes) ⊕ ``packs/healthcare/``
(eval-config) — a pack is now **data + grading + generation**.

The by-construction invariant is preserved verbatim (CLAUDE.md "labels are true by
construction"): the relocation is a MOVE, not an edit — the relocated injectors carry the
``InjectionRecipe`` (the label justification) byte-identical, only their imports of the
core primitives are repointed. The scribe corpus regenerates byte-identical.

The dependency points **pack → core** only (never core → pack at import): this package
imports the core primitives it builds against (``PackDefinition`` from ``lithrim_bench.packs``;
``EncounterSpec`` from the core; ``DefectInjector``/``InjectionRecipe`` via the relocated
injectors' own ``lithrim_bench.injectors.base`` imports; ``_pmh.clinical_conditions``, which
stays core in 5a). The core loads this module LAZILY (on first ``active_packs()`` use, by
which point ``lithrim_bench.packs`` is fully imported) — so there is no import cycle, and
it is loaded by FILE PATH from the manifest (``pack.json`` ``"generators"``), never by
``import packs.*``.

The registration surface is the module-level ``PACKS`` dict (mirror ``floors.py``'s
``SUPPRESS_EXECUTORS`` / ``FLOOR_EXECUTORS``): ``lithrim_bench.packs.active_packs()`` merges
it over the core's non-scribe recipes. The injector classes + synthesizers are re-exported
so the (relocated-symbol) test/script consumers reach them through the loader, exactly as
PACK-3's consumers reach ``RecordPresence`` via ``load_pack_floors()``.

5a is scribe-only; coding/hl7/scheduling/triage stay core via ``lithrim_bench.packs`` until
5b (when ``_pmh`` relocates with coding and the core ``packs.py`` empties to a thin resolver).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lithrim_bench.encounter_spec import EncounterSpec
from lithrim_bench.injectors.base import DefectInjector
from lithrim_bench.packs import PackDefinition

from ._hl7 import find_segment, parse_segments
from ._triage_scenarios import SCENARIOS, pick_scenario
from .coding_artifact import synthesize_coding_artifact
from .coding_transcript import synthesize_coding_transcript
from .fabricated_consent import FabricatedConsentInjector
from .fabricated_history import FabricatedHistoryInjector
from .hallucinated_detail import HallucinatedDetailInjector
from .hl7_adt_artifact import synthesize_hl7_adt_artifact
from .hl7_adt_transcript import synthesize_hl7_adt_transcript
from .hl7_invalid_field_format import Hl7InvalidFieldFormatInjector
from .hl7_malformed_date import Hl7MalformedDateInjector
from .hl7_missing_required_field import Hl7MissingRequiredFieldInjector
from .hl7_missing_segment import Hl7MissingSegmentInjector
from .hl7_trigger_event_mismatch import Hl7TriggerEventMismatchInjector
from .missed_escalation import MissedEscalationInjector
from .missing_allergy import MissingAllergyInjector
from .phi_disclosure_pre_verification import PhiDisclosurePreVerificationInjector
from .scheduling_artifact import synthesize_scheduling_artifact
from .scheduling_transcript import (
    VERIFICATION_END,
    VERIFICATION_START,
    synthesize_scheduling_transcript,
)
from .scribe_artifact import synthesize_scribe_artifact
from .transcript import synthesize_scribe_transcript
from .triage_artifact import synthesize_triage_artifact
from .triage_transcript import synthesize_triage_transcript
from .upcoding_risk import UpcodingRiskInjector
from .value_mismatch import ValueMismatchInjector
from .wrong_dosage import WrongDosageInjector


def _wrap_single(
    fn: Callable[[EncounterSpec], dict[str, Any]],
) -> Callable[[EncounterSpec], list[dict[str, Any]]]:
    def _inner(spec: EncounterSpec) -> list[dict[str, Any]]:
        return [fn(spec)]

    return _inner


SCRIBE_INJECTORS: list[type[DefectInjector]] = [
    WrongDosageInjector,
    MissingAllergyInjector,
    FabricatedHistoryInjector,
    ValueMismatchInjector,
    HallucinatedDetailInjector,
]

SCRIBE_PACK = PackDefinition(
    name="scribe_v1",
    agent_type="scribe",
    transcript_fn=synthesize_scribe_transcript,
    artifact_fn=_wrap_single(synthesize_scribe_artifact),
    injectors=SCRIBE_INJECTORS,
    requires_active_medication=True,
)

HL7_ADT_INJECTORS: list[type[DefectInjector]] = [
    Hl7MalformedDateInjector,
    Hl7MissingSegmentInjector,
    Hl7InvalidFieldFormatInjector,
    Hl7MissingRequiredFieldInjector,
    Hl7TriggerEventMismatchInjector,
]

HL7_ADT_PACK = PackDefinition(
    name="hl7_adt_v1",
    agent_type="hl7_adt",
    transcript_fn=synthesize_hl7_adt_transcript,
    artifact_fn=synthesize_hl7_adt_artifact,
    injectors=HL7_ADT_INJECTORS,
)

CODING_INJECTORS: list[type[DefectInjector]] = [
    UpcodingRiskInjector,
]

CODING_PACK = PackDefinition(
    name="coding_v1",
    agent_type="coding",
    transcript_fn=synthesize_coding_transcript,
    artifact_fn=synthesize_coding_artifact,
    injectors=CODING_INJECTORS,
)

# FabricatedConsentInjector is exported but intentionally NOT in
# SCHEDULING_INJECTORS: adding it would change what the existing scheduling_v1
# pack generates. The judge-calibration builder (scripts/generate_judge_calib.py)
# references it directly.
SCHEDULING_INJECTORS: list[type[DefectInjector]] = [
    PhiDisclosurePreVerificationInjector,
]

SCHEDULING_PACK = PackDefinition(
    name="scheduling_v1",
    agent_type="scheduling",
    transcript_fn=synthesize_scheduling_transcript,
    artifact_fn=synthesize_scheduling_artifact,
    injectors=SCHEDULING_INJECTORS,
)

TRIAGE_INJECTORS: list[type[DefectInjector]] = [
    MissedEscalationInjector,
]

TRIAGE_PACK = PackDefinition(
    name="triage_v1",
    agent_type="triage",
    transcript_fn=synthesize_triage_transcript,
    artifact_fn=synthesize_triage_artifact,
    injectors=TRIAGE_INJECTORS,
)

# The registration surface (PACK-5a D1): the core's active_packs() resolves the FULL recipe
# set from here (PACK-5b emptied the core ``_CORE_PACKS`` — all 5 agent-types are now pack-
# sourced). Declarative — no execution at import beyond building the recipes.
PACKS: dict[str, PackDefinition] = {
    SCRIBE_PACK.name: SCRIBE_PACK,
    HL7_ADT_PACK.name: HL7_ADT_PACK,
    CODING_PACK.name: CODING_PACK,
    SCHEDULING_PACK.name: SCHEDULING_PACK,
    TRIAGE_PACK.name: TRIAGE_PACK,
}

__all__ = [
    "PACKS",
    "SCRIBE_INJECTORS",
    "SCRIBE_PACK",
    "HL7_ADT_INJECTORS",
    "HL7_ADT_PACK",
    "CODING_INJECTORS",
    "CODING_PACK",
    "SCHEDULING_INJECTORS",
    "SCHEDULING_PACK",
    "TRIAGE_INJECTORS",
    "TRIAGE_PACK",
    "FabricatedConsentInjector",
    "FabricatedHistoryInjector",
    "HallucinatedDetailInjector",
    "Hl7InvalidFieldFormatInjector",
    "Hl7MalformedDateInjector",
    "Hl7MissingRequiredFieldInjector",
    "Hl7MissingSegmentInjector",
    "Hl7TriggerEventMismatchInjector",
    "MissedEscalationInjector",
    "MissingAllergyInjector",
    "PhiDisclosurePreVerificationInjector",
    "UpcodingRiskInjector",
    "ValueMismatchInjector",
    "WrongDosageInjector",
    "SCENARIOS",
    "VERIFICATION_END",
    "VERIFICATION_START",
    "find_segment",
    "parse_segments",
    "pick_scenario",
    "synthesize_coding_artifact",
    "synthesize_coding_transcript",
    "synthesize_hl7_adt_artifact",
    "synthesize_hl7_adt_transcript",
    "synthesize_scheduling_artifact",
    "synthesize_scheduling_transcript",
    "synthesize_scribe_artifact",
    "synthesize_scribe_transcript",
    "synthesize_triage_artifact",
    "synthesize_triage_transcript",
]
