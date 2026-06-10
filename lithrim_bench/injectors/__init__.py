from .base import DefectInjector, InjectionRecipe, InjectionResult
from .fabricated_consent import FabricatedConsentInjector
from .missed_escalation import MissedEscalationInjector
from .phi_disclosure_pre_verification import PhiDisclosurePreVerificationInjector

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

TRIAGE_INJECTORS: list[type[DefectInjector]] = [
    MissedEscalationInjector,
]

# The non-scribe CORE injectors (the scribe set relocated to the pack, PACK-5a; the HL7 +
# coding sets relocated, PACK-5b).
ALL_INJECTORS: list[type[DefectInjector]] = SCHEDULING_INJECTORS + TRIAGE_INJECTORS

__all__ = [
    "ALL_INJECTORS",
    "DefectInjector",
    "FabricatedConsentInjector",
    "InjectionRecipe",
    "InjectionResult",
    "MissedEscalationInjector",
    "PhiDisclosurePreVerificationInjector",
    "SCHEDULING_INJECTORS",
    "TRIAGE_INJECTORS",
]
