"""SHEPHERD-1 (W5): the proactive plan-aware shepherd system prompt (W2).

Pure prompt-construction assertions over ``apps/bff/agent/loop._system_prompt`` — no SDK,
no network, no [agent] extra. The shepherd stanza is a SUPERSET appended to the base
persona + HONESTY contract + active-agent naming, so a non-onboarding chat is unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import loop  # noqa: E402  (SDK-free: _system_prompt is a pure string builder)


def test_shepherd_prompt_carries_the_journey_order_and_next_step_instruction():
    p = loop._system_prompt("eval-7")
    # W2: knows the journey order.
    assert "Domain -> Judges -> Ground truth" in p
    assert "Run -> Review" in p
    # W2: leads — finds + proposes the next incomplete step, one at a time.
    assert "propose the next incomplete step" in p
    # SHEPHERD-1b (W2a, S-BS-150): the one-step rule is now FOREGROUNDED as an imperative
    # clause (one config PROPOSAL per turn, then STOP) rather than the buried mid-stanza line.
    assert "ONE STEP PER TURN" in p
    assert "EXACTLY ONE" in p and "then STOP" in p
    assert "first incomplete" in p.lower()
    # W2: proposes (the Save is the gate), never auto-commits.
    assert "PROPOSE, never auto-commit" in p


def test_shepherd_prompt_leads_a_fresh_eval_but_degrades_when_complete():
    p = loop._system_prompt("eval-7")
    # W2: opens with guidance on a fresh/empty eval.
    assert "fresh/empty eval" in p
    assert "set up your first evaluation" in p
    # back-compat: degrades to the reactive operator posture once setup is complete.
    assert "already COMPLETE" in p
    assert "reactive operator posture" in p
    # W2: stays honest — never claims a missing capability / an undone step.
    assert "never claim a capability you do not have" in p


def test_shepherd_prompt_is_a_superset_back_compat_invariants_intact():
    """The base persona, the HONESTY contract, and the active-agent naming all survive —
    a non-onboarding chat is behavior-unchanged (the stanza only ADDS)."""
    p = loop._system_prompt("eval-7")
    # base persona (the _SYSTEM_PROMPT head).
    assert "You are Lithrim's setup assistant" in p
    # the HONESTY-IS-THE-PRODUCT contract (load-bearing — must never be dropped).
    assert "HONESTY IS THE PRODUCT" in p
    assert "A manufactured win is a product FAILURE" in p
    # the CHATBIND-1 active-agent naming (the model targets the rail-selected agent).
    assert "`eval-7`" in p
    assert "Operate on" in p
    # the shepherd stanza is APPENDED after the base — its head appears after the persona head.
    assert p.index("SHEPHERD THE ONBOARDING") > p.index("You are Lithrim's setup assistant")
    assert p.index("SHEPHERD THE ONBOARDING") > p.index("HONESTY IS THE PRODUCT")


def test_shepherd_prompt_names_the_active_agent_distinctly():
    """NON-VACUOUS: the active-agent naming is per-call, not a literal — a different agent
    name appears, the prior does not."""
    a = loop._system_prompt("agent_alpha")
    b = loop._system_prompt("agent_beta")
    assert "`agent_alpha`" in a and "`agent_beta`" not in a
    assert "`agent_beta`" in b and "`agent_alpha`" not in b
    # both still carry the shepherd stanza (it is name-independent).
    assert "SHEPHERD THE ONBOARDING" in a
    assert "SHEPHERD THE ONBOARDING" in b
