from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_history import FabricatedHistoryInjector
from .missing_allergy import MissingAllergyInjector
from .value_mismatch import ValueMismatchInjector
from .wrong_dosage import WrongDosageInjector

ALL_INJECTORS: list[type[DefectInjector]] = [
    WrongDosageInjector,
    MissingAllergyInjector,
    FabricatedHistoryInjector,
    ValueMismatchInjector,
]

__all__ = [
    "ALL_INJECTORS",
    "DefectInjector",
    "FabricatedHistoryInjector",
    "InjectionRecipe",
    "InjectionResult",
    "MissingAllergyInjector",
    "ValueMismatchInjector",
    "WrongDosageInjector",
]
