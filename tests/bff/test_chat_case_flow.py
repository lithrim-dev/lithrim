"""NARR-CHAT-LOOP — the CONVERSATIONAL half of the ingest→explore→grade loop.

Diagnosis (live conversational dogfood 2026-06-18, FINDINGS_conversational_case_flow):
the UI case-selector works (Cases tab → click → Case tab → Run grades it), but the CHAT
tools were DECOUPLED from the ingested corpus:
  * no `list_cases` tool — "show me the cases" surfaced only the agent's seed case;
  * `show_case` took NO `case_id` — "open case X" claimed X but showed the seed
    (confident-but-wrong, the worst demo failure);
  * the chat `run_eval` had no `case_id` — it graded the seed, not the explored case;
  * there was no SHARED active case between the chat and the UI.

The fix mirrors the already-shipped UI case-selector: a `list_cases` tool, a `case_id` on
`show_case`/`run_eval` (both endpoints already accept it), and an `active_case` the chat
defaults to (sent by the shell, named in the system prompt). $0 + A-SAFE preserved: a
`case_id` is a case SELECTOR, never a paid knob.

Hermetic — NO real Claude, NO Azure. The handlers run against the real (frozen) BFF ops
bound over a tmp config DB + a tmp workspace out_dir. Requires the [bff] extra.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402  (SDK-free handlers/schemas)
from agent.loop import _SYSTEM_PROMPT, _system_prompt  # noqa: E402  (SDK-free)
from agent.tools import (  # noqa: E402
    LIST_CASES_SCHEMA,
    PAID_KEYS,
    RUN_EVAL_SCHEMA,
    SHOW_CASE_SCHEMA,
    list_cases_handler,
    run_eval_handler,
    show_case_handler,
)

from tests._house_fixture import house_agent  # noqa: E402

AGENT = "case_flow_agent"


def _envelope(case_id: str, *, context: str, response: str = "S (Subjective): ...") -> dict:
    from lithrim_bench.verification.jute_extractor import _to_envelope

    return _to_envelope({"case_id": case_id, "response": response, "context": context})


def _build_ctx(db, out, *, active_case=None):
    return bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=out,
        workdir=out / "ont",
        collections_db=out / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
        active_case=active_case,
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tmp config plane + a tmp workspace out_dir holding an ingested corpus, with the
    ToolContext bound to the real (frozen) BFF ops. The corpus (c1_ok / c2_ok) is the thing
    the chat tools must now reach."""
    db = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ingested_cases.jsonl").write_text(
        "\n".join(
            json.dumps(c, sort_keys=True)
            for c in (
                _envelope("c1_ok", context="Doctor: hi\nPatient: cramps"),
                _envelope("c2_ok", context="Doctor: hello"),
            )
        )
        + "\n"
    )
    fake_ws = types.SimpleNamespace(
        out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="case_flow_ws"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)
    return db, out


# ── list_cases — the chat can enumerate the ingested corpus ───────────────────


def test_list_cases_tool_lists_ingested_corpus_and_focuses_the_cases_tab(env):
    """CRITICAL #2: "show me the cases I can evaluate" must enumerate the INGESTED corpus
    (not the agent's seed). The tool lists every case_id and opens the Cases tab."""
    db, out = env
    ctx = _build_ctx(db, out)
    res = asyncio.run(list_cases_handler(ctx, {}))
    assert not res.get("is_error")
    text = res["content"][0]["text"]
    assert "c1_ok" in text and "c2_ok" in text  # the corpus is enumerated, not the seed
    assert "2" in text  # the count is surfaced
    # the Cases tab (the `corpus` artifact tab) is opened so the human SEES the corpus
    directive = [p for p in ctx.parts if p["type"] == "tool-open_artifact"]
    assert directive and directive[-1]["output"]["tab"] == "corpus"


def test_list_cases_tool_is_honest_when_the_corpus_is_empty(env, monkeypatch):
    """An empty corpus surfaces an honest "nothing ingested yet" — never a fabricated case."""
    db, out = env
    (out / "ingested_cases.jsonl").unlink()
    ctx = _build_ctx(db, out)
    res = asyncio.run(list_cases_handler(ctx, {}))
    assert not res.get("is_error")
    assert "0" in res["content"][0]["text"] or "no " in res["content"][0]["text"].lower()


# ── show_case(case_id=X) — opens X, not the seed; never claims a case it didn't open ──


def test_show_case_threads_case_id_and_updates_the_active_case(env):
    """CRITICAL #1: show_case(case_id=X) emits a Case-Summary card for X (the card carries
    case_id so it self-fetches X, not the seed), and it updates ctx.active_case so a same-turn
    run grades X."""
    db, out = env
    ctx = _build_ctx(db, out, active_case=None)
    res = asyncio.run(show_case_handler(ctx, {"case_id": "c1_ok"}))
    assert not res.get("is_error")
    assert "c1_ok" in res["content"][0]["text"]
    part = next(p for p in ctx.parts if p["type"] == "tool-case_summary")
    assert part["output"]["case_id"] == "c1_ok"  # the card fetches X (not the agent's seed)
    assert part["output"]["agent"] == AGENT
    assert ctx.active_case == "c1_ok"  # a same-turn run now defaults to X


def test_show_case_defaults_to_the_active_case(env):
    """show_case with NO case_id falls back to the shared active case (the case the human is
    exploring in the UI), not the agent's seed."""
    db, out = env
    ctx = _build_ctx(db, out, active_case="c2_ok")
    asyncio.run(show_case_handler(ctx, {}))
    part = next(p for p in ctx.parts if p["type"] == "tool-case_summary")
    assert part["output"]["case_id"] == "c2_ok"


# ── run_eval(case_id=X) — targets the explored case for a FRESH grade, not the seed ──


def _forbid_replay(**_kw):
    """RUN-EVAL-FRESH-1: run_eval must NOT call the bound replay op — it surfaces the cost-confirm."""
    raise AssertionError("run_eval must NOT call run_eval_replay (the stale $0 replay)")


def test_run_eval_targets_case_id_via_the_active_case(env):
    """CRITICAL #3 (RUN-EVAL-FRESH-1): run_eval(case_id=X) makes X the active case so the FRESH grade
    the human confirms (confirmPaidRun runs runEval(case_id=activeCase)) targets X — and it surfaces
    the cost-confirm directive (never the stale replay; a raise-on-call spy proves the op is unused)."""
    db, out = env
    ctx = _build_ctx(db, out)
    ctx.run_eval_replay = _forbid_replay
    asyncio.run(run_eval_handler(ctx, {"agent": AGENT, "case_id": "c1_ok"}))
    assert ctx.active_case == "c1_ok"  # the explored case is the one the fresh grade will target
    # CHAT-CASE-TARGET-1: the directive CARRIES the targeted case so the shell grades X, not the
    # stale client activeCase (the prior `output: {}` assertion encoded the dropped-case bug).
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "c1_ok"}}
    ]


def test_run_eval_with_no_case_id_keeps_the_active_case(env):
    """run_eval with NO case_id leaves the shared active case in place (the case the human is
    exploring), and still surfaces the cost-confirm — never the seed, never a replay. CHAT-CASE-
    TARGET-1: the directive carries that active case so confirmPaidRun targets it."""
    db, out = env
    ctx = _build_ctx(db, out, active_case="c2_ok")
    ctx.run_eval_replay = _forbid_replay
    asyncio.run(run_eval_handler(ctx, {"agent": AGENT}))
    assert ctx.active_case == "c2_ok"
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "c2_ok"}}
    ]


def test_run_eval_reaches_no_paid_op_with_an_injected_knob(env):
    """A-SAFE (load-bearing negative): even with paid knobs injected alongside case_id, run_eval
    reaches NO op at all (the raise-on-call replay spy is never hit) — it only proposes; the case_id
    is a selector that updates the active case, never a spend."""
    db, out = env
    ctx = _build_ctx(db, out)
    ctx.run_eval_replay = _forbid_replay
    res = asyncio.run(
        run_eval_handler(
            ctx,
            {"agent": AGENT, "case_id": "c1_ok", "live": True, "in_process": True, "confirm": True},
        )
    )
    assert not res.get("is_error")
    assert ctx.active_case == "c1_ok"
    # CHAT-CASE-TARGET-1: the directive carries ONLY the case SELECTOR — no injected paid knob ever
    # reaches the wire (the selector is not a spend; the human's confirm is still the sole paid path).
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "c1_ok"}}
    ]
    assert not any(k in ctx.parts[0]["output"] for k in PAID_KEYS)


# ── the bound list_cases op reaches the real corpus ───────────────────────────


def test_bound_list_cases_returns_the_ingested_ids(env):
    """The wired closure (not a stub) reaches the SAME corpus GET /v1/cases serves."""
    db, out = env
    ctx = _build_ctx(db, out)
    res = ctx.list_cases()
    assert res["count"] == 2
    assert {c["case_id"] for c in res["cases"]} == {"c1_ok", "c2_ok"}


# ── schemas + registry: A-SAFE preserved across the +1 surface ────────────────


def test_case_flow_schemas_carry_no_paid_knob():
    """case_id is a SELECTOR — present on show_case/run_eval, absent from the paid-knob set;
    list_cases takes no params."""
    assert {"case_id": str} == SHOW_CASE_SCHEMA
    assert "case_id" in RUN_EVAL_SCHEMA
    assert LIST_CASES_SCHEMA == {}
    for schema in (SHOW_CASE_SCHEMA, RUN_EVAL_SCHEMA, LIST_CASES_SCHEMA):
        assert not any(k in schema for k in PAID_KEYS)


def test_list_cases_joins_the_tool_set_once_and_context_carries_the_fields():
    names = [name for _, name, *_ in agent_tools._TOOL_SPECS]
    assert names.count("list_cases") == 1
    fields = set(agent_tools.ToolContext.__dataclass_fields__)
    assert {"list_cases", "active_case"} <= fields
    # every schema (the new tool included) is still no-paid-knob
    for _h, n, _d, schema in agent_tools._TOOL_SPECS:
        assert not any(k in schema for k in PAID_KEYS), n


# ── system prompt: the shell-selected active case is named + the nudges land ──


def test_system_prompt_names_the_active_case_and_nudges_list_and_show():
    """The model must default run_eval/show_case to the shared active case, call list_cases
    for "the cases", and never claim a case it did not open."""
    prompt = _system_prompt(AGENT, "clinical_scribe_05")
    assert "clinical_scribe_05" in prompt  # the active case is named
    assert "list_cases" in prompt  # the enumerate-the-corpus nudge
    assert "show_case" in prompt and "case_id" in prompt  # open-case-X uses case_id
    assert prompt.startswith(_SYSTEM_PROMPT)  # the static base is preserved
    # TOOLSEARCH-MISFIRE (positive reframe): the prompt no longer NAMES ToolSearch (the
    # "don't think of an elephant" priming) — it states positively that all tools are loaded.
    assert "ToolSearch" not in prompt and "tool_search" not in prompt
    assert "already loaded" in prompt.lower()
    # back-compat: no active case → the agent-only prompt still works (no crash, no case named)
    bare = _system_prompt(AGENT)
    assert AGENT in bare
    assert "clinical_scribe_05" not in bare
