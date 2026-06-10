"""Deterministic HL7 v2 ADT^A04 message synthesis.

ADT^A04 = patient registration (outpatient/admission). Matches the
shape validated by lithrim-backend's etlp-mapper mapping 25 (16 deep
field-level checks across MSH / EVN / PID / PV1 / AL1 / IN1).

Direct Python emitter; no simhospital dependency for v1. Phase 4 can
add a simhospital adapter behind the same interface if pathway-driven
generation becomes useful, but for the paper benchmark this is enough.

HL7 v2 field separators are fixed: | for fields, ^ for components,
~ for repetitions, \\ for escape, & for sub-components. The MSH-2
field MUST be exactly "^~\\&" — a frequent source of off-by-one bugs
in HL7 emitters and one of the things the validator checks.
"""
from __future__ import annotations

from typing import Any

from lithrim_bench.encounter_spec import EncounterSpec

_FIELD = "|"
_COMP = "^"
_MSH_2 = "^~\\&"

# Registration constants — shared with hl7_adt_transcript so the
# transcript can ground every ADT field. v1 hardcoded these only in
# the artifact emitter, leaving address / provider / ward / insurance
# ungrounded in the (name/DOB/gender-only) transcript.
REG_ADDRESS = {
    "street": "123 Main St",
    "city": "Boston",
    "state": "MA",
    "zip": "02101",
    "country": "USA",
}
ATTENDING = {"id": "DOC001", "family": "Patel", "given": "Anita", "prefix": "DR"}
WARD = {"point_of_care": "WARD-A", "room": "101", "bed": "1"}
PATIENT_CLASS = "O"  # O = outpatient (ADT^A04 registration)
PATIENT_CLASS_LABEL = "outpatient"
INSURANCE = {
    "plan_id": "PLAN001",
    "company_id": "INS001",
    "plan_code": "DEMOPLAN-1",
    "plan_name": "Lithrim Bench Coverage",
}


def _msg_dt(spec: EncounterSpec) -> str:
    return spec.encounter.start.strftime("%Y%m%d%H%M%S")


def _hl7_date(d) -> str:
    return d.strftime("%Y%m%d")


def _msh(spec: EncounterSpec) -> str:
    msg_id = f"MSG{spec.encounter.encounter_id[:8]}"
    return _FIELD.join([
        "MSH",
        _MSH_2,
        "LITHRIM_BENCH",
        "LITHRIM_FAC",
        "RECV_APP",
        "RECV_FAC",
        _msg_dt(spec),
        "",
        f"ADT{_COMP}A04",
        msg_id,
        "P",
        "2.5",
    ])


def _evn(spec: EncounterSpec) -> str:
    return _FIELD.join(["EVN", "A04", _msg_dt(spec)])


def _pid(spec: EncounterSpec) -> str:
    demo = spec.demographics
    name = _COMP.join([demo.last_name, demo.first_name, ""])
    address = _COMP.join([
        REG_ADDRESS["street"], "", REG_ADDRESS["city"],
        REG_ADDRESS["state"], REG_ADDRESS["zip"], REG_ADDRESS["country"],
    ])
    return _FIELD.join([
        "PID",
        "1",
        "",
        demo.patient_id,
        "",
        name,
        "",
        _hl7_date(demo.dob),
        demo.gender,
        "",
        "",
        address,
    ])


def _pv1(spec: EncounterSpec) -> str:
    """ADT^A04 visit segment. Calibrated to mapping 26's required fields.

    Live validator (etlp-mapper mapping 26 hl7-adt-a04-validator) checks:
      PV1.2 patient_class — required, non-empty, in {I,O,E}
      PV1.7 attending_doctor — required for order routing
    """
    visit_id = spec.encounter.encounter_id[:12]
    location = _COMP.join([WARD["point_of_care"], WARD["room"], WARD["bed"]])
    attending = _COMP.join([
        ATTENDING["id"], ATTENDING["family"], ATTENDING["given"], "", "", ATTENDING["prefix"],
    ])
    fields = ["PV1", "1", PATIENT_CLASS, location, "", "", "", attending]
    fields.extend([""] * (44 - len(fields)))
    fields.append(visit_id)
    return _FIELD.join(fields)


def _al1_for(spec: EncounterSpec) -> list[str]:
    """At least one AL1 row — mapping 26's allergy-segment check fires
    on absence. If the EncounterSpec has no allergies, emit an NKA marker
    so the message remains compliant with the validator's expectation."""
    if not spec.allergies:
        return [_FIELD.join([
            "AL1",
            "1",
            "DA",
            f"NKA{_COMP}No known allergies{_COMP}LITHRIM",
        ])]
    segments: list[str] = []
    for i, allergy in enumerate(spec.allergies[:3], start=1):
        segments.append(_FIELD.join([
            "AL1",
            str(i),
            "DA",
            f"{allergy.snomed_code}{_COMP}{allergy.description}{_COMP}SNOMED-CT",
        ]))
    return segments


def _in1(spec: EncounterSpec) -> str:
    """Insurance segment — required by mapping 26's insurance-segment check.
    Synthesized as a self-pay-equivalent commercial plan; the validator
    only checks presence, not coverage adequacy."""
    plan_name = _COMP.join([INSURANCE["plan_code"], INSURANCE["plan_name"]])
    return _FIELD.join([
        "IN1",
        "1",
        INSURANCE["plan_id"],
        INSURANCE["company_id"],
        plan_name,
    ])


def synthesize_hl7_adt_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    """Emit a well-formed ADT^A04 message as a single text artifact.

    The message is the artifact `content`; the type tag identifies it
    as hl7_adt_a04 which is what backend's mapping 25 validates.
    """
    segments = [
        _msh(spec),
        _evn(spec),
        _pid(spec),
        _pv1(spec),
    ]
    segments.extend(_al1_for(spec))
    segments.append(_in1(spec))
    body = "\r".join(segments) + "\r"
    return [
        {
            "type": "hl7_adt_a04",
            "content": body,
            "target_system": "EHR",
        }
    ]
