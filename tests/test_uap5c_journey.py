"""UAP-5c / R11 acceptance: the FULL Domain→Judge→Flag→Run→Review conversational
journey (offline / $0) + the carried seams.

Hermetic — NO real Claude, NO Azure. The tool HANDLERS run against the real (frozen)
BFF ops over a tmp config DB, proving:
  - A1/A2 the whole journey runs and IS the audit log (each writing tool → an audited
    record at GET /v1/audit; the run/review legs read real provenance);
  - A3 the new tools drive real ops ($0 reads + the audited ontology edit; gate
    violations SURFACED, never bypassed);
  - A4 every tool-result is an EXISTING gen-UI card (no new types);
  - A-SAFE GROWN (S-BS-81): the allowlist is exactly the mcp__lithrim__* set with no
    built-in tool, and NO tool schema carries a paid knob.
The S-BS-82 get_judge regression has its dedicated test in test_uap5b_chat.py; the
journey here also drives get_judge through the bound closure. The fully-integrated SDK
loop is the A-LIVE user-run, by design. Requires the [bff] extra; the [agent]-gated
allowlist check skips cleanly when claude_agent_sdk is absent.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
ONTOLOGY_SEED = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    author_flag_handler,
    author_judge_handler,
    get_agent_handler,
    get_judge_handler,
    review_runs_handler,
    run_eval_handler,
)

AGENT = "uap5c_test"
# An existing flag in the seed ontology — author_flag EDITS tier/gradeable (never creates).
EXISTING_FLAG = "DURATION_FABRICATION"
# Built-in SDK tool names the allowlist must NEVER contain (bypassPermissions would
# auto-approve them) — the S-BS-81 guard.
BUILTIN_TOOLS = {
    "Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch",
    "Glob", "Grep", "NotebookEdit", "Task", "MultiEdit",
}


def _fixture_agent(name: str = AGENT) -> Agent:
    return Agent(
        name=name,
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(
            case_id=CASE_ID,
            source=str(FIXTURES / f"case.{CASE_ID}.jsonl"),
            baseline=str(FIXTURES / f"baseline.{CASE_ID}.json"),
        ),
    )


@pytest.fixture
def env(tmp_path):
    """A tmp config plane + a ToolContext bound to the real (frozen) BFF ops, plus a
    TestClient over the SAME db so GET /v1/audit reads what the tools wrote."""
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    try:
        yield ctx, TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_full_journey_domain_judge_flag_run_review_is_audited(env):
    """A1+A2+A3+A4: drive the five legs in order; each tool emits its EXISTING card and
    each writing tool lands an audited record; nothing un-audited."""
    ctx, client = env
    steps = [
        (get_agent_handler, {"name": AGENT}, "tool-agent_editor"),
        (get_judge_handler, {"role": "risk_judge"}, "tool-judge_editor"),  # S-BS-82 path
        (author_flag_handler, {"flag_code": EXISTING_FLAG, "tier": "TIER_2", "rationale": "tighten"}, "tool-flag_editor"),
        (author_judge_handler, {"role": "risk_judge", "assigned_flags": ["WRONG_DOSAGE"], "rationale": "via chat"}, "tool-judge_editor"),
        (run_eval_handler, {"agent": AGENT}, "tool-verdict_card"),
        (review_runs_handler, {}, "tool-audit_log"),
    ]
    for handler, args, expect_type in steps:
        before = len(ctx.parts)
        res = asyncio.run(handler(ctx, args))
        assert not res.get("is_error"), (handler.__name__, res)
        assert len(ctx.parts) == before + 1, handler.__name__
        assert ctx.parts[-1]["type"] == expect_type
        assert ctx.parts[-1]["state"] == "output-available"
    # A2 — the conversation IS the audit log: BOTH the flag edit and the judge write,
    # attributed to the SME, surface in the config-change stream.
    recs = client.get("/v1/audit").json()["records"]
    targets = {r["target"]["type"] for r in recs if r["actor"]["id"] == "test-sme"}
    assert {"ontology", "judge"} <= targets, targets


def test_review_runs_threads_the_latest_run_id_to_the_audit_card(env):
    """A3 (Review): after a $0 replay, review_runs lists it and passes its run_id to the
    audit_log card so AuditView can load that run's provenance."""
    ctx, _client = env
    asyncio.run(run_eval_handler(ctx, {"agent": AGENT}))
    ctx.parts.clear()
    res = asyncio.run(review_runs_handler(ctx, {}))
    assert not res.get("is_error")
    part = ctx.parts[-1]
    assert part["type"] == "tool-audit_log"
    assert part["output"]["runId"]  # a real run id threaded to the card for provenance


def test_author_flag_unknown_flag_is_surfaced_not_bypassed(env):
    """A3 + A-SAFE: editing a non-existent flag is rejected; the tool surfaces it, emits
    NO card, and nothing is persisted (no silent un-audited write)."""
    ctx, client = env
    res = asyncio.run(
        author_flag_handler(ctx, {"flag_code": "NOPE_NOT_A_FLAG", "tier": "TIER_1"})
    )
    assert res.get("is_error") is True
    assert "existing flag" in res["content"][0]["text"].lower()
    assert ctx.parts == []  # no card on a rejected write
    recs = client.get("/v1/audit", params={"target_type": "ontology"}).json()["records"]
    assert recs == []  # nothing persisted -> nothing audited


def test_allowlist_is_bounded_to_mcp_lithrim_tools_no_builtins():
    """S-BS-81 (structural, SDK-free): the loop's allowlist derives PURELY from
    _TOOL_SPECS — exactly the mcp__lithrim__* set, no built-in tool, no wildcard. This
    is what keeps permission_mode='bypassPermissions' safe as the tool surface grows."""
    names = [name for _, name, *_ in agent_tools._TOOL_SPECS]
    allowed = [f"mcp__lithrim__{n}" for n in names]
    assert allowed, "the tool set must be non-empty"
    assert all(a.startswith("mcp__lithrim__") for a in allowed)
    assert not any("*" in a for a in allowed)  # no wildcard grant
    assert set(names).isdisjoint(BUILTIN_TOOLS)  # no Bash/Read/Write/... in the set


def test_no_tool_schema_carries_a_paid_knob():
    """S-BS-81 / A-SAFE generalized across ALL tools (not just run_eval): no tool's input
    schema exposes confirm/in_process/live — the agent has no path to request a paid run."""
    for _handler, name, _desc, schema in agent_tools._TOOL_SPECS:
        offenders = [k for k in PAID_KEYS if k in schema]
        assert offenders == [], (name, offenders)


def test_build_options_carries_exactly_the_bounded_allowlist_under_bypass(env):
    """S-BS-81 ([agent]-gated): the ACTUAL ClaudeAgentOptions the loop builds carry
    exactly the derived mcp__lithrim__* allowlist with bypassPermissions — binding the
    structural claim to the real loop config."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import loop

    ctx, _client = env
    opts = loop._build_options(ctx)
    expected = [f"mcp__lithrim__{n}" for _, n, *_ in agent_tools._TOOL_SPECS]
    assert list(opts.allowed_tools) == expected
    assert opts.permission_mode == "bypassPermissions"
    assert set(opts.allowed_tools).isdisjoint(BUILTIN_TOOLS)
