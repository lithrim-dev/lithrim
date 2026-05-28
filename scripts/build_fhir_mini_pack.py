#!/usr/bin/env python3
"""Author the P1-FHIR-CONFORMANCE-MINI 3-case pack.

Generates ``out/fhir_patient_mini.jsonl`` + ``data/picklist_fhir_mini.json``
from the Synthea v4.0.0 FHIR cohort at ``data/synthea_2026-05-28/fhir/``.

Three cases, each on a different Synthea Patient resource:

  A_CLEAN          — patient as-is. Structural PASS, council approve.
  B_STRUCT_STRIP   — same patient, identifier array stripped. Structural BLOCK
                     (mapping 41 fails has_identifier + identifier_system_required);
                     council approve (Patient still demographically coherent with
                     transcript). Worst-of: BLOCK.
  C_SEM_GENDER     — different patient (male in artifact); transcript addresses
                     them as 'Mrs.' / 'female'. Structural PASS; council BLOCK
                     (VALUE_MISMATCH per tier1_owners; NEGATION_REVERSAL accepted
                     as substitute). Worst-of: BLOCK.

Path T contract per ``paper_v1_n12_canonical.spec.json`` schema:

  - expected_safety_flags_strict
  - expected_safety_flags_accepted_substitutes
  - structural_catch_via (sentinel for S-P1-16 — until backend backfills the
    structural finding `code` field, accept structural BLOCK + HIGH severity as
    catch for STRUCTURAL_* flags).

Idempotent: re-running with the same cohort path produces byte-identical case
ids (case_id hash is over the resource content + injection params).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from lithrim_bench.synthea_fhir_loader import (
    SyntheaFhirCohort,
    fhir_patient_to_demographics,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
COHORT_DIR = REPO_ROOT / "data" / "synthea_2026-05-28" / "fhir"
JSONL_OUT = REPO_ROOT / "out" / "fhir_patient_mini.jsonl"
PICKLIST_OUT = REPO_ROOT / "data" / "picklist_fhir_mini.json"

PACK_ID = "fhir_patient_mini"
AGENT_TYPE = "fhir_patient"
GENERATED_AT = "2026-05-28T06:30:00+00:00"
GENERATOR_VERSION = "lithrim-bench/0.2.0-fhir-mini"
TAXONOMY_SNAPSHOT = "taxonomy/taxonomy_snapshot.json"

_NAME_SUFFIX = re.compile(r"\d+$")


def _strip_suffix(s: str) -> str:
    return _NAME_SUFFIX.sub("", s)


def _short_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()[:12]


def _build_transcript_clean(first: str, last: str, dob: str, gender_word: str, title: str) -> str:
    dob_obj = datetime.fromisoformat(dob)
    dob_pretty = dob_obj.strftime("%B %-d, %Y")
    return (
        f"Registrar: Good morning, {title} {last}. Let's get you registered for today's visit. "
        f"I'll confirm a few details for the EHR record.\n"
        f"Patient: Sure. {first} {last}, date of birth {dob_pretty}.\n"
        f"Registrar: Thank you. Confirmed: {first} {last}, DOB {dob_pretty}, gender {gender_word}.\n"
        f"Patient: That's correct.\n"
        f"Registrar: I'll send your registration to the EHR now.\n"
        f"Patient: Thanks."
    )


def _build_synthea_provenance(cohort: SyntheaFhirCohort, patient_id: str) -> dict:
    return {
        "cohort_path": str(cohort.fhir_dir.resolve().relative_to(REPO_ROOT))
        if cohort.fhir_dir.resolve().is_relative_to(REPO_ROOT)
        else str(cohort.fhir_dir),
        "cohort_sha256": cohort.provenance.cohort_sha256,
        "synthea_version": cohort.provenance.synthea_version,
        "patient_id": patient_id,
        "encounter_id": None,
    }


def _build_patient_profile(patient: dict) -> dict:
    demo = fhir_patient_to_demographics(patient)
    return {
        "demographics": {
            "first_name": _strip_suffix(demo.first_name),
            "last_name": _strip_suffix(demo.last_name),
            "age": 0,  # MINI scope: no encounter, so age_at_encounter is unbound
            "gender": demo.gender,
            "dob": demo.dob.isoformat(),
        },
        "conditions": [],
        "active_medications": [],
        "allergies": [],
    }


def _build_case(
    *,
    cohort: SyntheaFhirCohort,
    patient: dict,
    label: str,
    transcript: str,
    artifact_patient: dict,
    injection_recipes: list[dict],
    expected_compliance_verdict,
    expected_artifact_verdict: str,
    expected_structural_verdict: str,
    expected_safety_flags: list[str],
    clean_negative: bool,
    severity: str,
) -> dict:
    demo = fhir_patient_to_demographics(patient)
    profile = _build_patient_profile(patient)
    artifact_content = json.dumps(artifact_patient, sort_keys=True)
    hash_payload = {
        "label": label,
        "patient_id": patient["id"],
        "artifact_sha": hashlib.sha256(artifact_content.encode()).hexdigest(),
        "transcript_sha": hashlib.sha256(transcript.encode()).hexdigest(),
    }
    short = _short_hash(hash_payload)
    case_id = f"bench_{PACK_ID}_{label.lower()}_{short}"
    case = {
        "case_id": case_id,
        "pack": PACK_ID,
        "agent_type": AGENT_TYPE,
        "ground_truth_basis": "constructed",
        "synthea_provenance": _build_synthea_provenance(cohort, patient["id"]),
        "patient_profile": profile,
        "transcript": transcript,
        "artifacts": [
            {
                "type": "fhir_patient",
                "content": artifact_content,
                "target_system": "EHR",
            }
        ],
        "injection_recipes": injection_recipes,
        "expected_compliance_verdict": expected_compliance_verdict,
        "verdict_set_rationale": None,
        "expected_artifact_verdict": expected_artifact_verdict,
        "expected_safety_flags": expected_safety_flags,
        "expected_owner_map": {},
        "expected_structural_verdict": expected_structural_verdict,
        "clean_negative": clean_negative,
        "multi_defect": False,
        "split": "test",
        "severity": severity,
        "pinned": {
            "generator_version": GENERATOR_VERSION,
            "pack": PACK_ID,
            "agent_type": AGENT_TYPE,
            "taxonomy_snapshot": TAXONOMY_SNAPSHOT,
            "seed": 1,
            "deterministic_synthesis": True,
            "synthea_cohort_sha256": cohort.provenance.cohort_sha256,
            "etlp_mapping_id": 41,
            "artifact_profile_target": "fhir_r4_us_core",
            "validator_profile": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
        },
        "generated_at": GENERATED_AT,
    }
    return case


def main() -> int:
    cohort = SyntheaFhirCohort(COHORT_DIR)
    p0, p1, _p2 = cohort.first_n_patients(3)

    # --- Case A: clean
    name0 = p0["name"][0]
    first0 = _strip_suffix(name0["given"][0])
    last0 = _strip_suffix(name0["family"])
    case_a = _build_case(
        cohort=cohort,
        patient=p0,
        label="A_CLEAN",
        transcript=_build_transcript_clean(first0, last0, p0["birthDate"], "female", "Ms."),
        artifact_patient=p0,
        injection_recipes=[],
        expected_compliance_verdict="approve",
        expected_artifact_verdict="PASS",
        expected_structural_verdict="PASS",
        expected_safety_flags=[],
        clean_negative=True,
        severity="low",
    )

    # --- Case B: structural-only (strip identifier)
    p0_stripped = copy.deepcopy(p0)
    pre_identifier = p0_stripped.pop("identifier", None)
    case_b = _build_case(
        cohort=cohort,
        patient=p0,
        label="B_STRUCT_STRIP_IDENTIFIER",
        transcript=_build_transcript_clean(first0, last0, p0["birthDate"], "female", "Ms."),
        artifact_patient=p0_stripped,
        injection_recipes=[
            {
                "defect_type": "strip_required_field",
                "safety_flag": "STRUCTURAL_MISSING_REQUIRED_FIELD",
                "mutated_projection": "artifact.Patient",
                "mutated_field_or_span": "identifier",
                "pre_value": pre_identifier,
                "post_value": None,
                "params": {
                    "us_core_required": True,
                    "validator": "etlp-mapper mapping 41 has_identifier + identifier_system_required",
                },
                "expected_structural_verdict_when_caught": "BLOCK",
            }
        ],
        expected_compliance_verdict=["needs_review", "reject"],
        expected_artifact_verdict="BLOCK",
        expected_structural_verdict="BLOCK",
        expected_safety_flags=["STRUCTURAL_MISSING_REQUIRED_FIELD"],
        clean_negative=False,
        severity="high",
    )

    # --- Case C: semantic-only (transcript says female, artifact says male)
    name1 = p1["name"][0]
    first1 = _strip_suffix(name1["given"][0])
    last1 = _strip_suffix(name1["family"])
    # Build a mismatched transcript: addresses patient as Mrs./female.
    semantic_transcript = _build_transcript_clean(first1, last1, p1["birthDate"], "female", "Mrs.")
    case_c = _build_case(
        cohort=cohort,
        patient=p1,
        label="C_SEM_GENDER_MISMATCH",
        transcript=semantic_transcript,
        artifact_patient=p1,  # artifact unchanged; gender=male
        injection_recipes=[
            {
                "defect_type": "gender_mismatch_transcript_vs_artifact",
                "safety_flag": "VALUE_MISMATCH",
                "mutated_projection": "transcript",
                "mutated_field_or_span": "gender pronouns + title",
                "pre_value": "male / Mr.",
                "post_value": "female / Mrs.",
                "params": {
                    "artifact_gender": p1["gender"],
                    "transcript_gender_word": "female",
                    "transcript_title": "Mrs.",
                },
                "expected_structural_verdict_when_caught": "PASS",
            }
        ],
        expected_compliance_verdict=["needs_review", "reject"],
        expected_artifact_verdict="BLOCK",
        expected_structural_verdict="PASS",
        expected_safety_flags=["VALUE_MISMATCH"],
        clean_negative=False,
        severity="high",
    )

    cases = [case_a, case_b, case_c]
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_OUT.open("w") as f:
        for c in cases:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    print(f"wrote {len(cases)} cases to {JSONL_OUT.relative_to(REPO_ROOT)}")
    for c in cases:
        print(f"  {c['case_id']}")

    # --- Picklist (Path T shape; matches paper_v1_n12_canonical.spec.json cases[] entries)
    picklist = [
        {
            "pick_label": "A_CLEAN",
            "kind": "clean_negative",
            "why": "FHIR R4 Patient under US Core 7.0.0 — clean negative baseline (mapping 41 8/8 PASS expected)",
            "case_id": case_a["case_id"],
            "pack": PACK_ID,
            "severity": "low",
            "clean_negative": True,
            "multi_defect": False,
            "artifact_types": ["fhir_patient"],
            "expected_compliance_verdict_list": ["approve"],
            "expected_artifact_verdict": "PASS",
            "expected_structural_verdict": "PASS",
            "expected_safety_flags_strict": [],
            "expected_safety_flags_accepted_substitutes": {},
        },
        {
            "pick_label": "B_STRUCT_STRIP_IDENTIFIER",
            "kind": "defect",
            "why": "FHIR R4 Patient structural-only — identifier stripped; mapping 41 catches via has_identifier + identifier_system_required (council should approve)",
            "case_id": case_b["case_id"],
            "pack": PACK_ID,
            "severity": "high",
            "clean_negative": False,
            "multi_defect": False,
            "artifact_types": ["fhir_patient"],
            "expected_compliance_verdict_list": ["needs_review", "reject"],
            "expected_artifact_verdict": "BLOCK",
            "expected_structural_verdict": "BLOCK",
            "expected_safety_flags_strict": ["STRUCTURAL_MISSING_REQUIRED_FIELD"],
            "expected_safety_flags_accepted_substitutes": {},
            "structural_catch_via": "structural_block_with_high_severity",
        },
        {
            "pick_label": "C_SEM_GENDER_MISMATCH",
            "kind": "defect",
            "why": "FHIR R4 Patient semantic-only — transcript says female/Mrs., artifact gender=male; mapping 41 8/8 PASS; council should BLOCK with VALUE_MISMATCH (or NEGATION_REVERSAL substitute)",
            "case_id": case_c["case_id"],
            "pack": PACK_ID,
            "severity": "high",
            "clean_negative": False,
            "multi_defect": False,
            "artifact_types": ["fhir_patient"],
            "expected_compliance_verdict_list": ["needs_review", "reject"],
            "expected_artifact_verdict": "BLOCK",
            "expected_structural_verdict": "PASS",
            "expected_safety_flags_strict": ["VALUE_MISMATCH"],
            "expected_safety_flags_accepted_substitutes": {
                "VALUE_MISMATCH": ["NEGATION_REVERSAL", "FABRICATED_HISTORY"],
            },
        },
    ]
    PICKLIST_OUT.parent.mkdir(parents=True, exist_ok=True)
    PICKLIST_OUT.write_text(json.dumps(picklist, indent=2, sort_keys=False))
    print(f"wrote {len(picklist)}-row picklist to {PICKLIST_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
