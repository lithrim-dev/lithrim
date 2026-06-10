"""Clinical-PMH filtering: take EncounterSpec.conditions (raw Synthea
longitudinal record) and return a deduplicated, clinically-meaningful
list suitable for SOAP PMH and transcript grounding.

Synthea's conditions table mixes (disorder), (morphologic abnormality),
(finding), and (situation) entries — most patient records carry 15-25
total conditions including social findings (Full-time employment,
Social isolation, ...) that the live council should not consider PMH.

The 2026-05-21 live-pipeline smoke showed that enumerating the
unfiltered list in the transcript causes the council to miss
FABRICATED_HISTORY injections (signal lost in noise). Filtering keeps
the transcript+artifact pair tight enough that the fabricated entry
stands out.
"""
from __future__ import annotations

from lithrim_bench.encounter_spec import Condition

# Synthea description suffixes that are NOT clinical PMH. Anything with
# these tokens is filtered out.
_NON_PMH_TOKENS = (
    "(situation)",
    "(finding)",  # most findings are non-clinical; exceptions added explicitly below
)

# Findings that ARE clinically relevant PMH despite the (finding) suffix.
_FINDING_ALLOWLIST = {
    "Body mass index 30+ - obesity (finding)",
    "Prediabetes (finding)",
}


def clinical_conditions(conditions: list[Condition], limit: int = 6) -> list[Condition]:
    """Return a deduplicated, clinically-meaningful subset, oldest-first.

    Deduplicates by snomed_code (Synthea's longitudinal data emits the
    same condition multiple times across encounters). Caps at `limit`
    so very-multi-comorbid patients don't dilute the council's signal.
    """
    seen: set[str] = set()
    out: list[Condition] = []
    for c in conditions:
        if c.snomed_code in seen:
            continue
        desc = c.description
        if desc in _FINDING_ALLOWLIST:
            seen.add(c.snomed_code)
            out.append(c)
            continue
        if any(tok in desc for tok in _NON_PMH_TOKENS):
            continue
        seen.add(c.snomed_code)
        out.append(c)
        if len(out) >= limit:
            break
    return out
