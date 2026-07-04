"""REL-OPS-1 O2 — terminology edition pinning (record-only).

The floor's subsumption answers are edition-dependent (the 9/12-vs-2/12 clear-rate split was
an edition difference caught manually), yet no verdict records WHICH terminology edition
decided it. This cut stamps ``terminology_edition`` on every ``terminology_subsumption``
execution: the release identifier when the contract params or the tool's service config name
an ``edition_op``, else the honest ``"unrecorded"`` — never guessed, and a failed edition
lookup NEVER changes the grounding verdict (fail-honest, record-only; change DETECTION is a
later cut). $0/offline — the tool transport is faked."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402

from lithrim_bench.harness.grounding import (  # noqa: E402
    GroundedResult,
    TerminologySubsumption,
    Verdict,
)
from lithrim_bench.harness.grounding_check import audit_grounding_checks  # noqa: E402
from lithrim_bench.harness.ontology import VerificationContractDecl  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402

_CONCEPTS = {"alzheimer's disease": 26929004, "dementia": 52448006}
_IS_A = {(26929004, 52448006)}  # Alzheimer's is-a Dementia
_EDITION = "http://snomed.info/sct/900000000000207008/version/20250301"


class _FakeTerminology:
    instances: list[Any] = []
    edition_result: Any = {"edition": _EDITION}
    edition_raises = False

    def __init__(self, *a, **k):
        self.calls = []
        type(self).instances.append(self)

    def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "search":
            code = _CONCEPTS.get(str(args.get("query", "")).strip().lower())
            return [{"conceptId": code}] if code else []
        if name == "subsumed_by":
            pair = (args.get("concept_id"), args.get("subsumer_id"))
            return {"subsumedBy": pair in _IS_A or args.get("concept_id") == args.get("subsumer_id")}
        if name == "release_info":
            if type(self).edition_raises:
                raise RuntimeError("edition endpoint down")
            return type(self).edition_result
        raise AssertionError(f"unexpected tool op {name}")

    def close(self):
        pass


def _decl(params=None):
    return VerificationContractDecl(
        flag_code="FABRICATED_CLAIM", question="is the flagged term grounded in the record?",
        contract_type="terminology_subsumption", version="test/1",
        params={"tool": "my_terminology", "record_path": "record.conditions", **(params or {})},
    )


def _wire_fakes(monkeypatch, service=None):
    from lithrim_bench.harness import plugins
    from lithrim_bench.verification import mcp_client

    _FakeTerminology.instances = []
    _FakeTerminology.edition_result = {"edition": _EDITION}
    _FakeTerminology.edition_raises = False
    monkeypatch.setattr(
        plugins, "resolve_tool",
        lambda tool_id: SimpleNamespace(
            service=service or {"mcp": {"command": "fake", "args": []}}
        ),
    )
    monkeypatch.setattr(mcp_client, "McpStdioClient", _FakeTerminology)


def _finding(quote="Alzheimer's disease"):
    return {"code": "FABRICATED_CLAIM", "_evidence_spans": [{"quote": quote}]}


_CASE = {"transcript": "t", "record": {"conditions": ["Dementia"]}}


def _grounded_with(verdict, contract):
    return GroundedResult(
        active=[], suppressed=[
            {"finding": {"code": "FABRICATED_CLAIM"}, "verdict": verdict, "contract": contract}
        ],
        ungrounded=[], verdict="PASS", original_verdict="BLOCK",
    )


# ── (a) an edition op is configured → the trace carries the edition string ─────────────


def test_edition_op_param_stamps_the_release_on_the_verdict(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl({"edition_op": "release_info"})).check(_finding(), _CASE)
    assert v.disproved is True
    assert v.terminology_edition == _EDITION
    assert ("release_info", {}) in _FakeTerminology.instances[0].calls


def test_edition_op_from_the_tool_service_config(monkeypatch):
    _wire_fakes(
        monkeypatch,
        service={"mcp": {"command": "fake", "args": []}, "edition_op": "release_info"},
    )
    v = TerminologySubsumption(_decl()).check(_finding(), _CASE)
    assert v.disproved is True
    assert v.terminology_edition == _EDITION


def test_plain_string_edition_result_is_stamped_verbatim(monkeypatch):
    _wire_fakes(monkeypatch)
    _FakeTerminology.edition_result = "SNOMED-INTL-20250301"
    v = TerminologySubsumption(_decl({"edition_op": "release_info"})).check(_finding(), _CASE)
    assert v.terminology_edition == "SNOMED-INTL-20250301"


def test_edition_flows_into_blob_trace_audit_and_report(monkeypatch):
    _wire_fakes(monkeypatch)
    contract = TerminologySubsumption(_decl({"edition_op": "release_info"}))
    v = contract.check(_finding(), _CASE)
    grounded = _grounded_with(v, contract)

    blob = run_eval._grounded_block(grounded)
    assert blob["suppressed"][0]["terminology_edition"] == _EDITION

    records = audit_grounding_checks(["FABRICATED_CLAIM"], grounded, case_id="c1")
    assert records[0].why["terminology_edition"] == _EDITION

    comp = composite(grounded)
    assert comp["grounded_adjustments"][0]["terminology_edition"] == _EDITION


# ── (b) no edition op configured → "unrecorded" ────────────────────────────────────────


def test_no_edition_op_stamps_unrecorded(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl()).check(_finding(), _CASE)
    assert v.disproved is True
    assert v.terminology_edition == "unrecorded"
    assert all(op in ("search", "subsumed_by") for op, _ in _FakeTerminology.instances[0].calls)


def test_pre_tool_declines_are_stamped_unrecorded(monkeypatch):
    _wire_fakes(monkeypatch)
    v = TerminologySubsumption(_decl({"edition_op": "release_info"})).check(
        {"code": "FABRICATED_CLAIM"}, _CASE
    )
    assert v.disproved is False  # no flagged span → the finding stands, no tool session
    assert v.terminology_edition == "unrecorded"


# ── (c) edition op raising → "unrecorded" AND the grounding verdict is untouched ───────


def test_edition_lookup_failure_is_unrecorded_and_never_changes_the_verdict(monkeypatch):
    _wire_fakes(monkeypatch)
    baseline = TerminologySubsumption(_decl()).check(_finding(), _CASE)

    _wire_fakes(monkeypatch)
    _FakeTerminology.edition_raises = True
    v = TerminologySubsumption(_decl({"edition_op": "release_info"})).check(_finding(), _CASE)

    assert ("release_info", {}) in _FakeTerminology.instances[0].calls  # the lookup ran
    assert v.terminology_edition == "unrecorded"
    assert baseline.terminology_edition == "unrecorded"
    assert (v.disproved, v.matched_token, v.evidence, v.reason) == (
        baseline.disproved,
        baseline.matched_token,
        baseline.evidence,
        baseline.reason,
    )


def test_unrecognized_edition_result_shape_is_never_guessed(monkeypatch):
    _wire_fakes(monkeypatch)
    _FakeTerminology.edition_result = {"status": "ok"}
    v = TerminologySubsumption(_decl({"edition_op": "release_info"})).check(_finding(), _CASE)
    assert v.disproved is True
    assert v.terminology_edition == "unrecorded"


# ── the non-terminology record shapes stay byte-identical (no new key) ─────────────────


def test_non_terminology_records_do_not_grow_the_key():
    contract = SimpleNamespace(version="presence/1")
    v = Verdict(disproved=True, matched_token="zidovudine", evidence="line", reason="present")
    assert v.terminology_edition is None
    grounded = _grounded_with(v, contract)

    assert "terminology_edition" not in run_eval._grounded_block(grounded)["suppressed"][0]
    records = audit_grounding_checks(["FABRICATED_CLAIM"], grounded, case_id="c1")
    assert "terminology_edition" not in records[0].why
    assert "terminology_edition" not in composite(grounded)["grounded_adjustments"][0]
