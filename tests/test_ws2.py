"""WS-2 offline acceptance: snapshot-authoritative partition (D0/S-BS-10) +
domain-agnostic config injection on the harness side (D3).

No network, no Synthea CSV, no live call. The backend contract change (D1/D2)
is tested in lithrim-backend; here we prove the harness side:
  - A1: the ontology partitions gradeable (19) vs reference (4); the seed lint
        FAILS on a gradeable-outside-snapshot fixture and PASSES on the committed
        seed; reference findings are skip-logged, never scored.
  - A4: grade_live's request body carries the Agent's stored council_config +
        ontology when present (and exactly the WS-0/WS-1 body when absent);
        run_eval passes the loaded Agent config through to the live grade.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import grounding
from lithrim_bench.harness.config import Agent, Dataset, EvalProfile
from lithrim_bench.harness.grade import build_request_body
from lithrim_bench.harness.ontology import load_ontology

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seed_ontology  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
BASELINE = FIXTURES / f"baseline.{CASE_ID}.json"
CASE = FIXTURES / f"case.{CASE_ID}.jsonl"
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"

# The 4 fork flags — known but out-of-snapshot (S-BS-10 reference partition).
REFERENCE_FLAGS = {
    "FABRICATED_CONSENT_SCOPE",
    "MALAFFI_CODE_PROPAGATION",
    "MISSING_DUAL_CODING",
    "WRONG_PATIENT_INFO",
}


def _load_run_eval():
    """Import scripts/run_eval.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location(
        "run_eval_undertest", REPO_ROOT / "scripts" / "run_eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _agent_over_fixtures() -> Agent:
    return Agent(
        name="ws2_test",
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


def test_replay_without_baseline_fails_clean_not_typeerror(tmp_path):
    """S-BS-108: an imported/live-only agent (dataset.baseline=None) replays with a clear
    SystemExit (-> BFF 400), NOT Path(None) -> TypeError -> 500. Non-vacuous: pre-fix the
    Path(None) call raised TypeError, so this SystemExit/match assertion fails."""
    run_eval = _load_run_eval()
    house = house_agent(name="sbs108_no_baseline")  # neutral _core — the SystemExit is domain-agnostic
    agent = Agent(
        name="sbs108_no_baseline",
        eval_profile=house.eval_profile,
        dataset=Dataset(case_id=house.dataset.case_id, source=house.dataset.source, baseline=None),
    )
    with pytest.raises(SystemExit, match="no captured baseline"):
        run_eval.run(agent, live=False, in_process=False, out_dir=tmp_path / "out")


# ── A1: S-BS-10 gradeable/reference partition + lint gate ─────────────────────


def test_ontology_partitions_gradeable_and_reference():
    """A1 — 19 gradeable (in-snapshot, tiered) vs 4 reference (out-of-snapshot)."""
    ont = load_ontology(ONTOLOGY_SEED)
    gradeable = {f.flag for f in ont.gradeable_flags()}
    reference = {f.flag for f in ont.flags if not f.gradeable}

    assert len(gradeable) == 19
    assert reference == REFERENCE_FLAGS
    # gradeable <-> tiered; reference <-> untiered
    assert all(ont.flag(c).tier for c in gradeable)
    assert all(ont.flag(c).tier is None for c in reference)
    # query helpers agree
    assert ont.is_gradeable("FABRICATED_HISTORY") is True
    assert ont.is_reference("FABRICATED_HISTORY") is False
    assert ont.is_reference("WRONG_PATIENT_INFO") is True
    assert ont.is_gradeable("WRONG_PATIENT_INFO") is False
    # an unknown code is neither gradeable nor reference
    assert ont.is_gradeable("NOT_A_REAL_CODE") is False
    assert ont.is_reference("NOT_A_REAL_CODE") is False


def test_seed_gradeable_set_matches_snapshot():
    """A1 — the committed seed is consistent: every gradeable flag is in-snapshot."""
    seed = seed_ontology.build_seed()
    snapshot_codes = seed_ontology.load_snapshot_codes()
    assert len(snapshot_codes) == 19
    # no gradeable flag falls outside the snapshot — the live lint passes
    assert seed_ontology.gradeable_flags_outside_snapshot(seed["flags"], snapshot_codes) == []


def test_lint_fails_on_gradeable_outside_snapshot():
    """A1 — the lint FAILS (non-empty offenders) when a gradeable flag is unblessed."""
    flags = [
        {"flag": "WRONG_DOSAGE", "gradeable": True},  # in-snapshot — fine
        {"flag": "INVENTED_OFFENDER", "gradeable": True},  # gradeable but unblessed
        {"flag": "WRONG_PATIENT_INFO", "gradeable": False},  # reference — exempt
    ]
    snapshot_codes = {"WRONG_DOSAGE", "MISSING_ALLERGY"}
    offenders = seed_ontology.gradeable_flags_outside_snapshot(flags, snapshot_codes)
    assert offenders == ["INVENTED_OFFENDER"]


def test_reference_finding_is_skip_logged_never_scored():
    """A1 — a lone reference (out-of-snapshot) HIGH finding does NOT drive BLOCK."""
    ont = load_ontology(ONTOLOGY_SEED)
    result = {"findings": [{"code": "WRONG_PATIENT_INFO", "severity": "HIGH"}], "verdict": "BLOCK"}
    grounded = grounding.ground(result, {"transcript": ""}, ontology=ont)

    assert [f["code"] for f in grounded.skipped_non_gradeable] == ["WRONG_PATIENT_INFO"]
    assert grounded.active == []  # reference finding removed from the scored set
    assert grounded.verdict == "PASS"  # the HIGH would have BLOCKed if it were scored


def test_gradeable_finding_still_scores():
    """A1 — a gradeable HIGH finding still drives BLOCK (reference-skip is targeted)."""
    ont = load_ontology(ONTOLOGY_SEED)
    result = {"findings": [{"code": "FABRICATED_HISTORY", "severity": "HIGH"}], "verdict": "BLOCK"}
    grounded = grounding.ground(result, {"transcript": ""}, ontology=ont)

    assert grounded.skipped_non_gradeable == []
    assert [f["code"] for f in grounded.active] == ["FABRICATED_HISTORY"]
    assert grounded.verdict == "BLOCK"


# ── A4: harness injects the Agent's stored council_config + ontology ──────────


def test_build_request_body_omits_config_when_absent():
    """A4 — no stored config => exactly the WS-0/WS-1 body (backend sees None)."""
    case = {"artifacts": [{"content": "x", "type": "fhir_document_reference"}], "transcript": "t"}
    body = build_request_body(case, org_id="org-1")
    assert "council_config" not in body
    assert "ontology" not in body
    assert body["org_id"] == "org-1" and body["eval_mode"] is True


def test_build_request_body_injects_config_when_present():
    """A4 — stored council_config + ontology are carried in the request body."""
    case = {"artifacts": [{"content": "x", "type": "fhir_document_reference"}], "transcript": "t"}
    cc = {"disposition": "compose-over-live-v2"}
    ont = {"domain": "clinical", "ontology_version": "clinical/1"}
    body = build_request_body(case, org_id="org-1", council_config=cc, ontology=ont)
    assert body["council_config"] == cc
    assert body["ontology"] == ont


def test_run_eval_passes_agent_config_to_live_grade(tmp_path, monkeypatch):
    """A4 — run_eval.run() threads the Agent's stored config into the live grade."""
    run_eval = _load_run_eval()
    captured: dict = {}

    def _fake_grade_live(case, **kwargs):
        captured.update(kwargs)
        return json.loads(BASELINE.read_text())  # baseline-shaped, keeps run() offline

    monkeypatch.setattr(run_eval, "grade_live", _fake_grade_live)

    record = run_eval.run(_agent_over_fixtures(), live=True, out_dir=tmp_path / "out")

    assert record["provenance"]["grade_path"] == "live"
    assert captured["council_config"] == {"disposition": "compose-over-live-v2"}
    assert captured["ontology"]["domain"] == "clinical"
    assert len(captured["ontology"]["flags"]) == 23
