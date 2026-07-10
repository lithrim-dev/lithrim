"""INLINE-IMPACT-1: the inline cards must carry their own WHY.

Two gaps the demo-impact reassessment found in the BFF projection layer:
  * ``verdict_part`` drops the per-judge ``reason`` (the approve reads as a scorecard, not a reasoned
    verdict) and never threads ``composite.floor_adjustments`` (so the BLOCK card cannot show that a
    deterministic FLOOR — the rule the clinician authored — caught the omission; the demo's thesis).
  * ``run_eval_handler`` narrates ``grounded_adjustments`` (suppressions) but NOT the floor INJECTIONS,
    and ``show_case`` narration pushes the human to the side panel.

These pin the projection so the VerdictCard can render reasoning + a "Caught by floor rule" attribution
inline, and the agent stops pointing at the pane. Pure projection/narration — no moat, no engine.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import tools as agent_tools  # noqa: E402
from agent.adapter import verdict_part  # noqa: E402


def _record(*, floor=True, reason=True):
    fa = (
        [
            {
                "flag": "DISSENT_ERASURE",
                "action": "floor_block",
                "contract_type": "value_presence",
                "contract": "DISSENT_ERASURE/v1",
                "conforms": False,
                "disposition": "the patient's refusal was stated but missing from the note",
            },
            # an inconclusive floor must NOT be shown as a block (only injections flip the verdict)
            {"flag": "X", "action": "floor_inconclusive", "contract_type": "value_presence",
             "contract": "X/v1", "conforms": True, "disposition": "inconclusive"},
        ]
        if floor
        else []
    )
    vote = {"judge_role": "policy_judge", "vote": "PASS", "confidence": 0.9}
    if reason:
        vote["reason"] = "No safety findings; documentation aligns with the visit."
    return {
        "pipeline_run_id": "run-1",
        "composite": {
            "verdict": "block" if floor else "approve",
            "active_findings": ["DISSENT_ERASURE"] if floor else [],
            "floor_adjustments": fa,
        },
        "council": {"votes": [vote]},
    }


# ── verdict_part threads the per-vote reason (the approve becomes a reasoned verdict) ──


def test_verdict_part_threads_per_vote_reason():
    out = verdict_part(_record(floor=False, reason=True))["output"]
    assert out["votes"][0]["reason"] == "No safety findings; documentation aligns with the visit."


def test_verdict_part_omits_reason_key_when_absent():
    """Back-compat: a vote with no reason carries no reason key (the byte-identical prior shape)."""
    out = verdict_part(_record(floor=False, reason=False))["output"]
    assert "reason" not in out["votes"][0]


# ── verdict_part threads the floor attribution (the thesis: a rule caught it) ──


def test_verdict_part_threads_floor_blocks_attribution():
    """The BLOCK card must be able to show WHO caught it: the injected code + the floor contract +
    the one-line disposition — projected from composite.floor_adjustments (action == floor_block only)."""
    out = verdict_part(_record(floor=True))["output"]
    fb = out.get("floorBlocks")
    assert isinstance(fb, list) and len(fb) == 1, "only the floor_block injection, not the inconclusive"
    b = fb[0]
    assert b["flag"] == "DISSENT_ERASURE"
    assert b["contract_type"] == "value_presence"
    assert b["contract"] == "DISSENT_ERASURE/v1"
    assert "missing from the note" in b["disposition"]


def test_verdict_part_omits_floor_blocks_when_none():
    """Back-compat + honesty: a clean approve (no floor injection) carries no floorBlocks key, so the
    card shows nothing — never a fabricated 'caught by floor' on a clean pass."""
    out = verdict_part(_record(floor=False))["output"]
    assert "floorBlocks" not in out


# ── verdict_part threads the floor CLEARS (suppressions): the symmetric "false alarm cleared" ──


def _record_with_suppression():
    """An approve where a judge RAISED a finding that a deterministic floor then DISPROVED
    (``grounded.suppressed``) — the SNOMED-subsumption flip the demo turns on. The card must
    show WHO cleared it (the false alarm + the rule + the evidence), symmetric to floorBlocks."""
    return {
        "pipeline_run_id": "run-2",
        "composite": {"verdict": "approve", "active_findings": [], "floor_adjustments": []},
        "council": {"votes": [{"judge_role": "faithfulness_judge", "vote": "WARN", "confidence": 0.87}]},
        "grounded": {
            "suppressed": [
                {
                    "code": "FABRICATED_HISTORY",
                    "reason": "every documented history item is grounded by SNOMED subsumption",
                    "evidence": "all 1 documented PMH item(s) are == or subsumed-by a record concept (oracle codes=[31996006])",
                }
            ]
        },
    }


def test_verdict_part_threads_floor_clears_attribution():
    """The pass card must show WHO cleared a false alarm: the suppressed code + the reason + the
    evidence — projected from record.grounded.suppressed. This is the SNOMED-flip punchline inline."""
    out = verdict_part(_record_with_suppression())["output"]
    fc = out.get("floorClears")
    assert isinstance(fc, list) and len(fc) == 1
    c = fc[0]
    assert c["flag"] == "FABRICATED_HISTORY"
    assert "SNOMED subsumption" in c["reason"]
    assert "subsumed-by" in c["evidence"]


def test_verdict_part_omits_floor_clears_when_none():
    """Back-compat + honesty: a real clean pass (no suppression) carries no floorClears key — the
    card never shows a fabricated 'cleared by a fact-check' when nothing was actually cleared."""
    out = verdict_part(_record(floor=False))["output"]
    assert "floorClears" not in out


def test_verdict_part_threads_terminology_edition_on_a_clear():
    """REL-OPS-1 O2: a terminology-grounded suppression carries the release that decided it
    (grounded.suppressed[].terminology_edition) — the projection must not strip it, so the card
    can render the edition as secondary metadata beside the evidence."""
    rec = _record_with_suppression()
    rec["grounded"]["suppressed"][0]["terminology_edition"] = "unrecorded"
    out = verdict_part(rec)["output"]
    assert out["floorClears"][0]["terminology_edition"] == "unrecorded"


def test_verdict_part_omits_terminology_edition_on_a_legacy_clear():
    """Pre-O2 blobs carry no edition — the projected entry stays shape-identical (absent, not
    null), so legacy cards render exactly as before."""
    out = verdict_part(_record_with_suppression())["output"]
    assert "terminology_edition" not in out["floorClears"][0]


# ── the floor INJECTION attribution lives on verdict_part (run_eval no longer narrates a verdict) ──


def _spy_ctx():
    def _forbidden(*_a, **_k):
        raise AssertionError("run_eval must not call any bound op (it only proposes)")

    return agent_tools.ToolContext(
        author_judge=_forbidden, get_judge=_forbidden, run_eval_replay=_forbidden,
        get_agent=_forbidden, author_flag=_forbidden, review_runs=_forbidden,
        run_eval_pack=_forbidden, assemble_agent=_forbidden, delete_judge=_forbidden,
        create_flag=_forbidden, delete_flag=_forbidden, put_grounding_contract=_forbidden,
        kb_context=_forbidden, ingest_cases=_forbidden, list_cases=_forbidden,
        record_meta_verdict=_forbidden, default_agent="ws0_default",
    )


def test_run_eval_surfaces_the_cost_confirm_not_a_verdict_narration():
    """RUN-EVAL-FRESH-1 (supersedes the handler floor-narration): run_eval no longer renders a verdict
    or narrates findings — it surfaces the cost-confirm for a FRESH grade (it calls NO bound op). The
    floor-INJECTION attribution the demo needs now lives on verdict_part.floorBlocks (rendered after
    the fresh grade via confirmPaidRun), pinned by test_verdict_part_threads_floor_blocks_attribution
    above — so the 'a deterministic floor caught it' thesis is preserved on the live (fresh) path."""
    ctx = _spy_ctx()
    out = asyncio.run(agent_tools.run_eval_handler(ctx, {"agent": "ws0_default", "case_id": "c"}))
    text = out["content"][0]["text"].lower()
    assert "fresh" in text and ("cost-confirm" in text or "cost confirm" in text)
    # CHAT-CASE-TARGET-1: the directive carries the targeted case (the prior `output: {}` assertion
    # encoded the dropped-case bug — the shell graded the stale client activeCase instead).
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "c"}}
    ]


# ── show_case narration stops pushing to the pane ──


def test_show_case_tool_description_does_not_push_to_the_pane():
    """The show_case tool description must not train the agent to point at the side panel / 'View case'
    as the way to read the case — the inline card is the result."""
    spec = next(s for s in agent_tools._TOOL_SPECS if s[1] == "show_case")
    desc = spec[2].lower()
    assert "side panel" not in desc
    assert "opens the full case tab" not in desc
