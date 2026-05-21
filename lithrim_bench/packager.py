"""Case packager: writes a JSONL row conforming to the eval spec schema.

Schema source: EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md §1.1.

Recipes are always a list. Empty = clean negative. One = single-defect.
Two or more = multi-defect (the worst-of rule across recipe tiers
drives the resulting verdict and artifact verdict).
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

_VERDICT_RANK = {"approve": 0, "needs_review": 1, "reject": 2}
_ARTIFACT_VERDICT_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}
_TIER_VERDICT = {"TIER_1": "reject", "TIER_2": "reject", "TIER_3": "needs_review"}
_TIER_ARTIFACT = {"TIER_1": "BLOCK", "TIER_2": "BLOCK", "TIER_3": "WARN"}

# Synthesis markers used by injectors to locate dialogue regions.
# They're stripped at packaging time so they never appear in produced cases.
_SYNTHESIS_MARKERS = ("<!-- verification -->", "<!-- /verification -->")


def _clean_transcript(transcript: str) -> str:
    cleaned = "\n".join(
        line for line in transcript.split("\n")
        if line.strip() not in _SYNTHESIS_MARKERS
    )
    return cleaned.replace("\n\n\n", "\n\n").strip()


def _case_id(spec: EncounterSpec, recipes: list[InjectionRecipe], pack: str) -> str:
    if not recipes:
        suffix = "clean_negative"
    elif len(recipes) == 1:
        suffix = recipes[0].defect_type
    else:
        suffix = "multi_" + "+".join(r.defect_type for r in recipes)
    digest = hashlib.sha1(
        f"{spec.demographics.patient_id}|{spec.encounter.encounter_id}|{suffix}".encode()
    ).hexdigest()[:12]
    return f"bench_{pack}_{suffix}_{digest}"


def _verdicts_for(recipes: list[InjectionRecipe], taxonomy: Taxonomy) -> tuple[str, str]:
    if not recipes:
        return "approve", "PASS"
    compliance = "approve"
    artifact = "PASS"
    for r in recipes:
        tier = taxonomy.tier_of(r.safety_flag)
        if tier is None:
            continue
        c = _TIER_VERDICT[tier]
        a = _TIER_ARTIFACT[tier]
        if _VERDICT_RANK[c] > _VERDICT_RANK[compliance]:
            compliance = c
        if _ARTIFACT_VERDICT_RANK[a] > _ARTIFACT_VERDICT_RANK[artifact]:
            artifact = a
    return compliance, artifact


def package_case(
    *,
    spec: EncounterSpec,
    pack: str,
    agent_type: str,
    transcript: str,
    artifacts: list[dict[str, Any]],
    recipes: list[InjectionRecipe] | None = None,
    taxonomy: Taxonomy,
    pinned: dict[str, Any],
    clinical_severity: str | None = None,
) -> dict[str, Any]:
    """Build a single JSONL row.

    Enforces D1 (flag in known codes) and D3 (Tier-1 flag has a
    production owner) in-process. Raises ValueError on either.
    """
    recipes = list(recipes or [])
    for r in recipes:
        if r.safety_flag not in taxonomy.known_codes:
            raise ValueError(
                f"recipe.safety_flag {r.safety_flag!r} not in snapshotted taxonomy; "
                f"refresh taxonomy/taxonomy_snapshot.json or fix the injector"
            )
        if r.safety_flag in taxonomy.tier1_owners and not taxonomy.production_owners_of(
            r.safety_flag
        ):
            raise ValueError(
                f"recipe.safety_flag {r.safety_flag!r} has no production-owning judge"
            )

    expected_flags = sorted({r.safety_flag for r in recipes})
    expected_verdict, expected_artifact_verdict = _verdicts_for(recipes, taxonomy)

    if clinical_severity is None:
        clinical_severity = (
            "low"
            if not recipes
            else "high"
            if any(taxonomy.tier_of(r.safety_flag) in ("TIER_1", "TIER_2") for r in recipes)
            else "medium"
        )

    case_id = _case_id(spec, recipes, pack)

    expected_owner_map: dict[str, list[str]] = {}
    for r in recipes:
        if r.safety_flag in taxonomy.tier1_owners:
            expected_owner_map[r.safety_flag] = sorted(
                taxonomy.production_owners_of(r.safety_flag)
            )

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
            "active_medications": [m.description for m in spec.active_medications],
            "allergies": [a.description for a in spec.allergies],
        },
        "transcript": _clean_transcript(transcript),
        "artifacts": artifacts,
        "injection_recipes": [r.to_dict() for r in recipes],
        "expected_compliance_verdict": expected_verdict,
        "expected_artifact_verdict": expected_artifact_verdict,
        "expected_safety_flags": expected_flags,
        "expected_owner_map": expected_owner_map,
        "clean_negative": not recipes,
        "multi_defect": len(recipes) > 1,
        "severity": clinical_severity,
        "pinned": pinned,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_jsonl(rows: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
