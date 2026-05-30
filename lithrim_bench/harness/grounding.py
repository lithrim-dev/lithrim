"""Harness-side, post-hoc grounding: tool-checks that can flip a verdict.

The load-bearing exhibit is S-BS-7. The live council emits
``MEDICATION_NOT_IN_TRANSCRIPT`` as a confident false positive, citing — as its
proof of absence — the transcript line that *contains* the medication
(``zidovudine 300 MG Oral Tablet`` is verbatim in the transcript). No aggregation
lever separates this FP from the true defect ``FABRICATED_HISTORY``; both are
findings-first, fully evidenced, validated (REPORT_r3d_precheck_falsification).
The only lever that closes it reasons about span *content* — a presence-check.

WS-0 hardcodes the single presence-check contract inline (the SQLite ontology of
contracts is WS-1; real / mid-loop tool grounding via JUTE / pinecone is WS-3).
S-BS-8 null-code findings (structural/artifact findings the live pipeline returns
with ``code=None``) cannot be keyed to a contract — they are skip-logged into an
"ungrounded" bucket, surfaced in the report, and kept in the active set; never
silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Severity -> a [0,1] risk weight, used to re-score the composite verdict after
# suppression. HIGH/MEDIUM block; LOW warns; nothing passes.
SEVERITY_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2}

_DOSAGE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|%)\b", re.IGNORECASE)
# Form/route noise that is never a drug name; dropped before token matching.
_MED_NOISE = {
    "oral",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "extended",
    "release",
    "mucosal",
    "spray",
    "injection",
    "solution",
    "suspension",
    "hr",
    "er",
    "xr",
    "actuat",
    "mg",
    "mcg",
    "ml",
}


@dataclass(frozen=True)
class Verdict:
    """The outcome of running one contract against one finding."""

    disproved: bool
    matched_token: str | None = None
    evidence: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class GroundedResult:
    """The graded result after harness-side grounding.

    ``active`` is every finding that still contributes to the verdict (retained
    coded findings + null-code findings). ``suppressed`` are the disproved ones
    (removed from ``active``). ``ungrounded`` is the null-code subset (S-BS-8),
    a reporting view — those findings remain in ``active`` too.
    """

    active: list[dict[str, Any]]
    suppressed: list[dict[str, Any]]
    ungrounded: list[dict[str, Any]]
    verdict: str
    original_verdict: str | None
    result: dict[str, Any] = field(repr=False, default_factory=dict)
    case: dict[str, Any] = field(repr=False, default_factory=dict)


class VerificationContract:
    """A flag-keyed tool-check. ``check`` returns a :class:`Verdict`."""

    flag_code: str
    question: str
    version: str

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        raise NotImplementedError


def _med_tokens(med: str) -> set[str]:
    """Core drug-name tokens of a medication string (dosage/form/units stripped)."""
    cleaned = _DOSAGE_RE.sub(" ", med).lower()
    return {tok for tok in re.split(r"[^a-z]+", cleaned) if len(tok) >= 4 and tok not in _MED_NOISE}


def _line_containing(transcript: str, token: str) -> str | None:
    for line in transcript.splitlines():
        if token in line.lower():
            return line.strip()
    return None


class MedPresenceCheck(VerificationContract):
    """Disprove ``MEDICATION_NOT_IN_TRANSCRIPT`` when the med is in the transcript.

    Primary med source = ``patient_profile.active_medications`` (authoritative,
    from the bench). The finding's evidence spans are cross-checked as
    corroboration when present. Conservative: only suppress on a *positive*
    presence match; never suppress on a failed extraction.
    """

    flag_code = "MEDICATION_NOT_IN_TRANSCRIPT"
    question = "Is the flagged medication actually present in the transcript?"
    version = "med-presence-check/v1"

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        transcript = case.get("transcript") or ""
        transcript_lc = transcript.lower()
        meds = (case.get("patient_profile") or {}).get("active_medications") or []

        for med in meds:
            for token in _med_tokens(med):
                if token in transcript_lc:
                    line = _line_containing(transcript, token)
                    spans = finding.get("_evidence_spans") or []
                    corroborated = any(token in (s.get("quote") or "").lower() for s in spans)
                    reason = (
                        f"medication '{token}' (from active_medications '{med}') is "
                        f"present verbatim in the transcript"
                    )
                    if corroborated:
                        reason += (
                            "; the judge's own evidence span quotes the same line "
                            "it cites as proof of absence"
                        )
                    return Verdict(
                        disproved=True,
                        matched_token=token,
                        evidence=line,
                        reason=reason,
                    )
        return Verdict(
            disproved=False,
            reason="no active medication resolved to a token present in the transcript",
        )


# The one WS-0 contract, hardcoded (the SQLite ontology of contracts is WS-1).
WS0_CONTRACTS: list[VerificationContract] = [MedPresenceCheck()]


def _rescore(active: list[dict[str, Any]]) -> str:
    weight = max((SEVERITY_WEIGHT.get(f.get("severity"), 0.0) for f in active), default=0.0)
    if weight >= 0.5:
        return "BLOCK"
    if weight > 0.0:
        return "WARN"
    return "PASS"


def ground(result: dict[str, Any], case: dict[str, Any]) -> GroundedResult:
    """Run every matching contract over the result's findings; re-score the verdict.

    Disproved findings are removed from the active set. Null-code findings (S-BS-8)
    are skip-logged into ``ungrounded`` and retained in ``active``. Coded findings
    with no matching contract are retained unchanged.
    """
    contracts = {c.flag_code: c for c in WS0_CONTRACTS}
    semantic_evidence = {
        ev.get("violation_code"): ev for ev in (result.get("semantic") or {}).get("evidence", [])
    }
    findings = result.get("findings") or []

    active: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    ungrounded: list[dict[str, Any]] = []

    for finding in findings:
        code = finding.get("code")
        if code is None:
            ungrounded.append(finding)
            active.append(finding)
            continue
        contract = contracts.get(code)
        if contract is None:
            active.append(finding)
            continue
        enriched = dict(finding)
        ev = semantic_evidence.get(code)
        if ev is not None:
            enriched["_evidence_spans"] = ev.get("spans")
        verdict = contract.check(enriched, case)
        if verdict.disproved:
            suppressed.append({"finding": finding, "verdict": verdict, "contract": contract})
        else:
            active.append(finding)

    return GroundedResult(
        active=active,
        suppressed=suppressed,
        ungrounded=ungrounded,
        verdict=_rescore(active),
        original_verdict=result.get("verdict"),
        result=result,
        case=case,
    )
