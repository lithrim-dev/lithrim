"""REPRO-1 R4c — ``terminology_subsumption``: the CORE-GENERIC twin of the pack's clinical
floor. Grounds the FLAGGED SPAN's term(s) against the case's record concepts by is-a
subsumption through a USER-CONNECTED ``kind:tool`` terminology server — zero domain strings in
core: the tool id, the record path, and the op names are all SME-authored params; the
subsumption relation comes from the connected ontology, never from code.

Span-driven BY CONSTRUCTION (the SPAN-BIND-1 lesson baked in): the candidate terms ARE the
finding's own evidence-span quotes — this oracle can only speak to what the finding actually
flagged. Conservative: suppress ONLY when every candidate resolves AND is ==/subsumed-by a
record concept; no candidates / unresolved / un-subsumed / tool-absent → the finding STANDS
(never cleared by silence). $0/offline — the tool transport is faked."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grounding import (  # noqa: E402
    _CONTRACT_EXECUTORS,
    TerminologySubsumption,
)
from lithrim_bench.harness.ontology import VerificationContractDecl  # noqa: E402

_CONCEPTS = {"alzheimer's disease": 26929004, "dementia": 52448006, "hypertension": 38341003}
_IS_A = {(26929004, 52448006)}  # Alzheimer's is-a Dementia


class _FakeTerminology:
    def __init__(self, *a, **k):
        self.calls = []

    def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "search":
            code = _CONCEPTS.get(str(args.get("query", "")).strip().lower())
            return [{"conceptId": code}] if code else []
        if name == "subsumed_by":
            pair = (args.get("concept_id"), args.get("subsumer_id"))
            return {"subsumedBy": pair in _IS_A or args.get("concept_id") == args.get("subsumer_id")}
        raise AssertionError(f"unexpected tool op {name}")

    def close(self):
        pass


def _decl(params=None):
    return VerificationContractDecl(
        flag_code="FABRICATED_CLAIM", question="is the flagged term grounded in the record?",
        contract_type="terminology_subsumption", version="test/1",
        params={"tool": "my_terminology", "record_path": "record.conditions", **(params or {})},
    )


def _wire_fakes(monkeypatch):
    from lithrim_bench.harness import plugins
    from lithrim_bench.verification import mcp_client

    monkeypatch.setattr(
        plugins, "resolve_tool",
        lambda tool_id: SimpleNamespace(service={"mcp": {"command": "fake", "args": []}}),
    )
    monkeypatch.setattr(mcp_client, "McpStdioClient", _FakeTerminology)


def _finding(quote):
    return {"code": "FABRICATED_CLAIM", "_evidence_spans": [{"quote": quote}]}


_CASE = {"transcript": "t", "record": {"conditions": ["Dementia", "Hypertension"]}}


def test_subsumed_span_term_clears_the_false_block(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl()).check(_finding("Alzheimer's disease"), _CASE)
    assert v.disproved is True
    assert "26929004" in (v.evidence or "") or "26929004" in (v.reason or "")


def test_ungrounded_term_stands_a_genuine_fabrication(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl()).check(_finding("Lupus"), _CASE)
    assert v.disproved is False  # unresolvable term → never cleared


def test_resolved_but_not_subsumed_stands(monkeypatch):
    _wire_fakes(monkeypatch)
    case = {"transcript": "t", "record": {"conditions": ["Hypertension"]}}
    v = TerminologySubsumption(_decl()).check(_finding("Alzheimer's disease"), case)
    assert v.disproved is False


def test_no_span_or_empty_record_declines(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl()).check({"code": "FABRICATED_CLAIM"}, _CASE)
    assert v.disproved is False  # no flagged span → nothing this oracle may speak to
    v2 = TerminologySubsumption(_decl()).check(
        _finding("Alzheimer's disease"), {"record": {"conditions": []}}
    )
    assert v2.disproved is False


def test_unresolvable_tool_stands_never_500(monkeypatch):
    from lithrim_bench.harness import plugins

    monkeypatch.setattr(plugins, "resolve_tool", lambda tool_id: None)
    v = TerminologySubsumption(_decl()).check(_finding("Alzheimer's disease"), _CASE)
    assert v.disproved is False
    assert "not available" in (v.reason or "") or "tool" in (v.reason or "")


def test_term_regex_extracts_candidates_from_a_sentence_span(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(
        _decl({"term_regex": r"Alzheimer's disease|Dementia"})
    ).check(_finding("PMH significant for Alzheimer's disease, stable."), _CASE)
    assert v.disproved is True


def test_registered_as_a_core_suppress_executor():
    assert _CONTRACT_EXECUTORS["terminology_subsumption"] is TerminologySubsumption
