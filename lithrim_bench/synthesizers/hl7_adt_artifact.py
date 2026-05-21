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

from ..encounter_spec import EncounterSpec

_FIELD = "|"
_COMP = "^"
_MSH_2 = "^~\\&"


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
    address = _COMP.join(["123 Main St", "", "Boston", "MA", "02101", "USA"])
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
    visit_id = spec.encounter.encounter_id[:12]
    location = _COMP.join(["WARD-A", "101", "1"])
    return _FIELD.join([
        "PV1",
        "1",
        "O",
        location,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        visit_id,
    ])


def _al1_for(spec: EncounterSpec) -> list[str]:
    segments: list[str] = []
    for i, allergy in enumerate(spec.allergies[:3], start=1):
        segments.append(_FIELD.join([
            "AL1",
            str(i),
            "DA",
            f"{allergy.snomed_code}{_COMP}{allergy.description}{_COMP}SNOMED-CT",
        ]))
    return segments


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
    body = "\r".join(segments) + "\r"
    return [
        {
            "type": "hl7_adt_a04",
            "content": body,
            "target_system": "EHR",
        }
    ]
