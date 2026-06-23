"""Gap #4 — extraction targets the AGENT's evaluation criteria, not a fixed envelope.

The invariant + envelope become criteria-aware: the required extraction fields are DERIVED
from the active agent's ``verification_contracts`` (the ``*_path`` params the floors ground
against), so an ingested case carries ``patient_profile.*`` and the floor finally has an
oracle. Generic — driven by the ontology, not by any source format. RED before the change.
"""
from __future__ import annotations

from lithrim_bench.verification.jute_extractor import (
    build_extractor_generator,
    required_case_fields,
    score_extraction,
)


class _Contract:
    def __init__(self, params):
        self.params = params


class _StubOntology:
    def __init__(self, contracts):
        self.contracts = tuple(contracts)


class _StubClient:
    """A ``:3031`` stand-in: returns a canned array as the test-template output (no network)."""

    def __init__(self, array):
        self._array = array

    def test_template(self, template, sample_input):
        return {"compiled": True, "output": self._array}


def test_required_fields_derived_from_contracts():
    onto = _StubOntology(
        [
            _Contract({"oracle_path": "patient_profile.conditions", "match": "snomed_core"}),
            _Contract({"record_path": "patient_profile.active_medications", "dose_regex": "x"}),
            _Contract({"source_path": "transcript"}),  # single-segment → excluded (covered by §4.1)
        ]
    )
    fields = set(required_case_fields(onto))
    assert "patient_profile.conditions" in fields
    assert "patient_profile.active_medications" in fields
    assert "transcript" not in fields  # flat input already covered by response/context


def _record(**extra):
    base = {"case_id": "c1", "response": "the SOAP note", "context": "the transcript"}
    base.update(extra)
    return base


def test_invariant_rejects_when_criteria_field_missing():
    # satisfies §4.1 but lacks the criteria-required patient_profile.conditions → rejected.
    client = _StubClient([_record()])
    score = score_extraction(
        client, "tmpl", {"x": 1}, expected_count=1,
        required_fields=("patient_profile.conditions",),
    )
    assert score["accepted"] is False
    assert "patient_profile.conditions" in score["null_keys"]


def test_invariant_accepts_and_envelope_carries_criteria_field():
    rec = _record(patient_profile={"conditions": ["Type 2 diabetes mellitus"]})
    client = _StubClient([rec])
    score = score_extraction(
        client, "tmpl", {"x": 1}, expected_count=1,
        required_fields=("patient_profile.conditions",),
    )
    assert score["accepted"] is True
    case = score["cases"][0]
    assert case["patient_profile"]["conditions"] == ["Type 2 diabetes mellitus"]


def test_backward_compatible_no_required_fields():
    # default (no criteria) behaves exactly as the §4.1 invariant: a valid §4.1 record accepts.
    client = _StubClient([_record()])
    score = score_extraction(client, "tmpl", {"x": 1}, expected_count=1)
    assert score["accepted"] is True
    assert score["cases"][0]["case_id"] == "c1"


class _StubPredictor:
    """An injectable DSPy predictor that returns a fixed transform — no LM."""

    def __init__(self, yaml: str):
        self._yaml = yaml

    def __call__(self, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(jute_transform=self._yaml)


def _run_generation(array, required_fields):
    gen = build_extractor_generator(
        _StubClient(array),
        "dsl-excerpt",
        {"a": 1},
        expected_count=1,
        required_fields=required_fields,
        predictor=_StubPredictor("yaml: x"),
    )
    return gen.forward(extraction_rules="extract", sample_input={"a": 1})


def test_generation_gate_rejects_criteria_missing():
    # the generation loop won't converge on a §4.1-valid-but-criteria-blind transform.
    pred = _run_generation([_record()], ("patient_profile.conditions",))
    assert pred.accepted is False


def test_generation_gate_accepts_and_carries_criteria():
    rec = _record(patient_profile={"conditions": ["Type 2 diabetes mellitus"]})
    pred = _run_generation([rec], ("patient_profile.conditions",))
    assert pred.accepted is True
    assert pred.cases[0]["patient_profile"]["conditions"] == ["Type 2 diabetes mellitus"]


def test_single_segment_criteria_field_included():
    # stated_refusals/noted_refusals are TOP-LEVEL fields the concept_preservation floor needs —
    # NOT covered by the §4.1 envelope. The earlier ".-only" filter wrongly dropped them.
    onto = _StubOntology(
        [_Contract({"stated_path": "stated_refusals", "noted_path": "noted_refusals"})]
    )
    fields = set(required_case_fields(onto))
    assert "stated_refusals" in fields
    assert "noted_refusals" in fields


def test_empty_collection_criteria_field_is_present_not_missing():
    # an empty list is a VALID extraction (noted_refusals=[] IS the dissent-erasure the floor
    # grades) — present, not a mis-join. Only a null/absent key counts as missing.
    rec = _record(stated_refusals=["tetanus vaccine refusal"], noted_refusals=[])
    client = _StubClient([rec])
    score = score_extraction(
        client, "tmpl", {"x": 1}, expected_count=1,
        required_fields=("noted_refusals", "stated_refusals"),
    )
    assert score["accepted"] is True
