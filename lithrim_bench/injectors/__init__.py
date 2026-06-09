from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_consent import FabricatedConsentInjector
from .hl7_invalid_field_format import Hl7InvalidFieldFormatInjector
from .hl7_malformed_date import Hl7MalformedDateInjector
from .hl7_missing_required_field import Hl7MissingRequiredFieldInjector
from .hl7_missing_segment import Hl7MissingSegmentInjector
from .hl7_trigger_event_mismatch import Hl7TriggerEventMismatchInjector
from .missed_escalation import MissedEscalationInjector
from .phi_disclosure_pre_verification import PhiDisclosurePreVerificationInjector
from .upcoding_risk import UpcodingRiskInjector

# The 5 SCRIBE injectors (WrongDosage / MissingAllergy / FabricatedHistory / ValueMismatch /
# HallucinatedDetail) + the shared ``_soap`` helper relocated into the active healthcare
# pack's ``generators`` package (PACK-5a, healthcare-realm-as-pack); reach them via
# ``harness.pack.load_pack_generators()`` (or the ``scribe_v1`` recipe in
# ``lithrim_bench.packs.active_packs()``). The generic base (DefectInjector / InjectionRecipe
# / InjectionResult) stays core — it is the by-construction label machinery, domain-agnostic.

# FabricatedConsentInjector is exported but intentionally NOT in
# SCHEDULING_INJECTORS: adding it would change what the existing scheduling_v1
# pack generates. The judge-calibration builder (scripts/generate_judge_calib.py)
# references it directly.
SCHEDULING_INJECTORS: list[type[DefectInjector]] = [
    PhiDisclosurePreVerificationInjector,
]

CODING_INJECTORS: list[type[DefectInjector]] = [
    UpcodingRiskInjector,
]

TRIAGE_INJECTORS: list[type[DefectInjector]] = [
    MissedEscalationInjector,
]

HL7_ADT_INJECTORS: list[type[DefectInjector]] = [
    Hl7MalformedDateInjector,
    Hl7MissingSegmentInjector,
    Hl7InvalidFieldFormatInjector,
    Hl7MissingRequiredFieldInjector,
    Hl7TriggerEventMismatchInjector,
]

# The non-scribe CORE injectors (the scribe set relocated to the pack, PACK-5a).
ALL_INJECTORS: list[type[DefectInjector]] = (
    SCHEDULING_INJECTORS + CODING_INJECTORS + TRIAGE_INJECTORS + HL7_ADT_INJECTORS
)

__all__ = [
    "ALL_INJECTORS",
    "CODING_INJECTORS",
    "DefectInjector",
    "FabricatedConsentInjector",
    "HL7_ADT_INJECTORS",
    "Hl7InvalidFieldFormatInjector",
    "Hl7MalformedDateInjector",
    "Hl7MissingRequiredFieldInjector",
    "Hl7MissingSegmentInjector",
    "Hl7TriggerEventMismatchInjector",
    "InjectionRecipe",
    "InjectionResult",
    "MissedEscalationInjector",
    "PhiDisclosurePreVerificationInjector",
    "SCHEDULING_INJECTORS",
    "TRIAGE_INJECTORS",
    "UpcodingRiskInjector",
]
