"""NARR-5-CRIT-b — the agent SURFACES the CriterionBuilder widget inline (emit-only).

The conversational author-a-gradeable-criterion-by-talking surface, mirroring FAUTH-1's
``author_contract`` → ``contract_builder_part`` → ContractBuilder. The SPINE/CONTAINMENT
invariant (re-affirmed by the holistic critic): the agent EMITS a pre-filled CriterionBuilder
card and performs NO bound write op — the *human's* Save (``POST /v1/criterion``, the sanctioned
snapshot writer) is the SOLE write of the contract-of-record. The agent never mints a code itself.

Covers: the adapter-part shape; the handler emits exactly one part + writes NOTHING (emit-only,
proven via a ToolContext whose every bound op raises); A-SAFE (no paid knob in the schema, the
all-schemas sweep, registered in _TOOL_SPECS exactly once).
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


def test_criterion_builder_part_carries_seed():
    part = agent_adapter.criterion_builder_part(
        "ws0_default", code="EVERY_DOSE_IN_SOAP", tier="TIER_2", owner_role="faithfulness_judge"
    )
    assert part["type"] == "tool-criterion_builder"
    assert part["state"] == "output-available"
    # CRITERION-TEXT-1: the part now also seeds the criterion TEXT (agent-drafted, human-approved).
    assert part["output"] == {
        "agent": "ws0_default",
        "code": "EVERY_DOSE_IN_SOAP",
        "tier": "TIER_2",
        "owner_role": "faithfulness_judge",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
    }
    assert part.get("show_intent") == "auto"  # an authoring card the agent leads with → primary


def _stub_ctx():
    """A ToolContext whose every bound op RAISES — proves the SURFACE tool writes NOTHING."""

    def _forbidden(*_a, **_k):
        raise AssertionError("author_criterion must not call a bound write/grade op")

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


def test_author_criterion_emits_part_and_writes_nothing():
    ctx = _stub_ctx()
    out = asyncio.run(
        agent_tools.author_criterion_handler(
            ctx, {"code": "EVERY_DOSE_IN_SOAP", "tier": "TIER_2", "owner_role": "faithfulness_judge"}
        )
    )
    assert "is_error" not in out
    assert out["content"][0]["text"].strip()
    parts = [p for p in ctx.parts if p.get("type") == "tool-criterion_builder"]
    assert len(ctx.parts) == 1 and len(parts) == 1, ctx.parts
    o = parts[0]["output"]
    assert o == {
        "agent": "ws0_default",
        "code": "EVERY_DOSE_IN_SOAP",
        "tier": "TIER_2",
        "owner_role": "faithfulness_judge",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
    }


def test_author_criterion_defaults_to_empty_seed():
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.author_criterion_handler(ctx, {}))
    assert "is_error" not in out
    parts = [p for p in ctx.parts if p.get("type") == "tool-criterion_builder"]
    assert len(parts) == 1
    assert parts[0]["output"] == {
        "agent": "ws0_default",
        "code": "",
        "tier": "",
        "owner_role": "",
        "definition": "",
        "when_to_use": "",
        "when_NOT_to_use": "",
    }


def test_author_criterion_schema_has_no_paid_knob():
    for key in agent_tools.PAID_KEYS:
        assert key not in agent_tools.AUTHOR_CRITERION_SCHEMA
    for _h, name, _desc, schema in agent_tools._TOOL_SPECS:
        for key in agent_tools.PAID_KEYS:
            assert key not in schema, (name, key)


def test_author_criterion_registered_in_tool_specs_exactly_once():
    names = [name for _h, name, *_ in agent_tools._TOOL_SPECS]
    assert names.count("author_criterion") == 1
    spec = next(s for s in agent_tools._TOOL_SPECS if s[1] == "author_criterion")
    assert spec[3] is agent_tools.AUTHOR_CRITERION_SCHEMA
    assert spec[0] is agent_tools.author_criterion_handler


def test_toolcontext_carries_no_criterion_write_op():
    """CONTAINMENT INVARIANT (cold-critic seam, NARR-5-CRIT-b): the agent's ToolContext must NEVER
    carry a criterion-write op — author_criterion is emit-only and the human's Save (POST /v1/criterion)
    is the SOLE write of the contract-of-record. Pin it STRUCTURALLY so a future op-binding can't
    silently weaken the containment (the emit-only stub-ctx test only checks the EXISTING ops raise)."""
    fields = set(agent_tools.ToolContext.__dataclass_fields__)
    assert not any("criterion" in f for f in fields), fields
