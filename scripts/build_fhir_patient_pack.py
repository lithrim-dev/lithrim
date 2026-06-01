"""Build a by-construction FHIR Patient boundary pack for the RAG-vs-structural experiment.

Extends scripts/build_fhir_mini_pack.py's pattern (deepcopy a clean US-Core Patient,
apply ONE mutation, record the injection recipe = the label). Base Patients are read
from the existing mini pack (MAIN/out/fhir_patient_mini.jsonl) by absolute path — no
Synthea dependency, fully self-contained in the spike.

Defect taxonomy (the point: span the conformance space so the boundary is measurable):
  clean ×2                         -> expected PASS (no defect)
  ctrl_strip_birthDate             -> expected PASS  (birthDate is must-support 0..1, NOT
                                      required; stripping it is valid — a false-positive control)
  struct_strip_identifier          -> STRUCTURAL_MISSING_REQUIRED_FIELD (identifier 1..*)
  struct_strip_name                -> STRUCTURAL_MISSING_REQUIRED_FIELD (name 1..*)
  struct_strip_gender              -> STRUCTURAL_MISSING_REQUIRED_FIELD (gender 1..1)
  struct_gender_invalid_binding    -> STRUCTURAL_INVALID_CODE (gender not in administrative-gender)
  struct_birthDate_bad_datatype    -> STRUCTURAL_INVALID_DATATYPE (birthDate not a date)
  struct_name_empty_cardinality    -> STRUCTURAL_CARDINALITY (name = [], violates 1..*)
  sem_gender_mismatch              -> VALUE_MISMATCH (artifact valid; transcript disagrees)

`expected_structural_verdict` = what a CORRECT structural validator should do (BLOCK for real
structural violations, PASS otherwise). The experiment (fhir_boundary_smoke.py) measures what
the JUTE validator AND the RAG-of-spec validator each actually catch vs this truth.

Deterministic: fixed generated_at, case_id = sha256 over content; re-running is byte-identical.
Output: data/verification_packs/fhir_patient_v1.jsonl
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MINI = REPO_ROOT / "out" / "fhir_patient_mini.jsonl"
OUT = REPO_ROOT / "data" / "verification_packs" / "fhir_patient_v1.jsonl"

PACK_ID = "fhir_boundary_v1"
GENERATED_AT = "2026-05-31T00:00:00+00:00"
GENERATOR_VERSION = "lithrim-bench-spike/fhir-boundary-0.1.0"


def _load_base_patients() -> list[dict]:
    recs = [json.loads(line) for line in MINI.read_text().splitlines() if line.strip()]
    # record 0 (clean) and record 2 (semantic case's artifact is an unmutated, valid Patient)
    bases = []
    for idx in (0, 2):
        art = (recs[idx].get("artifacts") or [{}])[0]
        bases.append(json.loads(art["content"]))
    return bases


def _short_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _case(
    *,
    label: str,
    patient: dict,
    recipe: dict | None,
    expected_structural_verdict: str,
    expected_safety_flags: list[str],
    transcript: str = "",
    clean: bool = False,
    severity: str = "high",
) -> dict:
    content = json.dumps(patient, sort_keys=True)
    short = _short_hash(
        {"label": label, "artifact_sha": hashlib.sha256(content.encode()).hexdigest()}
    )
    return {
        "case_id": f"bench_{PACK_ID}_{label.lower()}_{short}",
        "pack": PACK_ID,
        "agent_type": "fhir_patient",
        "ground_truth_basis": "constructed",
        "transcript": transcript,
        "artifacts": [{"type": "fhir_patient", "content": content, "target_system": "EHR"}],
        "injection_recipes": [recipe] if recipe else [],
        "expected_compliance_verdict": "approve" if clean else ["needs_review", "reject"],
        "expected_artifact_verdict": "PASS"
        if expected_structural_verdict == "PASS" and clean
        else ("PASS" if clean else "BLOCK"),
        "expected_structural_verdict": expected_structural_verdict,
        "expected_safety_flags": expected_safety_flags,
        "clean_negative": clean,
        "multi_defect": False,
        "split": "test",
        "severity": severity if not clean else "low",
        "pinned": {
            "generator_version": GENERATOR_VERSION,
            "pack": PACK_ID,
            "deterministic_synthesis": True,
            "validator_profile": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
        },
        "generated_at": GENERATED_AT,
    }


def _recipe(defect: str, field: str, pre, post, flag: str, note: str) -> dict:
    return {
        "defect_type": defect,
        "safety_flag": flag,
        "mutated_projection": "artifact.Patient",
        "mutated_field_or_span": field,
        "pre_value": pre,
        "post_value": post,
        "params": {"us_core_note": note},
    }


def main() -> int:
    base0, base1 = _load_base_patients()
    cases: list[dict] = []

    # clean negatives
    cases.append(
        _case(
            label="A_CLEAN_0",
            patient=base0,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )
    cases.append(
        _case(
            label="A_CLEAN_1",
            patient=base1,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )

    # false-positive control: strip birthDate (must-support 0..1 — NOT required; valid)
    p = copy.deepcopy(base0)
    pre = p.pop("birthDate", None)
    cases.append(
        _case(
            label="CTRL_STRIP_BIRTHDATE",
            patient=p,
            recipe=_recipe(
                "strip_optional_field",
                "birthDate",
                pre,
                None,
                "NONE",
                "birthDate is must-support 0..1, not required -> removing it is conformant",
            ),
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            severity="low",
        )
    )

    # structural: strip required (1..) elements
    for fld in ("identifier", "name", "gender"):
        p = copy.deepcopy(base0)
        pre = p.pop(fld, None)
        cases.append(
            _case(
                label=f"STRUCT_STRIP_{fld.upper()}",
                patient=p,
                recipe=_recipe(
                    "strip_required_field",
                    fld,
                    pre,
                    None,
                    "STRUCTURAL_MISSING_REQUIRED_FIELD",
                    f"us-core-patient {fld} cardinality_min>=1",
                ),
                expected_structural_verdict="BLOCK",
                expected_safety_flags=["STRUCTURAL_MISSING_REQUIRED_FIELD"],
            )
        )

    # structural: invalid code binding (gender value set = administrative-gender)
    p = copy.deepcopy(base0)
    pre = p.get("gender")
    p["gender"] = "X"
    cases.append(
        _case(
            label="STRUCT_GENDER_INVALID_BINDING",
            patient=p,
            recipe=_recipe(
                "invalid_code_binding",
                "gender",
                pre,
                "X",
                "STRUCTURAL_INVALID_CODE",
                "gender must bind administrative-gender {male|female|other|unknown}",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_CODE"],
        )
    )

    # structural: wrong datatype (birthDate must be a date)
    p = copy.deepcopy(base0)
    pre = p.get("birthDate")
    p["birthDate"] = "not-a-date"
    cases.append(
        _case(
            label="STRUCT_BIRTHDATE_BAD_DATATYPE",
            patient=p,
            recipe=_recipe(
                "wrong_datatype",
                "birthDate",
                pre,
                "not-a-date",
                "STRUCTURAL_INVALID_DATATYPE",
                "birthDate type=date (YYYY[-MM[-DD]])",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_DATATYPE"],
        )
    )

    # structural: cardinality (name 1..* -> empty array)
    p = copy.deepcopy(base0)
    pre = p.get("name")
    p["name"] = []
    cases.append(
        _case(
            label="STRUCT_NAME_EMPTY_CARDINALITY",
            patient=p,
            recipe=_recipe(
                "bad_cardinality",
                "name",
                pre,
                [],
                "STRUCTURAL_CARDINALITY",
                "us-core-patient name cardinality 1..* -> empty violates min",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_CARDINALITY"],
        )
    )

    # semantic: artifact valid; transcript disagrees on gender (the shared blind spot)
    semantic_transcript = (
        "Registrar: Good morning, Mrs. Patient. Confirming gender female for the record.\n"
        "Patient: Yes, that's correct."
    )
    cases.append(
        _case(
            label="SEM_GENDER_MISMATCH",
            patient=base1,  # artifact unchanged/valid
            recipe=_recipe(
                "gender_mismatch_transcript_vs_artifact",
                "gender",
                f"artifact={base1.get('gender')}",
                "transcript=female/Mrs.",
                "VALUE_MISMATCH",
                "artifact is structurally valid; conflicts with transcript -> needs source grounding",
            ),
            expected_structural_verdict="PASS",
            expected_safety_flags=["VALUE_MISMATCH"],
            transcript=semantic_transcript,
        )
    )

    OUT.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in cases))
    print(f"wrote {len(cases)} cases -> {OUT.name}")
    for c in cases:
        rec = c["injection_recipes"] or [{}]
        d = rec[0].get("defect_type", "clean") if rec and rec[0] else "clean"
        print(
            f"  {c['case_id'][-34:]:34s} defect={d:42s} expect_structural={c['expected_structural_verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
