"""VALUE-GROUNDING-FLOOR-1 — every VALUE the artifact states must be present in the source.

The inverse of ``value_presence`` (source values must reach the artifact): here the ARTIFACT's
values (numbers, clock times) must each be found in the SOURCE, with deterministic value
normalization (numeric equality ``4.0 == 4``; ``17:30`` == ``5:30``; ``9:0`` == ``9:00``;
number words on the source side; list markers and single-digit counts ignored). Pure stdlib,
offline, ``deterministic: True`` in the manifest.

What it may CLAIM is bounded by measurement, not assertion. On the RAGTruth test split (human
span labels as gold; 2026-09-06 offline cut) a value absent from the source is:
  * a VIOLATION when the source is a structured RECORD (data-to-text): precision 0.78 strict /
    0.94 any-label, recall 0.82;
  * only a LEAD when the source is PROSE (news summaries): precision 0.10 strict.
So the tri-state is: ``conforms=True`` (>=1 value checked, all present: a recorded floor pass),
``conforms=False`` (a value is missing AND the case's ``source_kind`` is ``record`` — or the
contract pins ``on_missing: violation``), ``conforms=None`` otherwise: no values to check, no
source, or a missing value on prose, surfaced WITH the missing values as evidence so the
reviewer can escalate a named lead, never a silent pass and never an over-flag.

Written FIRST (RED): ``ValueGroundingTool`` / ``TOOL_VALUE_GROUNDING`` do not exist, the
``_core`` floor registry has no ``value_grounding`` executor, and the neutral ``_core`` pack
declares no contracts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grounding import (  # noqa: E402
    _contract_transport,
    floor_executors,
    ground,
)
from lithrim_bench.harness.ontology import from_dict, load_ontology  # noqa: E402
from lithrim_bench.verification import (  # noqa: E402
    STRUCTURAL_CONFORMANCE,
    TOOL_VALUE_GROUNDING,
    Claim,
    ValueGroundingTool,
    VerificationSpec,
)

_SEV = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}

_RECORD = json.dumps(
    {
        "name": "Finch & Fork",
        "city": "Santa Barbara",
        "hours": {"Sunday": "9:0-14:0", "Monday": "17:30-23:0"},
        "business_stars": 4.0,
        "review_count": 312,
    }
)
_PROSE = (
    "Nineteen people attended the meeting on Tuesday. The council approved the budget "
    "after a debate that ran past midnight."
)


def _spec(reference=None, version="value-grounding/test-1"):
    return VerificationSpec(
        tool=TOOL_VALUE_GROUNDING,
        applies_to_flags=("SOURCE_CONTRADICTION",),
        locus="",
        reference=reference or {},
        version=version,
    )


def _claim(artifact, case):
    return Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code="SOURCE_CONTRADICTION",
        subject=artifact,
        locus="",
        source=case,
    )


def _record_case(artifact):
    return {
        "source_kind": "record",
        "transcript": _RECORD,
        "artifacts": [{"type": "generated_response", "content": artifact}],
    }


def _prose_case(artifact):
    return {
        "source_kind": "prose",
        "transcript": _PROSE,
        "artifacts": [{"type": "generated_response", "content": artifact}],
    }


# ── A1: registration ──────────────────────────────────────────────────────────────────────

def test_tool_is_registered_with_no_required_reference_keys():
    assert TOOL_VALUE_GROUNDING == "value_grounding"
    spec = _spec()  # an empty reference must construct: every knob is optional
    assert spec.tool == "value_grounding"
    assert ValueGroundingTool().handles(spec)


def test_core_floor_registry_has_the_executor():
    ex = floor_executors("_core")["value_grounding"]
    assert ex.tool_factory(None).name == "value_grounding"
    assert ex.reference_builder({"inject_flag_code": "X", "inject_severity": "HIGH"}) == {}
    assert ex.reference_builder({"on_missing": "lead"}) == {"on_missing": "lead"}


# ── A2: tri-state semantics ───────────────────────────────────────────────────────────────

def test_record_source_missing_value_is_a_violation_with_the_value_named():
    art = "Rated 4.5 stars with 312 reviews. Open Sundays from 9:00 am to 2:00 pm."
    r = ValueGroundingTool().verify(_claim(art, _record_case(art)), _spec())
    assert r.conforms is False
    assert r.evidence["missing"] == ["4.5"]
    assert "312" in r.evidence["present"]
    assert "9:00" in r.evidence["present"] and "2:00" in r.evidence["present"]
    assert r.manifest["deterministic"] is True
    assert r.manifest["source_kind"] == "record"


def test_record_source_all_values_present_is_a_recorded_pass():
    art = "Rated 4 stars with 312 reviews. Open Mondays from 5:30 pm to 11:00 pm."
    r = ValueGroundingTool().verify(_claim(art, _record_case(art)), _spec())
    assert r.conforms is True
    assert r.evidence["missing"] == []
    assert set(r.evidence["present"]) >= {"4", "312", "5:30", "11:00"}
    assert r.evidence["checked"] == len(r.evidence["present"])


def test_prose_source_missing_value_is_a_lead_not_a_block():
    art = "Here is a summary in 84 words: nineteen people attended and the budget passed."
    r = ValueGroundingTool().verify(_claim(art, _prose_case(art)), _spec())
    assert r.conforms is None
    assert r.evidence["missing"] == ["84"]
    assert "lead" in r.evidence["reason"].lower()
    assert r.disposition == "INCONCLUSIVE"


def test_prose_source_all_values_present_is_still_a_pass():
    art = "19 people attended the meeting."
    r = ValueGroundingTool().verify(_claim(art, _prose_case(art)), _spec())
    assert r.conforms is True  # number word "nineteen" in the source grounds "19"
    assert r.evidence["present"] == ["19"]


def test_on_missing_pin_overrides_source_kind():
    art = "Here is a summary in 84 words: the budget passed."
    prose = ValueGroundingTool().verify(
        _claim(art, _prose_case(art)), _spec({"on_missing": "violation"})
    )
    assert prose.conforms is False
    art2 = "Rated 4.5 stars."
    rec = ValueGroundingTool().verify(_claim(art2, _record_case(art2)), _spec({"on_missing": "lead"}))
    assert rec.conforms is None and rec.evidence["missing"] == ["4.5"]


def test_nothing_to_check_is_inconclusive():
    art = "1. A first point. 2. A second point. COVID-19 was mentioned; a 5-star vibe."
    r = ValueGroundingTool().verify(_claim(art, _prose_case(art)), _spec())
    assert r.conforms is None
    assert "no values" in r.evidence["reason"].lower()
    empty = ValueGroundingTool().verify(_claim("", _prose_case("")), _spec())
    assert empty.conforms is None
    nosrc = ValueGroundingTool().verify(
        _claim("Rated 4.5 stars.", {"artifacts": [{"content": "Rated 4.5 stars."}]}), _spec()
    )
    assert nosrc.conforms is None


# ── A3: ground() integration through the FLOOR direction ─────────────────────────────────

def _flag(code):
    return {
        "flag": code,
        "category": "fidelity",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
        "owner_roles": ["reviewer"],
        "tier": "TIER_1",
        "gradeable": True,
    }


_ONT = {
    "ontology_version": "value_grounding_test_v1",
    "domain": "generic",
    "flags": [_flag("SOURCE_CONTRADICTION")],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "SOURCE_CONTRADICTION",
            "question": "Is every value the artifact states present in the source?",
            "contract_type": "value_grounding",
            "version": "value-grounding/test-1",
            "params": {
                "inject_flag_code": "SOURCE_CONTRADICTION",
                "inject_severity": "HIGH",
                "artifact_kind": "generated_response",
            },
        }
    ],
    "severity_map": _SEV,
}


def _council_pass():
    return {
        "verdict": "PASS",
        "findings": [],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": "PASS"}]},
    }


def test_ground_flips_a_record_contradiction_the_judges_missed():
    art = "Rated 4.5 stars with 312 reviews."
    g = ground(_council_pass(), _record_case(art), ontology=from_dict(_ONT))
    assert g.verdict == "BLOCK" and g.verdict_no_floor == "PASS"
    fb = g.floor_blocks[0]
    assert fb["injected_finding"]["code"] == "SOURCE_CONTRADICTION"
    assert fb["result"].evidence["missing"] == ["4.5"]
    assert g.coverage["floor_backstopped"] is True


def test_ground_records_a_pass_on_a_clean_record():
    art = "Rated 4 stars with 312 reviews."
    g = ground(_council_pass(), _record_case(art), ontology=from_dict(_ONT))
    assert g.verdict == "PASS"
    assert g.floor_blocks == [] and len(g.floor_passes) == 1
    assert g.coverage["floor_backstopped"] is True


def test_ground_surfaces_a_prose_lead_without_flipping():
    art = "Here is a summary in 84 words: the budget passed."
    g = ground(_council_pass(), _prose_case(art), ontology=from_dict(_ONT))
    assert g.verdict == "PASS"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is None
    assert g.floor_blocks[0]["result"].evidence["missing"] == ["84"]
    assert g.floor_passes == []
    assert g.coverage["floor_backstopped"] is False


# ── A4: the neutral _core pack binds it (manifest-only) ─────────────────────────────────

def test_core_pack_declares_the_grounding_contracts_all_in_process():
    ont = load_ontology(REPO_ROOT / "packs/_core/ontology.json")
    by_type = {}
    for c in ont.contracts:
        by_type.setdefault(c.contract_type, set()).add(c.flag_code)
    assert by_type["value_grounding"] == {"SOURCE_CONTRADICTION"}
    assert by_type["source_grounding"] >= {
        "UNSUPPORTED_ASSERTION",
        "SOURCE_CONTRADICTION",
        "FABRICATED_CLAIM",
    }
    # the neutral default still makes NO external call: every contract is in_process
    assert all(_contract_transport(c.contract_type) == "in_process" for c in ont.contracts)
    vg = next(c for c in ont.contracts if c.contract_type == "value_grounding")
    assert vg.params["inject_flag_code"] == "SOURCE_CONTRADICTION"
    assert vg.params["inject_severity"] == "HIGH"


@pytest.mark.parametrize("source_kind", ["record", "prose"])
def test_source_kind_is_read_off_the_case(source_kind):
    art = "Rated 4.5 stars."
    case = {"source_kind": source_kind, "transcript": _RECORD, "artifacts": [{"content": art}]}
    r = ValueGroundingTool().verify(_claim(art, case), _spec())
    assert r.conforms is (False if source_kind == "record" else None)
