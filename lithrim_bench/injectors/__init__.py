"""The generic by-construction injection base — the domain-agnostic label machinery.

PACK-5a/5b (healthcare-realm-as-pack) relocated ALL the clinical defect injectors (scribe /
hl7_adt / coding / scheduling / triage) + their per-agent registries into the active pack's
``generators`` package; reach them via ``harness.pack.load_pack_generators()`` (or the
recipes in ``lithrim_bench.packs.active_packs()``). Only the generic base stays core:
``DefectInjector`` (the ABC) + ``InjectionRecipe`` / ``InjectionResult`` — the recipe-IS-the-
label machinery, which is domain-agnostic.
"""
from .base import DefectInjector, InjectionRecipe, InjectionResult

__all__ = [
    "DefectInjector",
    "InjectionRecipe",
    "InjectionResult",
]
