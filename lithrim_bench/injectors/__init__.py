from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_history import FabricatedHistoryInjector
from .hallucinated_detail import HallucinatedDetailInjector
from .hl7_invalid_field_format import Hl7InvalidFieldFormatInjector
from .hl7_malformed_date import Hl7MalformedDateInjector
from .hl7_missing_required_field import Hl7MissingRequiredFieldInjector
from .hl7_missing_segment import Hl7MissingSegmentInjector
from .hl7_trigger_event_mismatch import Hl7TriggerEventMismatchInjector
from .missed_escalation import MissedEscalationInjector
from .missing_allergy import MissingAllergyInjector
from .phi_disclosure_pre_verification import PhiDisclosurePreVerificationInjector
from .upcoding_risk import UpcodingRiskInjector
from .value_mismatch import ValueMismatchInjector
from .wrong_dosage import WrongDosageInjector

SCRIBE_INJECTORS: list[type[DefectInjector]] = [
    WrongDosageInjector,
    MissingAllergyInjector,
    FabricatedHistoryInjector,
    ValueMismatchInjector,
    HallucinatedDetailInjector,
]

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

ALL_INJECTORS: list[type[DefectInjector]] = (
    SCRIBE_INJECTORS + SCHEDULING_INJECTORS + CODING_INJECTORS + TRIAGE_INJECTORS
    + HL7_ADT_INJECTORS
)

__all__ = [
    "ALL_INJECTORS",
    "CODING_INJECTORS",
    "DefectInjector",
    "FabricatedHistoryInjector",
    "HL7_ADT_INJECTORS",
    "HallucinatedDetailInjector",
    "Hl7InvalidFieldFormatInjector",
    "Hl7MalformedDateInjector",
    "Hl7MissingRequiredFieldInjector",
    "Hl7MissingSegmentInjector",
    "Hl7TriggerEventMismatchInjector",
    "InjectionRecipe",
    "InjectionResult",
    "MissedEscalationInjector",
    "MissingAllergyInjector",
    "PhiDisclosurePreVerificationInjector",
    "SCHEDULING_INJECTORS",
    "SCRIBE_INJECTORS",
    "TRIAGE_INJECTORS",
    "UpcodingRiskInjector",
    "ValueMismatchInjector",
    "WrongDosageInjector",
]
