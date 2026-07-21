"""READ-ATTRIB-1: the pre/post verdict delta must be attributable.

The scorecard's "verdict accuracy: reviewers alone X% -> with the floor Y%" band compared
two verdicts produced by two DIFFERENT rules: ``original_verdict`` (the council's tier rule)
and ``verdict`` (``severity_map.rescore``). The floor only ever ADDS to ``active`` or MOVES a
finding to ``suppressed``, so when it does neither, the two rules can still disagree and the
whole gap was silently billed to the floor.

``verdict_no_floor`` is the honest counterfactual: rescore, the SAME rule as ``verdict``, over
the finding set the grade would have had if the floor had never run (drop what the floor
injected, restore what a contract suppressed). ``verdict`` minus ``verdict_no_floor`` is then a
pure floor delta with nothing else mixed in.

Offline: no network, no model calls, no pack on disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

from lithrim_bench.harness.grounding import ground, rescore_without_floor
from lithrim_bench.harness.ontology import from_dict

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_SEVERITY_MAP = {  # the live clinverdict map: a lone MEDIUM is BELOW the block threshold
    "weights": {"HIGH": 1.0, "MEDIUM": 0.4, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        return None

    @property
    def headers(self):
        return {}


class _FailingFloorHttp:
    """Replays a compiled :3031 apply whose check FAILS, so the floor injects. Offline."""

    def post(self, url, json=None):
        checks = [{"name": "has-identifier", "field": "identifier", "status": "fail",
                   "message": "Missing identifier"}]
        return _Resp({"compiled": True, "output": {"request": {"checks": checks}}, "error": None})

    def close(self):
        pass


def _ontology(*, contracts=(), extra_flags=()):
    return from_dict(
        {
            "ontology_version": "read_attrib_v1",
            "domain": "test",
            "flags": [
                {
                    "flag": code,
                    "category": "accuracy",
                    "definition": "",
                    "when_to_use": "",
                    "when_NOT_to_use": "",
                    "owner_roles": ["reviewer"],
                    "tier": "tier2",
                    "gradeable": True,
                }
                for code in ("MISSING_CONTEXT", "HALLUCINATED_DETAIL", *extra_flags)
            ],
            "questions": [],
            "verification_contracts": list(contracts),
            "severity_map": _SEVERITY_MAP,
        }
    )


def _council(verdict, findings):
    return {"verdict": verdict, "findings": findings, "semantic": {"judge_votes": []}}


def test_idle_floor_gets_zero_credit_for_a_rule_only_gap():
    """THE regression: two reviewers each raise a DIFFERENT uncorroborated MEDIUM code.

    The council calls that a BLOCK; rescore calls it a WARN (0.4 < 0.5). The floor is not even
    declared. Pre-vs-post therefore differs while the floor moved nothing, and the band used to
    attribute the entire drop to the floor.
    """
    g = ground(
        _council(
            "BLOCK",
            [
                {"code": "MISSING_CONTEXT", "severity": "MEDIUM", "detail": "(judges=1)"},
                {"code": "HALLUCINATED_DETAIL", "severity": "MEDIUM", "detail": "(judges=1)"},
            ],
        ),
        {"artifacts": []},
        ontology=_ontology(),
    )

    assert g.original_verdict == "BLOCK"  # the council's tier rule
    assert g.verdict == "WARN"  # rescore: max MEDIUM 0.4 < block_at 0.5
    assert g.floor_blocks == [] and g.suppressed == []
    # the floor did nothing, so the counterfactual must equal the final verdict exactly
    assert g.verdict_no_floor == g.verdict == "WARN"


def test_a_real_floor_flip_separates_verdict_from_the_counterfactual():
    """End-to-end through ``ground()`` with a floor that actually fires.

    The direct-arithmetic tests below cannot catch ``verdict_no_floor = verdict`` in ground()
    itself, because every other ground() case here leaves the floor idle (where the two are
    EQUAL by definition). This is the one that pins them apart on the real path.
    """
    ont = _ontology(
        contracts=[
            {
                "flag_code": "FLOOR_VIOLATION",
                "question": "Does the artifact conform to the pinned contract?",
                "contract_type": "jute_gen",
                "version": "v1",
                "params": {
                    "service": "http://localhost:3031",
                    "artifact_kind": "fhir_patient",
                    "pinned_template": "resourceType: Patient",
                    "inject_flag_code": "FLOOR_VIOLATION",
                    "inject_severity": "HIGH",
                },
            }
        ],
        extra_flags=("FLOOR_VIOLATION",),
    )
    g = ground(
        _council("PASS", []),
        {"artifacts": [{"type": "fhir_patient", "content": '{"resourceType":"Patient"}'}]},
        ontology=ont,
        http_client=_FailingFloorHttp(),
    )

    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is not None
    assert g.verdict == "BLOCK"  # the floor injected a HIGH finding
    assert g.verdict_no_floor == "PASS"  # ...and without it there was nothing to score
    assert g.verdict_no_floor != g.verdict


def test_floor_injection_is_credited_to_the_floor():
    """The inverse direction: the counterfactual must NOT absorb a real floor flip."""
    active = [
        {"code": "MISSING_CONTEXT", "severity": "MEDIUM"},
        {"code": "FLOOR_CODE", "severity": "HIGH", "_floor": True},
    ]
    ont = _ontology()

    assert ont.severity_map.rescore(active) == "BLOCK"
    assert rescore_without_floor(active, [], ont.severity_map) == "WARN"


def test_suppressed_findings_are_restored_in_the_counterfactual():
    """A contract clearing a finding is floor-plane work too: undo it in the counterfactual."""
    ont = _ontology()
    suppressed = [{"finding": {"code": "HALLUCINATED_DETAIL", "severity": "HIGH"}}]

    assert ont.severity_map.rescore([]) == "PASS"
    assert rescore_without_floor([], suppressed, ont.severity_map) == "BLOCK"


def test_the_counterfactual_reaches_the_persisted_blob():
    """The whole feature is inert if ``_grounded_block`` drops the key: the BFF reads it off
    the record, so a missing key silently reports "no counterfactual" on every fresh grade."""
    from run_eval import _grounded_block

    g = ground(
        _council("BLOCK", [{"code": "MISSING_CONTEXT", "severity": "MEDIUM"}]),
        {"artifacts": []},
        ontology=_ontology(),
    )
    blob = _grounded_block(g)

    assert "verdict_no_floor" in blob
    assert blob["verdict_no_floor"] == g.verdict_no_floor == "WARN"


def test_counterfactual_is_read_only_over_the_finalized_buckets():
    """It must never perturb the grade: active/suppressed/verdict stay byte-identical."""
    active = [
        {"code": "MISSING_CONTEXT", "severity": "MEDIUM"},
        {"code": "FLOOR_CODE", "severity": "HIGH", "_floor": True},
    ]
    suppressed = [{"finding": {"code": "HALLUCINATED_DETAIL", "severity": "HIGH"}}]
    before = ([dict(f) for f in active], [dict(s) for s in suppressed])

    rescore_without_floor(active, suppressed, _ontology().severity_map)

    assert (active, suppressed) == before
