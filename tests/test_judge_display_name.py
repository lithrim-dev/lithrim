"""JUDGE-LABEL-1: an authorable display name for a reviewer seat.

The UI derives a reviewer's label from its role id (``copy.js:roleLabel``), so
``openbio_reviewer`` renders "Openbio reviewer" — a label that names a MODEL. Once a workspace
can bind any model to any seat (WS-JUDGE-BIND), that label is actively wrong: in an Opus-bound
workspace the seat called "Openbio reviewer" runs Opus.

Renaming the role ids would be the obvious fix and is the wrong one. Ids are load-bearing:
``tier1_owners`` and the per-role lens authority are keyed on them
(``compliance_council.py:1720``, ``pack.py:pack_lenses``), and every record already graded
carries the old id in its votes. So the ID stays and the LABEL becomes authorable.

Pinned here:
  * round-trip + back-compat — a row written before this cycle has no display_name and must
    load as "" (the UI then falls back to the derived label).
  * the label reaches the UI on the SERVED VOTE, not just the config: every reviewer surface
    (scorecard, reviewer cards, audit view, verdict card) renders votes, so attaching it at
    ``_council_view`` is what makes one write reach all of them — including for records graded
    before the name existed, since the lookup happens at serve time.
  * the id is NEVER replaced by the label in anything the engine reads back.

Offline: no network, no model calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import judges as J

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

ROLE = "openbio_reviewer"
LABEL = "Coverage reviewer"


def _record_with_votes(*roles):
    return {
        "result": {
            "semantic": {
                "judge_votes": [
                    {"judge_role": r, "vote": "BLOCK", "model": "anthropic/claude-opus-4-8"}
                    for r in roles
                ]
            }
        }
    }


# ── the config carries it ──────────────────────────────────────────────────────


def test_judge_config_roundtrips_the_display_name():
    jc = J.JudgeConfig(
        role=ROLE, model="", assigned_flags=(), validator_refs=(), display_name=LABEL
    )
    assert J.judge_to_dict(jc)["display_name"] == LABEL
    assert J.judge_from_dict(J.judge_to_dict(jc)).display_name == LABEL


def test_a_legacy_row_without_a_display_name_loads_as_blank():
    """Every row written before this cycle lacks the key; the UI then derives the label."""
    jc = J.judge_from_dict({"role": ROLE, "model": "m", "assigned_flags": []})
    assert jc.display_name == ""


def test_the_display_name_never_replaces_the_role_id():
    """The id is what tier1_owners and lens authority key on — a label must never stand in."""
    jc = J.JudgeConfig(
        role=ROLE, model="", assigned_flags=(), validator_refs=(), display_name=LABEL
    )
    blob = J.judge_to_dict(jc)
    assert blob["role"] == ROLE
    assert J.judge_from_dict(blob).role == ROLE


# ── it reaches the UI on the served vote ───────────────────────────────────────


def test_council_view_attaches_the_display_name_to_each_vote():
    """THE property: one authored name reaches every reviewer surface, because they all render
    votes rather than the judge config."""
    view = bff._council_view(
        _record_with_votes(ROLE, "risk_judge"), display_names={ROLE: LABEL}
    )
    by_role = {v["judge_role"]: v for v in view["votes"]}

    assert by_role[ROLE]["display_name"] == LABEL
    assert by_role[ROLE]["judge_role"] == ROLE, "the id must still ride the vote"


def test_a_role_with_no_authored_name_carries_an_empty_label():
    """Empty, not absent and not guessed — the shell owns the fallback derivation."""
    view = bff._council_view(
        _record_with_votes(ROLE, "risk_judge"), display_names={ROLE: LABEL}
    )
    by_role = {v["judge_role"]: v for v in view["votes"]}

    assert by_role["risk_judge"]["display_name"] == ""


def test_council_view_without_any_names_is_byte_identical_to_before():
    """The default path (no map passed) must not change what any existing caller receives."""
    view = bff._council_view(_record_with_votes(ROLE))

    assert view["votes"][0]["display_name"] == ""
    assert view["votes"][0]["judge_role"] == ROLE


def test_records_graded_before_the_name_existed_still_get_labelled():
    """The lookup is at SERVE time against the current config, so old blobs pick the name up."""
    old_blob = _record_with_votes(ROLE)  # nothing in it knows about display names
    view = bff._council_view(old_blob, display_names={ROLE: LABEL})

    assert view["votes"][0]["display_name"] == LABEL


# ── the config surface exposes it ──────────────────────────────────────────────


class _StubOntology:
    def flag(self, code):
        return None

    def questions_for(self, role):
        return []


def test_judge_summary_surfaces_the_display_name(monkeypatch):
    monkeypatch.setattr(bff, "_active_lens_by_role", lambda: {ROLE: set()})
    jc = J.JudgeConfig(
        role=ROLE, model="", assigned_flags=(), validator_refs=(), display_name=LABEL
    )
    summary = bff._judge_summary(ROLE, jc, _StubOntology(), bindings={})

    assert summary["display_name"] == LABEL
    assert summary["role"] == ROLE
