from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_history import FabricatedHistoryInjector
from .hallucinated_detail import HallucinatedDetailInjector
from .missing_allergy import MissingAllergyInjector
from .value_mismatch import ValueMismatchInjector
from .wrong_dosage import WrongDosageInjector

ALL_INJECTORS: list[type[DefectInjector]] = [
    WrongDosageInjector,
    MissingAllergyInjector,
    FabricatedHistoryInjector,
    ValueMismatchInjector,
    HallucinatedDetailInjector,
]

__all__ = [
    "ALL_INJECTORS",
    "DefectInjector",
    "FabricatedHistoryInjector",
    "HallucinatedDetailInjector",
    "InjectionRecipe",
    "InjectionResult",
    "MissingAllergyInjector",
    "ValueMismatchInjector",
    "WrongDosageInjector",
]
