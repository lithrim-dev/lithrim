"""FAUTH-3 (G2): the ASSIST keystone — prose → presence_check params, spine-invariant safe.

A physician describes a criterion; the agent cites the org policy via the retrieval-only
``kb_context``, then surfaces the ContractBuilder PRE-FILLED with suggested ``presence_check``
params (``author_contract`` with ``suggested_params``). The suggestion is a DRAFT the human edits
and Saves; the assist NEVER auto-writes the ontology and NEVER enters ``ground()``.

Covers A1 (the SPINE GUARD — the load-bearing test, non-vacuous BOTH ways), A3 (author_contract
threads suggested_params + stays emit-only), A4 (the deterministic prose→params suggestion shape),
A7 (A-SAFE: the extended schema carries no paid knob). SDK-free (the handlers are exercised without
the SDK, mirroring tests/bff/test_contract_builder_part.py).
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

# ── A4: the deterministic prose→params suggestion (no LLM, no network) ─────────


def test_suggest_presence_check_params_is_deterministic_and_correctly_keyed():
    """A4: the helper returns EXACTLY the PresenceCheck param keys (grounding.py:134-137:
    med_source[req], dosage_regex[req], token_min_len, noise_tokens), is deterministic (same
    input → same output), and threads an agent-supplied chart-path source_hint."""
    a = agent_assist.suggest_presence_check_params("MEDICATION_NOT_IN_TRANSCRIPT")
    b = agent_assist.suggest_presence_check_params("MEDICATION_NOT_IN_TRANSCRIPT")
    assert a == b  # deterministic
    assert set(a) == {"med_source", "dosage_regex", "token_min_len", "noise_tokens"}
    # the two PresenceCheck-REQUIRED keys are present + non-empty (else PresenceCheck KeyErrors).
    assert a["med_source"] and a["dosage_regex"]
    assert isinstance(a["token_min_len"], int)
    assert isinstance(a["noise_tokens"], list)
    # the agent supplies the chart path from the prose; it flows through verbatim.
    c = agent_assist.suggest_presence_check_params("X", source_hint="patient.meds")
    assert c["med_source"] == "patient.meds"


# ── A1: the SPINE GUARD (load-bearing, non-vacuous both ways) ──────────────────


class _Spy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_a, **_k):  # noqa: ANN002, ANN003
        self.calls += 1
        return {"ok": True}


def _forbidden(*_a, **_k):  # noqa: ANN002, ANN003
    raise AssertionError("the assist must not call a bound write/grade op")


def _spy_ctx(store, save_spy, kb_chunks):
    """A ToolContext where put_grounding_contract is a SPY that mutates ``store`` and kb_context
    returns canned chunks; every OTHER bound op RAISES (so any stray write is caught)."""

    def _save(**kw):
        save_spy()
        store.append({"flag_code": kw.get("flag_code"), "contract_type": kw.get("contract_type")})
        return {"flag_code": kw.get("flag_code"), "replaced": False}

    def _kb(**_kw):
        return kb_chunks

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
        put_grounding_contract=_save,  # the ONLY non-forbidden write op (a spy over `store`)
        kb_context=_kb,
        ingest_cases=_forbidden,
        list_cases=_forbidden,
        record_meta_verdict=_forbidden,
        default_agent="ws0_default",
    )


def test_spine_guard_assist_sequence_writes_nothing_explicit_save_does():
    """A1 (THE SPINE INVARIANT, non-vacuous BOTH ways): running the assist sequence —
    kb_context (cite the policy) then author_contract(suggested_params) (surface the pre-filled
    builder) — mutates NO ontology store and fires NO write op; an EXPLICIT put_grounding_contract
    for the same flag DOES mutate + DOES fire the write. The non-vacuous twin proves the guard
    catches a real write, not a vacuous no-op."""
    store, save_spy = [], _Spy()
    chunks = [{"text": "HIPAA §164.312(b) audit controls ...", "score": 0.91}]
    ctx = _spy_ctx(store, save_spy, chunks)
    sp = agent_assist.suggest_presence_check_params(
        "MEDICATION_NOT_IN_TRANSCRIPT", source_hint="transcript.text"
    )

    # (1) the agent cites the org policy — retrieval-only
    kb = asyncio.run(
        agent_tools.kb_context_handler(ctx, {"query": "medication not in transcript"})
    )
    assert "is_error" not in kb
    # (2) the agent surfaces the PRE-FILLED builder
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {
                "flag_code": "MEDICATION_NOT_IN_TRANSCRIPT",
                "suggested_params": sp,
                "question": "Is the flagged medication present in the record?",
            },
        )
    )
    assert "is_error" not in out

    # SPINE INVARIANT: the assist wrote NOTHING.
    assert store == [], "the assist must not write a contract"
    assert save_spy.calls == 0, "the assist must not call put_grounding_contract"

    # NON-VACUOUS: an explicit human Save DOES write (so the guard above is not vacuously true).
    ctx.put_grounding_contract(
        flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
        contract_type="presence_check",
        params=sp,
        question="q",
        version="v1",
        agent="ws0_default",
    )
    assert save_spy.calls == 1
    assert len(store) == 1 and store[0]["contract_type"] == "presence_check"


# ── A3: author_contract threads suggested_params, still emit-only ──────────────


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


def test_author_contract_threads_suggested_params_emit_only():
    """A3: author_contract with suggested_params emits a tool-contract_builder part whose output
    carries suggested_params (+ question) alongside {agent, flag_code}, and calls NO bound write op
    (the forbidden ctx proves emit-only)."""
    ctx = _stub_ctx()
    sp = {
        "med_source": "transcript.text",
        "dosage_regex": "x",
        "token_min_len": 4,
        "noise_tokens": [],
    }
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT", "suggested_params": sp, "question": "q?"},
        )
    )
    assert "is_error" not in out
    parts = [p for p in ctx.parts if p.get("type") == "tool-contract_builder"]
    assert len(parts) == 1
    o = parts[0]["output"]
    assert o["agent"] == "ws0_default"
    assert o["flag_code"] == "MEDICATION_NOT_IN_TRANSCRIPT"
    assert o["suggested_params"] == sp
    assert o["question"] == "q?"


def test_author_contract_builds_presence_check_skeleton_from_source_hint():
    """A4/A3: when the agent supplies a chart-path ``source_hint`` (lifted from the prose) WITHOUT
    an explicit suggested_params, the handler builds the DETERMINISTIC presence_check skeleton via
    the helper and threads it into the part — so the param KEYS are correct-by-construction (not
    LLM-hallucinated). Still emit-only (the forbidden ctx proves no write); the human edits + Saves."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx, {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT", "source_hint": "transcript.text"}
        )
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert o["suggested_params"] == agent_assist.suggest_presence_check_params(
        "MEDICATION_NOT_IN_TRANSCRIPT", source_hint="transcript.text"
    )


def test_author_contract_default_fills_skeleton_for_named_flag():
    """A1/FAUTH-3a (the reliability fix): for a NAMED flag with NO suggested_params and NO
    source_hint, author_contract DEFAULT-fills the deterministic presence_check skeleton (correct
    keys by construction) — so the pre-fill no longer depends on the live agent remembering to pass
    source_hint (which it did not, live). Still emit-only (the forbidden ctx proves no write)."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(ctx, {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT"})
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert o["suggested_params"] == agent_assist.suggest_presence_check_params(
        "MEDICATION_NOT_IN_TRANSCRIPT"
    )
    # the correct PresenceCheck keys, not the inert {"source":"response.claims"} default.
    assert set(o["suggested_params"]) == {"med_source", "dosage_regex", "token_min_len", "noise_tokens"}


def test_author_contract_empty_suggested_params_still_default_fills():
    """FAUTH-3a (the live SDK trap, found in A-LIVE): the SDK-MCP layer passes an EMPTY dict {} for an
    omitted dict-typed schema param (NOT None) — so a real named-flag call arrives as
    suggested_params={}. Treat {} as 'no suggestion' and STILL default-fill the deterministic
    skeleton; otherwise the card shows the inert {"source":"response.claims"} default (exactly the
    live bug). Belt: source_hint passed as "" (the str omitted-param default) must also not break it."""
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_contract_handler(
            ctx,
            {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT", "suggested_params": {}, "source_hint": ""},
        )
    )
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert set(o["suggested_params"]) == {"med_source", "dosage_regex", "token_min_len", "noise_tokens"}


def test_author_contract_no_flag_stays_empty():
    """FAUTH-3a: the "name the flag first" case is preserved — with NO flag_code there is nothing to
    bind a presence_check to, so the card stays EMPTY (no skeleton pre-fill)."""
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.author_contract_handler(ctx, {}))
    assert "is_error" not in out
    o = next(p for p in ctx.parts if p.get("type") == "tool-contract_builder")["output"]
    assert o == {"agent": "ws0_default", "flag_code": ""}


def test_author_contract_schema_carries_suggested_params_no_paid_knob():
    """A7 (A-SAFE, non-vacuous): AUTHOR_CONTRACT_SCHEMA gains suggested_params (dict) + question
    (str), still NO PAID_KEY anywhere in _TOOL_SPECS, and author_contract stays a single registered
    tool (extended, not duplicated → tool count unchanged)."""
    assert agent_tools.AUTHOR_CONTRACT_SCHEMA.get("suggested_params") is dict
    assert agent_tools.AUTHOR_CONTRACT_SCHEMA.get("source_hint") is str
    for key in agent_tools.PAID_KEYS:
        assert key not in agent_tools.AUTHOR_CONTRACT_SCHEMA
    for _h, name, _desc, schema in agent_tools._TOOL_SPECS:
        for key in agent_tools.PAID_KEYS:
            assert key not in schema, (name, key)
    names = [n for _h, n, *_ in agent_tools._TOOL_SPECS]
    assert names.count("author_contract") == 1
