"""CRITERION-JUTE-1c: the executable acceptance GATE for a candidate ``mcp_call`` +
``arguments_jute`` contract, replayed over the bidirectional subsumption corpus.

Spec Section 5.3 + 6.2 + 10. The gate answers ONE question: does this SME-authored
contract, when replayed finding-by-finding over the corpus, clear EVERY clean-generalization
negative (finding disproved -> the note generalized what the record supports -> PASS) AND
leave EVERY upcoded positive STANDING (finding not disproved -> the note is more specific than
the record -> BLOCK)? Pin ONLY if it does. A contract that clears a positive (a false clear),
lets a negative stand (a false block), or false-clears a fabrication that happens to share a
case with a clean generalization (the SPAN-BIND failure, cv_mts_104/105 class) is REJECTED.

HOW IT REPLAYS (the moat: the gate USES the frozen ``McpCallGrounding`` executor, it never
edits it): for each synthesized finding it builds the real
``grounding.McpCallGrounding(VerificationContractDecl(...))`` and calls ``.check(finding, case)``
with three seams injected so the run is networkless and deterministic:

  * ``plugins.resolve_tool`` -> a fake ``PluginManifest`` whose ``service.mcp.command`` is set
    (else the executor returns not_applicable and the finding stands vacuously);
  * ``McpStdioClient.call_tool`` -> the caller's ``snomed_oracle`` (the terminology fact source);
  * ``grounding._jute_client`` -> a fake client whose ``test_template`` stands in for the pinned
    :3031 transform, delegating to the caller's ``jute_apply(case, finding)``.

A finding is CLEARED iff its ``Verdict.disproved is True``. A case PASSES its expectation iff
(expected BLOCK => at least one finding STANDS) and (expected PASS => every finding CLEARS).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

# The fake tool id the gate binds. The contract params' ``tool`` is set to this by the test;
# the gate resolves it to a fake manifest so the executor reaches its terminology branch.
_GATE_TOOL_ID = "gate_snomed_subsumption"


class GateFailure(AssertionError):
    """Raised by :func:`assert_gate_passes` when a candidate contract fails the corpus gate.

    The message names the offending case ids by failure class so the SME sees exactly what
    the contract got wrong (a negative that stood, a positive that cleared, a span-bind
    fabrication that cleared) rather than a bare boolean.
    """


@dataclass(frozen=True)
class FindingResult:
    case_id: str
    role: str
    cleared: bool
    reason: str


@dataclass
class GateReport:
    """The per-case + aggregate result of replaying a contract over the corpus."""

    negatives_total: int = 0
    negatives_cleared: int = 0
    positives_total: int = 0
    positives_standing: int = 0
    span_bind_cases: int = 0
    span_bind_ok: int = 0
    failures: list[str] = field(default_factory=list)
    negative_stands: list[str] = field(default_factory=list)
    positive_clears: list[str] = field(default_factory=list)
    span_bind_fabrication_clears: list[str] = field(default_factory=list)
    findings: list[FindingResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def _fake_manifest() -> Any:
    """A resolvable ``kind: tool`` manifest with a stdio MCP command (the executor's gate)."""
    from lithrim_bench.harness.plugins import PluginManifest

    return PluginManifest.model_validate(
        {
            "id": _GATE_TOOL_ID,
            "kind": "tool",
            "tier": "core",
            "transport": "service",
            "implements": "tool.terminology",
            "service": {"mcp": {"command": "python", "args": ["-m", "gate.oracle"]}},
        }
    )


class _FakeJuteClient:
    """Stands in for the live :3031 ``EtlpJuteClient`` the 1a wire applies the pinned transform
    through. ``McpCallGrounding._shape_arguments`` calls ``test_template(jute, {case, finding})``;
    we ignore the ``jute`` text (its sha256 is verified upstream by the real executor before we are
    reached) and delegate to the caller's ``jute_apply(case, finding)``, returning the
    ``{compiled, output}`` envelope the executor expects."""

    def __init__(self, jute_apply: Callable[[dict, dict], dict]) -> None:
        self._jute_apply = jute_apply

    def test_template(self, template: str, sample_input: Any) -> dict:
        case = (sample_input or {}).get("case", {})
        finding = (sample_input or {}).get("finding", {})
        return self._jute_apply(case, finding)


def _check_finding(
    contract_params: dict,
    finding: dict,
    case: dict,
    *,
    jute_apply: Callable[[dict, dict], dict],
    snomed_oracle: Callable[[str, dict], Any],
) -> Any:
    """Run the real ``McpCallGrounding.check`` for ONE finding with the three seams injected."""
    from lithrim_bench.harness import grounding
    from lithrim_bench.harness.grounding import McpCallGrounding, VerificationContractDecl
    from lithrim_bench.verification import mcp_client

    decl = VerificationContractDecl(
        flag_code="UPCODED_DIAGNOSIS",
        question="Is the note diagnosis more specific than the record supports?",
        contract_type="mcp_call",
        params=contract_params,
        version="1c",
    )
    contract = McpCallGrounding(decl)

    def _call_tool(self, name: str, arguments: dict) -> Any:  # noqa: ANN001
        return snomed_oracle(name, arguments)

    with (
        patch(
            "lithrim_bench.harness.plugins.resolve_tool",
            lambda *a, **k: _fake_manifest(),
        ),
        patch.object(grounding, "_jute_client", lambda: _FakeJuteClient(jute_apply)),
        patch.object(mcp_client.McpStdioClient, "call_tool", _call_tool),
        patch.object(mcp_client.McpStdioClient, "close", lambda self: None),
    ):
        return contract.check(finding, case)


def _findings_of(case: dict) -> list[dict]:
    return list(case.get("_synth_findings") or [])


def _expected_block(case: dict) -> bool:
    verdict = str(case.get("expected_artifact_verdict") or "").upper()
    return verdict == "BLOCK"


def gate_contract_over_corpus(
    contract_params: dict,
    cases: list[dict],
    *,
    jute_apply: Callable[[dict, dict], dict],
    snomed_oracle: Callable[[str, dict], Any],
) -> GateReport:
    """Replay ``contract_params`` (an ``mcp_call`` + ``arguments_jute`` contract) over ``cases``.

    For each case, for each synthesized finding, run the real ``McpCallGrounding.check`` with the
    injected seams; a finding is CLEARED iff its ``Verdict.disproved is True``. Aggregate:

      * a NEGATIVE (expected PASS) case must have EVERY finding cleared; else it is a failure
        (``negative_stands``);
      * a POSITIVE (expected BLOCK) case must have AT LEAST ONE finding standing; if all cleared
        it is a failure (``positive_clears``);
      * a SPAN-BIND case (``_spanbind``) additionally requires every ``fabrication`` finding to
        STAND and every ``generalization`` finding to CLEAR — a fabrication that cleared is a
        distinct failure class (``span_bind_fabrication_clears``).
    """
    report = GateReport()
    for case in cases:
        cid = str(case.get("case_id"))
        findings = _findings_of(case)
        cleared_flags: list[bool] = []
        is_spanbind = bool(case.get("_spanbind"))
        span_ok = True
        for finding in findings:
            verdict = _check_finding(
                contract_params,
                finding,
                case,
                jute_apply=jute_apply,
                snomed_oracle=snomed_oracle,
            )
            cleared = getattr(verdict, "disproved", False) is True
            cleared_flags.append(cleared)
            role = str(finding.get("_role") or ("finding" if not is_spanbind else "?"))
            report.findings.append(
                FindingResult(cid, role, cleared, getattr(verdict, "reason", ""))
            )
            if is_spanbind:
                if finding.get("_fabrication") and cleared:
                    report.span_bind_fabrication_clears.append(cid)
                    span_ok = False
                if finding.get("_role") == "generalization_clears" and not cleared:
                    span_ok = False

        all_cleared = bool(cleared_flags) and all(cleared_flags)
        any_stands = any(not c for c in cleared_flags)

        if _expected_block(case):
            report.positives_total += 1
            if any_stands:
                report.positives_standing += 1
            else:
                report.positive_clears.append(cid)
                report.failures.append(cid)
        else:
            report.negatives_total += 1
            if all_cleared:
                report.negatives_cleared += 1
            else:
                report.negative_stands.append(cid)
                report.failures.append(cid)

        if is_spanbind:
            report.span_bind_cases += 1
            if span_ok:
                report.span_bind_ok += 1
            else:
                if cid not in report.failures:
                    report.failures.append(cid)

    # de-dup while preserving order (a span-bind case can fail two ways at once)
    seen: set[str] = set()
    report.failures = [c for c in report.failures if not (c in seen or seen.add(c))]
    return report


def assert_gate_passes(report: GateReport) -> None:
    """Raise :class:`GateFailure` naming the offending case ids unless the gate is fully clean.

    A clean gate: every negative cleared, every positive standing, every span-bind fabrication
    standing + every span-bind generalization cleared. Otherwise the contract does NOT pin.
    """
    if report.passed:
        return
    parts: list[str] = []
    if report.negative_stands:
        parts.append(f"negatives that STOOD (false block): {sorted(set(report.negative_stands))}")
    if report.positive_clears:
        parts.append(f"positives that CLEARED (false clear): {sorted(set(report.positive_clears))}")
    if report.span_bind_fabrication_clears:
        parts.append(
            "span-bind fabrications that CLEARED (span-bind false clear): "
            f"{sorted(set(report.span_bind_fabrication_clears))}"
        )
    if not parts:
        parts.append(f"failures: {report.failures}")
    raise GateFailure(
        "candidate mcp_call/arguments_jute contract FAILED the bidirectional corpus gate — "
        + "; ".join(parts)
    )


__all__ = [
    "GateReport",
    "FindingResult",
    "GateFailure",
    "gate_contract_over_corpus",
    "assert_gate_passes",
]
