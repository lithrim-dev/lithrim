"""FLOOR-STORY-1 — the served case_outcome honors the grounding floor (the ONE sanctioned
"milder than the votes" mechanism), while the cc2aa33 anti-milder-drift guarantee is preserved.

THE GAP (live run 9d89cfab, case cv_mts_002_clean_subsumption_alzheimers, 2026-07-04):
``_council_view`` RE-DERIVES ``case_outcome`` from the raw PRE-floor votes (cc2aa33's
anti-stale rule) with no floor awareness — all 5 judges voted BLOCK, the grounding floor
suppressed all 3 findings (grounded verdict PASS), yet the served outcome stayed FLAGGED,
so the report banner titled "Flagged" over a "Passed" grade.

THE RULE: the post-floor grounded verdict is the authoritative FINAL reading; the pre-floor
council verdict is provenance. The floor exception applies ONLY when the record's grounded
block shows real suppressions that made the verdict milder — a stale stored outcome milder
than the votes with NO floor involvement must still escalate (cc2aa33 preserved, pinned here).

Hermetic / $0 / offline: pure ``_council_view`` calls over synthesized records.
"""

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


def _block_vote(role: str) -> dict:
    return {"judge_role": role, "vote": "BLOCK", "confidence": 0.9, "variance": 0.0}


_FIVE_BLOCKS = [_block_vote(f"reviewer_{i}") for i in range(5)]


def _floor_cleared_record() -> dict:
    """The live 9d89cfab shape: 5 BLOCK votes; the floor suppressed all 3 findings → PASS."""
    return {
        "result": {"semantic": {"judge_votes": list(_FIVE_BLOCKS)}},
        "grounded": {
            "verdict": "PASS",
            "original_verdict": "BLOCK",
            "suppressed": [{"code": "FABRICATED_CLAIM"}] * 3,
        },
    }


def test_floor_exception_grounded_pass_wins_over_pre_floor_votes():
    view = bff._council_view(_floor_cleared_record())
    # the post-floor grounded verdict is the FINAL reading — never a contradicting FLAGGED
    assert view["case_outcome"] == "CLEAR", view
    # the pre-floor council reading survives as PROVENANCE (the flip story's first act)
    assert view["council_outcome"] == "FLAGGED", view
    # and the flip is quantified for the UI story
    assert view["floor_cleared"] == 3, view


def test_cc2aa33_preserved_stale_milder_stored_outcome_still_escalates():
    """NO floor involvement: a stale stored outcome milder than the votes must escalate."""
    record = {
        "result": {
            "semantic": {"judge_votes": [_block_vote("reviewer_a")]},
            "case_outcome": "CLEAR",  # stale stored value, milder than the BLOCK vote
        }
    }
    view = bff._council_view(record)
    assert view["case_outcome"] == "FLAGGED", view
    assert view["floor_cleared"] == 0, view


def test_suppression_without_a_verdict_flip_keeps_the_vote_outcome():
    """The floor suppressed something but the verdict stayed BLOCK — no exception fires."""
    record = {
        "result": {"semantic": {"judge_votes": list(_FIVE_BLOCKS)}},
        "grounded": {
            "verdict": "BLOCK",
            "original_verdict": "BLOCK",
            "suppressed": [{"code": "FABRICATED_CLAIM"}],
        },
    }
    view = bff._council_view(record)
    assert view["case_outcome"] == "FLAGGED", view
    assert view["floor_cleared"] == 0, view


def test_grounded_block_absent_behaves_exactly_as_today():
    """A legacy/hydrated record with no grounded block: the vote re-derivation stands."""
    record = {"result": {"semantic": {"judge_votes": list(_FIVE_BLOCKS)}}}
    view = bff._council_view(record)
    assert view["case_outcome"] == "FLAGGED", view
    assert view["floor_cleared"] == 0, view


def test_floor_cleared_to_warn_maps_to_needs_review_not_clear():
    """A partial clear (BLOCK → WARN) reads NEEDS_REVIEW — never over-claims a CLEAR."""
    record = {
        "result": {"semantic": {"judge_votes": list(_FIVE_BLOCKS)}},
        "grounded": {
            "verdict": "WARN",
            "original_verdict": "BLOCK",
            "suppressed": [{"code": "FABRICATED_CLAIM"}] * 2,
        },
    }
    view = bff._council_view(record)
    assert view["case_outcome"] == "NEEDS_REVIEW", view
    assert view["floor_cleared"] == 2, view
