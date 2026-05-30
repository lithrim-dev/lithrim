"""Harness-side, post-hoc grounding: tool-checks that can flip a verdict.

The load-bearing exhibit is S-BS-7. The live council emits
``MEDICATION_NOT_IN_TRANSCRIPT`` as a confident false positive, citing — as its
proof of absence — the transcript line that *contains* the medication
(``zidovudine 300 MG Oral Tablet`` is verbatim in the transcript). No aggregation
lever separates this FP from the true defect ``FABRICATED_HISTORY``; both are
findings-first, fully evidenced, validated (REPORT_r3d_precheck_falsification).
The only lever that closes it reasons about span *content* — a presence-check.

WS-1: the contract set is no longer hardcoded. Contracts are **declared in the
ontology** (``data/ontology/clinical_v1.json`` → ``verification_contracts``) and
this module supplies the *executors* keyed by ``contract_type``. The med
presence-check's extraction strategy (med source, token floor, dosage regex, noise
tokens) is read from the declaration's ``params`` — it is data, not module
constants (WS-0 critique Q4.3). The severity→verdict re-score is the ontology's
``severity_map`` (Q4.2). Real / mid-loop tool grounding via JUTE / pinecone is WS-3.

S-BS-8 null-code findings (structural/artifact findings the live pipeline returns
with ``code=None``) cannot be keyed to a contract — they are skip-logged into an
"ungrounded" bucket, surfaced in the report, and kept in the active set; never
silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ontology import Ontology, VerificationContractDecl, load_ontology


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
    a reporting view — those findings remain in ``active`` too. ``weights`` is the
    ontology severity→weight map, carried so the report can score without
    re-importing a constant.
    """

    active: list[dict[str, Any]]
    suppressed: list[dict[str, Any]]
    ungrounded: list[dict[str, Any]]
    verdict: str
    original_verdict: str | None
    weights: dict[str, float] = field(default_factory=dict)
    result: dict[str, Any] = field(repr=False, default_factory=dict)
    case: dict[str, Any] = field(repr=False, default_factory=dict)


class VerificationContract:
    """A flag-keyed tool-check. ``check`` returns a :class:`Verdict`."""

    flag_code: str
    question: str
    version: str

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        raise NotImplementedError


def _resolve_path(case: dict[str, Any], dotted: str) -> Any:
    """Resolve a dotted path (e.g. ``patient_profile.active_medications``)."""
    cur: Any = case
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _line_containing(transcript: str, token: str) -> str | None:
    for line in transcript.splitlines():
        if token in line.lower():
            return line.strip()
    return None


class PresenceCheck(VerificationContract):
    """Disprove an "X not in transcript" finding when X is in fact in the transcript.

    Built from a :class:`VerificationContractDecl`; the extraction strategy is the
    declaration's ``params`` (med source path, token floor, dosage regex, noise
    tokens). Conservative: only suppress on a *positive* presence match; never
    suppress on a failed extraction. The finding's evidence spans are cross-checked
    as corroboration when present (the S-BS-7 self-refuting span).
    """

    def __init__(self, decl: VerificationContractDecl) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        params = decl.params
        self._source = params["med_source"]
        self._token_min_len = int(params.get("token_min_len", 4))
        self._noise = set(params.get("noise_tokens") or [])
        self._dosage_re = re.compile(params["dosage_regex"], re.IGNORECASE)

    def _tokens(self, value: str) -> set[str]:
        cleaned = self._dosage_re.sub(" ", value).lower()
        return {
            tok
            for tok in re.split(r"[^a-z]+", cleaned)
            if len(tok) >= self._token_min_len and tok not in self._noise
        }

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        transcript = case.get("transcript") or ""
        transcript_lc = transcript.lower()
        values = _resolve_path(case, self._source) or []

        for value in values:
            for token in self._tokens(value):
                if token in transcript_lc:
                    line = _line_containing(transcript, token)
                    spans = finding.get("_evidence_spans") or []
                    corroborated = any(token in (s.get("quote") or "").lower() for s in spans)
                    reason = (
                        f"medication '{token}' (from {self._source} '{value}') is "
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
            reason="no source value resolved to a token present in the transcript",
        )


# contract_type -> executor factory. WS-3 adds JUTE / KB / vector executors here.
_CONTRACT_EXECUTORS = {"presence_check": PresenceCheck}


def _build_contract(decl: VerificationContractDecl) -> VerificationContract:
    factory = _CONTRACT_EXECUTORS.get(decl.contract_type)
    if factory is None:
        raise ValueError(f"no executor registered for contract_type {decl.contract_type!r}")
    return factory(decl)


def ground(
    result: dict[str, Any], case: dict[str, Any], *, ontology: Ontology | None = None
) -> GroundedResult:
    """Run every matching contract over the result's findings; re-score the verdict.

    Contracts and the severity map come from ``ontology`` (default: the committed
    clinical ontology). Disproved findings are removed from the active set.
    Null-code findings (S-BS-8) are skip-logged into ``ungrounded`` and retained in
    ``active``. Coded findings with no matching contract are retained unchanged.
    """
    ontology = ontology or load_ontology()
    contracts = {decl.flag_code: _build_contract(decl) for decl in ontology.contracts}
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
        verdict=ontology.severity_map.rescore(active),
        original_verdict=result.get("verdict"),
        weights=dict(ontology.severity_map.weights),
        result=result,
        case=case,
    )
