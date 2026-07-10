"""The per-judge, pre-consensus withstands-gate — UAP-3b D2 (THE MOAT, §2A).

For the authored DSPy trio, BEFORE the frozen ``ComplianceCouncil._apply_consensus``
runs, reconcile each judge's verdict against its deterministic signals
(``signals.build_judge_signals``) and **deterministically correct** a
signal-contradicted finding. A judge's verdict **stands only if its reasoning
withstands** the tagged ontology + validator signals (the Ralph-Loop critique,
deterministic floor this cycle):

  * **suppress** a finding a validator signal **disproves** (the dose IS grounded /
    the med IS in the transcript) — the S-BS-7 post-consensus suppress, generalized
    per-judge and PRE-consensus.
  * **reject** a finding that **violates a tagged ontology rule** — a code OUTSIDE the
    judge's assigned lens/owner that **no owning judge corroborates** (the observed
    DSPy-3b out-of-lens over-fire). When an owning judge DOES co-raise the code, the
    raise is legitimate corroboration and is **kept** (never drop a corroborated true
    finding — this is the by-construction-true guard, §2A invariant: the gate cannot
    relabel a true case).
  * otherwise the finding **withstands**, unchanged.

When the gate strips ALL of a judge's blocking findings, it also down-ranks that
judge's ``decision`` to ``approve`` (a judge with no grounded violation has no basis
to block) — the §2A "down-rank or correct a judge's reasoning". The CORRECTED seam
dicts feed the **unchanged** ``_apply_consensus`` (byte-0-delta; the gate is the only
new stage, inserted ABOVE the frozen seam).

This module is pure + deterministic (no LLM). The optional ``critique`` hook (an LLM
Ralph-Loop pass) is a parameter the gate is shaped to admit later WITHOUT a reshape —
deferred to UAP-3b-2 per plan-review D-A.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from .judge_metric import LENS_BY_ROLE
from .signals import (
    JudgeSignals,
    build_judge_signals,
    effective_lens,
)

_BLOCKING_DECISIONS = {"reject"}


@dataclass(frozen=True)
class WithstandsDecision:
    """The §2B critique ruling for one judge (``{signals_weighed, decision, what_failed}``)."""

    role: str
    decision: str  # "withstand" | "corrected"
    signals_weighed: dict[str, Any]
    what_failed: list[dict[str, Any]] = field(default_factory=list)
    decision_before: str | None = None
    decision_after: str | None = None

    def to_audit_why(self) -> dict[str, Any]:
        """The §2B critique-ruling ``why`` (audit.AuditRecord.why)."""
        return {
            "signals_weighed": self.signals_weighed,
            "decision": self.decision,
            "what_failed": self.what_failed,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _signals_weighed(signals: JudgeSignals) -> dict[str, Any]:
    return {
        "ontology_rules": [asdict(r) for r in signals.ontology_rules],
        "validator_outputs": [asdict(v) for v in signals.validator_outputs],
    }


def apply_withstands_gate(
    results: Sequence[Mapping[str, Any]],
    *,
    ontology: Any,
    case: Mapping[str, Any],
    lens_by_role: Mapping[str, frozenset[str]] = LENS_BY_ROLE,
    assignments: Mapping[str, Sequence[str]] | None = None,
    http_client: Any | None = None,
) -> tuple[list[dict[str, Any]], list[WithstandsDecision]]:
    """Reconcile each judge's verdict against its signals; return
    ``(corrected_results, decisions)``.

    ``results`` are the per-judge seam dicts (``{model: role, decision, confidence,
    findings, errors}``). ``corrected_results`` are NEW dicts of the SAME shape with
    signal-contradicted findings removed (and the decision down-ranked when emptied);
    the originals are not mutated. ``decisions`` is one :class:`WithstandsDecision` per
    judge (withstand or corrected) — the §2B audit + RLVR substrate.
    """
    raised_by_role: dict[str, set[str]] = {}
    for r in results:
        role = r.get("model") or ""
        codes = {
            (f.get("taxonomy_code") or "").strip()
            for f in (r.get("findings") or [])
            if isinstance(f, Mapping)
        }
        raised_by_role[role] = {c for c in codes if c}

    corrected_results: list[dict[str, Any]] = []
    decisions: list[WithstandsDecision] = []

    for r in results:
        role = r.get("model") or ""
        signals = build_judge_signals(
            r,
            role,
            ontology=ontology,
            case=case,
            lens_by_role=lens_by_role,
            assignments=assignments,
            http_client=http_client,
        )
        disproved = signals.disproved_codes()
        lens = effective_lens(role, lens_by_role=lens_by_role, assignments=assignments)

        kept: list[dict[str, Any]] = []
        what_failed: list[dict[str, Any]] = []
        for f in r.get("findings") or []:
            if not isinstance(f, Mapping):
                kept.append(dict(f) if isinstance(f, Mapping) else f)
                continue
            code = (f.get("taxonomy_code") or "").strip()

            # (1) validator disproves the finding → suppress.
            if code and code in disproved:
                reason = next(
                    (s.reason for s in signals.validator_outputs if s.code == code and s.disproved),
                    "validator disproved the finding",
                )
                what_failed.append(
                    {"code": code, "mode": "validator_disproved", "reason": reason}
                )
                continue

            # (2) ontology-rule violation: out of this judge's lens AND no owning
            # judge corroborates the code → reject. A corroborating owner protects it.
            if code and code not in lens:
                owner_corroborates = any(
                    code in raised_by_role.get(other, set())
                    and code in effective_lens(
                        other, lens_by_role=lens_by_role, assignments=assignments
                    )
                    for other in raised_by_role
                    if other != role
                )
                if not owner_corroborates:
                    what_failed.append(
                        {
                            "code": code,
                            "mode": "ontology_rule_out_of_lens",
                            "reason": (
                                f"{code!r} is outside {role!r}'s assigned lens/owner and "
                                f"no owning judge corroborates it"
                            ),
                        }
                    )
                    continue

            kept.append(dict(f))

        corrected = dict(r)
        corrected["findings"] = kept
        decision_before = r.get("decision")
        decision_after = decision_before
        if what_failed and not kept and decision_before in _BLOCKING_DECISIONS:
            # the gate stripped every blocking finding — down-rank the verdict.
            decision_after = "approve"
            corrected["decision"] = decision_after
        corrected_results.append(corrected)

        decisions.append(
            WithstandsDecision(
                role=role,
                decision="corrected" if what_failed else "withstand",
                signals_weighed=_signals_weighed(signals),
                what_failed=what_failed,
                decision_before=decision_before,
                decision_after=decision_after,
            )
        )

    return corrected_results, decisions
