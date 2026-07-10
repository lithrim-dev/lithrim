"""SIGNATURE-1 read surfaces: `grade_signature` + `cost_tokens` project on the run list row
and the run audit report (plus the self-describing `grade_config` on the report).

Why: cost_tokens was captured in the blob (LAYER0-READ-1) but projected NOWHERE — a DSPy
cache-served "in_process" grade (tokens=0) was indistinguishable from a paid one on every
read surface (the cache-masquerade trap); and without the signature on the read path a user
cannot assert "same config" across two runs. Additive fields; legacy blobs project None.

$0/offline — pure projection functions over dict blobs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_BLOB = {
    "pipeline_run_id": "r-1",
    "case_id": "c1",
    "agent_id": "ag",
    "verdict": "BLOCK",
    "grade_path": "in_process",
    "grade_signature": "sig-abc",
    "cost_tokens": {"prompt": 100, "completion": 40, "total": 140},
    "grade_config": {"criteria": {"risk_judge": "the criterion"}, "models": {}},
    "stage_results": {"semantic": {"judge_votes": []}},
}


def test_run_summary_projects_signature_and_cost():
    row = bff._run_summary(_BLOB)
    assert row["grade_signature"] == "sig-abc"
    assert row["cost_tokens"] == {"prompt": 100, "completion": 40, "total": 140}


def test_run_summary_legacy_blob_projects_none_not_fabricated():
    row = bff._run_summary({"pipeline_run_id": "r-old", "verdict": "WARN"})
    assert row["grade_signature"] is None
    assert row["cost_tokens"] is None


def test_run_audit_report_carries_signature_cost_and_grade_config():
    rep = bff._run_audit_report(_BLOB, "r-1")
    assert rep["grade_signature"] == "sig-abc"
    assert rep["cost_tokens"]["total"] == 140
    assert rep["grade_config"]["criteria"]["risk_judge"] == "the criterion"
