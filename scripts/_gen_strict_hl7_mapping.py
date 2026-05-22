"""Item 6: ask the etlp-mapper copilot to extend the ADT^A04 validator
(mapping 26) with the 3 format/value-set checks it lacks.

Current mapping 26 is presence-only (16 checks) — it catches
missing-segment + missing-required-field but passes through
malformed-date, invalid-field-format, and trigger-event-mismatch.
This requests a stricter validator covering all five defect classes,
scoped to common/widespread HL7 v2.x conformance (not site-specific
customization).

Usage:  python scripts/_gen_strict_hl7_mapping.py
"""
import json
import urllib.request
import urllib.error

ETLP = "http://localhost:3031"

# Parsed valid ADT^A04 (from mapping 26 test_data "valid-full").
SAMPLE_INPUT = {
    "resource": {
        "MSH": {"type": {"code": "ADT", "event": "A04"},
                "version": {"id": "2.4"}, "id": "MSG00001"},
        "EVN": {"event_type_code": "A04"},
        "PID": {"identifiers": [{"value": "PATID1234"}],
                "name": [{"family": {"surname": "JONES"}, "given": "WILLIAM"}],
                "birth_date": {"time": "19610615"},
                "gender": "M",
                "address": [{"city": "GREENSBORO", "state": "NC",
                             "postal_code": "27401"}]},
        "PV1": {"patient_class": "O",
                "attending_doctor": [{"id": "1234",
                                      "family": {"surname": "SMITH"}}]},
        "IN1": {"_present": True},
        "AL1": {"_present": True},
    }
}

# Expected output for the valid sample: every check passes. The 3 new
# checks are shown explicitly; the 16 existing presence checks are
# retained from the existing_template.
EXPECTED_OUTPUT = {
    "request": {
        "valid": True,
        "resourceType": "ADT-A04",
        "totalChecks": 19,
        "passedChecks": 19,
        "failedChecks": 0,
        "checks": [
            {"name": "dob-format-valid", "field": "PID.7", "status": "pass",
             "message": "Date of birth is a valid 8-digit YYYYMMDD date",
             "value": "19610615"},
            {"name": "gender-value-valid", "field": "PID.8", "status": "pass",
             "message": "Administrative gender is a valid HL7 Table 0001 code",
             "value": "M"},
            {"name": "trigger-event-consistent", "field": "EVN.1", "status": "pass",
             "message": "EVN event type code matches the MSH-9 trigger event",
             "value": "A04"},
        ],
    }
}

DESCRIPTION = """\
Extend this HL7 v2.x ADT^A04 patient-registration conformance validator
with format and value-set checks. The current template is presence-only
(every check just tests that a field exists); it cannot catch a field
that is present but malformed. Keep ALL 16 existing presence checks
unchanged. ADD exactly these 3 new checks, scoped to common, widespread,
standard HL7 v2.x conformance (not site-specific customization):

1. dob-format-valid (field PID.7): the patient date of birth
   resource.PID.birth_date.time must be a valid 8-digit calendar date in
   YYYYMMDD form. Check that its length is exactly 8. status pass/fail.
   On fail message: "Date of birth is not a valid 8-digit YYYYMMDD date
   — EHR date parser will reject the message".

2. gender-value-valid (field PID.8): the administrative gender
   resource.PID.gender must be one of the HL7 Table 0001 codes:
   A, F, M, N, O, U. status pass/fail. On fail message: "Administrative
   gender is not a valid HL7 Table 0001 code (A,F,M,N,O,U)".

3. trigger-event-consistent (field EVN.1): the EVN event type code
   resource.EVN.event_type_code must equal the MSH-9 trigger event
   resource.MSH.type.event — a message whose EVN segment disagrees with
   its MSH trigger is internally inconsistent. status pass/fail. On fail
   message: "EVN event type code does not match the MSH-9 trigger event
   — internally inconsistent message".

The output must keep the exact same ValidationResult shape: a top-level
`request` object with valid (boolean: passedChecks = totalChecks),
resourceType "ADT-A04", totalChecks (now 19), passedChecks, failedChecks,
and a flat `checks` array of all 19 check objects (each with name, field,
status, message, and value where applicable). Append the 3 new checks
after the existing 16. Update totalChecks to 19 and the valid/passed/
failed arithmetic accordingly. Emit raw YAML only — no code fences, no
prose.
"""


def fetch_mapping_yaml(mapping_id: int) -> str:
    with urllib.request.urlopen(f"{ETLP}/mappings/{mapping_id}") as r:
        return json.load(r)["content"]["yaml"]


def main() -> None:
    existing = fetch_mapping_yaml(26)
    body = {
        "sample_input": SAMPLE_INPUT,
        "expected_output": EXPECTED_OUTPUT,
        "description": DESCRIPTION,
        "source_format": "hl7v2",
        "target_platform": "jute-validator",
        "existing_template": existing,
    }
    req = urllib.request.Request(
        f"{ETLP}/mappings/generate",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:800]}")
        return
    print(f"confidence: {result.get('confidence')}")
    print(f"retries_used: {result.get('retries_used')}")
    tr = result.get("test_result") or {}
    print(f"test_result.compiled: {tr.get('compiled')}  warning: {tr.get('warning')}")
    template = result.get("template", "")
    out = "out/strict_hl7_adt_a04.yaml"
    with open(out, "w") as f:
        f.write(template)
    print(f"wrote {out} ({len(template)} chars)")


if __name__ == "__main__":
    main()
