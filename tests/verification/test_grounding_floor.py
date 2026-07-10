"""Offline tests for the WS-3 structural-FLOOR wiring in harness/grounding.

The floor is the inverse of the suppress direction: a bench-accepted structural
contract runs over the artifact and injects a BLOCK the council MISSED, flipping a
confident PASS -> BLOCK. All offline: the :3031 apply is replayed by a fake http
client (the grade_replay/grade_live mirror); the committed pinned validator is the
floor's reproducible artifact.
"""

from __future__ import annotations

from pathlib import Path

from lithrim_bench.harness.correction import build_floor_correction
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import from_dict, load_ontology
from lithrim_bench.harness.report import composite

REPO_ROOT = Path(__file__).resolve().parents[2]
PINNED_VALIDATOR = REPO_ROOT / "validators" / "fhir_us_core_patient_validator.generated.jute"
FLOOR_TYPES = {"structural_jute", "jute_gen"}

_FAIL = [
    {
        "name": "has-identifier",
        "field": "identifier",
        "status": "fail",
        "message": "Missing identifier",
    }
]
_PASS = [{"name": "has-identifier", "field": "identifier", "status": "pass", "message": "ok"}]

COUNCIL_PASS = {
    "verdict": "PASS",
    "findings": [],
    "semantic": {
        "judge_votes": [
            {
                "judge_role": "compliance_judge",
                "vote": "PASS",
                "findings": [],
                "confidence": 1.0,
                "model": "x",
            }
        ]
    },
}
DEFECT_CASE = {"artifacts": [{"type": "fhir_patient", "content": '{"resourceType":"Patient"}'}]}


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


class _ReplayHttp:
    """Replays /mappings/test-template with a chosen compiled verdict (no live :3031)."""

    def __init__(self, *, checks, compiled=True):
        self._checks = checks
        self._compiled = compiled
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        if url.endswith("/mappings/test-template"):
            output = {"request": {"checks": self._checks}} if self._compiled else None
            return _Resp(
                {
                    "compiled": self._compiled,
                    "output": output,
                    "error": None if self._compiled else "boom",
                }
            )
        raise AssertionError(url)

    def close(self):
        pass


class _BoomHttp:
    """Any HTTP call fails — proves the floor path is NOT touched when no floor is declared."""

    def post(self, *a, **k):
        raise AssertionError("floor made an HTTP call when no floor contract was declared")

    def get(self, *a, **k):
        raise AssertionError("floor made an HTTP call when no floor contract was declared")

    def close(self):
        pass


def _floor_ontology(*, pinned_template):
    return from_dict(
        {
            "ontology_version": "floor_test_v1",
            "domain": "test",
            "flags": [
                {
                    "flag": "FHIR_STRUCTURAL_VIOLATION",
                    "category": "structural",
                    "definition": "",
                    "when_to_use": "",
                    "when_NOT_to_use": "",
                    "owner_roles": ["structural_validator"],
                    "tier": "tier1",
                    "gradeable": True,
                }
            ],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "FHIR_STRUCTURAL_VIOLATION",
                    "question": "Does the artifact conform to the pinned structural contract?",
                    "contract_type": "jute_gen",
                    "version": "v1",
                    "params": {
                        "service": "http://localhost:3031",
                        "artifact_kind": "fhir_patient",
                        "pinned_template": pinned_template,
                        "inject_flag_code": "FHIR_STRUCTURAL_VIOLATION",
                        "inject_severity": "HIGH",
                    },
                }
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1},
                "block_at_or_above": 1.0,
                "warn_above": 0.0,
            },
        }
    )


def test_pinned_validator_is_clean_patient():
    # refinement #3: the floor's committed artifact is the clean US-Core Patient validator,
    # NOT the buggy-timestamp transaction validator retained only as narrative provenance.
    text = PINNED_VALIDATOR.read_text()
    assert "resourceType: Patient" in text
    assert "timestamp" not in text.lower()


def test_floor_flips_pass_to_block_and_emits_correction():
    ont = _floor_ontology(pinned_template=PINNED_VALIDATOR.read_text())
    http = _ReplayHttp(checks=_FAIL)
    g = ground(COUNCIL_PASS, DEFECT_CASE, ontology=ont, http_client=http)

    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is not None
    assert "FHIR_STRUCTURAL_VIOLATION" in [f.get("code") for f in g.active]

    comp = composite(g)
    assert comp["verdict"] == "reject" and comp["floor_block_count"] == 1
    assert comp["floor_adjustments"][0]["action"] == "floor_block"

    rec = build_floor_correction(
        floor_block=g.floor_blocks[0],
        result=COUNCIL_PASS,
        composite_before="PASS",
        composite_after=g.verdict,
        ontology=ont,
    )
    assert rec["schema_version"] == "ws3-floor-correction/1" and rec["direction"] == "floor_inject"
    assert rec["tool_result"]["conforms"] is False
    # inverse rollout: the missing judge vote is retained (the council that certified the defect)
    assert rec["rollout"] and rec["rollout"][0]["output"]["vote"] == "PASS"
    assert rec["owner_roles"] == ["structural_validator"]


def test_floor_satisfied_is_noop():
    ont = _floor_ontology(pinned_template=PINNED_VALIDATOR.read_text())
    g = ground(COUNCIL_PASS, DEFECT_CASE, ontology=ont, http_client=_ReplayHttp(checks=_PASS))
    assert g.verdict == "PASS" and g.floor_blocks == []  # conforms True -> no record, no flip


def test_floor_inconclusive_never_flips():
    ont = _floor_ontology(pinned_template=PINNED_VALIDATOR.read_text())
    # uncompiled template -> conforms None -> surfaced, never flips
    g = ground(
        COUNCIL_PASS,
        DEFECT_CASE,
        ontology=ont,
        http_client=_ReplayHttp(checks=_PASS, compiled=False),
    )
    assert g.verdict == "PASS"
    assert len(g.floor_blocks) == 1 and g.floor_blocks[0]["injected_finding"] is None
    assert composite(g)["floor_block_count"] == 0  # inconclusive is not a block


def test_backward_compat_default_ontology_has_no_floor():
    # refinement #1: the committed clinical ontology declares NO floor contract, so ground()
    # is the pre-WS-3 behaviour with floor_blocks == [] and the floor path makes no HTTP call.
    ont = load_ontology()
    assert [d for d in ont.contracts if d.contract_type in FLOOR_TYPES] == []
    g = ground(COUNCIL_PASS, DEFECT_CASE, ontology=ont, http_client=_BoomHttp())
    assert g.floor_blocks == [] and g.verdict == "PASS"
