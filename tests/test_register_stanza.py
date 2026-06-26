"""UX-COPY-REGISTER-1: the "speak to a person" register stanza (a prompt-contract test).

Pure prompt-construction assertions over ``apps/bff/agent/loop._system_prompt`` — no SDK,
no network, no [agent] extra. The register stanza is a SUPERSET appended to the base persona
+ HONESTY contract + shepherd guidance, so the existing behavior is unchanged; this only adds
the rule that governs what the model SAYS (it still calls the tools by their exact names).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import loop  # noqa: E402  (SDK-free: _system_prompt is a pure string builder)


def test_register_stanza_is_present_in_the_assembled_prompt():
    p = loop._system_prompt("eval-7")
    # the stanza header is present and reachable in the assembled system prompt.
    assert "HOW TO SPEAK TO THE USER" in p
    # the constant is what got appended (not some near-duplicate string).
    assert loop._REGISTER_STANZA in p


def test_register_stanza_instructs_the_translation_map():
    p = loop._system_prompt("eval-7")
    # the locked terminology map is taught: council/judge/verdict/states/lens/ontology/
    # contract/corpus all map to their user-facing words.
    assert "the reviewers" in p
    assert "a reviewer" in p
    assert "the result" in p
    assert "flagged" in p and "passed" in p and "needs a look" in p
    assert "what a reviewer checks for" in p
    assert "your checks" in p
    assert "fact-check" in p
    assert "saved cases" in p


def test_register_stanza_forbids_leaking_the_machinery():
    p = loop._system_prompt("eval-7")
    # never print tool names / HTTP / ports / hex-ids; prefer the action verb.
    assert "NEVER print a tool/function name" in p
    assert "focus_artifact" in p  # named as a thing to NOT print
    assert "open the report" in p
    assert "run the evaluation" in p
    assert "grade this case" in p
    # a run is "your latest run", not a hex id.
    assert "your latest run" in p


def test_register_stanza_does_not_relax_honesty():
    """The translation layer must NOT round a flagged result up to a pass — it sits beneath
    the load-bearing HONESTY contract, which is still present and ordered above it."""
    p = loop._system_prompt("eval-7")
    assert "HONESTY IS THE PRODUCT" in p
    assert "does NOT relax the HONESTY contract" in p
    # ordering: the register rule is appended AFTER the honesty contract + the shepherd stanza.
    assert p.index("HOW TO SPEAK TO THE USER") > p.index("HONESTY IS THE PRODUCT")
    assert p.index("HOW TO SPEAK TO THE USER") > p.index("SHEPHERD THE ONBOARDING")
