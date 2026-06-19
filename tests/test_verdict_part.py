"""verdict_part (the run_eval -> VerdictCard adapter) must project the REAL council
output — verdict + the active findings (the "why") + confidence/agreement + the
faithfulness-judge status — never a demo fill. [[no-static-components-in-live-eval-ui]]
adapter.py is stdlib-only, so this runs in the default suite."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent.adapter import verdict_part  # noqa: E402


def _record(verdict, findings, votes):
    return {
        "case_id": "byo_clinical_unlabeled",
        "pipeline_run_id": "run-xyz",
        "composite": {"verdict": verdict, "stage_verdict": "BLOCK", "active_findings": findings},
        "council": {"votes": votes},
    }


def test_verdict_part_projects_real_findings_and_faithfulness():
    out = verdict_part(_record(
        "reject",
        ["FABRICATED_HISTORY", "HALLUCINATED_DETAIL", "INCOMPLETE_DOCUMENTATION"],
        [
            {"judge_role": "risk_judge", "vote": "PASS", "confidence": 1.0},
            {"judge_role": "policy_judge", "vote": "WARN", "confidence": 0.99},
            {"judge_role": "faithfulness_judge", "vote": "BLOCK", "confidence": 0.98},
        ],
    ))["output"]
    assert out["verdict"] == "REJECT"
    # the body is the REAL findings, not an empty/demo Q&A
    assert "FABRICATED_HISTORY" in out["answer"] and "3 finding" in out["answer"]
    assert "refund policy" not in out["answer"]  # no DEMO leak
    # confidence + agreement are realized off the votes
    assert out["confidence"] == "0.99"  # mean of 1.0/0.99/0.98
    assert out["agreement"] == "1 / 3"  # only risk matches votes[0]=PASS
    # the faithfulness pillar reflects the faithfulness judge's actual BLOCK
    assert out["pillar"] == "Faithfulness" and out["pillarStatus"] == "flagged"


def test_verdict_part_clean_pass_has_no_findings_and_clear_faithfulness():
    out = verdict_part(_record(
        "approve", [],
        [{"judge_role": "faithfulness_judge", "vote": "PASS", "confidence": 0.9}],
    ))["output"]
    assert out["verdict"] == "APPROVE"
    assert "No findings" in out["answer"]
    assert out["pillarStatus"] == "clear ✓"


def test_verdict_part_carries_inline_votes_and_run_id():
    """CONV-FIRST §3: the inline VerdictCard is the WHOLE result — it renders per-judge votes +
    the clinician-dissent form in the conversation. So verdict_part must project the realized
    per-judge votes (role/vote/confidence) AND the pipeline_run_id the inline dissent binds to."""
    out = verdict_part(_record(
        "approve", [],
        [
            {"judge_role": "risk_judge", "vote": "PASS", "confidence": 1.0},
            {"judge_role": "policy_judge", "vote": "WARN", "confidence": 0.99},
            {"judge_role": "faithfulness_judge", "vote": "PASS", "confidence": 0.98},
        ],
    ))["output"]
    # the run the inline dissent form attaches to (META-VERDICT-1)
    assert out["runId"] == "run-xyz"
    # the realized per-judge votes, projected flat (role/vote/confidence)
    assert isinstance(out["votes"], list) and len(out["votes"]) == 3
    assert out["votes"][0] == {"role": "risk_judge", "vote": "PASS", "confidence": 1.0}
    assert out["votes"][1]["role"] == "policy_judge" and out["votes"][1]["vote"] == "WARN"
