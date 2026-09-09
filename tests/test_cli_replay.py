"""``lithrim replay``: one round of the loop at $0 from the committed sample baselines.

The DoD's no-key round: the five tracked RAGTruth cases replay their council baselines, the
grounding checks run live, and the scorecard comes out in both vocabularies with no BFF, no
key, and no network."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lithrim_bench.cli import replay as rp

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "samples/ragtruth/cases.jsonl"


def test_replay_round_scores_the_sample_in_both_vocabularies():
    cases, audits, rows = rp.replay_round(CASES, CASES.parent, rp.DEFAULT_ONTOLOGY)
    assert len(cases) == 5 and set(audits) == {c["case_id"] for c in cases}
    states = {r["case_id"]: r["state"] for r in rows}
    assert states["ragtruth_10545"] == "FLAGGED"  # the record-backed contradiction the floor proves
    assert all(s in ("CLEARED", "FLAGGED", "ESCALATED") for s in states.values())
    from lithrim_bench.cli import scoring

    res = scoring.score(cases, audits, pack="_core")
    assert {"Data2txt", "QA", "Summary", "OVERALL"} <= set(res["per_task"])
    assert res["per_task"]["OVERALL"]["graded"] == 5
    text = scoring.render(res, scoring.resolve_vocabulary("ragtruth", "_core"))
    assert "SOURCE_CONTRADICTION [Evident Conflict / Subtle Conflict]" in text
    assert "verdict rule:" in text


def test_audit_from_replay_keeps_errors_and_only_that_judges_evidence():
    result = {
        "semantic": {
            "judge_votes": [
                {"judge_role": "a", "vote": "BLOCK", "findings": ["X"], "errors": []},
                {"judge_role": "b", "vote": "PASS", "findings": [], "errors": ["timeout", None]},
            ],
            "evidence": [{"judge": "a", "spans": [{"quote": "q1"}]}, {"judge": "b", "spans": []}],
        }
    }
    audit = rp.audit_from_replay(result, "BLOCK")
    assert audit["grounded_verdict"] == "BLOCK"
    a, b = audit["judges"]
    assert a["evidence"] == [{"judge": "a", "spans": [{"quote": "q1"}]}] and a["findings"] == ["X"]
    assert b["errors"] == ["timeout"] and b["evidence"] == [{"judge": "b", "spans": []}]


def test_the_cli_replays_offline_with_no_stack(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "lithrim_bench.cli", "replay", "--cases", str(CASES)],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin:/bin", "LITHRIM_JUDGE_CACHE": "0"},
    )
    assert out.returncode == 0, out.stderr
    assert "replayed round ($0)" in out.stdout and "OVERALL" in out.stdout
    assert "Evident Conflict" in out.stdout
    js = subprocess.run(
        [sys.executable, "-m", "lithrim_bench.cli", "replay", "--cases", str(CASES), "--json"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin:/bin"},
    )
    body = json.loads(js.stdout)
    assert len(body["states"]) == 5 and body["score"]["per_task"]["OVERALL"]["graded"] == 5


def test_a_missing_baseline_is_reported_never_faked(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps({"case_id": "nope", "artifacts": [{"content": "x"}], "transcript": "s"}) + "\n"
    )
    try:
        rp.replay_round(cases, tmp_path, rp.DEFAULT_ONTOLOGY)
    except FileNotFoundError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("a case without a baseline must not replay")
