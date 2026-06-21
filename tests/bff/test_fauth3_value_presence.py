"""S-BS-143: the ASSIST must reach the FLOOR direction (``value_presence``), not only the
SUPPRESS direction (``presence_check``).

``presence_check`` is a SUPPRESS executor (``harness/grounding.py`` ``_CONTRACT_EXECUTORS`` →
``suppress_executors()``): it can only REMOVE findings, so a contract authored as presence_check can
never flip council-APPROVE → BLOCK. The case-10 completeness floor needs ``value_presence`` (a FLOOR
executor, ``packs/narrative/floors.py`` ``FLOOR_EXECUTORS``): it INJECTS a BLOCK when a required/spoken
value is absent. Before S-BS-143 the ASSIST hard-wired presence_check in four places, so the
conversationally-authored floor SILENTLY did nothing. This pins the two-direction ASSIST.

The FAUTH-3 invariant is preserved: the LLM (agent) reads the prose and picks the DIRECTION
(``contract_type``); the deterministic helper fills the correct KEYS for whichever type; the handler
stays emit-only; the human edits + Saves (the sole audited write).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import assist as agent_assist  # noqa: E402
from agent import tools as agent_tools  # noqa: E402


def _forbidden(*_a, **_k):  # noqa: ANN002, ANN003
    raise AssertionError("the assist must not call a bound write/grade op")


def _stub_ctx():
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


# ── the deterministic value_presence (FLOOR) suggestion ────────────────────────


def test_suggest_value_presence_params_is_deterministic_and_correctly_keyed():
    """The helper returns the ValuePresence keys (``spec.py`` required: ``value_regex``; optional
    ``source_path``, default ``transcript``), is deterministic, and threads a source_hint into
    source_path. value_regex must be non-empty (else ValuePresence's reference_builder is inert)."""
    a = agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    b = agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    assert a == b  # deterministic
    assert set(a) == {"value_regex", "source_path"}
    assert a["value_regex"]  # required, non-empty
    assert a["source_path"] == "transcript"  # the executor default
    c = agent_assist.suggest_value_presence_params("X", source_hint="soap.note")
    assert c["source_path"] == "soap.note"


def test_suggest_contract_params_dispatches_by_type():
    """The dispatcher routes by contract_type: value_presence → the floor skeleton; presence_check
    (and any other/unknown type) → the presence_check skeleton (back-compat default)."""
    vp = agent_assist.suggest_contract_params("value_presence", "DISSENT_ERASURE")
    assert vp == agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    pc = agent_assist.suggest_contract_params("presence_check", "MEDICATION_NOT_IN_TRANSCRIPT")
    assert pc == agent_assist.suggest_presence_check_params("MEDICATION_NOT_IN_TRANSCRIPT")
    # an unspecified/unknown type falls back to presence_check (the historical default)
    default = agent_assist.suggest_contract_params("", "MEDICATION_NOT_IN_TRANSCRIPT")
    assert default == agent_assist.suggest_presence_check_params("MEDICATION_NOT_IN_TRANSCRIPT")


# ── author_contract: the agent picks the floor direction ───────────────────────


def test_author_contract_value_presence_default_fills_floor_skeleton():
    """S-BS-143 (the keystone): with ``contract_type='value_presence'`` and a named flag (no
    suggested_params), the handler DEFAULT-fills the value_presence FLOOR skeleton and the emitted
    part carries ``contract_type='value_presence'`` so the card opens on the floor type — not the
    presence_check suppress default. Still emit-only (the forbidden ctx proves no write)."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {
                "flag_code": "DISSENT_ERASURE",
                "contract_type": "value_presence",
                "source_hint": "transcript",
            },
        )
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert o["contract_type"] == "value_presence"
    assert o["suggested_params"] == agent_assist.suggest_value_presence_params(
        "DISSENT_ERASURE", source_hint="transcript"
    )
    assert set(o["suggested_params"]) == {"value_regex", "source_path"}


def test_author_contract_value_presence_with_empty_suggested_params_still_floor_fills():
    """The SDK-MCP {} omitted-dict trap (FAUTH-3a) also applies on the floor path: suggested_params={}
    must STILL default-fill the value_presence skeleton (not the inert default)."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {"flag_code": "DISSENT_ERASURE", "contract_type": "value_presence", "suggested_params": {}},
        )
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert o["contract_type"] == "value_presence"
    assert set(o["suggested_params"]) == {"value_regex", "source_path"}


# ── back-compat: the presence_check default path is byte-identical ──────────────


def test_author_contract_default_path_is_presence_check_and_omits_contract_type():
    """Back-compat (non-vacuous): with NO contract_type, the handler still default-fills the
    presence_check skeleton AND the part output OMITS contract_type entirely — so the un-typed path is
    the byte-identical FAUTH-3 shape and the FE keeps its presence_check default."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(ctx, {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT"})
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert "contract_type" not in o
    assert o["suggested_params"] == agent_assist.suggest_presence_check_params(
        "MEDICATION_NOT_IN_TRANSCRIPT"
    )


def test_author_contract_no_flag_stays_empty_even_with_type():
    """The "name the flag first" empty card is preserved even when a contract_type is passed: with no
    flag there is nothing to bind, so no skeleton pre-fill — but the chosen type still rides through so
    the card opens on the right type once the human names the flag."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(ctx, {"contract_type": "value_presence"})
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert "suggested_params" not in o
    assert o["contract_type"] == "value_presence"
    assert o["flag_code"] == ""


# ── A-SAFE: the extended schema carries no paid knob ───────────────────────────


def test_author_contract_schema_carries_contract_type_no_paid_knob():
    """AUTHOR_CONTRACT_SCHEMA gains contract_type (str), still NO PAID_KEY, still a single registered
    tool (extended, not duplicated)."""
    assert agent_tools.AUTHOR_CONTRACT_SCHEMA.get("contract_type") is str
    for key in agent_tools.PAID_KEYS:
        assert key not in agent_tools.AUTHOR_CONTRACT_SCHEMA
    names = [n for _h, n, *_ in agent_tools._TOOL_SPECS]
    assert names.count("author_contract") == 1
