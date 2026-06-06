"""ASAFE-1 / S-BS-90: the A-SAFE tool floor is the PreToolUse DENY GATE, not the
allowlist value. This is the offline, non-vacuous guard the four prior cycles lacked
(they asserted the allowed_tools VALUE via a stub source that never ran the real loop;
the ONB-0 A-LIVE caught the live agent spontaneously running built-in Bash — S-BS-90).

These checks are NECESSARY-not-sufficient on their own — the load-bearing proof is the
LIVE refusal attestation (docs/research/RUN_asafe1_live_2026-06-06.json): the real loop
refuses Bash at the TOOL LAYER, not by persona. This file proves the gate's LOGIC is
deterministic + fail-closed and that isolation is set.

Non-vacuity (the fresh-critic re-check): revert the deny branch in `_deny_non_lithrim`
(make it `return {}` for every tool) and the Bash/missing-name cases below MUST start
FAILING. If they still pass, the gate is vacuous.

Requires the [agent] extra (claude-agent-sdk); skips cleanly when absent.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
ONTOLOGY_SEED = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _build_options, _deny_non_lithrim  # noqa: E402

AGENT = "asafe1_test"


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
def ctx(tmp_path):
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    return bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )


def _decision(out: dict) -> str | None:
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")


# ── the gate logic (deterministic, fail-closed) ──────────────────────────────


def test_builtin_tools_are_denied_at_the_hook():
    """A-DENY (offline half): every built-in tool the bypass would auto-approve is DENIED
    by the PreToolUse hook. This is the path the live agent took (probe-1 spontaneous Bash)."""
    for name in ("Bash", "Read", "Write", "Edit", "WebFetch", "Task", "Glob", "Grep"):
        out = asyncio.run(_deny_non_lithrim({"tool_name": name}, "tid", {"signal": None}))
        assert _decision(out) == "deny", name
        assert name in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_lithrim_tools_pass_through():
    """A-WORKS (offline half): the 8 mcp__lithrim__* tools are NOT denied (pass-through ==
    allowed under the existing allowlist) — the gate bounds, it does not break the journey."""
    for _h, name, *_ in agent_tools._TOOL_SPECS:
        qualified = f"mcp__lithrim__{name}"
        out = asyncio.run(_deny_non_lithrim({"tool_name": qualified}, "tid", {"signal": None}))
        assert _decision(out) is None, qualified  # no decision -> allowed


def test_hook_is_fail_closed_on_missing_or_malformed_input():
    """SECURITY (fail-closed): under bypassPermissions a raising/ambiguous hook could fail
    OPEN. A missing/None tool_name, an empty dict, or None input must all DEFAULT-DENY and
    never raise."""
    for bad in ({}, {"tool_name": None}, {"tool_name": ""}, None, {"other": "x"}):
        out = asyncio.run(_deny_non_lithrim(bad, "tid", {"signal": None}))
        assert _decision(out) == "deny", bad


def test_a_non_lithrim_namespace_is_denied():
    """A foreign MCP namespace (e.g. one inherited from the user's ~/.claude) is denied —
    only the exact mcp__lithrim__ prefix passes."""
    out = asyncio.run(_deny_non_lithrim({"tool_name": "mcp__other__do"}, "t", {"signal": None}))
    assert _decision(out) == "deny"


# ── the options carry the gate + isolation ───────────────────────────────────


def test_build_options_registers_the_pretooluse_deny_hook(ctx):
    """The ACTUAL options the loop builds register the deny hook on PreToolUse, and the
    registered callback is _deny_non_lithrim (Bash -> deny through the real registration)."""
    opts = _build_options(ctx)
    matchers = opts.hooks["PreToolUse"]
    assert matchers, "no PreToolUse matcher registered"
    callbacks = [cb for m in matchers for cb in m.hooks]
    assert _deny_non_lithrim in callbacks
    hook = callbacks[0]
    out = asyncio.run(hook({"tool_name": "Bash"}, "tid", {"signal": None}))
    assert _decision(out) == "deny"


def test_build_options_is_isolated_and_carries_only_the_lithrim_server(ctx):
    """A-ISOLATION: setting_sources=[] (+ skills=[]) so the loop inherits NO ~/.claude
    settings/MCP servers; mcp_servers is EXACTLY {"lithrim"} so no foreign mcp__*__* slips
    past the prefix check; allowed_tools stays the derived lithrim set (defense-in-depth)."""
    opts = _build_options(ctx)
    assert opts.setting_sources == []
    assert opts.skills == []
    assert set(opts.mcp_servers) == {"lithrim"}
    expected = [f"mcp__lithrim__{n}" for _, n, *_ in agent_tools._TOOL_SPECS]
    assert list(opts.allowed_tools) == expected
    assert all(a.startswith("mcp__lithrim__") for a in opts.allowed_tools)
