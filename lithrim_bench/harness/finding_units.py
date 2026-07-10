"""FINDING-UNITS-1 — the span-cluster attribution clerk.

One defect span = ONE finding unit. When sibling codes from an ontology-declared
``code_family`` fire on OVERLAPPING evidence quotes, they are one defect with a
disputed name, not N defects — the clerk consolidates them into a single unit
carrying the full code-set (every attribution kept, displayed, none dropped).

A clerk, NOT a critic: it never judges correctness and never picks a survivor
(survivor-picking rules dropped 11-17 gold codes on the 2026-07-01 clean baseline;
the merge reached the oracle ceiling BLIND — strict P=27.0% -> unit P=46.3%, recall
byte-identical). It therefore sits BESIDE the frozen consensus/withstands moat,
computed post-hoc over stored grade records at score/read time — no grade-path edit.

Rule constants are corpus-gate-validated (tests/test_finding_units.py A6). Do not
tune ``CONTAINMENT_THRESHOLD`` or the clustering shape without re-running the gate.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

CONTAINMENT_THRESHOLD = 0.6

_WORD = re.compile(r"[^a-z0-9 ]")


@dataclass(frozen=True)
class FindingUnit:
    """One defect span: the attributed code-set + the evidence that clustered it."""

    codes: tuple[str, ...]
    quotes: tuple[str, ...]
    judges: tuple[str, ...]


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_WORD.sub(" ", (text or "").lower()).split())


def _containment(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _overlapping(quotes_a: list[str], quotes_b: list[str]) -> bool:
    toks_a = [_tokens(q) for q in quotes_a]
    toks_b = [_tokens(q) for q in quotes_b]
    return any(
        _containment(ta, tb) >= CONTAINMENT_THRESHOLD for ta in toks_a for tb in toks_b
    )


def consolidate(
    active_codes: Iterable[str],
    evidence: Iterable[Mapping],
    code_families: Mapping[str, Iterable[str]] | None,
) -> list[FindingUnit]:
    """Cluster the case's ACTIVE codes into finding units.

    ``evidence`` is the grade record's ``result.semantic.evidence`` shape —
    ``[{judge, violation_code, spans: [{quote}]}]``. Codes cluster iff they share a
    ``code_families`` family AND any pair of their quotes overlaps (token containment
    >= :data:`CONTAINMENT_THRESHOLD`); connected components merge transitively. No
    families declared -> every active code is its own unit (behavior-identical
    default). A code SHOULD belong to at most one family; if declared in several,
    the last-declared family wins (dict order) — a declaration hygiene rule, not a
    merge widener. INVARIANT: the union of unit codes == the active codes — the
    clerk reshapes attribution, it never adds or drops a finding.
    """
    active = sorted({c for c in active_codes if c})
    quotes: dict[str, list[str]] = {c: [] for c in active}
    judges: dict[str, list[str]] = {c: [] for c in active}
    for e in evidence or ():
        code = e.get("violation_code")
        if code not in quotes:
            continue
        judge = e.get("judge")
        if judge and judge not in judges[code]:
            judges[code].append(judge)
        for span in e.get("spans") or ():
            quote = (span.get("quote") or "").strip()
            if quote and quote not in quotes[code]:
                quotes[code].append(quote)

    family_of: dict[str, str] = {}
    for family, members in (code_families or {}).items():
        for code in members or ():
            family_of[code] = family

    edges: dict[str, set[str]] = {c: set() for c in active}
    candidates = [c for c in active if c in family_of and quotes[c]]
    for i, c1 in enumerate(candidates):
        for c2 in candidates[i + 1 :]:
            if family_of[c1] != family_of[c2]:
                continue
            if _overlapping(quotes[c1], quotes[c2]):
                edges[c1].add(c2)
                edges[c2].add(c1)

    units: list[FindingUnit] = []
    seen: set[str] = set()
    for code in active:
        if code in seen:
            continue
        component: set[str] = set()
        stack = [code]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(edges[current] - component)
        seen |= component
        members = sorted(component)
        unit_quotes: list[str] = []
        unit_judges: list[str] = []
        for m in members:
            for q in quotes[m]:
                if q not in unit_quotes:
                    unit_quotes.append(q)
            for j in judges[m]:
                if j not in unit_judges:
                    unit_judges.append(j)
        units.append(
            FindingUnit(codes=tuple(members), quotes=tuple(unit_quotes), judges=tuple(unit_judges))
        )
    return units


def _unit_codes(unit) -> set[str]:
    if isinstance(unit, FindingUnit):
        return set(unit.codes)
    return set(unit)


def _family_closure(
    codes: Iterable[str], code_families: Mapping[str, Iterable[str]] | None
) -> set[str]:
    """``codes`` ∪ every declared same-family sibling of each code. ``None`` families ⇒
    the codes unchanged (exact match)."""
    out = set(codes)
    if not code_families:
        return out
    families = [set(ms or ()) for ms in code_families.values()]
    for code in list(out):
        for members in families:
            if code in members:
                out |= members
    return out


def score_units(
    units_by_case: Mapping[str, Iterable],
    gold_by_case: Mapping[str, set[str]],
    code_families: Mapping[str, Iterable[str]] | None = None,
) -> dict:
    """Score consolidated units against per-case gold code-sets.

    A unit is a TP if gold intersects its code-set (the defect was caught, whatever
    the judges named it), else ONE FP (a wrong cluster never multi-counts). Recall is
    over GOLD CODES (``matched_gold``), so a unit covering two golds credits both —
    precision is honest at the unit level, recall at the gold level. Units may be
    :class:`FindingUnit` or plain code iterables (the BFF matrix rides code lists).

    LAYER3-DESCOPE-1: with ``code_families`` given, matching is FAMILY-AWARE — a gold
    code is caught when a DECLARED SIBLING fired on it (the recall-side mirror of the
    twin-FP merge; e.g. gpt-4.1 codes UNSUPPORTED_ASSERTION as its FABRICATED_CLAIM
    sibling). Implemented by expanding gold to its family-closure before intersecting;
    a gold code is ``matched`` iff a unit-code lies in its own family-closure. ``None``
    (the default) is exact match — byte-identical to the pre-Layer-3 behavior.
    """
    tp = fp = fn = matched_total = 0
    for cid, gold in gold_by_case.items():
        gold_closure = _family_closure(gold, code_families)
        # per gold code, the sibling set a caught unit-code may land in
        closure_of = {g: _family_closure({g}, code_families) for g in gold}
        matched: set[str] = set()
        for unit in units_by_case.get(cid) or ():
            ucodes = _unit_codes(unit)
            if ucodes & gold_closure:
                tp += 1
                matched |= {g for g, clo in closure_of.items() if ucodes & clo}
            else:
                fp += 1
        matched_total += len(matched)
        fn += len(gold - matched)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = matched_total / (matched_total + fn) if matched_total + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "matched_gold": matched_total,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }
