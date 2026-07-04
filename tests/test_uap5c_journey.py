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

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    assemble_agent_handler,
    author_flag_handler,
    review_runs_handler,
    run_eval_pack_handler,
)

AGENT = "uap5c_test"
# Built-in SDK tool names the allowlist must NEVER contain (bypassPermissions would
# auto-approve them) — the S-BS-81 guard.
BUILTIN_TOOLS = {
    "Bash",
    "Read",
    "Write",
    "Edit",
    "WebFetch",
    "WebSearch",
    "Glob",
    "Grep",
    "NotebookEdit",
    "Task",
    "MultiEdit",
}


def _fixture_agent(name: str = AGENT):
    return house_agent(name=name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tmp config plane + a ToolContext bound to the real (frozen) BFF ops, plus a
    TestClient over the SAME db so GET /v1/audit reads what the tools wrote."""
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    # Hermetic active workspace: the eval-pack batch routes IN-PROCESS (the _core default), not via
    # whatever out/workspaces/.active a local shell session left set (the process-global pointer
    # tests must not read — the isolation seam).
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
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


def test_review_runs_threads_the_latest_run_id_to_the_audit_card(env):
    """A3 (Review): after a stored run exists, review_runs lists it and passes its run_id to the
    audit_log card so AuditView can load that run's provenance. RUN-EVAL-FRESH-1: run_eval no longer
    creates a run (it surfaces the cost-confirm), so seed a real stored run via the bound $0 op."""
    ctx, _client = env
    ctx.run_eval_replay(agent=AGENT)  # the bound $0 op still seeds a real stored run
    ctx.parts.clear()
    res = asyncio.run(review_runs_handler(ctx, {}))
    assert not res.get("is_error")
    part = ctx.parts[-1]
    assert part["type"] == "tool-audit_log"
    assert part["output"]["runId"]  # a real run id threaded to the card for provenance


# ── CONV-UX-1 (W3): GenUI gating — error-suppression + the show_intent tag ────────────


def test_w3_a_failing_tool_emits_no_part(env):
    """W3 / A4 (gating-named re-assert): a tool whose underlying call FAILS surfaces the error
    and emits NO gen-UI part — the off-context-card-next-to-an-error must never originate at the
    BFF. (The live Audit-card-next-to-404 was a SUCCESSFUL read; this pins the failure half.)"""
    ctx, _client = env
    res = asyncio.run(author_flag_handler(ctx, {"flag_code": "NOPE_NOT_A_FLAG", "tier": "TIER_1"}))
    assert res.get("is_error") is True
    assert ctx.parts == []  # no part emitted on a failed tool call


def test_w3_review_runs_part_is_tagged_ondemand(env):
    """W3 / A4: the PASSIVE review_runs read tags its audit_log part ``ondemand`` so the shell
    collapses it to a compact affordance — exactly the orientation read the live drive rendered
    off-context as a full Audit-trail card next to the 404."""
    ctx, _client = env
    ctx.run_eval_replay(agent=AGENT)  # seed a real stored run (run_eval no longer creates one)
    ctx.parts.clear()
    asyncio.run(review_runs_handler(ctx, {}))
    part = ctx.parts[-1]
    assert part["type"] == "tool-audit_log"
    assert part["show_intent"] == "ondemand"


def test_w3_author_judge_part_is_tagged_auto():
    """W3 / A4: the PRIMARY result the user asked to create (a judge) tags its judge_editor part
    ``auto`` so it renders as the inline card — the contrast that makes the gating non-vacuous vs
    the ``ondemand`` audit read above. Asserted at the adapter (pack-owner-independent): author_judge
    emits ``judge_part`` whose default intent is ``auto``."""
    from agent.adapter import audit_part, judge_part

    assert judge_part("risk_judge", AGENT)["show_intent"] == "auto"  # the created-card path
    assert audit_part("run-1")["show_intent"] == "ondemand"  # the passive-read path (contrast)


def test_author_flag_unknown_flag_is_surfaced_not_bypassed(env):
    """A3 + A-SAFE: editing a non-existent flag is rejected; the tool surfaces it, emits
    NO card, and nothing is persisted (no silent un-audited write)."""
    ctx, client = env
    res = asyncio.run(author_flag_handler(ctx, {"flag_code": "NOPE_NOT_A_FLAG", "tier": "TIER_1"}))
    assert res.get("is_error") is True
    assert "existing flag" in res["content"][0]["text"].lower()
    assert ctx.parts == []  # no card on a rejected write
    recs = client.get("/v1/audit", params={"target_type": "ontology"}).json()["records"]
    assert recs == []  # nothing persisted -> nothing audited


def test_allowlist_is_bounded_to_mcp_lithrim_tools_no_builtins():
    """S-BS-81 (structural, SDK-free): the loop's allowlist derives PURELY from
    _TOOL_SPECS — exactly the mcp__lithrim__* set, no built-in tool, no wildcard.

    NECESSARY, NOT SUFFICIENT (S-BS-90): the allowlist VALUE does not bound the loop under
    bypassPermissions — enforcement is the PreToolUse deny gate. See test_asafe_tool_gate +
    the S-BS-90 live attestation (docs/research/RUN_asafe1_live_2026-06-06.json)."""
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
    structural claim to the real loop config.

    NECESSARY, NOT SUFFICIENT (S-BS-90): bypassPermissions makes the allowlist non-binding;
    the real bound is the PreToolUse deny gate (test_asafe_tool_gate + the live attestation)."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import loop

    ctx, _client = env
    opts = loop._build_options(ctx)
    expected = [f"mcp__lithrim__{n}" for _, n, *_ in agent_tools._TOOL_SPECS]
    assert list(opts.allowed_tools) == expected
    assert opts.permission_mode == "bypassPermissions"
    assert set(opts.allowed_tools).isdisjoint(BUILTIN_TOOLS)


# ── UAP-5c-2 + CRUD-1 + FLAG-1 + CHATBIND-2: re-prove A-SAFE across the surface (== 12) ─


def test_split_and_crud_tools_grow_the_set_to_nine_with_no_paid_knob():
    """A-SAFE (structural): the UAP-5c-2 split tools (eval-pack batch + agent-roster write),
    the CRUD-1 ``delete_judge`` revert, the FLAG-1 ``create_flag``/``delete_flag``, the CHATBIND-2
    ``focus_artifact`` pane directive, the CHATBIND-3 ``show_case`` source-input card, and the
    CHATBIND-4 ``propose_live_run`` consented paid-run hand-off — make the 14-tool set, and NONE
    exposes a paid knob — the S-BS-81 no-paid-knob guarantee generalized across the widened surface.
    (The exhaustive sweep over ALL 17 is test_no_tool_schema_carries_a_paid_knob; the focus_artifact
    / show_case / propose_live_run A-SAFE bounds are tests/test_chatbind2_pane.py; the NARR-2
    ingest_cases A-SAFE bound is tests/bff/test_ingest_cases_tool.py.)"""
    names = [name for _, name, *_ in agent_tools._TOOL_SPECS]
    assert len(names) == 24, names  # +PHASE2-WIRE create_judge +TOOL-AUTHOR-1 author_tool (surfaces, no paid knob)
    assert {
        "run_eval_pack",
        "assemble_agent",
        "delete_judge",
        "create_flag",
        "delete_flag",
        "show_case",
        "propose_live_run",
    } <= set(names)
    by_name = {name: schema for _h, name, _d, schema in agent_tools._TOOL_SPECS}
    for tool in ("run_eval_pack", "assemble_agent", "delete_judge", "create_flag", "delete_flag"):
        assert [k for k in PAID_KEYS if k in by_name[tool]] == [], tool


def test_run_eval_pack_drops_an_injected_live_knob(env, monkeypatch):
    """A-SAFE (THE load-bearing negative): run_eval_pack is the FIRST tool over a
    paid-capable op. Even with live=True/confirm injected into the tool args, the bound op
    receives live=False — the wrapper hardcodes the $0 path; no paid batch is reachable."""
    ctx, _client = env
    captured = {}

    def _spy(req, *, db_path=None, out_dir=None, collections_db=None, workdir=None):
        captured["live"] = req.live
        captured["pack_id"] = req.pack_id
        return {"pack": {"outcomes": []}, "run_ids": []}

    monkeypatch.setattr(bff, "eval_pack_run_endpoint", _spy)
    asyncio.run(
        run_eval_pack_handler(
            ctx,
            {"pack_id": "p", "agents": [AGENT], "live": True, "confirm": True, "in_process": True},
        )
    )
    assert captured["live"] is False  # the injected paid knob was DROPPED at the bound op


def test_run_eval_pack_threads_workdir_on_the_non_core_subprocess_path(env, monkeypatch):
    """Regression (the FastAPI endpoint-as-plain-call Depends trap, S-BS-82 family): on a NON-_core
    workspace the eval-pack batch routes to the pack-bound subprocess via a grade_fn that resolves the
    agent ontology under ``workdir``. If the closure forgets to pass ``workdir=`` to
    eval_pack_run_endpoint, workdir stays an unresolved ``Depends()`` and ``Path(workdir)`` raises
    BEFORE the subprocess is reached — so reaching the spy proves the workdir was threaded through."""
    ctx, _client = env
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="demo", pack="healthcare", packs_dir="x"),
    )
    seen = {}

    def _spy(
        *, agent_name, config_db, ontology_path, collections_db, out_dir, live, in_process, ws
    ):
        seen["ontology_path"] = ontology_path  # reached ONLY if workdir resolved (no Depends leak)
        raise SystemExit("captured after the subprocess routing resolved the ontology path")

    monkeypatch.setattr(bff, "_grade_via_subprocess", _spy)
    asyncio.run(run_eval_pack_handler(ctx, {"pack_id": "p", "agents": [AGENT]}))
    assert "ontology_path" in seen  # the grade_fn resolved workdir and reached the subprocess call


def test_run_eval_pack_handler_never_forwards_a_paid_knob(env):
    """A-SAFE: even if a paid key is injected into the tool args, the handler drops it —
    ctx.run_eval_pack is called with pack_id + agents ONLY (mirrors the run_eval guard)."""
    ctx, _client = env
    seen = {}

    def _spy(*, pack_id, agents, **kw):
        seen["pack_id"] = pack_id
        seen["agents"] = agents
        seen["extra"] = kw
        return {"pack": {"outcomes": []}, "run_ids": []}

    ctx.run_eval_pack = _spy
    asyncio.run(
        run_eval_pack_handler(
            ctx,
            {"pack_id": "p", "agents": [AGENT], "in_process": True, "live": True, "confirm": True},
        )
    )
    assert seen == {"pack_id": "p", "agents": [AGENT], "extra": {}}


def test_run_eval_pack_batches_real_runs_that_round_trip_to_review_runs(env):
    """A3: a $0 replay batch runs real evals whose run ids round-trip to the run history
    (GET /v1/runs via review_runs), and the tool emits the pure-read audit_log card with the
    batch's newest run id threaded for provenance (D-B — no window.confirm paid surface)."""
    ctx, _client = env
    res = asyncio.run(run_eval_pack_handler(ctx, {"pack_id": "chat-pack", "agents": [AGENT]}))
    assert not res.get("is_error"), res
    part = ctx.parts[-1]
    assert part["type"] == "tool-audit_log"
    run_id = part["output"]["runId"]
    assert run_id  # a real batch run id threaded to the card
    listing = ctx.review_runs(limit=10)
    listed = {r.get("run_id") for r in (listing.get("runs") or [])}
    assert run_id in listed  # the batch round-trips to the run history


def test_assemble_agent_roster_edit_is_an_audited_agent_write(env):
    """A2/A3: assemble_agent edits ONE facet (the judges roster) and the write is audited —
    a target_type=agent AuditRecord attributed to the SME, and the roster actually changed."""
    ctx, client = env
    res = asyncio.run(
        assemble_agent_handler(
            ctx,
            {"name": AGENT, "remove_judge": "faithfulness_judge", "rationale": "drop for the test"},
        )
    )
    assert not res.get("is_error"), res
    assert ctx.parts[-1]["type"] == "tool-agent_editor"
    recs = client.get("/v1/audit", params={"target_type": "agent"}).json()["records"]
    assert any(r["actor"]["id"] == "test-sme" and r["target"]["type"] == "agent" for r in recs)
    ag = client.get("/v1/agent", params={"name": AGENT}).json()
    assert "faithfulness_judge" not in ag["eval_profile"]["judges"]  # the one-facet delta applied


def test_assemble_agent_unknown_judge_is_surfaced_not_bypassed(env):
    """A-SAFE: adding an unknown judge role is rejected; the tool surfaces it, emits NO card,
    and nothing is persisted (no silent un-audited write, no fabricated judge)."""
    ctx, client = env
    res = asyncio.run(assemble_agent_handler(ctx, {"name": AGENT, "add_judge": "nope_judge"}))
    assert res.get("is_error") is True
    assert "known judge" in res["content"][0]["text"].lower()
    assert ctx.parts == []  # no card on a rejected write
    recs = client.get("/v1/audit", params={"target_type": "agent"}).json()["records"]
    assert recs == []  # nothing persisted -> nothing audited
