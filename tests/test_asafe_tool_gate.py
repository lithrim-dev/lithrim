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

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _build_options, _deny_non_lithrim  # noqa: E402

AGENT = "asafe1_test"


def _fixture_agent(name: str = AGENT):
    return house_agent(name=name)


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


def _reason(out: dict) -> str:
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


def test_discovery_tools_are_denied_with_a_targeted_redirect():
    """TOOLSEARCH-MISFIRE: a tool-discovery / loader call (ToolSearch and friends) is still DENIED,
    but with a TARGETED reason that redirects the model to call the loaded tool directly — so its
    retry is instant instead of probing again. NON-VACUOUS: the reason names 'already loaded' + a
    lithrim tool, which the generic refusal does not."""
    for name in ("ToolSearch", "tool_search", "tool-search", "load_tool", "loadTool", "list_tools", "kb_search"):
        out = asyncio.run(_deny_non_lithrim({"tool_name": name}, "t", {"signal": None}))
        assert _decision(out) == "deny", name
        low = _reason(out).lower()
        assert "already loaded" in low and "directly" in low, (name, _reason(out))


def test_non_discovery_builtins_keep_the_generic_refusal():
    """The targeted redirect is SCOPED to discovery names — a plain built-in (Bash/Read/...) still
    gets the generic 'not a Lithrim tool' refusal (so test_builtin_tools_are_denied_at_the_hook's
    `name in reason` contract holds), not the redirect."""
    for name in ("Bash", "Read", "Write", "Edit", "WebFetch", "Task"):
        out = asyncio.run(_deny_non_lithrim({"tool_name": name}, "t", {"signal": None}))
        assert _decision(out) == "deny", name
        assert name in _reason(out)
        assert "already loaded" not in _reason(out).lower()  # not the discovery redirect


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
    # TOOLSEARCH-MISFIRE root control: `tools=[]` un-offers ALL built-ins (incl. ToolSearch) so the
    # model never sees them — the deny hook is now defense-in-depth, not the only bound. The MCP
    # server rides a separate path, so the 18 lithrim tools survive (asserted above).
    assert opts.tools == []
    assert "ToolSearch" in opts.disallowed_tools
