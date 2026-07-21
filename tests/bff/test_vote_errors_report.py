"""VOTE-ERRORS (BFF half) — the council.votes / run-audit projections carry each vote's
``errors`` so a failed judge call is visible on the report surface, not silently rendered
as a considered vote. Empty list when the vote carried none (back-compat with older blobs)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

import app as bff  # noqa: E402


def _record(errors):
    vote = {"judge_role": "risk_judge", "vote": "WARN", "confidence": None,
            "model": "azure/gpt-4.1", "reason": ""}
    if errors is not None:
        vote["errors"] = errors
    return {"result": {"semantic": {"judge_votes": [vote]}}}


def test_council_view_carries_vote_errors():
    view = bff._council_view(_record(["RuntimeError: boom"]))
    assert view["votes"][0]["errors"] == ["RuntimeError: boom"]


def test_council_view_defaults_errors_empty_on_legacy_votes():
    view = bff._council_view(_record(None))
    assert view["votes"][0]["errors"] == []


def test_run_audit_report_carries_vote_errors():
    doc = {
        "stage_results": {"semantic": {"judge_votes": [
            {"judge_role": "risk_judge", "vote": "WARN", "confidence": None,
             "model": "azure/gpt-4.1", "reason": "", "findings": [],
             "errors": ["RuntimeError: boom"]},
        ]}},
        "verdict": "needs_review",
    }
    rep = bff._run_audit_report(doc, "run-1")
    assert rep["judges"][0]["errors"] == ["RuntimeError: boom"]
