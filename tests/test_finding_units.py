"""FINDING-UNITS-1 — the span-cluster attribution clerk (pure module).

One defect span = ONE finding unit. Sibling codes from an ontology-declared
``code_family`` that fired on OVERLAPPING evidence quotes consolidate into a single
unit carrying the full code-set. A clerk, NOT a critic: it never judges correctness,
never drops a code (A2 invariant), so it cannot lose recall. Validated offline on the
2026-07-01 clean baseline: strict P=27.0% -> unit P=46.3%, R identical (the oracle
ceiling, reached blind). Rule constants (family membership, containment >= 0.6) are
gate-validated — do not tune without re-running the corpus gate (A6).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lithrim_bench.harness.finding_units import FindingUnit, consolidate, score_units

FAMILIES = {
    "fabrication": [
        "VALUE_MISMATCH",
        "SOURCE_CONTRADICTION",
        "HALLUCINATED_DETAIL",
        "FABRICATED_CLAIM",
        "INTERNAL_INCONSISTENCY",
    ]
}


def _ev(code, *quotes, judge="faithfulness_judge"):
    return {"judge": judge, "violation_code": code, "spans": [{"quote": q} for q in quotes]}


def codes_of(units):
    return sorted(sorted(u.codes) for u in units)


# ---- A1: twin-merge -----------------------------------------------------------------


def test_a1_twin_codes_on_overlapping_span_merge_into_one_unit():
    active = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"}
    evidence = [
        _ev("FABRICATED_CLAIM", "mild pitting edema noted bilaterally in the lower extremities"),
        _ev("HALLUCINATED_DETAIL", "pitting edema noted bilaterally", judge="risk_judge"),
    ]
    units = consolidate(active, evidence, FAMILIES)
    assert len(units) == 1
    (u,) = units
    assert set(u.codes) == active
    assert "risk_judge" in u.judges and "faithfulness_judge" in u.judges
    assert any("edema" in q for q in u.quotes)


# ---- A2: no-drop invariant -----------------------------------------------------------


def test_a2_union_of_unit_codes_always_equals_active_codes():
    active = {
        "FABRICATED_CLAIM",
        "HALLUCINATED_DETAIL",
        "INTERNAL_INCONSISTENCY",
        "HISTORY_OMISSION",
        "MISSING_CONTEXT",
    }
    evidence = [
        _ev("FABRICATED_CLAIM", "positive Phalen's test on the right wrist"),
        _ev("HALLUCINATED_DETAIL", "positive Phalen's test", judge="risk_judge"),
        _ev("INTERNAL_INCONSISTENCY", "note contradicts its own medication list"),
        _ev("HISTORY_OMISSION", "patient reported a 1970 hospitalization"),
        # MISSING_CONTEXT: active but no evidence quote at all
    ]
    units = consolidate(active, evidence, FAMILIES)
    assert set().union(*(set(u.codes) for u in units)) == active


# ---- A3: default-inert without code_families ------------------------------------------


def test_a3_no_code_families_means_one_unit_per_active_code():
    active = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"}
    evidence = [
        _ev("FABRICATED_CLAIM", "pitting edema noted bilaterally"),
        _ev("HALLUCINATED_DETAIL", "pitting edema noted bilaterally", judge="risk_judge"),
    ]
    for families in (None, {}):
        units = consolidate(active, evidence, families)
        assert codes_of(units) == [["FABRICATED_CLAIM"], ["HALLUCINATED_DETAIL"]]


# ---- A4: never merge across family lines / disjoint spans / missing quotes ------------


def test_a4_non_family_codes_never_merge_even_on_identical_quotes():
    active = {"FABRICATED_CLAIM", "HISTORY_OMISSION"}
    q = "patient denies chest pain at rest"
    units = consolidate(
        active,
        [_ev("FABRICATED_CLAIM", q), _ev("HISTORY_OMISSION", q, judge="risk_judge")],
        FAMILIES,
    )
    assert codes_of(units) == [["FABRICATED_CLAIM"], ["HISTORY_OMISSION"]]


def test_a4_family_codes_on_disjoint_spans_stay_separate():
    active = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"}
    units = consolidate(
        active,
        [
            _ev("FABRICATED_CLAIM", "sibling with colon cancer"),
            _ev("HALLUCINATED_DETAIL", "positive Tinel's sign at the right carpal tunnel"),
        ],
        FAMILIES,
    )
    assert codes_of(units) == [["FABRICATED_CLAIM"], ["HALLUCINATED_DETAIL"]]


def test_a4_active_code_without_quotes_stays_a_singleton():
    active = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL"}
    units = consolidate(active, [_ev("FABRICATED_CLAIM", "pitting edema")], FAMILIES)
    assert codes_of(units) == [["FABRICATED_CLAIM"], ["HALLUCINATED_DETAIL"]]


def test_a4_transitive_overlap_clusters_three_codes():
    active = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY"}
    units = consolidate(
        active,
        [
            _ev("FABRICATED_CLAIM", "opioid use disorder actively seeking additional prescriptions"),
            _ev("HALLUCINATED_DETAIL", "opioid use disorder actively seeking", judge="risk_judge"),
            _ev(
                "INTERNAL_INCONSISTENCY",
                "actively seeking additional prescriptions today",
                judge="policy_judge",
            ),
        ],
        FAMILIES,
    )
    assert codes_of(units) == [
        ["FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY"]
    ]


# ---- A5: unit scoring semantics --------------------------------------------------------


def test_a5_twin_fp_disappears_under_unit_scoring():
    # gold = FABRICATED_CLAIM; judges raised the gold code + its twin on the same span.
    units = [
        FindingUnit(
            codes=("FABRICATED_CLAIM", "HALLUCINATED_DETAIL"),
            quotes=("pitting edema",),
            judges=("faithfulness_judge", "risk_judge"),
        )
    ]
    s = score_units({"c1": units}, {"c1": {"FABRICATED_CLAIM"}})
    assert (s["tp"], s["fp"], s["fn"]) == (1, 0, 0)
    assert s["precision"] == 1.0 and s["recall"] == 1.0


def test_a5_wrong_family_cluster_scores_exactly_one_fp():
    units = [
        FindingUnit(
            codes=("FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY"),
            quotes=("q",),
            judges=("j",),
        )
    ]
    s = score_units({"c1": units}, {"c1": set()})
    assert (s["tp"], s["fp"], s["fn"]) == (0, 1, 0)


def test_a5_unmatched_gold_counts_fn_and_one_unit_credits_each_gold_once():
    units = [
        FindingUnit(codes=("FABRICATED_CLAIM", "VALUE_MISMATCH"), quotes=("q",), judges=("j",)),
    ]
    s = score_units(
        {"c1": units}, {"c1": {"FABRICATED_CLAIM", "VALUE_MISMATCH", "HISTORY_OMISSION"}}
    )
    # ONE unit hits two golds: 1 TP unit, both golds matched, the third gold is the FN.
    assert (s["tp"], s["fp"], s["fn"]) == (1, 0, 1)


# ---- A7: family-aware recall (LAYER3-DESCOPE-1) ---------------------------------------
# A gold code is caught when a DECLARED SIBLING fires on it — the recall-side mirror of the
# twin-FP merge. UNSUPPORTED_ASSERTION (a fabrication sibling gpt-4.1 codes as
# FABRICATED_CLAIM) is credited at unit level without a judge change. code_families=None
# stays byte-identical (A1-A6 above are the non-vacuity proof).
_FAM = {"fabrication": ["FABRICATED_CLAIM", "UNSUPPORTED_ASSERTION", "HALLUCINATED_DETAIL"]}


def test_a7_gold_matched_when_a_declared_sibling_was_caught():
    # judge raised FABRICATED_CLAIM; gold is the sibling UNSUPPORTED_ASSERTION.
    units = [FindingUnit(codes=("FABRICATED_CLAIM",), quotes=("q",), judges=("j",))]
    s = score_units({"c": units}, {"c": {"UNSUPPORTED_ASSERTION"}}, code_families=_FAM)
    assert (s["tp"], s["fp"], s["fn"], s["matched_gold"]) == (1, 0, 0, 1)


def test_a7_unrelated_code_does_not_family_match():
    # VALUE_MISMATCH is NOT in the fabrication family — must NOT credit the gold.
    units = [FindingUnit(codes=("VALUE_MISMATCH",), quotes=("q",), judges=("j",))]
    s = score_units({"c": units}, {"c": {"UNSUPPORTED_ASSERTION"}}, code_families=_FAM)
    assert (s["tp"], s["fp"], s["fn"], s["matched_gold"]) == (0, 1, 1, 0)


def test_a7_none_families_is_byte_identical_to_exact_match():
    units = [FindingUnit(codes=("FABRICATED_CLAIM",), quotes=("q",), judges=("j",))]
    gold = {"c": {"UNSUPPORTED_ASSERTION"}}
    assert score_units({"c": units}, gold) == score_units({"c": units}, gold, code_families=None)
    # and with no families the sibling is NOT credited (the pre-Layer-3 behavior)
    assert score_units({"c": units}, gold)["fn"] == 1


def test_a7_exact_gold_still_matches_and_no_double_count():
    # both the exact code and a sibling present: still one unit TP, gold matched once.
    units = [FindingUnit(codes=("FABRICATED_CLAIM", "UNSUPPORTED_ASSERTION"), quotes=("q",), judges=("j",))]
    s = score_units({"c": units}, {"c": {"UNSUPPORTED_ASSERTION"}}, code_families=_FAM)
    assert (s["tp"], s["fp"], s["fn"], s["matched_gold"]) == (1, 0, 0, 1)


# ---- A6: the corpus gate (the real referee; skips when the snapshot is absent) ---------

_CLEANRUN = os.environ.get("LITHRIM_BENCH_CLEANRUN_DIR", "")
_CORPUS = (
    Path(__file__).resolve().parents[1]
    / "packs-dropin"
    / "clinverdict"
    / "examples"
    / "clinverdict_mts_v1.jsonl"
)


@pytest.mark.skipif(
    not (_CLEANRUN and Path(_CLEANRUN).is_dir() and _CORPUS.is_file()),
    reason="clean-run snapshot not present (set LITHRIM_BENCH_CLEANRUN_DIR)",
)
def test_a6_corpus_gate_unit_tp_equals_strict_tp_and_recall_never_drops():
    gold = {}
    for line in _CORPUS.read_text().splitlines():
        row = json.loads(line)
        gold[row["case_id"]] = set(row.get("expected_safety_flags") or [])
    strict_tp = strict_fn = 0
    units_by_case, gold_by_case = {}, {}
    for f in sorted(Path(_CLEANRUN).glob("cv_mts_*.json")):
        rec = json.loads(f.read_text())
        cid = rec.get("case_id")
        if cid not in gold:
            continue
        active = {
            (x.get("code") or x.get("flag_code"))
            for x in (rec.get("grounded") or {}).get("active", [])
        }
        evidence = ((rec.get("result") or {}).get("semantic") or {}).get("evidence") or []
        units_by_case[cid] = consolidate(active, evidence, FAMILIES)
        gold_by_case[cid] = gold[cid]
        strict_tp += len(active & gold[cid])
        strict_fn += len(gold[cid] - active)
    assert len(units_by_case) == 173
    s = score_units(units_by_case, gold_by_case)
    # The clerk merges attribution; it must never lose a catch.
    assert s["tp"] == strict_tp
    assert s["fn"] == strict_fn
    strict_recall = strict_tp / (strict_tp + strict_fn)
    assert s["recall"] >= strict_recall
