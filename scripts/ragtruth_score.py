#!/usr/bin/env python
"""Score a graded RAGTruth slice against its human labels, the way the paper does.

Reads the slice file (``scripts/ragtruth_cases.py --slice``) for the human spans and the
BFF's run trail (``GET /v1/runs`` + ``/v1/runs/{id}/audit``) for the latest verdict and each
judge's evidence spans per case, then reports, per task and overall:

  response level  precision / recall / F1 of "hallucinated" (verdict BLOCK/WARN after the
                  floor, vs. the human label "any span"), the paper's Table 4 metric;
  span level      a predicted span is a hit when it overlaps any human span by character
                  range; recall counts human spans overlapped by any predicted span (the
                  paper's character-overlap span metric, Table 5).

Judge evidence spans arrive as quotes; each is located in the response text (first exact
occurrence, else the longest common prefix match) to get a character range. Quotes that
cannot be located are counted as predicted spans with no overlap (a miss for precision),
never silently dropped.

Usage:
    python scripts/ragtruth_score.py --slice out/ragtruth/slice_pilot.jsonl [--bff http://localhost:8787]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import defaultdict
from pathlib import Path


def _get(bff: str, path: str) -> dict:
    with urllib.request.urlopen(bff + path, timeout=60) as r:
        return json.load(r)


def _prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p is not None and r is not None and p + r else None
    return p, r, f


def _fmt(x: float | None) -> str:
    return "  n/a" if x is None else f"{100 * x:5.1f}"


def locate(quote: str, text: str) -> tuple[int, int] | None:
    q = quote.strip().strip('"').strip("'")
    if not q:
        return None
    i = text.find(q)
    if i >= 0:
        return i, i + len(q)
    low_i = text.lower().find(q.lower())
    if low_i >= 0:
        return low_i, low_i + len(q)
    # longest prefix of the quote (word-bounded) that occurs in the text
    words = q.split()
    for n in range(len(words) - 1, 2, -1):
        head = " ".join(words[:n])
        j = text.find(head)
        if j >= 0:
            return j, j + len(head)
    return None


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def score(slice_rows: list[dict], audits: dict[str, dict]) -> dict:
    per_task: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_code: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unlocated: list[tuple[str, str]] = []
    for case in slice_rows:
        cid = case["case_id"]
        task = case["ragtruth"]["task_type"]
        audit = audits.get(cid)
        if audit is None:
            per_task[task]["ungraded"] += 1
            continue
        t = per_task[task]
        t["graded"] += 1
        if any(j.get("errors") for j in audit.get("judges") or []):
            t["refused"] += (
                1  # a judge call failed (e.g. a content-filter refusal); decided without it
            )
        human = [(lab["start"], lab["end"]) for lab in case["ragtruth"]["labels"]]
        gold_hall = bool(human)
        verdict = (audit.get("grounded_verdict") or audit.get("verdict") or "").upper()
        pred_hall = verdict in ("BLOCK", "WARN", "REJECT", "NEEDS_REVIEW")
        t["r_tp"] += pred_hall and gold_hall
        t["r_fp"] += pred_hall and not gold_hall
        t["r_fn"] += (not pred_hall) and gold_hall
        t["r_tn"] += (not pred_hall) and (not gold_hall)
        # per-code (case level): the codes the judges raised vs the codes the human labels map to
        gold_codes = {
            lab.get("code") for lab in case["ragtruth"]["labels"] if lab.get("code")
        } or set(case.get("expected_safety_flags") or [])
        raised_codes = {c for j in audit.get("judges") or [] for c in (j.get("findings") or [])}
        for code in gold_codes | raised_codes:
            per_code[code]["tp"] += code in gold_codes and code in raised_codes
            per_code[code]["fp"] += code in raised_codes and code not in gold_codes
            per_code[code]["fn"] += code in gold_codes and code not in raised_codes
        response = case["artifacts"][0]["content"]
        pred_spans: list[tuple[int, int]] = []
        seen: set[str] = set()
        for j in audit.get("judges") or []:
            for ev in j.get("evidence") or []:
                if ev.get("judge") not in (j.get("judge_role"), None):
                    continue
                for sp in ev.get("spans") or []:
                    quote = (sp.get("quote") or "").strip()
                    if not quote or quote in seen:
                        continue
                    seen.add(quote)
                    rng = locate(quote, response)
                    if rng is None:
                        unlocated.append((cid, quote[:60]))
                        t["s_fp"] += 1
                        continue
                    pred_spans.append(rng)
        for ps in pred_spans:
            if any(_overlaps(ps, h) for h in human):
                t["s_tp"] += 1
            else:
                t["s_fp"] += 1
        for h in human:
            if not any(_overlaps(ps, h) for ps in pred_spans):
                t["s_fn"] += 1
    overall: dict[str, int] = defaultdict(int)
    for t in per_task.values():
        for k, v in t.items():
            overall[k] += v
    per_task["OVERALL"] = overall
    return {"per_task": per_task, "per_code": per_code, "unlocated": unlocated}


def audits_from_predictions(path: Path, slice_rows: list[dict]) -> dict[str, dict]:
    """PAPER-PROMPT-1: shape a predictions file (scripts/ragtruth_paper_prompt.py) like the run
    audits ``score`` reads, so one scorer scores every row of the table. An untyped prediction
    carries no code (per-code rows stay empty by construction); a row with an error is a judge
    that answered nothing (verdict PASS, ``errors`` set), a miss on a positive."""
    known = {r["case_id"] for r in slice_rows}
    audits: dict[str, dict] = {}
    for line in path.open():
        if not line.strip():
            continue
        p = json.loads(line)
        if p["case_id"] not in known:
            continue
        err = p.get("error")
        hall = bool(p.get("hallucinated")) and not err
        audits[p["case_id"]] = {
            "grounded_verdict": "BLOCK" if hall else "PASS",
            "judges": [
                {
                    "judge_role": "paper_prompt",
                    "vote": "BLOCK" if hall else "PASS",
                    "findings": [],
                    "errors": [err] if err else [],
                    "evidence": [
                        {"judge": "paper_prompt", "violation_code": None, "spans": [{"quote": q}]}
                        for q in (p.get("spans") or [])
                    ],
                }
            ],
        }
    return audits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", type=Path, required=True)
    ap.add_argument(
        "--grade",
        type=Path,
        default=None,
        help="score the runs named in a cohort grade file (grade_<tag>.json, its matrix rows' "
        "run_id) instead of each case's latest run: re-scores a historical round",
    )
    ap.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="score a paper-prompt predictions file instead of the run trail (untyped spans: "
        "response- and span-level only)",
    )
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument(
        "--vocabulary",
        default="ragtruth",
        help="the kind:importer dataset whose terms label the per-code rows (IMPORTER-1); "
        "'' to print taxonomy codes only",
    )
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.slice.open()]
    audits: dict[str, dict] = {}
    if args.predictions:
        audits = audits_from_predictions(args.predictions, rows)
        print(f"scoring predictions file {args.predictions} (untyped spans: no per-code rows)")
    elif args.grade:
        grade = json.loads(args.grade.read_text())
        run_ids = {
            r["case_id"]: r.get("run_id") for r in grade.get("matrix") or [] if r.get("run_id")
        }
        print(f"scoring the {len(run_ids)} runs named in {args.grade}")
        for case in rows:
            rid = run_ids.get(case["case_id"])
            if rid:
                audits[case["case_id"]] = _get(args.bff, f"/v1/runs/{rid}/audit")
    else:
        for case in rows:
            cid = case["case_id"]
            runs = (
                _get(args.bff, f"/v1/runs?agent={args.agent}&case_id={cid}&limit=1").get("runs")
                or []
            )
            if runs:
                audits[cid] = _get(args.bff, f"/v1/runs/{runs[0]['run_id']}/audit")
    res = score(rows, audits)
    print(
        f"{'task':10s} {'n':>3s} {'P':>6s} {'R':>6s} {'F1':>6s}   |  span {'P':>6s} {'R':>6s} {'F1':>6s}"
    )
    for task in sorted(res["per_task"], key=lambda k: (k == "OVERALL", k)):
        t = res["per_task"][task]
        rp, rr, rf = _prf(t["r_tp"], t["r_fp"], t["r_fn"])
        sp, sr, sf = _prf(t["s_tp"], t["s_fp"], t["s_fn"])
        note = f"  ({t['ungraded']} ungraded)" if t.get("ungraded") else ""
        if t.get("refused"):
            note += f"  [{t['refused']} judge call(s) refused/failed, decided without the vote]"
        print(
            f"{task:10s} {t['graded']:3d} {_fmt(rp)} {_fmt(rr)} {_fmt(rf)}   |       {_fmt(sp)} {_fmt(sr)} {_fmt(sf)}{note}"
        )
    vocab = None
    if args.predictions:
        print(
            "\nper code: not applicable (the predictions are untyped spans; scored at response and "
            "span level only)"
        )
    elif args.vocabulary:
        from lithrim_bench.harness.plugins import importer_vocabulary

        vocab = importer_vocabulary(args.vocabulary, pack="_core")
    print(
        f"\nper code (case level; judge raised vs human label{', ' + vocab.dataset + ' terms in brackets' if vocab else ''}):"
    )
    for code in sorted(res["per_code"]) if not args.predictions else []:
        c = res["per_code"][code]
        p, r, f = _prf(c["tp"], c["fp"], c["fn"])
        term = (
            f" [{' / '.join(vocab.terms_for(code)) or vocab.untyped_prediction_class.split(';')[0]}]"
            if vocab
            else ""
        )
        print(
            f"  {code}{term}: tp {c['tp']} fp {c['fp']} fn {c['fn']}  P {_fmt(p)} R {_fmt(r)} F1 {_fmt(f)}"
        )
    if vocab and not args.predictions:
        print(
            f"  verdict rule: {vocab.verdict_rule.get(vocab.dataset)} == {vocab.verdict_rule.get('lithrim')}"
        )
    if res["unlocated"]:
        print(
            f"\n{len(res['unlocated'])} judge quote(s) not located in the response (counted as span FPs):"
        )
        for cid, q in res["unlocated"][:10]:
            print(f"  {cid}: {q!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
