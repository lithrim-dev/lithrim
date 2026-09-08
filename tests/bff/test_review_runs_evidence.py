"""The chat's $0 run review hands the model each judge's vote AND its own evidence spans.

Observed 2026-09-09 (BYO-Claude journey): after a live grade the assistant, asked for the
audit trail, said the stored record gave it "findings and the vote tally, not a per-finding
span" and reconstructed quotes from the case text instead. The audit projection carried the
spans all along; ``review_runs_handler`` discarded everything but the verdict."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro
from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from agent.tools import review_runs_handler  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

AGENT = "review_evidence_agent"
CASE = "demo-002"
QUOTE = "Lungs with rhonchi at right base."


def _blob(run_id: str) -> dict:
    return {
        "pipeline_run_id": run_id,
        "replay_of": None,
        "agent_id": AGENT,
        "case_id": CASE,
        "timestamp": "2026-09-08T22:15:08.727333Z",
        "verdict": "BLOCK",
        "gate_decision": "escalate",
        "stages_executed": ["semantic"],
        "grounded": {
            "verdict": "BLOCK",
            "original_verdict": "BLOCK",
            "suppressed": [],
            "floor_blocks": [
                {
                    "flag": "SOURCE_CONTRADICTION",
                    "action": "floor_inconclusive",
                    "contract_type": "value_grounding",
                    "conforms": None,
                    "disposition": "INCONCLUSIVE",
                }
            ],
        },
        "stage_results": {
            "semantic": {
                "judge_votes": [
                    {
                        "judge_role": "faithfulness_judge",
                        "vote": "BLOCK",
                        "confidence": None,
                        "model": "byo-claude",
                        "findings": ["SOURCE_CONTRADICTION"],
                    },
                    {
                        "judge_role": "policy_judge",
                        "vote": "WARN",
                        "confidence": 0.91,
                        "model": "gpt-4o",
                        "findings": [],
                    },
                ],
                "evidence": [
                    {
                        "judge": "faithfulness_judge",
                        "violation_code": "SOURCE_CONTRADICTION",
                        "spans": [{"quote": QUOTE, "turn_ids": []}],
                    }
                ],
            }
        },
    }


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    collections_db = tmp_path / "coll.sqlite"
    run_coro(provenance_store_for(collections_db).save_blob(_blob(str(uuid.uuid4()))))
    return bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=collections_db,
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )


def test_review_runs_text_carries_each_judges_vote_and_own_spans(ctx):
    res = asyncio.run(review_runs_handler(ctx, {"case_id": CASE}))
    assert not res.get("is_error"), res
    text = res["content"][0]["text"]
    assert "faithfulness_judge: BLOCK" in text
    assert "no logprobs" in text  # an honest None, never a fabricated number
    assert "policy_judge: WARN (confidence 0.91)" in text
    assert QUOTE in text and "[SOURCE_CONTRADICTION]" in text
    # the span belongs to the faithfulness judge only; it must not be echoed under policy_judge
    policy_block = text.split("policy_judge")[1]
    assert QUOTE not in policy_block
    # an inconclusive floor entry is NOT an enforcement: the count must say so
    assert (
        "grounding floor: 0 judge signal(s) disproved, 0 enforced, 1 could not be grounded" in text
    )
