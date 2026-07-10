"""WS-4a offline acceptance: the flywheel slice (corpus + eval-pack + calibration check).

Replay-only, no network, byte-deterministic. The flywheel-projection slice (A1/A2 —
the suppress-record corpus row, the corpus round-trip, and the eval-pack round-trip)
runs against a SELF-CONTAINED, in-repo ``support_ticket_qa`` fixture pack
(``packs/support_ticket_qa/`` — its real ``taxonomy_snapshot.json`` flag codes), so the
plumbing exercises with NO external ``healthcare`` Pro pack: the case, its captured
baseline, and a ``presence_check``-carrying ontology are all synthesized inline below,
exactly the "author the fixture inline" pattern the floor-projection case already uses.
The floor-projection case is synthesized offline via a fake replay http client exactly as
tests/verification/test_grounding_floor.py does (no live :3031). Covers driver
§5 A1–A4 (A4 = full-suite-green + ruff, checked at the suite level).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lithrim_bench.harness import corpus, evalpack
from lithrim_bench.harness.config import Agent, Dataset, EvalProfile
from lithrim_bench.harness.correction import build_correction, build_floor_correction
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.harness.report import calibration_check
from tests._house_fixture import HOUSE_CASE_ID, house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
WS4A_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws4a"
PINNED_VALIDATOR = REPO_ROOT / "validators" / "fhir_us_core_patient_validator.generated.jute"

# ── the self-contained support_ticket_qa flywheel fixture (no external healthcare pack) ──
# The case, its captured baseline, and the ontology are authored inline so the A1/A2
# projection plumbing runs on the in-repo `support_ticket_qa` pack (real taxonomy codes:
# FABRICATED_POLICY stands; UNSUPPORTED_COMMITMENT is the suppressible finding a
# presence_check clears because the committed term IS present in the source thread).
CASE_ID = "support_ticket_qa_unsupported_commitment"

_STQ_ONTOLOGY = {
    "ontology_version": "support_ticket_qa/1",
    "domain": "support_ticket_qa",
    "flags": [
        {
            "flag": "FABRICATED_POLICY",
            "category": "accuracy",
            "definition": "",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": ["policy_judge"],
            "tier": "TIER_1",
            "gradeable": True,
        },
        {
            "flag": "UNSUPPORTED_COMMITMENT",
            "category": "accuracy",
            "definition": "",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": [],
            "tier": "TIER_1",
            "gradeable": True,
        },
    ],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "UNSUPPORTED_COMMITMENT",
            "contract_type": "presence_check",
            "version": "commitment-presence-check/v1",
            "question": "Is the committed term actually present in the source thread (the transcript)?",
            "params": {
                "med_source": "source_facts.referenced_terms",
                "dosage_regex": r"\b\d+(?:\.\d+)?\s*(?:%|x)\b",
                "token_min_len": 4,
                "noise_tokens": ["the", "and", "that"],
            },
        }
    ],
    "severity_map": {
        "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
        "block_at_or_above": 0.5,
        "warn_above": 0.0,
    },
}

_STQ_CASE = {
    "case_id": CASE_ID,
    "pack": "support_ticket_qa",
    "ground_truth_basis": "constructed",
    "transcript": (
        "Customer: Will my subscription include priority support once I upgrade?\n"
        "Agent: Yes, the premium plan includes priority support and a dedicated account manager."
    ),
    "source_facts": {"referenced_terms": ["priority support"]},
    "artifacts": [
        {
            "type": "support_reply",
            "content": (
                "Thanks for reaching out! Your premium plan includes priority support. "
                "We also guarantee a full refund at any time for any reason, and every "
                "customer receives lifetime free hardware replacements."
            ),
        }
    ],
    "expected_compliance_verdict": "reject",
    "expected_artifact_verdict": "BLOCK",
    "expected_safety_flags": ["FABRICATED_POLICY"],
    "clean_negative": False,
    "multi_defect": False,
    "severity": "high",
    "injection_recipes": [
        {
            "defect_type": "inject_fabricated_policy",
            "safety_flag": "FABRICATED_POLICY",
            "mutated_projection": "artifact_text",
            "mutated_field_or_span": "support_reply.content",
            "pre_value": "(no such policy)",
            "post_value": "full refund at any time; lifetime free hardware replacements",
        }
    ],
    "expected_owner_map": {"FABRICATED_POLICY": ["policy_judge"]},
    "pinned": {
        "generator_version": "lithrim-bench/0.1.0",
        "pack": "support_ticket_qa",
        "taxonomy_snapshot": "packs/support_ticket_qa/taxonomy_snapshot.json",
    },
}

# The captured /v1/pipeline/evaluate baseline: the council BLOCKED, raising both the
# suppressible UNSUPPORTED_COMMITMENT and the standing FABRICATED_POLICY. The graded
# result + the top-level findings live under provenance.stage_results (the shape
# grade_replay -> provenance_to_result rehydrates), so replay grounds identically.
_STQ_FINDINGS = [
    {
        "type": "semantic",
        "severity": "HIGH",
        "code": "UNSUPPORTED_COMMITMENT",
        "detail": "UNSUPPORTED_COMMITMENT (judges=2)",
        "field": None,
        "check_name": None,
        "chunk_id": None,
        "start_ms": None,
        "end_ms": None,
        "speaker": None,
    },
    {
        "type": "semantic",
        "severity": "HIGH",
        "code": "FABRICATED_POLICY",
        "detail": "FABRICATED_POLICY (judges=2)",
        "field": None,
        "check_name": None,
        "chunk_id": None,
        "start_ms": None,
        "end_ms": None,
        "speaker": None,
    },
]

_STQ_SEMANTIC = {
    "status": "BLOCK",
    "findings": ["UNSUPPORTED_COMMITMENT", "FABRICATED_POLICY"],
    "evidence": [
        {
            "violation_code": "UNSUPPORTED_COMMITMENT",
            "judge": "risk_judge",
            "spans": [{"quote": "the premium plan includes priority support", "turn_ids": []}],
        }
    ],
    "judge_votes": [
        {
            "judge_role": "risk_judge",
            "vote": "BLOCK",
            "findings": ["UNSUPPORTED_COMMITMENT", "FABRICATED_POLICY"],
            "confidence": 1.0,
            "model": "x",
        },
        {
            "judge_role": "policy_judge",
            "vote": "BLOCK",
            "findings": ["UNSUPPORTED_COMMITMENT", "FABRICATED_POLICY"],
            "confidence": 1.0,
            "model": "x",
        },
        {
            "judge_role": "faithfulness_judge",
            "vote": "PASS",
            "findings": [],
            "confidence": 1.0,
            "model": "x",
        },
    ],
    "metadata": {},
}

_STQ_BASELINE = {
    "verdict": "BLOCK",
    "gate_decision": "escalate",
    "findings": _STQ_FINDINGS,
    "duration_ms": 0,
    "structural": {
        "status": "PASS",
        "findings": [],
        "evidence": [],
        "judge_votes": None,
        "metadata": {},
    },
    "semantic": _STQ_SEMANTIC,
    "artifact": {
        "status": "PASS",
        "findings": [],
        "evidence": [],
        "judge_votes": None,
        "metadata": {},
    },
    "transform": None,
    "provenance": {
        "pipeline_run_id": "b1c2d3e4-f5a6-4788-9a0b-1c2d3e4f5a6b",
        "org_id": "0000000000000000000000aa",
        "timestamp": "2026-06-01T00:00:00.000000Z",
        "request_hash": "0" * 64,
        "stages_executed": ["structural", "semantic", "artifact", "verdict"],
        "stage_results": {
            "structural": {
                "status": "PASS",
                "findings": [],
                "evidence": [],
                "judge_votes": None,
                "metadata": {},
            },
            "semantic": _STQ_SEMANTIC,
        },
        "verdict": "BLOCK",
        "findings": _STQ_FINDINGS,
    },
    "regenerate_hints": [],
}

# scripts/ on path so the test can drive the canonical run_eval.run core (the run_ws0 precedent).
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402


def _stq_ontology():
    return from_dict(_STQ_ONTOLOGY)


def _write_stq_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Materialize the inline support_ticket_qa case / baseline / ontology to files
    (run_eval.run + grade_replay read paths); returns (case, baseline, ontology)."""
    case_path = tmp_path / f"case.{CASE_ID}.jsonl"
    case_path.write_text(json.dumps(_STQ_CASE))
    baseline_path = tmp_path / f"baseline.{CASE_ID}.json"
    baseline_path.write_text(json.dumps(_STQ_BASELINE))
    ontology_path = tmp_path / "ontology.json"
    ontology_path.write_text(json.dumps(_STQ_ONTOLOGY))
    return case_path, baseline_path, ontology_path


def _agent(tmp_path: Path) -> Agent:
    case_path, baseline_path, ontology_path = _write_stq_fixture(tmp_path)
    return Agent(
        name="ws4a_test",
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="support_ticket_qa/1",
            ontology_path=str(ontology_path),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:support_ticket_qa/1",
        ),
        dataset=Dataset(
            case_id=CASE_ID,
            source=str(case_path),
            baseline=str(baseline_path),
        ),
    )


def _suppress_record() -> dict:
    """A ws0-correction/1 record from the self-contained support_ticket_qa flywheel:
    the presence_check disproves UNSUPPORTED_COMMITMENT (the committed term is present)."""
    ont = _stq_ontology()
    grounded = ground(_STQ_BASELINE, _STQ_CASE, ontology=ont)
    return build_correction(
        suppressed_entry=grounded.suppressed[0],
        result=_STQ_BASELINE,
        composite_before=grounded.original_verdict,
        composite_after=grounded.verdict,
        ontology=ont,
    )


# ── floor synthesis (offline, the test_grounding_floor pattern) ───────────────


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
    """Replays /mappings/test-template with a failing compiled check (no live :3031)."""

    def post(self, url, json=None):
        assert url.endswith("/mappings/test-template")
        checks = [
            {"name": "has-identifier", "field": "identifier", "status": "fail", "message": "x"}
        ]
        return _Resp({"compiled": True, "output": {"request": {"checks": checks}}, "error": None})

    def close(self):
        pass


_COUNCIL_PASS = {
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
_DEFECT_CASE = {"artifacts": [{"type": "fhir_patient", "content": '{"resourceType":"Patient"}'}]}


def _floor_ontology():
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
                        "pinned_template": PINNED_VALIDATOR.read_text(),
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


def _floor_record() -> dict:
    """A real ws3-floor-correction/1 record from a synthesized structural-floor flip."""
    ont = _floor_ontology()
    g = ground(_COUNCIL_PASS, _DEFECT_CASE, ontology=ont, http_client=_ReplayHttp())
    return build_floor_correction(
        floor_block=g.floor_blocks[0],
        result=_COUNCIL_PASS,
        composite_before="PASS",
        composite_after=g.verdict,
        ontology=ont,
    )


# ── A1: the corpus projects BOTH directions, byte-deterministically ───────────

_ROW_KEYS = {
    "schema_version",
    "case_id",
    "action",
    "flag_code",
    "verdict_before",
    "verdict_after",
    "contract",
    "contract_version",
    "ontology_version",
    "owner_roles",
    "rollout_ref",
}


def test_project_suppress_record():
    """A1 — a suppress record projects to a full-provenance corpus-row/1."""
    rec = _suppress_record()
    row = corpus.project(rec, case_id=CASE_ID)
    assert set(row) == _ROW_KEYS
    assert row["schema_version"] == "corpus-row/1"
    assert row["case_id"] == CASE_ID
    assert row["action"] == "suppress"
    assert row["flag_code"] == "UNSUPPORTED_COMMITMENT"
    assert row["verdict_before"] == "BLOCK" and row["verdict_after"] == "BLOCK"
    assert row["contract"] == "PresenceCheck"  # the executor class name, not the flag
    assert row["contract_version"] == "commitment-presence-check/v1"
    assert row["ontology_version"] == "support_ticket_qa/1"
    assert row["owner_roles"] == []
    assert row["rollout_ref"] == corpus.rollout_ref(rec)
    assert corpus.project(rec, case_id=CASE_ID) == row  # deterministic re-projection


def test_project_floor_record():
    """A1 — the floor branch projects too (else corpus-row/1's floor path is untested prose)."""
    rec = _floor_record()
    row = corpus.project(rec, case_id="fhir_defect_case")
    assert set(row) == _ROW_KEYS
    assert row["action"] == "floor"
    assert row["flag_code"] == "FHIR_STRUCTURAL_VIOLATION"
    assert row["contract"] == "jute_gen"  # floor identity is contract_type
    assert row["verdict_before"] == "PASS" and row["verdict_after"] == "BLOCK"
    assert row["owner_roles"] == ["structural_validator"]
    assert row["rollout_ref"] == corpus.rollout_ref(rec)


def test_corpus_append_read_roundtrip_and_deterministic(tmp_path):
    """A1 — the WS-0 flywheel appends a corpus-row/1; re-read round-trips; byte-deterministic."""
    rec = _suppress_record()
    rows = corpus.build_corpus([rec], case_id=CASE_ID)
    assert len(rows) == 1 and rows[0]["action"] == "suppress"

    path = tmp_path / "corpus.ndjson"
    corpus.append_row(rows[0], path=path)
    corpus.append_row(rows[0], path=path)  # append-only lake
    assert list(corpus.read_corpus(path)) == [rows[0], rows[0]]

    serialized = json.dumps(rows[0], sort_keys=True)
    assert serialized == json.dumps(corpus.project(rec, case_id=CASE_ID), sort_keys=True)


def test_committed_example_corpus_fixture_shape():
    """A1 — the committed example fixture is a valid corpus-row/1 (rollout_ref NOT asserted resolvable).
    Re-minted over the neutral _core house fixture (S-BS-137): a presence_check suppress row."""
    rows = list(corpus.read_corpus(WS4A_FIXTURES / "corpus.example.ndjson"))
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == _ROW_KEYS
    assert row["schema_version"] == "corpus-row/1"
    assert row["action"] == "suppress"
    assert row["case_id"] == HOUSE_CASE_ID
    assert row["flag_code"] == "UNSUPPORTED_ASSERTION"
    assert row["contract"] == "PresenceCheck"


# ── A2: the eval-pack round-trips ─────────────────────────────────────────────


def test_evalpack_build_load_roundtrip(tmp_path):
    """A2 — an eval-pack built over the support_ticket_qa case round-trips (build -> dump -> load)."""
    pack = evalpack.build_pack("ws4a_thin", [_agent(tmp_path)], out_dir=tmp_path / "out")
    assert pack["schema_version"] == "evalpack/1"
    assert pack["pack_id"] == "ws4a_thin"
    assert [c["case_id"] for c in pack["cases"]] == [CASE_ID]
    assert pack["cases"][0]["expected"] == {
        "compliance_verdict": "reject",
        "safety_flags": ["FABRICATED_POLICY"],
    }

    outcome = pack["outcomes"][0]
    assert outcome["verdict"] == "reject"  # grounded outcome
    assert outcome["corrections"][0]["action"] == "suppress"  # corpus-row/1 provenance carried

    path = evalpack.dump_pack(pack, tmp_path / "pack.json")
    assert evalpack.load_pack(path) == pack  # identity round-trip


# ── A3: the minimal calibration check is report-only ──────────────────────────


def test_calibration_check_reports_match_and_ece(tmp_path):
    """A3 — calibration_check yields verdict-match + ECE; status PASS (report-only, not a gate).
    Domain-agnostic plumbing: runs on the neutral _core house baseline (same N=1 vote shape)."""
    record = run_eval.run(house_agent(name="ws4a_house"), out_dir=tmp_path / "out")
    summary = calibration_check([record])
    assert summary["verdict_match_rate"] == 1.0
    assert summary["status"] == "PASS"
    assert summary["n_cases"] == 1 and summary["n_matched"] == 1
    assert summary["ece"] == 0.5  # house baseline: 2 non-null confidences @ 1.0, expected_block
    assert summary["n_with_confidence"] == 2
    assert summary["caveat"] is not None and "small N" in summary["caveat"]


def test_calibration_check_warns_on_verdict_mismatch():
    """A3 — status is driven by verdict-match ONLY (advisory WARN); ECE never moves it."""
    rec = {
        "composite": {"verdict": "approve"},
        "calibration": {"ece": 0.0, "n_with_confidence": 8},  # perfect ECE...
        "provenance": {"expected_compliance_verdict": "reject"},
    }
    summary = calibration_check([rec])
    assert summary["status"] == "WARN"  # ...still WARN, because the verdict missed
    assert summary["verdict_match_rate"] == 0.0
