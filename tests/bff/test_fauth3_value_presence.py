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
    """S-BS-143b: the helper returns a GRADE-VALID floor skeleton, deterministically. Beyond the
    ValuePresence reference keys (``value_regex`` required; ``source_path``, ``match``), it MUST carry
    the INJECTION keys the floor needs to turn a violation into a BLOCK — ``inject_flag_code`` (the code
    the floor injects on absence; = the flag) + ``inject_severity`` (grounding.py:716-719 reads BOTH;
    without them GRADE-GUARD-1 skip-logs the contract as malformed → it never flips, the S-BS-143b bug).
    source_hint threads into source_path."""
    a = agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    b = agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    assert a == b  # deterministic
    assert set(a) == {"value_regex", "source_path", "match", "inject_flag_code", "inject_severity"}
    assert a["value_regex"]  # required, non-empty
    assert a["source_path"] == "transcript"  # the executor default
    assert a["match"] == "any"  # concept co-presence (FAUTH-4b: tolerate paraphrase, no false-block)
    assert a["inject_flag_code"] == "DISSENT_ERASURE"  # the floor injects THIS code on absence
    assert a["inject_severity"] == "HIGH"
    c = agent_assist.suggest_value_presence_params("X", source_hint="soap.note")
    assert c["source_path"] == "soap.note"
    assert c["inject_flag_code"] == "X"  # tracks the flag, not a hardcode


def test_value_presence_skeleton_grades_valid_and_injects(monkeypatch):
    """S-BS-143b (the end-to-end proof the rehearsal MISSED): a value_presence floor authored with
    NOTHING but the assist skeleton must actually FLIP a council APPROVE → BLOCK. Build a contract from
    suggest_value_presence_params alone, run the real ``ground()`` over a council-PASS + a case whose
    transcript states a refusal the artifact erased — the floor must INJECT the block (not skip-log as
    malformed). This is the regression that the prior 'card shows value_presence' check did not catch."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "narrative")  # value_presence is a narrative-pack floor
    import json as _json

    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.ontology import from_dict

    params = agent_assist.suggest_value_presence_params("DISSENT_ERASURE")
    # Build on the committed narrative ontology (full envelope) + append the net-new flag + the
    # floor authored from NOTHING but the assist skeleton.
    raw = _json.loads((REPO_ROOT / "packs" / "narrative" / "ontology.json").read_text())
    raw["flags"].append(
        {
            "flag": "DISSENT_ERASURE",
            "category": "completeness",
            "definition": "An explicit patient refusal in the transcript erased from the note.",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": ["policy_judge"],
            "tier": "TIER_1",
            "gradeable": True,
        }
    )
    raw.setdefault("verification_contracts", []).append(
        {
            "flag_code": "DISSENT_ERASURE",
            "question": "Is the patient's refusal preserved in the note?",
            "contract_type": "value_presence",
            "version": "v1",
            "params": params,
        }
    )
    ont = from_dict(raw)
    case = {
        "transcript": "Patient: I don't want any tetanus vaccine.",
        "artifacts": [{"content": "S: wooden splinter removed and cleaned. No vaccine discussion recorded."}],
    }
    council_approve = {
        "verdict": "PASS",
        "findings": [],
        "semantic": {"judge_votes": [{"judge_role": "policy_judge", "vote": "PASS", "findings": []}]},
    }
    g = ground(council_approve, case, ontology=ont)
    injected = [b["injected_finding"]["code"] for b in g.floor_blocks if b["injected_finding"] is not None]
    assert injected == ["DISSENT_ERASURE"], "the assist skeleton must produce a floor that INJECTS the block"
    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"  # the flip is real


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
    # S-BS-143b: a GRADE-VALID floor — the injection keys must ride so the floor actually flips.
    assert set(o["suggested_params"]) == {
        "value_regex", "source_path", "match", "inject_flag_code", "inject_severity"
    }
    assert o["suggested_params"]["inject_flag_code"] == "DISSENT_ERASURE"


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
    assert set(o["suggested_params"]) == {
        "value_regex", "source_path", "match", "inject_flag_code", "inject_severity"
    }


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
