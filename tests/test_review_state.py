"""REVIEW-STATE-1 — the three-state reviewer decision is computed ONCE, in the engine.

The product invariant: a case is CLEARED only when the deterministic layer materially
supported the PASS (a recorded floor pass, or a judge signal disproved with evidence),
FLAGGED only when a check injected the block, and everything else is ESCALATED with the
reason a person needs. A judge's confidence never clears a case.

Until this cycle the mapping lived only in ``scripts/queue_demo.py``: the report pane and
the inline card rendered every graded case as reject/BLOCK with nothing to separate a proven
defect from an unproven signal. Now ``composite()`` carries the decision as ``review`` so the
CLI, the persisted record and the shell read one source.

Written FIRST (RED): ``lithrim_bench.harness.report.review_state`` does not exist,
``composite()`` carries no ``review`` block, and ``floor_adjustments`` rows carry no evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import from_dict  # noqa: E402
from lithrim_bench.harness.report import composite, review_state  # noqa: E402

_STATES = {"CLEARED", "FLAGGED", "ESCALATED"}


# ── the mapping, unit-level over grounded-result shapes (moved from the queue script) ────


def _decl(ct):
    return SimpleNamespace(contract_type=ct, version="v1", flag_code="X")


def _res(conforms, **ev):
    return SimpleNamespace(conforms=conforms, evidence=ev, reason=ev.get("reason"))


def _grounded(verdict, no_floor, cov, active=(), blocks=(), passes=(), suppressed=()):
    return SimpleNamespace(
        verdict=verdict,
        verdict_no_floor=no_floor,
        coverage=cov,
        active=list(active),
        floor_blocks=list(blocks),
        floor_passes=list(passes),
        suppressed=list(suppressed),
    )


def test_flagged_requires_a_floor_injected_block():
    g = _grounded(
        "BLOCK",
        "PASS",
        {"grounded": 1, "cleared": 0, "floor_backstopped": True},
        active=[{"code": "SOURCE_CONTRADICTION", "_floor": True}],
        blocks=[
            {
                "decl": _decl("value_grounding"),
                "result": _res(False, missing=["4.5"], reason="absent from the record"),
                "injected_finding": {"code": "SOURCE_CONTRADICTION"},
            }
        ],
    )
    r = review_state(g)
    assert r["state"] == "FLAGGED" and r["check"] == "value_grounding" and "4.5" in r["evidence"]


def test_a_judge_only_block_is_escalated_not_flagged():
    g = _grounded(
        "BLOCK",
        "BLOCK",
        {"grounded": 0, "cleared": 0, "judge_only": 1, "floor_backstopped": False},
        active=[{"code": "UNSUPPORTED_ASSERTION"}],
    )
    r = review_state(g)
    assert r["state"] == "ESCALATED" and "UNSUPPORTED_ASSERTION" in r["reason"]


def test_cleared_requires_a_floor_pass_or_a_disproved_signal():
    g = _grounded(
        "PASS",
        "PASS",
        {"grounded": 0, "cleared": 0, "floor_passes": 1, "floor_backstopped": True},
        passes=[
            {
                "decl": _decl("value_grounding"),
                "result": _res(True, checked=3, present=["4", "312", "9:00"], missing=[]),
            }
        ],
    )
    assert review_state(g)["state"] == "CLEARED"
    g2 = _grounded(
        "PASS",
        "BLOCK",
        {"grounded": 0, "cleared": 1, "floor_backstopped": True},
        suppressed=[
            {
                "finding": {"code": "UNSUPPORTED_ASSERTION"},
                "contract": _decl("source_grounding"),
                "verdict": SimpleNamespace(reason="fully grounded"),
            }
        ],
    )
    assert review_state(g2)["state"] == "CLEARED"


def test_a_judge_only_pass_is_escalated_never_cleared():
    g = _grounded("PASS", "PASS", {"grounded": 0, "cleared": 0, "floor_backstopped": False})
    r = review_state(g)
    assert r["state"] == "ESCALATED" and "judges alone" in r["reason"]


def test_a_prose_lead_is_escalated_with_the_value_named():
    g = _grounded(
        "PASS",
        "PASS",
        {"grounded": 0, "cleared": 0, "floor_backstopped": False},
        blocks=[
            {
                "decl": _decl("value_grounding"),
                "result": _res(None, missing=["84"], reason="lead"),
                "injected_finding": None,
            }
        ],
    )
    r = review_state(g)
    assert r["state"] == "ESCALATED" and "84" in r["reason"]


# ── composite() over a REAL ground() result: the record carries the decision ─────────────

_SEV = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}


def _flag(code):
    return {
        "flag": code,
        "category": "fidelity",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
        "owner_roles": ["reviewer"],
        "tier": "TIER_1",
        "gradeable": True,
    }


_ONT = {
    "ontology_version": "review_state_test_v1",
    "domain": "generic",
    "flags": [_flag("SOURCE_CONTRADICTION"), _flag("UNSUPPORTED_ASSERTION")],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "SOURCE_CONTRADICTION",
            "question": "Is every value the artifact states present in the source?",
            "contract_type": "value_grounding",
            "version": "value-grounding/test-1",
            "params": {
                "inject_flag_code": "SOURCE_CONTRADICTION",
                "inject_severity": "HIGH",
                "artifact_kind": "generated_response",
            },
        }
    ],
    "severity_map": _SEV,
}

_RECORD = json.dumps({"name": "Finch & Fork", "business_stars": 4.0, "review_count": 312})


def _record_case(artifact):
    return {
        "source_kind": "record",
        "transcript": _RECORD,
        "artifacts": [{"type": "generated_response", "content": artifact}],
    }


def _council(verdict, *codes):
    return {
        "verdict": verdict,
        "findings": [{"code": c, "severity": "HIGH", "type": "semantic"} for c in codes],
        "semantic": {"judge_votes": [{"judge_role": "reviewer", "vote": verdict}]},
    }


def test_composite_flags_a_value_the_check_contradicted_with_the_evidence_attached():
    art = "Rated 4.5 stars with 312 reviews."
    comp = composite(ground(_council("PASS"), _record_case(art), ontology=from_dict(_ONT)))
    review = comp["review"]
    assert review["state"] == "FLAGGED"
    assert review["check"] == "value_grounding" and "4.5" in review["evidence"]
    assert review["floor_backstopped"] is True
    # the fact-check row itself carries what it found (parity with floor_passes)
    row = comp["floor_adjustments"][0]
    assert row["action"] == "floor_block" and row["evidence"]["missing"] == ["4.5"]


def test_composite_escalates_a_judge_only_block_with_the_codes_named():
    art = "A family-run spot in the city centre."  # no values: the check cannot speak
    comp = composite(
        ground(
            _council("BLOCK", "UNSUPPORTED_ASSERTION"), _record_case(art), ontology=from_dict(_ONT)
        )
    )
    review = comp["review"]
    assert review["state"] == "ESCALATED"
    assert "UNSUPPORTED_ASSERTION" in review["reason"] and review["floor_backstopped"] is False
    assert review["judge_codes"] == ["UNSUPPORTED_ASSERTION"]


def test_composite_clears_only_on_a_recorded_floor_pass():
    art = "Rated 4 stars with 312 reviews."
    comp = composite(ground(_council("PASS"), _record_case(art), ontology=from_dict(_ONT)))
    review = comp["review"]
    assert review["state"] == "CLEARED" and review["check"] == "value_grounding"
    assert "2 value(s) checked" in review["evidence"]
    assert comp["floor_pass_count"] == 1 and review["floor_backstopped"] is True


def test_review_block_names_every_field_the_shell_reads():
    art = "Rated 4 stars with 312 reviews."
    review = composite(ground(_council("PASS"), _record_case(art), ontology=from_dict(_ONT)))[
        "review"
    ]
    assert set(review) >= {
        "state",
        "reason",
        "check",
        "evidence",
        "judge_codes",
        "floor_backstopped",
        "verdict",
        "verdict_no_floor",
    }
    assert review["state"] in _STATES
