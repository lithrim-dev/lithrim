"""CHATBIND-1 (S-BS-103): the conversational chat loop operates on the ACTIVE agent.

The live dogfood (DOGFOOD-1) found chat reviewing ``ws0_default`` while a different
case was rail-selected. Corrected root cause (the BFF loop, not the shell — the shell
threads ``activeAgent`` end-to-end already):

  A1  the system prompt was STATIC and named no active agent, so the model emitted the
      conventional ``ws0_default`` for the agent-scoped tools. ``_system_prompt(active)``
      now names the rail-selected agent + instructs default-targeting. (net-new fn.)
  A2  ``_review_runs`` listed ALL runs regardless of agent. It now SCOPES to req_agent.
  A3  A-SAFE: the ONLY ``_build_options`` change is the ``system_prompt=`` value — the
      deny-hook + isolation + allowlist + max_turns stay byte-identical, and no schema
      gains a paid knob.

Hermetic — NO real Claude, NO Azure. Requires the [bff] extra; the gate-not-disturbed
check additionally needs [agent] (skipped cleanly when absent).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402  (SDK-free handlers/schemas)
from agent.loop import _SYSTEM_PROMPT, _system_prompt  # noqa: E402  (SDK-free; no [agent] needed)

AGENT = "chatbind_active"
OTHER = "other_agent"


def _fixture_agent(name: str = AGENT):
    return house_agent(name=name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tmp config plane + a ToolContext bound to the real (frozen) BFF ops over a tmp
    collections DB. The closures are called DIRECTLY (no router), so no TestClient is
    needed — we exercise the bound ops the chat loop drives. The agent is the NEUTRAL _core
    house fixture and the active workspace is pinned to _core (the isolation seam) so the $0
    replay runs in-process on the neutral pack in a bare CE checkout."""
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    collections_db = tmp_path / "coll.sqlite"
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=collections_db,
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    return ctx, collections_db


# ── A1 — the system prompt names the active agent (net-new; non-vacuous) ──────


def test_system_prompt_names_the_active_agent_and_instructs_default_targeting():
    """A1: ``_system_prompt(active)`` names the active agent + instructs default-targeting.
    NON-VACUOUS — the static ``_SYSTEM_PROMPT`` base names NO agent; the appended stanza is
    what binds the active one (so the model stops emitting a stale ``ws0_default``)."""
    prompt = _system_prompt("imported_X")
    assert "imported_X" not in _SYSTEM_PROMPT  # the base is agent-agnostic (the bug)
    assert "imported_X" in prompt  # the stanza binds the active agent
    low = prompt.lower()
    assert "by default" in low  # the default-targeting instruction
    assert "get_agent" in prompt and "review_runs" in prompt  # the agent-scoped tools named
    assert prompt.startswith(_SYSTEM_PROMPT)  # the static base is preserved verbatim
    # not hardcoded — a different active agent threads through
    assert "ws9_other" in _system_prompt("ws9_other")


# ── A2 — review_runs is scoped to the active agent (non-vacuous) ──────────────


def test_review_runs_is_scoped_to_the_active_agent(env):
    """A2: ``review_runs`` returns ONLY the active agent's runs. A real $0 replay persists a
    run under AGENT; a hand-inserted run under OTHER shares the SAME collections DB. NON-
    VACUOUS — on the pre-fix (unscoped) ``_review_runs`` the OTHER run leaks into the list
    and this fails; scoped, it is filtered out and ``latest`` reflects the active agent."""
    from lithrim_bench.harness.collections import PIPELINE_RUNS

    ctx, collections_db = env
    rec = ctx.run_eval_replay(agent=AGENT)  # a real $0 replay -> persists agent_id=AGENT
    mine = rec.get("pipeline_run_id")
    assert mine, "the active agent's replay must persist an addressable run id"

    PIPELINE_RUNS.insert(
        {"pipeline_run_id": "other-agent-run-1", "agent_id": OTHER, "verdict": "approve"},
        db_path=collections_db,
    )

    listing = ctx.review_runs(limit=10)
    runs = listing["runs"]
    assert {r.get("agent") for r in runs} == {AGENT}  # ONLY the active agent's runs
    ids = {r.get("run_id") for r in runs}
    assert mine in ids  # the active agent's run is present
    assert "other-agent-run-1" not in ids  # the other agent's run is filtered out
    assert listing["latest_run_id"] == mine  # latest reflects the ACTIVE agent


def test_review_runs_is_empty_when_the_active_agent_has_no_runs(env):
    """A2 (the negative): a foreign-agent run alone yields an EMPTY active-agent history —
    the scope does not leak another agent's runs as the 'latest' (the live symptom)."""
    from lithrim_bench.harness.collections import PIPELINE_RUNS

    ctx, collections_db = env
    PIPELINE_RUNS.insert(
        {"pipeline_run_id": "foreign-1", "agent_id": OTHER, "verdict": "approve"},
        db_path=collections_db,
    )
    listing = ctx.review_runs(limit=10)
    assert listing["runs"] == []
    assert listing["latest_run_id"] is None
    assert listing["latest_audit"] is None


# ── A3 — the active-agent prompt does not disturb the A-SAFE gate ─────────────


def test_active_agent_prompt_does_not_disturb_the_asafe_gate(env):
    """A3 (the HARD-GATE re-proof): the ONLY ``_build_options`` change is the system_prompt
    VALUE. The prompt now names the active agent, appended to the byte-identical static base;
    the PreToolUse deny-hook + isolation + allowlist + max_turns are UNCHANGED, and no tool
    schema gains a paid knob. (Re-run ``tests/test_asafe_tool_gate.py`` for the gate logic.)"""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent.loop import _build_options, _deny_non_lithrim

    ctx, _collections_db = env
    opts = _build_options(ctx)
    # the change reached the options: the prompt names the active agent, on the static base
    assert AGENT in opts.system_prompt
    assert opts.system_prompt.startswith(_SYSTEM_PROMPT)
    # the A-SAFE gate + isolation are byte-identical (the prompt threading touched nothing else)
    callbacks = [cb for m in opts.hooks["PreToolUse"] for cb in m.hooks]
    assert _deny_non_lithrim in callbacks
    assert opts.permission_mode == "bypassPermissions"
    assert opts.setting_sources == []
    assert opts.skills == []
    expected = [f"mcp__lithrim__{n}" for _, n, *_ in agent_tools._TOOL_SPECS]
    assert list(opts.allowed_tools) == expected
    assert opts.max_turns == 12
    # no paid knob anywhere in the tool surface (A-SAFE — the binding adds no paid path)
    for _h, _n, _d, schema in agent_tools._TOOL_SPECS:
        assert not any(k in schema for k in agent_tools.PAID_KEYS), _n
