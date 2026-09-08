"""LEAD-AUTHORITY-1: a code the ledger has NOT promoted may raise a lead (WARN -> escalate) but never
block on its own. ``severity_map.lead_codes`` is optional; absent, rescoring is byte-identical."""

import json
from pathlib import Path

from lithrim_bench.harness.grounding import rescore_without_floor
from lithrim_bench.harness.ontology import SeverityMap, load_ontology

CORE = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}
F = lambda code, sev: {"code": code, "severity": sev}  # noqa: E731


def _sm(lead_codes=()):
    return SeverityMap(
        weights=CORE["weights"],
        block_at_or_above=0.5,
        warn_above=0.0,
        lead_codes=frozenset(lead_codes),
    )


def test_default_is_byte_identical_to_the_shipped_rescore():
    base = SeverityMap(weights=CORE["weights"], block_at_or_above=0.5, warn_above=0.0)
    for active in (
        [],
        [F("X", "HIGH")],
        [F("X", "MEDIUM")],
        [F("X", "LOW")],
        [F("X", "LOW"), F("Y", "HIGH")],
    ):
        assert _sm().rescore(active) == base.rescore(active)


def test_a_lead_code_never_blocks_on_its_own():
    assert _sm({"FABRICATED_CLAIM"}).rescore([F("FABRICATED_CLAIM", "HIGH")]) == "WARN"
    assert (
        _sm({"FABRICATED_CLAIM"}).rescore(
            [F("FABRICATED_CLAIM", "HIGH"), F("FABRICATED_CLAIM", "MEDIUM")]
        )
        == "WARN"
    )


def test_a_lead_is_never_silently_passed():
    assert _sm({"X"}).rescore([F("X", "LOW")]) == "WARN"
    assert _sm({"X"}).rescore([F("X", None)]) == "WARN"


def test_a_promoted_code_still_blocks_beside_leads():
    assert (
        _sm({"FABRICATED_CLAIM"}).rescore(
            [F("FABRICATED_CLAIM", "HIGH"), F("SOURCE_CONTRADICTION", "HIGH")]
        )
        == "BLOCK"
    )
    assert _sm({"FABRICATED_CLAIM"}).rescore([F("SOURCE_CONTRADICTION", "MEDIUM")]) == "BLOCK"


def test_rescore_without_floor_honours_lead_codes():
    active = [
        F("FABRICATED_CLAIM", "HIGH"),
        {"code": "SOURCE_CONTRADICTION", "severity": "HIGH", "_floor": True},
    ]
    assert rescore_without_floor(active, [], _sm({"FABRICATED_CLAIM"})) == "WARN"
    assert rescore_without_floor(active, [], _sm()) == "BLOCK"


def test_parser_reads_lead_codes_and_defaults_to_empty(tmp_path):
    base = json.loads(Path("packs/_core/ontology.json").read_text())
    assert load_ontology("packs/_core/ontology.json").severity_map.lead_codes == frozenset()
    variant = dict(base)
    variant["severity_map"] = {
        **base["severity_map"],
        "lead_codes": ["FABRICATED_CLAIM", "UNSUPPORTED_ASSERTION"],
    }
    p = tmp_path / "variant.json"
    p.write_text(json.dumps(variant))
    assert load_ontology(p).severity_map.lead_codes == frozenset(
        {"FABRICATED_CLAIM", "UNSUPPORTED_ASSERTION"}
    )
