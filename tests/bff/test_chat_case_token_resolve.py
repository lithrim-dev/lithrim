"""CHAT-CASE-TOKEN-RESOLVE — the $0 chat/tool path resolves a SHORT/PREFIX case token to a
UNIQUE full case_id BEFORE the exact-match run query.

THE REGRESSION (live-confirmed 2026-07-04, introduced by 0cd20ec RUN-TRAIL-CASE-SCOPE):
with NOTHING armed, "run a $0 replay of cv_mts_002 and show the report" makes the chat extract
the short token ``cv_mts_002`` (``_zero_dollar_case_token``) and pass it as ``case_id`` to the
case-scoped GET /v1/runs, which does EXACT match against the store. The stored id is
``cv_mts_002_clean_subsumption_alzheimers``, so exact-match on the prefix returns 0 runs, and the
chat narrates the FALSE "no runs on record for case cv_mts_002" — for a case that has runs.

curl proof (verbatim, against :18787):
    GET /v1/runs?agent=repro_agent&case_id=cv_mts_002                       → 0 runs
    GET /v1/runs?agent=repro_agent&case_id=cv_mts_002_clean_subsumption_…   → 5+ runs

THE FIX (this file pins it): a resolver in the CHAT/TOOL layer (``review_runs_handler`` — the
single choke point for BOTH the model-called and the deterministic $0 fallback paths) maps a
short/prefix token to the UNIQUE full case_id against the agent's known case ids (the same source
that backs GET /v1/cases/browser). Semantics:
  * exact known id → wins outright;
  * unique prefix of exactly ONE known id → that full id;
  * matches MULTIPLE → do NOT guess: stay UNSCOPED + narrate honestly ("matches N cases: …");
  * matches ZERO → today's honest empty (unscoped read).
  * an ARMED case (ctx.active_case, a known full id) WINS over a typed short token.

The shared exact-match GET /v1/runs query is UNTOUCHED (the replay-baseline resolver
``latest_authoritative_for`` depends on exact match). Resolution lives in the tool layer only.

Hermetic / $0 / offline. review_runs is stubbed to record the case_id it actually received; the
known-case list is stubbed. No SDK, no network, no paid surface.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

from agent.tools import (  # noqa: E402
    ToolContext,
    _resolve_case_token,
    review_runs_handler,
)

FULL = "cv_mts_002_clean_subsumption_alzheimers"
KNOWN = [
    FULL,
    "cv_mts_101_missing_allergy",
    "cv_mts_104_fabricated_history",
    "cv_mts_105_fabricated_history",
]


# ── T1 — the pure resolver (unit, non-vacuous) ────────────────────────────────


def test_exact_id_wins_outright():
    assert _resolve_case_token(FULL, KNOWN) == (FULL, None)


def test_unique_prefix_resolves_to_the_full_id():
    """The live defect token: cv_mts_002 is a unique prefix of exactly one known id."""
    assert _resolve_case_token("cv_mts_002", KNOWN) == (FULL, None)


def test_ambiguous_prefix_does_not_guess():
    """cv_mts_10 is a prefix of THREE known ids → resolve to None (unscoped) and hand back an
    honest ambiguity note listing the matches. NEVER silently pick one."""
    resolved, note = _resolve_case_token("cv_mts_10", KNOWN)
    assert resolved is None
    assert note is not None
    assert "cv_mts_101_missing_allergy" in note
    assert "cv_mts_104_fabricated_history" in note
    assert "cv_mts_105_fabricated_history" in note


def test_unknown_token_keeps_empty_behavior():
    """A token that matches nothing → the token itself, no note (today's honest-empty read:
    the exact-match query returns 0 runs, unchanged)."""
    assert _resolve_case_token("nope_xyz", KNOWN) == ("nope_xyz", None)


def test_no_token_is_a_noop():
    assert _resolve_case_token(None, KNOWN) == (None, None)
    assert _resolve_case_token("", KNOWN) == (None, None)


def test_empty_known_list_never_resolves():
    """No known ids → the token passes through unchanged (never crashes)."""
    assert _resolve_case_token("cv_mts_002", []) == ("cv_mts_002", None)


# ── the handler integration ($0, no paid surface) ─────────────────────────────


def _ctx(*, active_case=None, known=None, capture: dict):
    """A ToolContext whose review_runs records the case_id it received, so we can pin what the
    resolver threaded. known_case_ids returns the stubbed known list."""

    def _review_runs(**kwargs):
        capture["case_id"] = kwargs.get("case_id")
        return {"runs": [], "latest_run_id": None, "latest_audit": None,
                "case_id": kwargs.get("case_id")}

    noop = lambda **_kw: {}  # noqa: E731
    return ToolContext(
        author_judge=noop, get_judge=noop, run_eval_replay=noop, get_agent=noop,
        author_flag=noop, review_runs=_review_runs, run_eval_pack=noop, assemble_agent=noop,
        delete_judge=noop, create_flag=noop, delete_flag=noop, put_grounding_contract=noop,
        kb_context=noop, ingest_cases=noop, list_cases=noop, record_meta_verdict=noop,
        default_agent="repro_agent", active_case=active_case,
        known_case_ids=(lambda: list(known if known is not None else KNOWN)),
    )


def test_handler_resolves_prefix_before_the_exact_match_query():
    """review_runs_handler({"case_id": "cv_mts_002"}) → the review_runs op is called with the
    FULL id, never the raw prefix (the exact-match query would return 0)."""
    cap: dict = {}
    ctx = _ctx(capture=cap)
    asyncio.run(review_runs_handler(ctx, {"case_id": "cv_mts_002"}))
    assert cap["case_id"] == FULL


def test_handler_narrates_the_resolved_full_id_not_the_prefix():
    """The narration names the resolved full id (so the scope is honest) — NOT the token."""
    cap: dict = {}
    ctx = _ctx(capture=cap)
    res = asyncio.run(review_runs_handler(ctx, {"case_id": "cv_mts_002"}))
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert FULL in text
    # the audit card carries the resolved full id too
    cards = [p for p in ctx.parts if p.get("type") == "tool-audit_log"]
    assert cards and cards[0]["output"].get("caseId") == FULL


def test_handler_ambiguous_prefix_stays_unscoped_and_asks():
    """An ambiguous prefix → the op is called UNSCOPED (case_id=None, never a wrong guess) and
    the narration asks which case (lists the matches)."""
    cap: dict = {}
    ctx = _ctx(capture=cap)
    res = asyncio.run(review_runs_handler(ctx, {"case_id": "cv_mts_10"}))
    assert cap["case_id"] is None
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert "cv_mts_101_missing_allergy" in text
    assert "cv_mts_104_fabricated_history" in text


def test_handler_unknown_token_keeps_empty_behavior():
    """An unknown token → passes through (case_id=token), the exact-match query returns 0 runs —
    today's honest empty, unchanged. No crash, no note."""
    cap: dict = {}
    ctx = _ctx(capture=cap)
    res = asyncio.run(review_runs_handler(ctx, {"case_id": "totally_unknown"}))
    assert cap["case_id"] == "totally_unknown"
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert "0 run(s) on record" in text


def test_armed_full_id_case_wins_over_a_typed_short_token():
    """ARMED beats typed: ctx.active_case is a known full id; the message-derived args carry a
    DIFFERENT short token — the armed full id is the scope."""
    cap: dict = {}
    ctx = _ctx(active_case="cv_mts_101_missing_allergy", capture=cap)
    asyncio.run(review_runs_handler(ctx, {"case_id": "cv_mts_002"}))
    assert cap["case_id"] == "cv_mts_101_missing_allergy"


def test_no_known_case_ids_binding_degrades_to_todays_behavior():
    """A ctx built WITHOUT known_case_ids (a test stub / a ctx missing the binding) must not
    crash — the token passes through exactly as today (exact-match query)."""
    cap: dict = {}

    def _review_runs(**kwargs):
        cap["case_id"] = kwargs.get("case_id")
        return {"runs": [], "latest_run_id": None, "latest_audit": None,
                "case_id": kwargs.get("case_id")}

    noop = lambda **_kw: {}  # noqa: E731
    ctx = ToolContext(
        author_judge=noop, get_judge=noop, run_eval_replay=noop, get_agent=noop,
        author_flag=noop, review_runs=_review_runs, run_eval_pack=noop, assemble_agent=noop,
        delete_judge=noop, create_flag=noop, delete_flag=noop, put_grounding_contract=noop,
        kb_context=noop, ingest_cases=noop, list_cases=noop, record_meta_verdict=noop,
        default_agent="repro_agent",
    )
    asyncio.run(review_runs_handler(ctx, {"case_id": "cv_mts_002"}))
    assert cap["case_id"] == "cv_mts_002"  # unchanged pass-through
