"""Case packager: writes a JSONL row conforming to the eval spec schema.

Schema source: EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md §1.1.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .encounter_spec import EncounterSpec
from .injectors.base import InjectionRecipe
from .taxonomy import Taxonomy


def _case_id(spec: EncounterSpec, defect_type: str | None, pack: str) -> str:
    digest_input = f"{spec.demographics.patient_id}|{spec.encounter.encounter_id}|{defect_type or 'clean'}"
    h = hashlib.sha1(digest_input.encode()).hexdigest()[:12]
    suffix = defect_type or "clean_negative"
    return f"bench_{pack}_{suffix}_{h}"


def package_case(
    *,
    spec: EncounterSpec,
    pack: str,
    agent_type: str,
    transcript: str,
    artifacts: list[dict[str, Any]],
    recipe: InjectionRecipe | None,
    taxonomy: Taxonomy,
    pinned: dict[str, Any],
    clinical_severity: str = "high",
) -> dict[str, Any]:
    """Build a single JSONL row.

    Raises ValueError if the recipe's safety_flag is not in the snapshotted
    taxonomy, or if no production judge owns it. This is the in-process
    enforcement of defects D1 and D3.
    """
    if recipe is not None:
        if recipe.safety_flag not in taxonomy.known_codes:
            raise ValueError(
                f"recipe.safety_flag {recipe.safety_flag!r} is not in snapshotted "
                f"KNOWN_TAXONOMY_CODES; refresh taxonomy/taxonomy_snapshot.json "
                f"or fix the injector"
            )
        if recipe.safety_flag in taxonomy.tier1_owners and not taxonomy.production_owners_of(
            recipe.safety_flag
        ):
            raise ValueError(
                f"recipe.safety_flag {recipe.safety_flag!r} has no owner in "
                f"production_judges; reassign ownership before scoring"
            )

    expected_flags = [recipe.safety_flag] if recipe else []
    expected_verdict = _verdict_for(recipe, taxonomy)
    expected_artifact_verdict = _artifact_verdict_for(recipe, taxonomy)

    case_id = _case_id(spec, recipe.defect_type if recipe else None, pack)

    return {
        "case_id": case_id,
        "pack": pack,
        "agent_type": agent_type,
        "ground_truth_basis": "constructed",
        "synthea_provenance": {
            "cohort_path": spec.provenance.cohort_path,
            "cohort_sha256": spec.provenance.cohort_sha256,
            "synthea_version": spec.provenance.synthea_version,
            "patient_id": spec.demographics.patient_id,
            "encounter_id": spec.encounter.encounter_id,
        },
        "patient_profile": {
            "demographics": {
                "first_name": spec.demographics.first_name,
                "last_name": spec.demographics.last_name,
                "age": spec.demographics.age_at_encounter,
                "gender": spec.demographics.gender,
                "dob": spec.demographics.dob.isoformat(),
            },
            "conditions": [c.description for c in spec.conditions],
            "active_medications": [
                f"{m.description}".strip() for m in spec.active_medications
            ],
            "allergies": [a.description for a in spec.allergies],
        },
        "transcript": transcript,
        "artifacts": artifacts,
        "injection_recipe": recipe.to_dict() if recipe else None,
        "expected_compliance_verdict": expected_verdict,
        "expected_artifact_verdict": expected_artifact_verdict,
        "expected_safety_flags": expected_flags,
        "expected_owner_map": (
            {recipe.safety_flag: sorted(taxonomy.production_owners_of(recipe.safety_flag))}
            if recipe and recipe.safety_flag in taxonomy.tier1_owners
            else {}
        ),
        "clean_negative": recipe is None,
        "severity": clinical_severity,
        "pinned": pinned,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _verdict_for(recipe: InjectionRecipe | None, taxonomy: Taxonomy) -> str:
    if recipe is None:
        return "approve"
    tier = taxonomy.tier_of(recipe.safety_flag)
    if tier == "TIER_1":
        return "reject"
    if tier == "TIER_2":
        return "reject"
    if tier == "TIER_3":
        return "needs_review"
    return "needs_review"


def _artifact_verdict_for(recipe: InjectionRecipe | None, taxonomy: Taxonomy) -> str:
    if recipe is None:
        return "PASS"
    tier = taxonomy.tier_of(recipe.safety_flag)
    if tier == "TIER_1":
        return "BLOCK"
    if tier == "TIER_2":
        return "BLOCK"
    if tier == "TIER_3":
        return "WARN"
    return "WARN"


def write_jsonl(rows: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
