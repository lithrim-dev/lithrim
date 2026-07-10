"""PHASE2-WIRE — the agent SURFACES the JudgeBuilder card inline (emit-only).

The last-mile conversational "create a new judge by talking" surface, mirroring NARR-5-CRIT-b's
``author_criterion`` → ``criterion_builder_part`` → CriterionBuilder. The SPINE/CONTAINMENT
invariant: the agent EMITS a JudgeBuilder card (seeded with the role id) and performs NO bound
write op — the *human's* "Create judge" click (``POST /v1/judges``, the sanctioned snapshot writer)
is the SOLE write. The agent never mints the judge itself.

Distinct from ``author_judge`` (which ASSIGNS a lens to an EXISTING role → tool-judge_editor):
``create_judge`` CREATES a NEW judge role / new council voice via the card (→ tool-judge_builder).

Covers: the adapter-part shape; the handler emits exactly one part + writes NOTHING (emit-only,
proven via a ToolContext whose every bound op raises); A-SAFE (no paid knob in the schema, the
all-schemas sweep, registered in _TOOL_SPECS exactly once); the CONTAINMENT structural pin (no
ToolContext field can carry a judge-create write op).
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


def test_judge_builder_part_carries_seed():
    part = agent_adapter.judge_builder_part("ws0_default", role="escalation_judge")
    assert part["type"] == "tool-judge_builder"
    assert part["state"] == "output-available"
    assert part["output"] == {"agent": "ws0_default", "role": "escalation_judge"}
    assert part.get("show_intent") == "auto"  # an authoring card the agent leads with → primary


def _stub_ctx():
    """A ToolContext whose every bound op RAISES — proves the SURFACE tool writes NOTHING."""

    def _forbidden(*_a, **_k):
        raise AssertionError("create_judge must not call a bound write/grade op")

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


def test_create_judge_emits_part_and_writes_nothing():
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.create_judge_handler(ctx, {"role": "escalation_judge"}))
    assert "is_error" not in out
    assert out["content"][0]["text"].strip()
    parts = [p for p in ctx.parts if p.get("type") == "tool-judge_builder"]
    assert len(ctx.parts) == 1 and len(parts) == 1, ctx.parts
    assert parts[0]["output"] == {"agent": "ws0_default", "role": "escalation_judge"}


def test_create_judge_defaults_to_empty_role():
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.create_judge_handler(ctx, {}))
    assert "is_error" not in out
    parts = [p for p in ctx.parts if p.get("type") == "tool-judge_builder"]
    assert len(parts) == 1
    assert parts[0]["output"] == {"agent": "ws0_default", "role": ""}


def test_create_judge_schema_has_no_paid_knob():
    for key in agent_tools.PAID_KEYS:
        assert key not in agent_tools.CREATE_JUDGE_SCHEMA
    for _h, name, _desc, schema in agent_tools._TOOL_SPECS:
        for key in agent_tools.PAID_KEYS:
            assert key not in schema, (name, key)


def test_create_judge_registered_in_tool_specs_exactly_once():
    names = [name for _h, name, *_ in agent_tools._TOOL_SPECS]
    assert names.count("create_judge") == 1
    spec = next(s for s in agent_tools._TOOL_SPECS if s[1] == "create_judge")
    assert spec[3] is agent_tools.CREATE_JUDGE_SCHEMA
    assert spec[0] is agent_tools.create_judge_handler


def test_toolcontext_carries_no_judge_create_write_op():
    """CONTAINMENT INVARIANT (PHASE2-WIRE): the agent's ToolContext must NEVER carry a judge-create
    op — create_judge is emit-only and the human's "Create judge" click (POST /v1/judges) is the SOLE
    write of the new council voice. Pin it STRUCTURALLY so a future op-binding can't silently weaken
    the containment (the emit-only stub-ctx test only checks the EXISTING ops raise)."""
    fields = set(agent_tools.ToolContext.__dataclass_fields__)
    assert not any(("judge_builder" in f) or ("create_judge" in f) for f in fields), fields
