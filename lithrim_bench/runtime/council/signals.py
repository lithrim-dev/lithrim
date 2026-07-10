"""The per-judge signals bus — UAP-3b D1 (the §2A withstands-gate floor).

For one LLM judge's seam-dict result, assemble the **deterministic signals** the
withstands-gate (``withstands.py``) reconciles its verdict against:

  * **ontology-rule signals** — for each code the judge raised (and each code it
    *owns* per its lens but did NOT raise), the tagged rule from the ontology:
    ``tier`` / ``owner_roles`` (the roles whose lens carries the code) /
    ``when_to_use`` / ``when_NOT_to_use`` / ``severity_weight``. The owner/lens half
    is sourced from ``judge_metric.LENS_BY_ROLE`` — the production owner-consistent
    authority — NOT the committed ontology's ``owner_roles`` (which are stale v1 roles
    carrying no ``faithfulness_judge``; S-BS-59). The ontology supplies the tier /
    when / when-NOT / severity tags.
  * **validator-output signals** — the deterministic result of running each of the
    judge's raised codes through its matching suppress contract
    (``PresenceCheck`` / ``KbGrounding`` / the active pack's ``record_presence``),
    executed by REUSING ``grounding.py``'s ``_build_contract`` + the pack-merged
    ``suppress_executors()`` registry — never reimplemented.

Pure + deterministic, **NO LLM**. The signals are the floor that lets the critique
*ground* a judge's reasoning rather than merely self-critique it (the
``critique-pass-precision-not-floor`` finding). This module composes
``harness.grounding`` (the deterministic SIGNAL engine) + ``harness.ontology`` (the
rule tags) + ``judge_metric.LENS_BY_ROLE`` (the lens/owner authority); the
orchestration is the net-new, the executors are reused as-is.

Import-clean on default deps: ``grounding`` / ``ontology`` / ``judge_metric`` are all
stdlib-only at module load (``grounding`` lazy-imports the ``[verification]`` tools
inside its methods), so importing this module pulls no ``dspy`` / ``openai`` / httpx.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ...harness import grounding
from ...harness.ontology import Ontology
from .judge_metric import LENS_BY_ROLE


@dataclass(frozen=True)
class OntologyRuleSignal:
    """One tagged ontology rule, as it bears on a (judge, code) pair."""

    code: str
    raised: bool
    in_lens: bool
    owner_roles: tuple[str, ...]
    tier: str | None
    severity_weight: float
    when_to_use: str
    when_NOT_to_use: str


@dataclass(frozen=True)
class ValidatorOutputSignal:
    """The deterministic result of one suppress contract over one raised finding."""

    code: str
    contract_type: str
    contract_version: str
    disproved: bool
    reason: str
    evidence: str | None = None


@dataclass(frozen=True)
class JudgeSignals:
    """All deterministic signals assembled for one judge's verdict."""

    role: str
    ontology_rules: tuple[OntologyRuleSignal, ...]
    validator_outputs: tuple[ValidatorOutputSignal, ...]

    def disproved_codes(self) -> frozenset[str]:
        """The codes a validator signal disproves (the suppress targets)."""
        return frozenset(s.code for s in self.validator_outputs if s.disproved)


def effective_lens(
    role: str,
    *,
    lens_by_role: Mapping[str, frozenset[str]] = LENS_BY_ROLE,
    assignments: Mapping[str, Sequence[str]] | None = None,
) -> frozenset[str]:
    """The codes ``role`` has authority over: its production lens UNION any flags the
    SME has authored onto it (the §2A "assign an ontology subset" — a judge's authored
    assignment widens its lens; it never narrows the production owner-consistent base).
    """
    base = lens_by_role.get(role, frozenset())
    authored = (assignments or {}).get(role) or ()
    return frozenset(base) | frozenset(authored)


def owners_of(
    code: str,
    *,
    lens_by_role: Mapping[str, frozenset[str]] = LENS_BY_ROLE,
    assignments: Mapping[str, Sequence[str]] | None = None,
) -> tuple[str, ...]:
    """The roles whose effective lens carries ``code`` (its authoritative owners)."""
    return tuple(
        r
        for r in lens_by_role
        if code in effective_lens(r, lens_by_role=lens_by_role, assignments=assignments)
    )


def _raised_codes(result: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for f in result.get("findings") or []:
        code = (f.get("taxonomy_code") or "").strip() if isinstance(f, Mapping) else ""
        if code:
            out.append(code)
    return out


def _to_grounding_finding(code: str, seam_finding: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a seam finding (``{taxonomy_code, evidence_spans}``) to the shape
    ``grounding``'s contract executors read (``{code, _evidence_spans}``)."""
    return {"code": code, "_evidence_spans": list(seam_finding.get("evidence_spans") or [])}


def build_judge_signals(
    result: Mapping[str, Any],
    role: str,
    *,
    ontology: Ontology,
    case: Mapping[str, Any],
    lens_by_role: Mapping[str, frozenset[str]] = LENS_BY_ROLE,
    assignments: Mapping[str, Sequence[str]] | None = None,
    http_client: Any | None = None,
) -> JudgeSignals:
    """Assemble the deterministic signals for one judge's seam-dict ``result``.

    ``result`` is a per-judge seam dict (``{model: role, decision, findings:[{taxonomy_code,
    evidence_spans}], ...}``). ``case`` is the graded case (the contract executors read
    its transcript / artifact). Returns a :class:`JudgeSignals` value object — pure,
    no LLM, no mutation of ``result``.
    """
    findings = [f for f in (result.get("findings") or []) if isinstance(f, Mapping)]
    raised = [(f.get("taxonomy_code") or "").strip() for f in findings]
    raised = [c for c in raised if c]

    # ── ontology-rule signals: every raised code + every owned-but-not-raised code.
    lens = effective_lens(role, lens_by_role=lens_by_role, assignments=assignments)
    rule_codes = list(dict.fromkeys(raised)) + [c for c in sorted(lens) if c not in raised]
    rules: list[OntologyRuleSignal] = []
    for code in rule_codes:
        decl = ontology.flag(code)
        sm = ontology.severity_map
        # the rule's severity weight is the flag's tier-implied weight; fall back to
        # the worst weight so an unmapped code never silently scores 0.
        weight = 0.0
        if decl is not None:
            weight = max(sm.weights.values(), default=0.0) if decl.tier == "TIER_1" else (
                sm.weights.get("MEDIUM", 0.0)
            )
        rules.append(
            OntologyRuleSignal(
                code=code,
                raised=code in raised,
                in_lens=code in lens,
                owner_roles=owners_of(
                    code, lens_by_role=lens_by_role, assignments=assignments
                ),
                tier=decl.tier if decl is not None else None,
                severity_weight=weight,
                when_to_use=decl.when_to_use if decl is not None else "",
                when_NOT_to_use=decl.when_NOT_to_use if decl is not None else "",
            )
        )

    # ── validator-output signals: run each raised code through its suppress contract.
    validators: list[ValidatorOutputSignal] = []
    for f in findings:
        code = (f.get("taxonomy_code") or "").strip()
        if not code:
            continue
        decl = ontology.contract_for(code)
        if decl is None or decl.contract_type not in grounding.suppress_executors():
            continue
        contract = grounding._build_contract(decl, http_client=http_client)
        verdict = contract.check(_to_grounding_finding(code, f), dict(case))
        validators.append(
            ValidatorOutputSignal(
                code=code,
                contract_type=decl.contract_type,
                contract_version=decl.version,
                disproved=bool(verdict.disproved),
                reason=verdict.reason,
                evidence=verdict.evidence,
            )
        )

    return JudgeSignals(
        role=role,
        ontology_rules=tuple(rules),
        validator_outputs=tuple(validators),
    )
