"""UAP-3b-2 (the deferred UAP-3b A6) — GroundingChecks as first-class, config-authored
INDEPENDENT entities, audited at the post-consensus locus.

All $0 / default deps: the GroundingCheck audit is a pure projection over the
``grounded`` partitions ``ground()`` already produced (the vendored WS-0 baseline +
the S-BS-7 MED suppression), so no council, no dspy/openai, no network. The headline:
a declared GroundingCheck's execution is audited as its OWN entity
(``actor.type='grounding_check'``, action ``suppress``/``floor_block``/``run`` —
distinct from the gate's ``withstand``/``flip``), while ``ground()``/``composite()``
stay byte-additively-identical for the floor-less ``clinical_v1`` ontology.
"""
from __future__ import annotations

import json

import pytest

from lithrim_bench.harness.config import agent_from_dict, agent_to_dict
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.grounding_check import audit_grounding_checks
from lithrim_bench.harness.report import composite
from tests._house_fixture import pack_ws0_dir

CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
_MED = "MEDICATION_NOT_IN_TRANSCRIPT"


@pytest.fixture
def baseline() -> dict:
    fixtures = pack_ws0_dir()
    return json.loads((fixtures / f"baseline.{CASE_ID}.json").read_text())


@pytest.fixture
def case() -> dict:
    fixtures = pack_ws0_dir()
    return json.loads((fixtures / f"case.{CASE_ID}.jsonl").read_text().splitlines()[0])


def test_declared_groundingcheck_audited_as_independent_entity(baseline, case):
    """A6 — a declared GroundingCheck whose suppress contract disproved a finding is
    audited as its own entity: actor.type=grounding_check, action=suppress, the §2B
    validator-execution ``why`` (contract / conforms / deterministic_result /
    grounded_fact)."""
    grounded = ground(baseline, case)
    assert {s["finding"]["code"] for s in grounded.suppressed} == {_MED}  # the S-BS-7 floor

    records = audit_grounding_checks([_MED], grounded, run_id="run-1", case_id=CASE_ID)
    assert len(records) == 1
    rec = records[0]
    assert rec.actor.type == "grounding_check"
    assert rec.actor.id == _MED
    assert rec.action == "suppress"  # grounding-appropriate, NOT the gate's withstand/flip
    assert rec.target.type == "finding" and rec.target.id == _MED
    assert rec.run_id == "run-1" and rec.case_id == CASE_ID
    assert rec.why["conforms"] is False
    assert rec.why["deterministic_result"] == "disproved"
    assert "zidovudine" in (rec.why["grounded_fact"] or "").lower()
    assert rec.why["matched_token"] == "zidovudine"


def test_undeclared_profile_emits_nothing(baseline, case):
    """The post-consensus path is a no-op without a declaration — every committed agent
    (grounding_checks == ()) emits ZERO records, so existing runs are byte-unchanged."""
    grounded = ground(baseline, case)
    assert audit_grounding_checks((), grounded, run_id="r", case_id="c") == []


def test_only_declared_checks_are_audited(baseline, case):
    """A GroundingCheck that is NOT declared is not audited even if its contract ran —
    declaration is the entity boundary (a different code declared → the MED suppress is
    not promoted)."""
    grounded = ground(baseline, case)
    records = audit_grounding_checks(["WRONG_DOSAGE"], grounded, run_id="r", case_id="c")
    assert records == []


def test_ground_and_composite_additively_identical(baseline, case):
    """A6 — the entity audit is a READ-ONLY projection: ``ground()``'s suppress/floor
    partitions + the composite verdict are byte-unchanged across the audit call (it
    never mutates ``grounded`` and ``ground()`` never sees the declaration)."""
    grounded = ground(baseline, case)
    before = (
        [s["finding"]["code"] for s in grounded.suppressed],
        [f.get("code") for f in grounded.active],
        list(grounded.floor_blocks),
        grounded.verdict,
        composite(grounded)["verdict"],
    )
    audit_grounding_checks([_MED, "WRONG_DOSAGE"], grounded, run_id="r", case_id="c")
    after = (
        [s["finding"]["code"] for s in grounded.suppressed],
        [f.get("code") for f in grounded.active],
        list(grounded.floor_blocks),
        grounded.verdict,
        composite(grounded)["verdict"],
    )
    assert before == after
    # the floor-less clinical_v1 default: no floor partition regardless.
    assert grounded.floor_blocks == []


def test_eval_profile_grounding_checks_roundtrips():
    """The additive ``EvalProfile.grounding_checks`` field round-trips, and an agent
    that does NOT declare it serializes byte-identically (no stray key) — back-compat
    for the committed seeds + their audit before/after diffs."""
    base = {
        "name": "gc_agent",
        "eval_profile": {
            "judges": ["risk_judge"],
            "council_config": {},
            "ontology_ref": "clinical/1",
            "ontology_path": "packs/healthcare/ontology.json",
            "tools": ["presence_check"],
            "kb_bindings": {},
            "severity_map_ref": "ontology:clinical/1",
        },
        "dataset": {"case_id": "c", "source": "s.jsonl", "baseline": "b.json", "mode": "replay"},
    }
    # undeclared → no grounding_checks key emitted (byte-identical serialization).
    a0 = agent_from_dict(base)
    assert a0.eval_profile.grounding_checks == ()
    assert "grounding_checks" not in agent_to_dict(a0)["eval_profile"]

    # declared → round-trips as a tuple and re-serializes.
    declared = json.loads(json.dumps(base))
    declared["eval_profile"]["grounding_checks"] = [_MED]
    a1 = agent_from_dict(declared)
    assert a1.eval_profile.grounding_checks == (_MED,)
    assert agent_to_dict(a1)["eval_profile"]["grounding_checks"] == [_MED]
