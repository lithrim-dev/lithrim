"""INGEST-TEMPLATE-1: a registry of hand-authored, deterministic JUTE templates for KNOWN
ingest source shapes, routed in preference to LM-generation.

Ingestion LM-generates the JUTE transform for every novel shape — on a SIMPLE, KNOWN shape
(the agent message-trace ``{runs:[{id, messages, final, expected_*}]}``) the LM re-derives the
mapping and silently drops fields (it dropped the BYO ground-truth labels; INGEST-LABELS-1
patched that in Python). A hand-authored JUTE template is better on every axis: deterministic,
carries the labels BY CONSTRUCTION (JUTE-pure), pinned + auditable + still live-gated.

These cover:
  * ``_known_shape_template`` — the conservative matcher (matches the agent-trace shape; a
    near-miss → ``None`` → the existing REUSE/LM-gen path is untouched).
  * the curated template CONTENT — the label lines + the joinStr context + the case_id/response
    fields the LM-gen path dropped (MUTATION: dropping the two ``expected_*`` lines from
    ``_AGENT_TRACE_TEMPLATE`` turns the "carries labels" assertion RED).
  * the on-:3031 proof (live-gated; SKIPS cleanly when :3031 is unreachable — NOT a bare-CE gate).

Requires the ``[bff]`` extra (``import app`` is the BFF surface); skipped cleanly on a bare core.
Pack-independent (no healthcare reads).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

import app as bff  # noqa: E402

from lithrim_bench.verification import EtlpJuteClient  # noqa: E402

# The exact agent message-trace shape: {runs:[{id, messages, final, expected_*}]}. run_001 is a
# labeled positive (a non-empty flag set), run_002 a declared clean-negative ([] IS a label).
_AGENT_TRACE_SAMPLE = {
    "runs": [
        {
            "id": "run_001",
            "messages": [
                {"role": "system", "content": "SYS"},
                {"role": "user", "content": "USER"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
                {"role": "tool", "content": "TOOL"},
            ],
            "final": {"content": "the assistant final answer"},
            "expected_compliance_verdict": "reject",
            "expected_safety_flags": ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"],
        },
        {
            "id": "run_002",
            "messages": [
                {"role": "system", "content": "SYS2"},
                {"role": "user", "content": "USER2"},
            ],
            "final": {"content": "a faithful answer"},
            "expected_compliance_verdict": "approve",
            "expected_safety_flags": [],
        },
    ]
}


# ── matcher: matches the agent-trace shape ────────────────────────────────────


def test_known_shape_template_matches_the_agent_trace():
    """The agent message-trace shape resolves to a curated template (a ``str``)."""
    tpl = bff._known_shape_template(_AGENT_TRACE_SAMPLE)
    assert isinstance(tpl, str) and tpl
    assert tpl == bff._AGENT_TRACE_TEMPLATE


def test_known_shape_template_matches_a_minimal_single_run():
    """A minimal one-run trace (id + list messages + dict final) still matches."""
    sample = {"runs": [{"id": "r1", "messages": [{"role": "user", "content": "a"}],
                        "final": {"content": "b"}}]}
    assert bff._known_shape_template(sample) == bff._AGENT_TRACE_TEMPLATE


# ── matcher: conservative — a near-miss returns None (→ LM-gen) ────────────────


@pytest.mark.parametrize(
    "sample",
    [
        pytest.param({"no_runs": []}, id="non-runs-dict"),
        pytest.param({"runs": []}, id="empty-runs"),
        pytest.param({"runs": [{"id": "r1", "messages": [{"content": "a"}]}]}, id="missing-final"),
        pytest.param({"runs": [{"id": "r1", "final": {"content": "b"}}]}, id="missing-messages"),
        pytest.param({"runs": [{"messages": [], "final": {"content": "b"}}]}, id="missing-id"),
        pytest.param({"runs": [{"id": "", "messages": [], "final": {}}]}, id="falsy-id"),
        pytest.param({"runs": [{"id": "r1", "messages": "x", "final": {}}]}, id="messages-not-list"),
        pytest.param({"runs": [{"id": "r1", "messages": [], "final": "x"}]}, id="final-not-dict"),
        pytest.param({"runs": "x"}, id="runs-not-list"),
        pytest.param([{"id": "r1"}], id="top-level-list"),
        pytest.param("not a dict", id="non-dict"),
        pytest.param({"runs": [{"id": "r1", "messages": [], "final": {}}, 42]}, id="non-dict-entry"),
    ],
)
def test_known_shape_template_returns_none_for_a_near_miss(sample):
    """A conservative matcher: a non-matching variant → ``None`` → the existing REUSE/LM-gen
    path runs (unchanged for novel shapes)."""
    assert bff._known_shape_template(sample) is None


# ── the curated template CARRIES the labels by construction (the mutation target) ──


def test_curated_template_carries_labels_by_construction():
    """THE THESIS: the hand-authored template emits the BYO ground-truth labels JUTE-purely —
    the exact fields the LM-gen path dropped. MUTATION the driver names: drop the two
    ``expected_*`` lines from ``_AGENT_TRACE_TEMPLATE`` → these two assertions go RED."""
    tpl = bff._AGENT_TRACE_TEMPLATE
    assert "expected_compliance_verdict: $ e.expected_compliance_verdict" in tpl
    assert "expected_safety_flags: $ e.expected_safety_flags" in tpl


def test_curated_template_carries_the_grading_fields():
    """The grading fields the case needs: the case_id, the final response, and the joinStr
    context (system+user+tool, robust to the null-content tool-call message)."""
    tpl = bff._AGENT_TRACE_TEMPLATE
    assert "case_id: $ e.id" in tpl
    assert "response: $ e.final.content" in tpl
    assert 'context: $ joinStr("\\n\\n", e.messages.*.content)' in tpl
    assert "$map: $ resource.runs" in tpl


# ── live-gated on-:3031 proof (SKIPS cleanly when :3031 is unreachable) ────────


def _jute_reachable() -> bool:
    try:
        spec = EtlpJuteClient(base_url=bff._jute_base_url()).get_dsl_spec()
        return bool(spec)
    except Exception:  # noqa: BLE001 — any transport failure means :3031 is down → skip
        return False


@pytest.mark.skipif(not _jute_reachable(), reason="needs a live JUTE mapper on :3031")
def test_curated_template_compiles_and_carries_labels_on_3031():
    """The on-:3031 proof: the curated template compiles (``error`` falsy) and the output cases
    carry case_id, the joinStr context (system+SEP+user+SEP+tool, skipping the null-content
    tool-call message), the final response, AND the ``expected_safety_flags`` VERBATIM (run_001 →
    the two flags, run_002 → the empty clean-negative). This is the by-construction label carry.

    The joinStr separator is the literal two-char ``\\n`` sequence the YAML carries (a REAL newline
    inside a JUTE quoted scalar fails to compile — CONFIRMED live; the driver's ``\\\\n\\\\n``
    Python escape is the only variant that compiles), so the context separator is ``\\n\\n``
    verbatim, NOT a parsed newline."""
    sep = "\\n\\n"  # the literal backslash-n-backslash-n joinStr separator (proven-live)
    client = EtlpJuteClient(base_url=bff._jute_base_url())
    out = client.test_template(bff._AGENT_TRACE_TEMPLATE, _AGENT_TRACE_SAMPLE)
    assert not out.get("error"), out.get("error")
    cases = out.get("output")
    assert isinstance(cases, list) and len(cases) == 2
    by_id = {c.get("case_id"): c for c in cases}

    c1 = by_id["run_001"]
    assert c1["response"] == "the assistant final answer"
    assert c1["context"] == sep.join(["SYS", "USER", "TOOL"])  # null tool-call message skipped
    assert c1["expected_compliance_verdict"] == "reject"
    assert c1["expected_safety_flags"] == ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"]

    c2 = by_id["run_002"]
    assert c2["response"] == "a faithful answer"
    assert c2["context"] == sep.join(["SYS2", "USER2"])  # the 2-message no-tool trace maps cleanly
    assert c2["expected_compliance_verdict"] == "approve"
    assert c2["expected_safety_flags"] == []
