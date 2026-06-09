"""WS-4a offline acceptance: the flywheel slice (corpus + eval-pack + calibration check).

Replay-only, no network, byte-deterministic. Everything runs against the vendored
WS-0 fixtures + the committed clinical ontology; the floor-projection case is
synthesized offline via a fake replay http client exactly as
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

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
WS4A_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws4a"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
BASELINE = FIXTURES / f"baseline.{CASE_ID}.json"
CASE = FIXTURES / f"case.{CASE_ID}.jsonl"
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"
PINNED_VALIDATOR = REPO_ROOT / "validators" / "fhir_us_core_patient_validator.generated.jute"

# scripts/ on path so the test can drive the canonical run_eval.run core (the run_ws0 precedent).
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402


def _agent() -> Agent:
    return Agent(
        name="ws4a_test",
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(case_id=CASE_ID, source=str(CASE), baseline=str(BASELINE)),
    )


def _suppress_record() -> dict:
    """A real ws0-correction/1 record from the WS-0 replay flywheel."""
    baseline = json.loads(BASELINE.read_text())
    case = json.loads(CASE.read_text().splitlines()[0])
    grounded = ground(baseline, case)
    return build_correction(
        suppressed_entry=grounded.suppressed[0],
        result=baseline,
        composite_before=grounded.original_verdict,
        composite_after=grounded.verdict,
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
    assert row["flag_code"] == "MEDICATION_NOT_IN_TRANSCRIPT"
    assert row["verdict_before"] == "BLOCK" and row["verdict_after"] == "BLOCK"
    assert row["contract"] == "PresenceCheck"  # the executor class name, not the flag
    assert row["contract_version"] == "med-presence-check/v1"
    assert row["ontology_version"] == "clinical/1"
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
    """A1 — the committed example fixture is a valid corpus-row/1 (rollout_ref NOT asserted resolvable)."""
    rows = list(corpus.read_corpus(WS4A_FIXTURES / "corpus.example.ndjson"))
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == _ROW_KEYS
    assert row["schema_version"] == "corpus-row/1"
    assert row["action"] == "suppress"
    assert row["flag_code"] == "MEDICATION_NOT_IN_TRANSCRIPT"


# ── A2: the eval-pack round-trips ─────────────────────────────────────────────


def test_evalpack_build_load_roundtrip(tmp_path):
    """A2 — an eval-pack built over the WS-0 case round-trips (build -> dump -> load identical)."""
    pack = evalpack.build_pack("ws4a_thin", [_agent()], out_dir=tmp_path / "out")
    assert pack["schema_version"] == "evalpack/1"
    assert pack["pack_id"] == "ws4a_thin"
    assert [c["case_id"] for c in pack["cases"]] == [CASE_ID]
    assert pack["cases"][0]["expected"] == {
        "compliance_verdict": "reject",
        "safety_flags": ["FABRICATED_HISTORY"],
    }

    outcome = pack["outcomes"][0]
    assert outcome["verdict"] == "reject"  # grounded outcome
    assert outcome["corrections"][0]["action"] == "suppress"  # corpus-row/1 provenance carried

    path = evalpack.dump_pack(pack, tmp_path / "pack.json")
    assert evalpack.load_pack(path) == pack  # identity round-trip


# ── A3: the minimal calibration check is report-only ──────────────────────────


def test_calibration_check_reports_match_and_ece(tmp_path):
    """A3 — calibration_check yields verdict-match + ECE; status PASS (report-only, not a gate)."""
    record = run_eval.run(_agent(), out_dir=tmp_path / "out")
    summary = calibration_check([record])
    assert summary["verdict_match_rate"] == 1.0
    assert summary["status"] == "PASS"
    assert summary["n_cases"] == 1 and summary["n_matched"] == 1
    assert summary["ece"] == 0.5  # WS-0 baseline: 2 non-null confidences @ 1.0, expected_block
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
