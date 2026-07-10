"""GroundingCheck entities (UAP-3b-2 — the deferred UAP-3b A6).

A **GroundingCheck** is a first-class, config-authored **INDEPENDENT** entity (§2A):
the floor/suppress contracts of :mod:`lithrim_bench.harness.grounding`, promoted from
anonymous post-consensus machinery into **declared entities that are audited per
execution** — distinct from the judge-ATTACHED validators the withstands-gate's
signals bus consumes (those run PRE-consensus, per-judge; these run POST-consensus,
independent of any judge — the §13 locus=BOTH split).

This is the **light** surface (D-D): it does NOT re-run or alter ``ground()`` — the
verdict + the suppress/floor partitions stay byte-identical. It PROJECTS the
executions ``ground()`` already performed (those declared in
:attr:`EvalProfile.grounding_checks`) into per-entity
:class:`~lithrim_bench.harness.audit.AuditRecord`s with ``actor.type='grounding_check'``
and a **grounding-appropriate** action (``suppress`` / ``floor_block`` / ``run``),
deliberately distinct from the gate's ``withstand`` / ``flip`` so the two correction
loops separate cleanly in the audit. A config-plane GroundingCheck CRUD UI is a
follow-on; this cycle is declaration + audit only.

``why`` follows the §2B validator-execution shape
(``{contract, conforms, deterministic_result, grounded_fact}``).
"""
from __future__ import annotations

from collections.abc import Sequence

from .audit import Actor, AuditRecord, Target
from .grounding import GroundedResult


def audit_grounding_checks(
    declared: Sequence[str],
    grounded: GroundedResult,
    *,
    run_id: str | None = None,
    case_id: str | None = None,
) -> list[AuditRecord]:
    """Project the declared GroundingChecks' executions into per-entity AuditRecords.

    ``declared`` is :attr:`EvalProfile.grounding_checks` — the flag codes promoted to
    independent GroundingCheck entities. An empty declaration → ``[]`` (every existing
    committed agent, so the post-consensus path is byte-unchanged). A record is emitted
    only for a declared check that **actually engaged this evaluation**:

    - a flag in ``grounded.suppressed``  → ``suppress`` (the contract disproved a finding);
    - a flag injected via ``grounded.floor_blocks`` → ``floor_block`` (a real structural
      violation the council missed);
    - a floor that ran inconclusively (``injected_finding is None``) → ``run`` (it executed
      over the artifact but did not block — surfaced, not silent).

    A declared **suppress** check with no matching finding this eval did not execute, so
    it emits no record (honest — never a fabricated ``run``). ``ground()``'s own logic is
    untouched: this reads the partitions it already produced.
    """
    if not declared:
        return []
    declared_set = {str(c) for c in declared}
    records: list[AuditRecord] = []

    for s in grounded.suppressed:
        code = s["finding"].get("code")
        if str(code) not in declared_set:
            continue
        verdict = s["verdict"]
        why = {
            "contract": s["contract"].version,
            "conforms": False,
            "deterministic_result": "disproved",
            "grounded_fact": verdict.evidence,
            "matched_token": verdict.matched_token,
        }
        edition = getattr(verdict, "terminology_edition", None)
        if edition is not None:
            # REL-OPS-1 O2: WHICH terminology edition decided it — absent (not null) for
            # non-terminology contracts, so their audit shape is byte-identical.
            why["terminology_edition"] = edition
        records.append(
            AuditRecord(
                actor=Actor(type="grounding_check", id=str(code)),
                action="suppress",
                target=Target(type="finding", id=str(code)),
                why=why,
                run_id=run_id,
                case_id=case_id,
            )
        )

    for b in grounded.floor_blocks:
        flag = (b["injected_finding"] or {}).get("code") or b["decl"].params.get(
            "inject_flag_code"
        )
        if str(flag) not in declared_set:
            continue
        injected = b["injected_finding"] is not None
        records.append(
            AuditRecord(
                actor=Actor(type="grounding_check", id=str(flag)),
                action="floor_block" if injected else "run",
                target=Target(
                    type="finding" if injected else "case",
                    id=str(flag) if injected else str(case_id),
                ),
                why={
                    "contract": b["decl"].version,
                    "contract_type": b["decl"].contract_type,
                    "conforms": b["result"].conforms,
                    "deterministic_result": b["result"].disposition,
                    "grounded_fact": b["result"].evidence,
                },
                run_id=run_id,
                case_id=case_id,
            )
        )

    return records
