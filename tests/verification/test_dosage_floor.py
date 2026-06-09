"""Offline tests for the deterministic dosage-grounding FLOOR (no network, no LLM).

The dose floor grounds every dose DOCUMENTED in the artifact against the encounter
evidence — the transcript instruction and (when declared) the patient chart. A dose
grounded in neither flips the verdict by injecting WRONG_DOSAGE; this is the
deterministic analogue of the record-grounding moat, and it never calls a judge or
the network. Grounding against transcript+chart (not transcript alone) closes the
same blind spot a transcript-only judge has — proven by ``test_*_record`` below.
"""

from __future__ import annotations

from lithrim_bench.harness import pack
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.verification import (
    TOOL_DOSAGE_GROUNDING,
    Claim,
    VerificationSpec,
)

# PACK-3: the DosageGroundingTool floor relocated into the active healthcare pack.
DosageGroundingTool = pack.load_pack_floors().DosageGroundingTool

# the SME-pinned extraction pattern (mirrors the proven module _DOSE_RE)
_DOSE_REGEX = r"\d+(?:\.\d+)?\s*(?:MG/ML|MG/ACTUAT|MCG|MG|ML|G|UNITS?)\b"

# the encounter ground-truth: the clinician instructs 10 MG -> 20 MG (the artifact must match)
_TRANSCRIPT = (
    "Doctor: I'm increasing your lisinopril from 10 MG to 20 MG daily. Recheck in a month."
)
_CLEAN_NOTE = "PLAN:\n- Lisinopril 20 MG once daily\n- Follow up in 1 month"
_DRIFT_NOTE = "PLAN:\n- Lisinopril 40 MG once daily\n- Follow up in 1 month"  # 40 stated nowhere
_NO_DOSE_NOTE = "PLAN:\n- Continue current care\n- Follow up in 1 month"

COUNCIL_PASS = {"verdict": "PASS", "findings": []}


def _case(*, note, transcript=_TRANSCRIPT, active_medications=None):
    pp = {"conditions": []}
    if active_medications is not None:
        pp["active_medications"] = active_medications
    return {
        "case_id": "dose_fixture",
        "transcript": transcript,
        "artifacts": [{"type": "scribe_note", "content": note}],
        "patient_profile": pp,
    }


def _dose_ontology(*, record_path=None):
    params = {
        "dose_regex": _DOSE_REGEX,
        "transcript_path": "transcript",
        "inject_flag_code": "WRONG_DOSAGE",
        "inject_severity": "HIGH",
    }
    if record_path:
        params["record_path"] = record_path
    return from_dict(
        {
            "ontology_version": "dosage_floor_test_v1",
            "domain": "test",
            "flags": [
                {
                    "flag": "WRONG_DOSAGE",
                    "category": "safety",
                    "definition": "",
                    "when_to_use": "",
                    "when_NOT_to_use": "",
                    "owner_roles": ["risk_judge"],
                    "tier": "tier1",
                    "gradeable": True,
                }
            ],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "WRONG_DOSAGE",
                    "question": "Is every documented dose grounded in the encounter?",
                    "contract_type": TOOL_DOSAGE_GROUNDING,
                    "version": "dosage-grounding/v1",
                    "params": params,
                }
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
                "block_at_or_above": 0.5,
                "warn_above": 0.0,
            },
        }
    )


# --------------------------------------------------------------------------- #
# the floor, end to end through ground()
# --------------------------------------------------------------------------- #
def test_dosage_floor_flips_pass_to_block():
    # the council PASSed; the deterministic floor catches the 40 MG it never stated.
    g = ground(COUNCIL_PASS, _case(note=_DRIFT_NOTE), ontology=_dose_ontology())
    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is not None
    inj = g.floor_blocks[0]["injected_finding"]
    assert inj["code"] == "WRONG_DOSAGE" and inj["severity"] == "HIGH"
    assert g.floor_blocks[0]["result"].evidence["ungrounded_doses"] == ["40MG"]


def test_dosage_floor_clean_is_noop():
    # documented 20 MG is exactly what the transcript instructs -> conforms, no flip.
    g = ground(COUNCIL_PASS, _case(note=_CLEAN_NOTE), ontology=_dose_ontology())
    assert g.verdict == "PASS" and g.floor_blocks == []


def test_dosage_floor_no_parseable_dose_is_inconclusive():
    # nothing to ground -> conforms None -> surfaced, never flips, never clears by silence.
    g = ground(COUNCIL_PASS, _case(note=_NO_DOSE_NOTE), ontology=_dose_ontology())
    assert g.verdict == "PASS"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is None


def test_dosage_floor_grounds_against_record_not_just_transcript():
    # the moat lesson: a dose absent from THIS transcript but present in the chart is
    # NOT a fabrication. With the chart oracle declared, the floor does not false-fire.
    note = "PLAN:\n- Metformin 500 MG twice daily"
    transcript = "Doctor: keep taking your current medications. See you in three months."
    meds = ["Metformin 500 MG Oral Tablet", "Lisinopril 20 MG Oral Tablet"]
    with_chart = ground(
        COUNCIL_PASS,
        _case(note=note, transcript=transcript, active_medications=meds),
        ontology=_dose_ontology(record_path="patient_profile.active_medications"),
    )
    assert with_chart.verdict == "PASS" and with_chart.floor_blocks == []

    # without the chart oracle, transcript-only grounding wrongly flags it -> proves the
    # record axis is load-bearing (same shape as the council's transcript-only blind spot).
    transcript_only = ground(
        COUNCIL_PASS,
        _case(note=note, transcript=transcript, active_medications=meds),
        ontology=_dose_ontology(),
    )
    assert transcript_only.verdict == "BLOCK"


# --------------------------------------------------------------------------- #
# the tool's tri-state contract, directly
# --------------------------------------------------------------------------- #
def _verify(note, *, transcript=_TRANSCRIPT, record_path=None, meds=None):
    ref = {"dose_regex": _DOSE_REGEX, "transcript_path": "transcript"}
    if record_path:
        ref["record_path"] = record_path
    spec = VerificationSpec(
        tool=TOOL_DOSAGE_GROUNDING,
        applies_to_flags=("WRONG_DOSAGE",),
        locus="dosage",
        reference=ref,
        version="dosage-grounding/v1",
    )
    src = {"transcript": transcript}
    if meds is not None:
        src["patient_profile"] = {"active_medications": meds}
    claim = Claim(
        claim_type="structural_conformance", flag_code="WRONG_DOSAGE", subject=note, source=src
    )
    return DosageGroundingTool().verify(claim, spec)


def test_tool_tri_state():
    assert _verify(_CLEAN_NOTE).conforms is True
    assert _verify(_DRIFT_NOTE).conforms is False
    assert _verify(_NO_DOSE_NOTE).conforms is None  # inconclusive, never a silent clear


def test_tool_spec_requires_dose_regex():
    import pytest

    with pytest.raises(ValueError, match="dose_regex"):
        VerificationSpec(
            tool=TOOL_DOSAGE_GROUNDING,
            applies_to_flags=("WRONG_DOSAGE",),
            locus="dosage",
            reference={"transcript_path": "transcript"},  # missing the required dose_regex
            version="v1",
        )
