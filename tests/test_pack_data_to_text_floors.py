"""packs/data_to_text/floors.py: the ``null_negation`` SUPPRESS contract, registered by the pack with
zero engine edits. A NULL_AS_NEGATION finding is DISPROVED when the response negates no attribute the
record holds as null; it STANDS, with the span as evidence, when it does."""

import json

from lithrim_bench.harness import grounding as G
from lithrim_bench.harness.ontology import VerificationContractDecl, load_ontology

PACK = "data_to_text"
PARAMS = {
    "record_path": "transcript",
    "attributes_path": "attributes",
    "attribute_terms": {
        "WiFi": ["wifi", "wi-fi", "internet"],
        "OutdoorSeating": ["outdoor seating", "patio"],
    },
}
RECORD = json.dumps({"name": "Cafe", "attributes": {"WiFi": None, "OutdoorSeating": "True"}})


def _decl(params=PARAMS):
    return VerificationContractDecl(
        flag_code="NULL_AS_NEGATION",
        question="q",
        contract_type="null_negation",
        params=params,
        version="null-negation/1",
    )


def _case(text, record=RECORD):
    return {
        "case_id": "x",
        "source_kind": "record",
        "transcript": record,
        "artifacts": [{"content": text}],
    }


def test_pack_registers_null_negation_as_a_suppress_contract_without_engine_edits():
    assert "null_negation" in G.suppress_executors(PACK)
    assert "null_negation" not in G.suppress_executors("_core")


def test_null_negations_finds_only_negated_null_attributes():
    from packs.data_to_text.floors import null_negations

    assert [
        m["attribute"]
        for m in null_negations(RECORD, "There is no WiFi, but the patio is lovely.", PARAMS)
    ] == ["WiFi"]
    assert null_negations(RECORD, "Free WiFi and a lovely patio.", PARAMS) == []
    assert (
        null_negations(RECORD, "No outdoor seating here.", PARAMS) == []
    )  # OutdoorSeating is "True", not null
    assert [m["attribute"] for m in null_negations(RECORD, "Wi-Fi is not available.", PARAMS)] == [
        "WiFi"
    ]
    assert (
        null_negations(json.dumps({"name": "Cafe"}), "no wifi", PARAMS) == []
    )  # no attributes block: nothing to say


def test_check_disproves_an_ungrounded_finding_and_keeps_a_grounded_one():
    ex = G.suppress_executors(PACK)["null_negation"](_decl())
    finding = {"code": "NULL_AS_NEGATION", "severity": "HIGH", "evidence": "says no wifi"}
    v = ex.check(finding, _case("Free WiFi and a lovely patio."))
    assert v.disproved is True and "negat" in v.reason.lower()
    v2 = ex.check(finding, _case("There is no WiFi."))
    assert v2.disproved is False and "WiFi" in (v2.evidence or "")


def test_check_never_clears_on_a_broken_reference():
    ex = G.suppress_executors(PACK)["null_negation"](_decl())
    v = ex.check({"code": "NULL_AS_NEGATION"}, _case("no wifi", record="not json at all"))
    assert v.disproved is False and "inconclusive" in v.reason.lower()


def test_ground_suppresses_the_over_raised_code_end_to_end(monkeypatch):
    onto = load_ontology("packs/data_to_text/ontology.json")
    assert any(
        c.contract_type == "null_negation" and c.flag_code == "NULL_AS_NEGATION"
        for c in onto.contracts
    )
    result = {
        "verdict": "BLOCK",
        "findings": [{"code": "NULL_AS_NEGATION", "severity": "HIGH", "evidence": "no wifi"}],
        "semantic": {"judge_votes": []},
    }
    monkeypatch.setenv(
        "LITHRIM_BENCH_PACK", PACK
    )  # ground() resolves pack executors via the active pack
    if True:
        g = G.ground(result, _case("Free WiFi and a lovely patio."), ontology=onto)
        assert [s["finding"]["code"] for s in g.suppressed] == [
            "NULL_AS_NEGATION"
        ] and g.verdict == "PASS"
        g2 = G.ground(result, _case("There is no WiFi."), ontology=onto)
        assert not g2.suppressed and g2.verdict == "BLOCK"


def test_nested_null_members_are_checked_by_dotted_key():
    from packs.data_to_text.floors import null_negations

    record = json.dumps(
        {
            "attributes": {
                "Ambience": {"romantic": None, "casual": True},
                "Music": {"live": None, "dj": False},
            }
        }
    )
    params = {
        **PARAMS,
        "attribute_terms": {
            **PARAMS["attribute_terms"],
            "Ambience.romantic": ["romantic"],
            "Music.live": ["live music"],
        },
    }
    assert [
        m["attribute"]
        for m in null_negations(record, "Not a romantic spot, and there is no live music.", params)
    ] == ["Ambience.romantic", "Music.live"]
    assert null_negations(record, "Not a casual spot.", params) == []  # casual is True, not null
    assert (
        null_negations(record, "No DJ.", {**params, "attribute_terms": {"Music.dj": ["dj"]}}) == []
    )  # dj is False, not null
