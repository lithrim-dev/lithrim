"""NARR-2 acceptance: the ingest_cases SDK-MCP tool (the 17th) — drop JSON → generate →
live-gate → PIN → audited corpus upsert, with deny-default + A-SAFE held.

The trust posture (mirrors add_grounding_contract): the handler calls the bound
ctx.ingest_cases(...) and SURFACES a structured error (invariant failed / :3031 down /
nothing pinned) exactly as add_grounding_contract_handler surfaces 404/422 — never
bypassed, never a paid run; on accept it emits a `corpus` focus part and returns the case
count. On the error path NOTHING is pinned/persisted/upserted (A3 negative).

Layers (by import weight, mirroring test_flag_crud.py):
  - STRUCTURAL / A-SAFE (plain core — agent package is SDK-free + fastapi-free): the 17-tool
    bound; ingest_cases carries NO paid knob; the S-BS-90 deny hook covers it (byte-frozen).
  - HANDLER (plain core, stub ctx): accept pins-once + corpus-focus part (A3); an invariant
    failure surfaces a structured error and pins NOTHING (A3 negative).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# the agent package is import-safe on the default core (SDK lazy; no fastapi at module level),
# so the STRUCTURAL + HANDLER layers run in BOTH suites (not only under [bff]).
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _deny_non_lithrim  # noqa: E402

# ── STRUCTURAL / A-SAFE (plain core — SDK-free) ──────────────────────────────────


def test_registry_adds_exactly_ingest_cases_and_deny_hook_frozen():
    """A5: _TOOL_SPECS grew by exactly one (16 → 17) and contains ingest_cases; NO tool
    carries a paid knob (the S-BS-81 guarantee generalized, non-vacuous over the full set);
    the A-SAFE deny hook passes ingest_cases (allowed) yet still DENIES a built-in (byte-
    frozen — the 17th tool is bounded for free)."""
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert len(names) == 19 and len(set(names)) == 19, names  # +META-VERDICT-1 record_meta_verdict
    assert "ingest_cases" in names
    assert "record_meta_verdict" in names

    for _h, n, _d, schema in agent_tools._TOOL_SPECS:  # NON-VACUOUS: includes the new tool
        assert [k for k in agent_tools.PAID_KEYS if k in schema] == [], (n, schema)

    by_name = {n: schema for _h, n, _d, schema in agent_tools._TOOL_SPECS}
    assert "json" in by_name["ingest_cases"]  # the JSON dump to ingest
    assert "ingest_cases" in agent_tools.ToolContext.__dataclass_fields__

    def decision(out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    allow = asyncio.run(
        _deny_non_lithrim({"tool_name": "mcp__lithrim__ingest_cases"}, "t", {"signal": None})
    )
    assert decision(allow) is None  # no decision == allowed
    deny = asyncio.run(_deny_non_lithrim({"tool_name": "Bash"}, "t", {"signal": None}))
    assert decision(deny) == "deny"


# ── HANDLER (plain core, stub ctx) ───────────────────────────────────────────────


def _stub_ctx(*, ingest_cases=None):
    def _noop(*_a, **_k):
        return {"actor": {"id": "sme"}}

    return agent_tools.ToolContext(
        author_judge=_noop,
        get_judge=_noop,
        run_eval_replay=_noop,
        get_agent=_noop,
        author_flag=_noop,
        review_runs=_noop,
        run_eval_pack=_noop,
        assemble_agent=_noop,
        delete_judge=_noop,
        create_flag=_noop,
        delete_flag=_noop,
        put_grounding_contract=_noop,
        kb_context=_noop,
        ingest_cases=ingest_cases or _noop,
        list_cases=_noop,
        record_meta_verdict=_noop,
    )


def test_ingest_presents_then_pins_on_accept():
    """A3: on accept the handler calls the bound ctx.ingest_cases (which generates → live-
    gates → PINs → upserts the corpus + writes one AuditRecord), emits a `corpus` focus
    part, and returns the case count. The handler holds NO pin/persist logic of its own —
    that is the bound op's, exercised end-to-end in the [bff] layer."""
    seen: dict = {}

    def fake(json_dump, extraction_rules, agent):
        seen["json"] = json_dump
        seen["rules"] = extraction_rules
        seen["agent"] = agent
        return {
            "cases": [{"case_id": "x-1"}, {"case_id": "x-2"}],
            "mapping_id": 555,
            "count": 2,
        }

    ctx = _stub_ctx(ingest_cases=fake)
    out = asyncio.run(
        agent_tools.ingest_cases_handler(
            ctx, {"json": '{"resource": {"id": "x"}}', "extraction_rules": "per-scene"}
        )
    )
    assert "is_error" not in out
    assert "2" in out["content"][0]["text"]  # the case count
    assert seen["json"] == '{"resource": {"id": "x"}}'
    assert seen["rules"] == "per-scene"
    # a corpus focus part was emitted (the gen-UI directive opening the corpus tab)
    parts = [p for p in ctx.parts if p.get("output", {}).get("tab") == "corpus"]
    assert parts, ctx.parts


def test_ingest_pins_nothing_on_invariant_fail():
    """A3 negative: an invariant failure / :3031-down path surfaces a STRUCTURED error and
    pins NOTHING — no corpus part is emitted, the run is not a paid one, the error text
    states nothing was persisted (the same surface add_grounding_contract uses)."""

    def boom(json_dump, extraction_rules, agent):
        raise RuntimeError(
            "extraction invariant failed: 3 of 5 records null on required keys; nothing pinned"
        )

    ctx = _stub_ctx(ingest_cases=boom)
    out = asyncio.run(agent_tools.ingest_cases_handler(ctx, {"json": "{}"}))
    assert out.get("is_error") is True
    assert "nothing pinned" in out["content"][0]["text"].lower()
    # NOTHING was emitted on the error path (no corpus focus, no run)
    assert ctx.parts == []


def test_ingest_requires_json():
    """A malformed call with no JSON is refused with a structured error, never a crash and
    never a pin."""
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.ingest_cases_handler(ctx, {}))
    assert out.get("is_error") is True
    assert ctx.parts == []
