"""Offline analysis — what does the same N=12 data look like under different
composition strategies than worst-of?

Reads out/pilot_thesis_n12_trio.ndjson (or a path you pass), computes 5 strategies,
emits a comparison table. No API calls — pure re-aggregation of existing votes.

Strategies tested:
  worst-of            (current baseline)  reject > needs_review > approve
  majority            ≥2/3 agree wins; else worst-of
  llama-tiebreak      ≥2/3 agree wins; ties (1-1-1) broken by Llama
  llama-veto-approve  if Llama=approve AND no judge rejects → final=approve; else worst-of
  conf-gated          gpt-4.1 + Llama votes ignored if conf < 0.85; Mistral always counted; then worst-of

Goal: find the strategy that keeps 10/10 defect catch while dropping FP rate on cleans.

Usage:
    python3 scripts/analyze_composition_strategies.py [path/to/ndjson]
    # default: out/pilot_thesis_n12_trio.ndjson
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GPT = "gpt-4.1"
MISTRAL = "Mistral-Large-3"
LLAMA = "Llama-4-Maverick-17B-128E-Instruct-FP8"

VERDICT_ORDER = {"reject": 3, "needs_review": 2, "approve": 1}


def worst_of(verdicts):
    valid = [v for v in verdicts if v in VERDICT_ORDER]
    if not valid:
        return None
    return max(valid, key=lambda v: VERDICT_ORDER[v])


def is_catch(v):
    return v in ("reject", "needs_review")


def is_match(observed, expected):
    if expected is None:
        return False
    if isinstance(expected, str):
        return observed == expected
    if isinstance(expected, list):
        return observed in expected
    return False


# ------- Strategies -------

def s_worst_of(row):
    verdicts = [row["models"][m].get("verdict") for m in (GPT, MISTRAL, LLAMA)]
    return worst_of(verdicts)


def s_majority(row):
    verdicts = [row["models"][m].get("verdict") for m in (GPT, MISTRAL, LLAMA)]
    c = Counter(v for v in verdicts if v)
    if not c:
        return None
    top, n = c.most_common(1)[0]
    if n >= 2:
        return top
    return worst_of(verdicts)


def s_llama_tiebreak(row):
    verdicts = [row["models"][m].get("verdict") for m in (GPT, MISTRAL, LLAMA)]
    c = Counter(v for v in verdicts if v)
    if not c:
        return None
    top, n = c.most_common(1)[0]
    if n >= 2:
        return top
    # 1-1-1 tie — Llama tiebreaks
    return row["models"][LLAMA].get("verdict") or worst_of(verdicts)


def s_llama_veto_approve(row):
    llama = row["models"][LLAMA].get("verdict")
    others = [row["models"][GPT].get("verdict"), row["models"][MISTRAL].get("verdict")]
    if llama == "approve" and "reject" not in others:
        return "approve"
    verdicts = [llama] + others
    return worst_of(verdicts)


def s_conf_gated(row, threshold=0.85):
    """gpt-4.1 + Llama votes ignored if confidence < threshold (treated as approve).
    Mistral always counted (no confidence available)."""
    effective = []
    for m in (GPT, MISTRAL, LLAMA):
        mr = row["models"][m]
        v = mr.get("verdict")
        c = mr.get("confidence")
        if c is None:
            effective.append(v)  # Mistral always counts
        elif c >= threshold:
            effective.append(v)
        else:
            effective.append("approve")  # uncertain → don't escalate
    return worst_of(effective)


STRATEGIES = [
    ("worst-of",            s_worst_of),
    ("majority",            s_majority),
    ("llama-tiebreak",      s_llama_tiebreak),
    ("llama-veto-approve",  s_llama_veto_approve),
    ("conf-gated@0.85",     s_conf_gated),
]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "out" / "pilot_thesis_n12_trio.ndjson"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run test_n12_trio.py first.")

    rows = []
    with path.open() as fp:
        for line in fp:
            rows.append(json.loads(line))

    defects = [r for r in rows if not r.get("clean_negative")]
    cleans = [r for r in rows if r.get("clean_negative")]

    print(f"Loaded {len(rows)} rows from {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    print(f"{len(defects)} defects, {len(cleans)} clean negatives\n")

    # Compute strategy results per row
    strategy_outcomes = {name: [] for name, _ in STRATEGIES}
    for r in rows:
        for name, fn in STRATEGIES:
            verdict = fn(r)
            strategy_outcomes[name].append({
                "pick": r["pick_label"],
                "case_id": r["case_id"],
                "clean": r.get("clean_negative", False),
                "expected": r["expected_compliance_verdict"],
                "verdict": verdict,
                "catch": is_catch(verdict),
                "match": is_match(verdict, r["expected_compliance_verdict"]),
                "fp": r.get("clean_negative") and is_catch(verdict),
            })

    # Aggregate per strategy
    print("=" * 88)
    print(f"{'Strategy':<22} {'Catch/Defect':<14} {'FP/Clean':<10} {'Match':<10} {'Unanim':<10}")
    print("-" * 88)
    for name, _ in STRATEGIES:
        outcomes = strategy_outcomes[name]
        defect_outcomes = [o for o in outcomes if not o["clean"]]
        clean_outcomes = [o for o in outcomes if o["clean"]]
        catches = sum(1 for o in defect_outcomes if o["catch"])
        fps = sum(1 for o in clean_outcomes if o["fp"])
        matches = sum(1 for o in outcomes if o["match"])
        print(f"{name:<22} {catches}/{len(defect_outcomes):<13} {fps}/{len(clean_outcomes):<10} {matches}/{len(outcomes):<10}")

    print("\n" + "=" * 88)
    print("PER-CASE — what each strategy says, in order")
    print("=" * 88)
    print(f"{'Pick':<5} {'Kind':<8} {'Expected':<22} ", end="")
    for name, _ in STRATEGIES:
        print(f"{name[:16]:<18}", end="")
    print()
    print("-" * 130)
    for i, r in enumerate(rows):
        exp = r["expected_compliance_verdict"]
        exp_str = "/".join(exp) if isinstance(exp, list) else (exp or "—")
        kind = "clean" if r.get("clean_negative") else ("multi" if r.get("multi_defect") else "defect")
        print(f"{r['pick_label']:<5} {kind:<8} {exp_str:<22} ", end="")
        for name, _ in STRATEGIES:
            v = strategy_outcomes[name][i]["verdict"] or "?"
            match_marker = "✓" if strategy_outcomes[name][i]["match"] else " "
            if strategy_outcomes[name][i]["fp"]:
                cell = f"{v}❌"
            else:
                cell = f"{v}{match_marker}"
            print(f"{cell:<18}", end="")
        print()

    # Recommendation
    print("\n" + "=" * 88)
    print("RECOMMENDATION")
    print("=" * 88)
    best_no_fp = []
    for name, _ in STRATEGIES:
        outcomes = strategy_outcomes[name]
        defect_outcomes = [o for o in outcomes if not o["clean"]]
        clean_outcomes = [o for o in outcomes if o["clean"]]
        catches = sum(1 for o in defect_outcomes if o["catch"])
        fps = sum(1 for o in clean_outcomes if o["fp"])
        matches = sum(1 for o in outcomes if o["match"])
        # Score: prioritize zero FP, then defect catches, then matches
        score = (-fps, catches, matches)
        best_no_fp.append((score, name, catches, fps, matches, len(defect_outcomes), len(clean_outcomes), len(outcomes)))
    best_no_fp.sort(reverse=True)
    print()
    print("Strategies ranked (zero-FP first, then catches, then match-rate):")
    for rank, (score, name, catches, fps, matches, nd, nc, nt) in enumerate(best_no_fp, 1):
        marker = " ← BEST" if rank == 1 else ""
        print(f"  {rank}. {name:<22}  catches={catches}/{nd}  fp={fps}/{nc}  match={matches}/{nt}{marker}")


if __name__ == "__main__":
    main()
