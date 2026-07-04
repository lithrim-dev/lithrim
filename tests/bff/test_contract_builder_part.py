"""FAUTH-1 (G1): the agent SURFACES the ContractBuilder INPUT widget inline.

The mirror is ``get_judge`` → ``judge_part`` → ``JudgeEditor`` (a $0 surface tool that
emits an interactive editor; the *human's* Save is the write). ``author_contract`` is the
contract-authoring twin: it emits ``tool-contract_builder`` (seeded with the in-context
``flag_code`` + agent) and performs NO bound write op — the widget's existing
``putGroundingContract`` save (the audited write) persists it.

Covers A1 (the agent surfaces the builder inline + carries {agent, flag_code} + writes
NOTHING), A3 (A-SAFE: no paid knob in the schema, surfaces-not-spends + the allowlist still
equals _TOOL_SPECS). Mirrors ``tests/test_verdict_part.py`` (adapter-part shape) +
``tests/bff/test_meta_verdict.py`` (the A-SAFE / no-side-effect ToolContext stub).

adapter.py is stdlib-only, so the adapter-part check runs in the default suite; the handler
+ A-SAFE checks are SDK-free (``author_contract_handler`` is exercised without the SDK).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import adapter as agent_adapter  # noqa: E402
from agent import tools as agent_tools  # noqa: E402

# ── the adapter part shape (A1) ──────────────────────────────────────────────


def test_contract_builder_part_carries_agent_and_flag_code():
    """contract_builder_part(agent, flag_code) projects the seed the inline widget mounts
    pre-bound to: a ``tool-contract_builder`` part whose flat-spread output carries
    {agent, flag_code} (the registry spreads part.output as props). Mirrors flag_part/judge_part."""
    part = agent_adapter.contract_builder_part("ws0_default", "INFORMED_DISSENT_ERASURE")
    assert part["type"] == "tool-contract_builder"
    assert part["state"] == "output-available"
    assert part["output"] == {"agent": "ws0_default", "flag_code": "INFORMED_DISSENT_ERASURE"}
    # an INPUT widget the agent leads with is a PRIMARY result → rendered as a full card.
    assert part.get("show_intent") == "auto"


# ── the conversational tool (author_contract) ────────────────────────────────


def _stub_ctx():
    """A ToolContext whose every bound op RAISES if called — so the test proves the
    SURFACE tool writes NOTHING (it must only emit a part + return text)."""

    def _forbidden(*_a, **_k):
        raise AssertionError("author_contract must not call a bound write/grade op")

    return agent_tools.ToolContext(
        author_judge=_forbidden,
        get_judge=_forbidden,
        run_eval_replay=_forbidden,
        get_agent=_forbidden,
        author_flag=_forbidden,
        review_runs=_forbidden,
        run_eval_pack=_forbidden,
        assemble_agent=_forbidden,
        delete_judge=_forbidden,
        create_flag=_forbidden,
        delete_flag=_forbidden,
        put_grounding_contract=_forbidden,
        kb_context=_forbidden,
        ingest_cases=_forbidden,
        list_cases=_forbidden,
        record_meta_verdict=_forbidden,
        default_agent="ws0_default",
    )


def test_author_contract_emits_contract_builder_part():
    """A1: author_contract_handler emits EXACTLY one tool-contract_builder part whose output
    carries {agent, flag_code}, returns guidance text, and performs NO bound write op."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(ctx, {"flag_code": "INFORMED_DISSENT_ERASURE"})
    )
    # surfaces-not-spends: a non-error text result, no crash.
    assert "is_error" not in out
    assert out["content"][0]["text"].strip()
    # exactly one part, of the contract-builder type, seeded with the in-context flag + agent.
    parts = [p for p in ctx.parts if p.get("type") == "tool-contract_builder"]
    assert len(ctx.parts) == 1 and len(parts) == 1, ctx.parts
    o = parts[0]["output"]
    assert o["agent"] == "ws0_default"
    assert o["flag_code"] == "INFORMED_DISSENT_ERASURE"
    # FAUTH-3a: a NAMED-flag card now opens PRE-FILLED with the deterministic presence_check skeleton
    # (correct keys by construction), so the human edits rather than hand-writes JSON. Still emit-only.
    assert set(o["suggested_params"]) == {"med_source", "dosage_regex", "token_min_len", "noise_tokens"}


def test_author_contract_defaults_agent_and_handles_missing_flag():
    """A1: the seed defaults — agent defaults to ctx.default_agent; an omitted/blank flag_code
    surfaces as an empty seed (the widget's own validation gates Save, R5), never a crash."""
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.author_contract_handler(ctx, {}))
    assert "is_error" not in out
    parts = [p for p in ctx.parts if p.get("type") == "tool-contract_builder"]
    assert len(parts) == 1
    assert parts[0]["output"]["agent"] == "ws0_default"
    assert parts[0]["output"]["flag_code"] == ""
    # FAUTH-3a: no flag named yet → nothing to bind a presence_check to → no skeleton pre-fill.
    assert "suggested_params" not in parts[0]["output"]


# ── CRITERION-JUTE-1d: a TOOL-GROUNDED (mcp_call) flag ALSO surfaces CriterionJuteBuilder ─────


def test_criterion_jute_builder_part_carries_the_seed():
    """criterion_jute_builder_part projects the seed the inline card mounts pre-bound to: a
    ``tool-criterion_jute_builder`` part whose flat-spread output carries
    {agent, flag_code, tool, call, criterion}. The mirror is contract_builder_part."""
    part = agent_adapter.criterion_jute_builder_part(
        "ws0_default", flag_code="UPCODING_RISK", tool="hermes_snomed", call="subsumed_by", criterion="c"
    )
    assert part["type"] == "tool-criterion_jute_builder"
    assert part["state"] == "output-available"
    assert part["output"] == {
        "agent": "ws0_default", "flag_code": "UPCODING_RISK",
        "tool": "hermes_snomed", "call": "subsumed_by", "criterion": "c",
    }
    assert part.get("show_intent") == "auto"


def test_author_contract_also_surfaces_criterion_jute_for_mcp_call():
    """CRITERION-JUTE-1d: for a TOOL-GROUNDED (mcp_call) flag, author_contract ADDITIONALLY emits
    the CriterionJuteBuilder card (the generate→gate→pin surface), seeded from the tool/call in the
    suggested_params. Still EMIT-ONLY (no bound write op) — the human's Pin is the sole write."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {
                "flag_code": "UPCODING_RISK",
                "contract_type": "mcp_call",
                "question": "record-vs-note subsumption",
                "suggested_params": {"tool": "hermes_snomed", "call": "subsumed_by"},
            },
        )
    )
    assert "is_error" not in out
    types = [p.get("type") for p in ctx.parts]
    # BOTH cards surface: the contract builder AND the criterion-jute builder.
    assert "tool-contract_builder" in types
    cj = [p for p in ctx.parts if p.get("type") == "tool-criterion_jute_builder"]
    assert len(cj) == 1, ctx.parts
    o = cj[0]["output"]
    assert o["flag_code"] == "UPCODING_RISK"
    assert o["tool"] == "hermes_snomed" and o["call"] == "subsumed_by"
    assert o["criterion"] == "record-vs-note subsumption"


def test_author_contract_does_not_surface_criterion_jute_for_non_mcp_call():
    """The criterion-jute card is scoped to the mcp_call direction — a presence_check flag surfaces
    ONLY the contract builder (the default path is byte-identical to FAUTH-1)."""
    ctx = _stub_ctx()
    asyncio.run(
        agent_tools.author_contract_handler(
            ctx, {"flag_code": "WRONG_DOSAGE", "contract_type": "presence_check"}
        )
    )
    assert not [p for p in ctx.parts if p.get("type") == "tool-criterion_jute_builder"]


# ── A-SAFE: no paid knob, surfaces-not-spends, allowlist == _TOOL_SPECS ───────


def test_author_contract_schema_has_no_paid_knob():
    """A3 (A-SAFE, non-vacuous): AUTHOR_CONTRACT_SCHEMA carries no PAID_KEY — the agent has no
    path to a paid run through this surface. Asserted both directly and generically over every
    tool schema in _TOOL_SPECS (a regression adding a paid knob anywhere fails here)."""
    for key in agent_tools.PAID_KEYS:
        assert key not in agent_tools.AUTHOR_CONTRACT_SCHEMA
    for _h, name, _desc, schema in agent_tools._TOOL_SPECS:
        for key in agent_tools.PAID_KEYS:
            assert key not in schema, (name, key)


def test_author_contract_is_registered_in_tool_specs_exactly_once():
    """A3 / A5: author_contract joins _TOOL_SPECS (so the loop's allowlist auto-includes it),
    exactly once, with the no-paid-knob schema. The allowlist is derived from _TOOL_SPECS, so
    this is the same set the A-SAFE deny hook bounds."""
    names = [name for _h, name, *_ in agent_tools._TOOL_SPECS]
    assert names.count("author_contract") == 1
    spec = next(s for s in agent_tools._TOOL_SPECS if s[1] == "author_contract")
    assert spec[3] is agent_tools.AUTHOR_CONTRACT_SCHEMA
    # the registered handler is the SURFACE handler (not a write op).
    assert spec[0] is agent_tools.author_contract_handler
