"""JUDGE-ERROR-1: a judge call that failed is not a cache replay.

Observed 2026-09-09: 12 of 450 RAGTruth cases came back with cost_tokens total 0 because
Azure's content filter refused the prompt; the scorecard called them cache_replays and the
write-up called the run disqualified. The judge cache was off (CACHE-TRAP-2); the model was
asked and refused. Such a case is a judge error, reported under its own count."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402


def _record(*, total_tokens, errors):
    return {
        "result": {
            "provenance": {"cost_tokens": {"prompt": 0, "completion": 0, "total": total_tokens}}
        },
        "council": {
            "votes": [{"judge_role": "ragtruth_detector", "vote": "WARN", "errors": errors}]
        },
    }


def test_a_refused_judge_call_is_a_judge_error_not_a_cache_replay():
    rec = _record(total_tokens=0, errors=["LMInvalidRequestError: ContentPolicyViolationError"])
    assert bff._cache_replay_flag(rec, spends=True) is False
    assert bff._judge_error_count(rec) == 1


def test_zero_tokens_with_a_clean_vote_is_still_a_cache_replay():
    rec = _record(total_tokens=0, errors=[])
    assert bff._cache_replay_flag(rec, spends=True) is True
    assert bff._judge_error_count(rec) == 0


def test_a_zero_dollar_replay_is_never_accused():
    assert bff._cache_replay_flag(_record(total_tokens=0, errors=[]), spends=False) is False
