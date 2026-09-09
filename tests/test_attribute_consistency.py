"""ATTR-CONSISTENCY-1: a record-source floor over the record's attribute fields.

Source validation of the RAGTruth v3 clears (2026-09-09) found 7 of 10 judge misses were
assertions the record decides: "validated parking" vs BusinessParking.validated=false,
"do not offer outdoor seating" vs OutdoorSeating=null, "open every day" vs hours missing
Monday. The paper's own data-to-text rule applies: null is unknown (a lead), never a negation."""

from __future__ import annotations

import json

from lithrim_bench.harness.grounding import floor_executors
from lithrim_bench.verification import (
    STRUCTURAL_CONFORMANCE,
    TOOL_ATTRIBUTE_CONSISTENCY,
    AttributeConsistencyTool,
    Claim,
    VerificationSpec,
)

RECORD = {
    "name": "Tinker's Burgers",
    "hours": {"Monday": "11:0-17:0", "Tuesday": "11:0-17:0"},
    "attributes": {
        "BusinessParking": {
            "garage": False,
            "street": True,
            "validated": False,
            "lot": True,
            "valet": False,
        },
        "RestaurantsReservations": True,
        "OutdoorSeating": None,
        "WiFi": "free",
        "RestaurantsTakeOut": True,
        "Music": None,
        "Ambience": {"romantic": False, "casual": True},
    },
}


def _spec(reference=None):
    return VerificationSpec(
        tool=TOOL_ATTRIBUTE_CONSISTENCY,
        applies_to_flags=("SOURCE_CONTRADICTION",),
        locus="",
        reference=reference or {},
        version="attribute-consistency/test",
    )


def _verify(text, record=RECORD, source_kind="record", reference=None):
    case = {
        "source_kind": source_kind,
        "transcript": json.dumps(record) if source_kind == "record" else record,
        "artifacts": [{"type": "generated_response", "content": text}],
    }
    claim = Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code="SOURCE_CONTRADICTION",
        subject=text,
        locus="",
        source=case,
    )
    return AttributeConsistencyTool().verify(claim, _spec(reference))


def test_contradicting_boolean_is_a_violation_with_the_field_named():
    r = _verify("Guests enjoy validated parking and free Wi-Fi.")
    assert r.conforms is False
    assert r.evidence["missing"] == ["attributes.BusinessParking.validated=True vs record False"]
    assert r.evidence["present"] == ["attributes.WiFi=True"]


def test_null_field_is_unknown_never_a_negation():
    r = _verify("They do not offer outdoor seating, but they take reservations.")
    assert r.conforms is True, r.evidence  # reservations checked and true; seating is a lead
    assert r.evidence["unknown"] == ["attributes.OutdoorSeating=False (record null)"]
    only_null = _verify("There is live music every night.")
    assert only_null.conforms is None and "null fields are unknown" in only_null.evidence["reason"]


def test_negated_assertion_agrees_with_a_false_field():
    r = _verify("There is no valet, and the atmosphere is casual rather than romantic.")
    assert r.conforms is True
    assert (
        set(r.evidence["present"])
        == {
            "attributes.BusinessParking.valet=False",
            "attributes.Ambience.casual=True",
        }
        or "attributes.Ambience.romantic=False" in r.evidence["present"]
    )


def test_every_day_against_a_two_day_hours_record_is_a_violation():
    r = _verify("They are open every day for lunch.")
    assert r.conforms is False and r.evidence["contradictions"][0]["field"] == "hours"
    full = dict(
        RECORD,
        hours={
            d: "9:0-17:0"
            for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        },
    )
    assert _verify("Open daily.", record=full).conforms is True
    no_hours = dict(RECORD, hours=None)
    assert _verify("Open every day.", record=no_hours).conforms is None


def test_prose_sources_and_no_assertions_are_inconclusive():
    assert (
        _verify(
            "A charming spot with outdoor seating.",
            record="Some article text.",
            source_kind="prose",
        ).conforms
        is None
    )
    assert _verify("Located downtown.").conforms is None


def test_registry_and_contract_declare_the_floor():
    ex = floor_executors("_core")["attribute_consistency"]
    assert ex.tool_factory(None).name == "attribute_consistency"
    assert ex.reference_builder({"inject_flag_code": "X"}) == {}
    assert ex.reference_builder({"hours_field": "opening_hours"}) == {
        "hours_field": "opening_hours"
    }
    from pathlib import Path

    ont = json.loads(
        (Path(__file__).resolve().parents[1] / "packs/_core/ontology.json").read_text()
    )
    decl = [
        c for c in ont["verification_contracts"] if c["contract_type"] == "attribute_consistency"
    ]
    assert len(decl) == 1 and decl[0]["version"] == "attribute-consistency/1"
    assert decl[0]["flag_code"] == "SOURCE_CONTRADICTION"


def test_negation_shapes_seen_on_ragtruth_records():
    """Real sentences from the 450 that a naive scope got wrong (2026-09-09 preview)."""
    rec = dict(
        RECORD,
        attributes=dict(
            RECORD["attributes"],
            RestaurantsReservations=False,
            RestaurantsTakeOut=True,
            WiFi="no",
            Ambience={"casual": True, "hipster": False, "upscale": False, "trendy": False},
        ),
    )

    def claims(text):
        r = _verify(text, record=rec)
        return {
            c["field"].split(".")[-1]: c["claimed"] for c in r.evidence["contradictions"]
        }, r.conforms

    assert claims("They also offer takeout and do not accept reservations.") == ({}, True)
    assert claims("Reservations are not accepted and WiFi is not available.") == ({}, True)
    assert claims("The ambiance is casual, not hipster or upscale.") == ({}, True)
    assert claims("Street and garage parking are not provided.") == ({}, True)
    assert claims("There is no garage, street, or valet parking.")[1] is not False
    assert claims(
        "It's not suitable for trendy or upscale dining as it has a casual ambiance."
    ) == ({}, True)
    # and a real contradiction still fires
    assert claims("They accept reservations.") == ({"RestaurantsReservations": True}, False)
