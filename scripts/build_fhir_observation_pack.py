"""Engagement-two oracle: a by-construction FHIR Observation boundary pack.

Deliberately a SECOND resource (not Patient) to instrument the compounding-margin claim:
how much of the engagement-one machinery transfers? The defect taxonomy + `_case`/`_recipe`
builders are reused verbatim from build_fhir_boundary_pack.py; only the clean instances +
the per-field mapping are new (the irreducible domain spec).

Observation conformance space (base FHIR R4 + US-Core observation-clinical-result):
  clean x2                          -> PASS
  ctrl_strip_effective              -> PASS  (effective[x] is 0..1 — optional; FP control,
                                      the dateTime analog of Patient's birthDate control)
  struct_strip_status               -> BLOCK (status 1..1 required)
  struct_strip_code                 -> BLOCK (code 1..1 required)
  struct_status_invalid_binding     -> BLOCK (status not in observation-status value set)
  struct_effective_bad_datatype     -> BLOCK (effectiveDateTime not a FHIR dateTime)
  sem_value_mismatch                -> PASS  (artifact valid; transcript disagrees -> needs source)

Note vs Patient: Observation's required elements (status, code) are SCALARS, so the
"empty-array violates 1..*" cardinality class has no clean analog here — dropped. That
omission is itself a per-resource domain fact, not a gap in the machinery.

Deterministic: fixed generated_at, case_id = sha256 over content. Byte-identical re-runs.
Output: data/verification_packs/fhir_observation_v1.jsonl
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "data" / "verification_packs" / "fhir_observation_v1.jsonl"

PACK_ID = "observation_boundary_v1"
GENERATED_AT = "2026-05-31T00:00:00+00:00"
GENERATOR_VERSION = "lithrim-bench-spike/observation-boundary-0.1.0"

# two clean, valid base FHIR R4 Observations (hand-authored, by-construction -> true labels)
BASE0 = {
    "resourceType": "Observation",
    "status": "final",
    "code": {
        "coding": [
            {"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}
        ]
    },
    "subject": {"reference": "Patient/0149546a"},
    "effectiveDateTime": "2026-05-30T09:00:00Z",
    "valueQuantity": {
        "value": 120,
        "unit": "mmHg",
        "system": "http://unitsofmeasure.org",
        "code": "mm[Hg]",
    },
}
BASE1 = {
    "resourceType": "Observation",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose"}]},
    "subject": {"reference": "Patient/0190e572"},
    "effectiveDateTime": "2026-05-28T14:30:00Z",
    "valueQuantity": {
        "value": 95,
        "unit": "mg/dL",
        "system": "http://unitsofmeasure.org",
        "code": "mg/dL",
    },
}


def _short_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _case(
    *,
    label: str,
    obs: dict,
    recipe: dict | None,
    expected_structural_verdict: str,
    expected_safety_flags: list[str],
    transcript: str = "",
    clean: bool = False,
    severity: str = "high",
) -> dict:
    content = json.dumps(obs, sort_keys=True)
    short = _short_hash(
        {"label": label, "artifact_sha": hashlib.sha256(content.encode()).hexdigest()}
    )
    return {
        "case_id": f"bench_{PACK_ID}_{label.lower()}_{short}",
        "pack": PACK_ID,
        "agent_type": "fhir_observation",
        "ground_truth_basis": "constructed",
        "transcript": transcript,
        "artifacts": [{"type": "fhir_observation", "content": content, "target_system": "EHR"}],
        "injection_recipes": [recipe] if recipe else [],
        "expected_compliance_verdict": "approve" if clean else ["needs_review", "reject"],
        "expected_artifact_verdict": "PASS" if clean else "BLOCK",
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
            "validator_profile": "http://hl7.org/fhir/StructureDefinition/Observation",
        },
        "generated_at": GENERATED_AT,
    }


def _recipe(defect: str, field: str, pre, post, flag: str, note: str) -> dict:
    return {
        "defect_type": defect,
        "safety_flag": flag,
        "mutated_projection": "artifact.Observation",
        "mutated_field_or_span": field,
        "pre_value": pre,
        "post_value": post,
        "params": {"fhir_note": note},
    }


def main() -> int:
    cases: list[dict] = []

    cases.append(
        _case(
            label="A_CLEAN_0",
            obs=BASE0,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )
    cases.append(
        _case(
            label="A_CLEAN_1",
            obs=BASE1,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )

    # FP control: strip effectiveDateTime (effective[x] is 0..1 — optional; valid to omit)
    p = copy.deepcopy(BASE0)
    pre = p.pop("effectiveDateTime", None)
    cases.append(
        _case(
            label="CTRL_STRIP_EFFECTIVE",
            obs=p,
            recipe=_recipe(
                "strip_optional_field",
                "effectiveDateTime",
                pre,
                None,
                "NONE",
                "effective[x] is 0..1, not required -> removing it is conformant",
            ),
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            severity="low",
        )
    )

    # structural: strip required (1..1) scalars
    for fld in ("status", "code"):
        p = copy.deepcopy(BASE0)
        pre = p.pop(fld, None)
        cases.append(
            _case(
                label=f"STRUCT_STRIP_{fld.upper()}",
                obs=p,
                recipe=_recipe(
                    "strip_required_field",
                    fld,
                    pre,
                    None,
                    "STRUCTURAL_MISSING_REQUIRED_FIELD",
                    f"Observation {fld} cardinality 1..1",
                ),
                expected_structural_verdict="BLOCK",
                expected_safety_flags=["STRUCTURAL_MISSING_REQUIRED_FIELD"],
            )
        )

    # structural: invalid code binding (status value set = observation-status)
    p = copy.deepcopy(BASE0)
    pre = p.get("status")
    p["status"] = "bogus"
    cases.append(
        _case(
            label="STRUCT_STATUS_INVALID_BINDING",
            obs=p,
            recipe=_recipe(
                "invalid_code_binding",
                "status",
                pre,
                "bogus",
                "STRUCTURAL_INVALID_CODE",
                "status must bind observation-status {registered|preliminary|final|amended|...}",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_CODE"],
        )
    )

    # structural: wrong datatype (effectiveDateTime must be a FHIR dateTime)
    p = copy.deepcopy(BASE0)
    pre = p.get("effectiveDateTime")
    p["effectiveDateTime"] = "not-a-date"
    cases.append(
        _case(
            label="STRUCT_EFFECTIVE_BAD_DATATYPE",
            obs=p,
            recipe=_recipe(
                "wrong_datatype",
                "effectiveDateTime",
                pre,
                "not-a-date",
                "STRUCTURAL_INVALID_DATATYPE",
                "effectiveDateTime type=dateTime (YYYY-MM-DD[Thh:mm:ss[+zz:zz]])",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_DATATYPE"],
        )
    )

    # semantic: artifact valid; transcript disagrees on the value (shared blind spot)
    semantic_transcript = (
        "Nurse: Recording the glucose reading as 250 mg/dL, patient is hyperglycemic.\n"
        "Provider: Noted, 250."
    )
    cases.append(
        _case(
            label="SEM_VALUE_MISMATCH",
            obs=BASE1,  # artifact unchanged/valid (value=95)
            recipe=_recipe(
                "value_mismatch_transcript_vs_artifact",
                "valueQuantity.value",
                "artifact=95",
                "transcript=250",
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
        print(f"  {c['expected_structural_verdict']:5s} | {d:42s} | {c['case_id'][-30:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
