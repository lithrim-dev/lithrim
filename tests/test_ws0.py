"""WS-0 offline acceptance: one case end-to-end against the captured baseline.

No network, no Synthea CSV, no live council call. Everything runs against the
vendored fixtures in tests/fixtures/ws0/ (the captured /v1/pipeline/evaluate
baseline + the single driver-cited case row), so the suite is self-contained on a
fresh clone — out/ is gitignored, so tests must not read from it. The --live grade
path exists in lithrim_bench.harness.grade but is deliberately NOT exercised here.

Covers driver §5 A1–A4.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.correction import build_correction, emit
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.persist import load, persist
from lithrim_bench.harness.report import calibration, composite

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
BASELINE = FIXTURES / f"baseline.{CASE_ID}.json"
CASE = FIXTURES / f"case.{CASE_ID}.jsonl"


@pytest.fixture
def baseline() -> dict:
    return json.loads(BASELINE.read_text())


@pytest.fixture
def case() -> dict:
    return json.loads(CASE.read_text().splitlines()[0])


def test_fixtures_are_self_contained():
    """A4 — the suite reads only vendored fixtures, never gitignored out/."""
    assert BASELINE.exists() and CASE.exists()


def test_med_fp_suppressed_history_retained(baseline, case):
    """A2 — MED FP disproved+suppressed; FABRICATED_HISTORY retained; verdict stays reject."""
    grounded = ground(baseline, case)

    suppressed_codes = {s["finding"]["code"] for s in grounded.suppressed}
    assert suppressed_codes == {"MEDICATION_NOT_IN_TRANSCRIPT"}

    sup = grounded.suppressed[0]
    assert sup["verdict"].disproved is True
    assert sup["verdict"].matched_token == "zidovudine"
    assert "zidovudine" in (sup["verdict"].evidence or "").lower()

    active_codes = {f.get("code") for f in grounded.active}
    assert "FABRICATED_HISTORY" in active_codes
    assert "MEDICATION_NOT_IN_TRANSCRIPT" not in active_codes

    assert grounded.verdict == "BLOCK"
    assert composite(grounded)["verdict"] == "reject"


def test_null_code_findings_skiplogged(baseline, case):
    """S-BS-8 — null-code findings are bucketed as ungrounded, never silently dropped."""
    grounded = ground(baseline, case)
    assert len(grounded.ungrounded) == 4
    assert all(f.get("code") is None for f in grounded.ungrounded)
    # surfaced (in ungrounded) AND retained (in active) — not dropped
    for f in grounded.ungrounded:
        assert f in grounded.active


def test_correction_record_emitted(baseline, case, tmp_path):
    """A3 — one structured, versioned correction record with rollout + tool result."""
    grounded = ground(baseline, case)
    out = tmp_path / "corrections.ndjson"

    records = []
    for entry in grounded.suppressed:
        rec = build_correction(
            suppressed_entry=entry,
            result=baseline,
            composite_before=grounded.original_verdict,
            composite_after=grounded.verdict,
        )
        emit(rec, path=out)
        records.append(rec)

    assert len(records) == 1
    assert sum(1 for _ in out.open()) == 1

    rec = records[0]
    assert rec["schema_version"] == "ws0-correction/1"
    assert rec["original_label"] == "MEDICATION_NOT_IN_TRANSCRIPT"
    assert rec["corrected_label"] is None
    assert rec["composite_before"] == "BLOCK"
    assert rec["composite_after"] == "BLOCK"
    assert rec["ontology_version"] == "ws0-hardcoded/0"
    assert rec["contract_version"] == "med-presence-check/v1"
    assert rec["tool_result"]["disproved"] is True

    # rollout = the contributing judges, each carrying its own confidence (raw-events shape)
    roles = {r["judge_role"] for r in rec["rollout"]}
    assert roles == {"policy_judge", "faithfulness_judge"}
    assert all("confidence" in r and "model" in r for r in rec["rollout"])


def test_persist_idempotent_doc_shim(baseline, case, tmp_path):
    """S-BS-4 — fs blob + SQLite doc-shim, idempotent on case_id (re-run = one row)."""
    record = {"case_id": CASE_ID, "verdict": "reject", "n": 1}
    paths = persist(CASE_ID, record, out_dir=tmp_path)
    persist(CASE_ID, {**record, "n": 2}, out_dir=tmp_path)  # re-run overwrites

    import sqlite3

    rows = sqlite3.connect(paths["sqlite"]).execute("SELECT COUNT(*) FROM records").fetchone()[0]
    assert rows == 1
    assert load(CASE_ID, db_path=paths["sqlite"])["n"] == 2
    assert Path(paths["blob"]).exists()


def test_calibration_is_report_only(baseline):
    """Calibration returns a diagnostic (bins + ECE + honest small-N caveat); never raises/gates."""
    cal = calibration(baseline, expected_block=True)
    assert cal["n_with_confidence"] == 2
    assert cal["n_null_confidence"] == 1
    assert cal["ece"] == pytest.approx(0.5)
    assert cal["caveat"] is not None and "small N" in cal["caveat"]


def test_run_ws0_end_to_end_replay_exit_zero(tmp_path):
    """A1 — the full pipeline runs end-to-end via scripts/run_ws0.py (replay), exit 0."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_ws0.py"),
            "--source",
            str(CASE),
            "--baseline",
            str(BASELINE),
            "--out-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "verdict: reject" in proc.stdout
    assert "MEDICATION_NOT_IN_TRANSCRIPT -> SUPPRESSED" in proc.stdout
    assert "ECE:" in proc.stdout
