from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_history import FabricatedHistoryInjector
from .hallucinated_detail import HallucinatedDetailInjector
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

ALL_INJECTORS: list[type[DefectInjector]] = (
    SCRIBE_INJECTORS + SCHEDULING_INJECTORS + CODING_INJECTORS + TRIAGE_INJECTORS
)

__all__ = [
    "ALL_INJECTORS",
    "CODING_INJECTORS",
    "DefectInjector",
    "FabricatedHistoryInjector",
    "HallucinatedDetailInjector",
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
