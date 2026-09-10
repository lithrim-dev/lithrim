"""Score a graded labeled slice against its human spans, in both vocabularies.

Reads the slice file for the human spans (``gold_spans_path`` of the importer manifest, else
top-level ``gold_spans``) and the BFF's run trail (``/v1/runs/{id}/audit``) for the latest
verdict and each judge's evidence spans per case, then reports, per task and overall:

  response level  precision / recall / F1 of "hallucinated" (verdict BLOCK/WARN after the
                  floor, vs. the human label "any span");
  span level      a predicted span is a hit when it overlaps any human span by character
                  range; recall counts human spans overlapped by any predicted span.

Judge evidence spans arrive as quotes; each is located in the response text (first exact
occurrence, else the longest common prefix match) to get a character range. Quotes that
cannot be located are counted as predicted spans with no overlap (a miss for precision),
never silently dropped. Per-code rows name the taxonomy code and the dataset's own terms.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from lithrim_bench.harness.plugins import (
    case_gold_spans,
    case_task,
    default_importer,
    importer_vocabulary,
)

from . import http


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


def score(slice_rows: list[dict], audits: dict[str, dict], *, pack: str | None = None) -> dict:
    per_task: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_code: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unlocated: list[tuple[str, str]] = []
    for case in slice_rows:
        cid = case["case_id"]
        task = case_task(case, pack=pack) or "ALL"
        gold_spans = case_gold_spans(case, pack=pack) or []
        audit = audits.get(cid)
        if audit is None:
            per_task[task]["ungraded"] += 1
            continue
        t = per_task[task]
        t["graded"] += 1
        if any(j.get("errors") for j in audit.get("judges") or []):
            # a judge call failed (e.g. a content-filter refusal); decided without it
            t["refused"] += 1
        human = [
            (lab["start"], lab["end"])
            for lab in gold_spans
            if lab.get("start") is not None and lab.get("end") is not None
        ]
        gold_hall = bool(gold_spans)
        verdict = (audit.get("grounded_verdict") or audit.get("verdict") or "").upper()
        pred_hall = verdict in ("BLOCK", "WARN", "REJECT", "NEEDS_REVIEW")
        t["r_tp"] += pred_hall and gold_hall
        t["r_fp"] += pred_hall and not gold_hall
        t["r_fn"] += (not pred_hall) and gold_hall
        t["r_tn"] += (not pred_hall) and (not gold_hall)
        # per-code (case level): the codes the judges raised vs the codes the human labels map to
        gold_codes = {lab.get("code") for lab in gold_spans if lab.get("code")} or set(
            case.get("expected_safety_flags") or []
        )
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
    """Shape a predictions file (an external detector's ``{case_id, hallucinated, spans[],
    error}`` rows) like the run audits ``score`` reads, so one scorer scores every row of a
    table. An untyped prediction carries no code (per-code rows stay empty by construction); a
    row with an error is a judge that answered nothing (verdict PASS, ``errors`` set)."""
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
                    "judge_role": "predictions",
                    "vote": "BLOCK" if hall else "PASS",
                    "findings": [],
                    "errors": [err] if err else [],
                    "evidence": [
                        {"judge": "predictions", "violation_code": None, "spans": [{"quote": q}]}
                        for q in (p.get("spans") or [])
                    ],
                }
            ],
        }
    return audits


def audits_for_grade(bff: str, grade: dict, slice_rows: list[dict]) -> dict[str, dict]:
    """The audits of exactly the runs a cohort grade file names (its matrix rows' run_id)."""
    run_ids = {r["case_id"]: r.get("run_id") for r in grade.get("matrix") or [] if r.get("run_id")}
    audits: dict[str, dict] = {}
    for case in slice_rows:
        rid = run_ids.get(case["case_id"])
        if rid:
            audits[case["case_id"]] = http.get(bff, f"/v1/runs/{rid}/audit")
    return audits


def audits_latest(bff: str, agent: str, slice_rows: list[dict]) -> dict[str, dict]:
    """Each case's latest run audit in the trail."""
    audits: dict[str, dict] = {}
    for case in slice_rows:
        cid = case["case_id"]
        runs = http.get(bff, f"/v1/runs?agent={agent}&case_id={cid}&limit=1").get("runs") or []
        if runs:
            audits[cid] = http.get(bff, f"/v1/runs/{runs[0]['run_id']}/audit")
    return audits


def resolve_vocabulary(dataset: str | None, pack: str | None = None):
    """The importer manifest to label per-code rows with: the named dataset, else the pack's
    only importer, else None (taxonomy codes only)."""
    if dataset:
        return importer_vocabulary(dataset, pack=pack)
    return default_importer(pack)


def table(res: dict, vocab=None) -> dict:
    """The scorecard as JSON rows (what ``render`` prints, for a service or a UI): per-task
    rows with response- and span-level P/R/F1 (percent, None when undefined) and the refused
    count, per-code rows with the dataset's own terms, the unlocated quotes, and the verdict
    rule in both vocabularies. Dataset-neutral: every dataset word comes from ``vocab``."""
    pct = lambda x: None if x is None else round(100 * x, 1)  # noqa: E731
    per_task = []
    for task in sorted(res["per_task"], key=lambda k: (k == "OVERALL", k)):
        t = res["per_task"][task]
        rp, rr, rf = _prf(t["r_tp"], t["r_fp"], t["r_fn"])
        sp, sr, sf = _prf(t["s_tp"], t["s_fp"], t["s_fn"])
        per_task.append(
            {
                "task": task,
                "n": t["graded"],
                "ungraded": t.get("ungraded", 0),
                "refused": t.get("refused", 0),
                "P": pct(rp),
                "R": pct(rr),
                "F1": pct(rf),
                "span_P": pct(sp),
                "span_R": pct(sr),
                "span_F1": pct(sf),
                "tp": t["r_tp"],
                "fp": t["r_fp"],
                "fn": t["r_fn"],
                "tn": t["r_tn"],
            }
        )
    per_code = []
    for code in sorted(res["per_code"]):
        c = res["per_code"][code]
        p, r, f = _prf(c["tp"], c["fp"], c["fn"])
        per_code.append(
            {
                "code": code,
                "dataset_terms": vocab.terms_for(code) if vocab else [],
                "tp": c["tp"],
                "fp": c["fp"],
                "fn": c["fn"],
                "P": pct(p),
                "R": pct(r),
                "F1": pct(f),
            }
        )
    return {
        "per_task": per_task,
        "per_code": per_code,
        "unlocated": [{"case_id": cid, "quote": q} for cid, q in res["unlocated"]],
        "vocabulary": {
            "id": vocab.id if vocab else None,
            "dataset": vocab.dataset if vocab else None,
            "verdict_rule": dict(vocab.verdict_rule) if vocab else {},
            "untyped_prediction_class": vocab.untyped_prediction_class if vocab else None,
        },
    }


def render(res: dict, vocab=None, *, predictions: bool = False) -> str:
    lines = [
        f"{'task':10s} {'n':>3s} {'P':>6s} {'R':>6s} {'F1':>6s}   |  span {'P':>6s} {'R':>6s} {'F1':>6s}"
    ]
    for task in sorted(res["per_task"], key=lambda k: (k == "OVERALL", k)):
        t = res["per_task"][task]
        rp, rr, rf = _prf(t["r_tp"], t["r_fp"], t["r_fn"])
        sp, sr, sf = _prf(t["s_tp"], t["s_fp"], t["s_fn"])
        note = f"  ({t['ungraded']} ungraded)" if t.get("ungraded") else ""
        if t.get("refused"):
            note += f"  [{t['refused']} judge call(s) refused/failed, decided without the vote]"
        lines.append(
            f"{task:10s} {t['graded']:3d} {_fmt(rp)} {_fmt(rr)} {_fmt(rf)}   |       "
            f"{_fmt(sp)} {_fmt(sr)} {_fmt(sf)}{note}"
        )
    if predictions:
        lines.append(
            "\nper code: not applicable (the predictions are untyped spans; scored at response "
            "and span level only)"
        )
    else:
        terms = f", {vocab.dataset} terms in brackets" if vocab else ""
        lines.append(f"\nper code (case level; judge raised vs human label{terms}):")
        for code in sorted(res["per_code"]):
            c = res["per_code"][code]
            p, r, f = _prf(c["tp"], c["fp"], c["fn"])
            term = ""
            if vocab:
                names = " / ".join(vocab.terms_for(code)) or "no dataset term"
                term = f" [{names}]"
            lines.append(
                f"  {code}{term}: tp {c['tp']} fp {c['fp']} fn {c['fn']}  "
                f"P {_fmt(p)} R {_fmt(r)} F1 {_fmt(f)}"
            )
        if vocab:
            lines.append(
                f"  verdict rule: {vocab.verdict_rule.get(vocab.dataset)} == "
                f"{vocab.verdict_rule.get('lithrim')}"
            )
    if res["unlocated"]:
        lines.append(
            f"\n{len(res['unlocated'])} judge quote(s) not located in the response "
            "(counted as span FPs):"
        )
        for cid, q in res["unlocated"][:10]:
            lines.append(f"  {cid}: {q!r}")
    return "\n".join(lines)


def add_arguments(ap) -> None:
    ap.add_argument("--slice", type=Path, required=True, help="the labeled slice (JSONL)")
    ap.add_argument(
        "--grade",
        type=Path,
        default=None,
        help="score the runs named in a cohort grade file (grade_<tag>.json) instead of each "
        "case's latest run: re-scores a historical round",
    )
    ap.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="score an external predictions file instead of the run trail (untyped spans: "
        "response- and span-level only)",
    )
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument(
        "--vocabulary",
        default=None,
        help="the kind:importer dataset whose terms label the per-code rows; defaults to the "
        "pack's only importer",
    )
    ap.add_argument("--pack", default=None, help="the pack whose importers resolve case paths")


def cmd_score(a) -> int:
    rows = [json.loads(line) for line in a.slice.open() if line.strip()]
    if a.predictions:
        audits = audits_from_predictions(a.predictions, rows)
        print(f"scoring predictions file {a.predictions} (untyped spans: no per-code rows)")
    elif a.grade:
        grade = json.loads(a.grade.read_text())
        audits = audits_for_grade(a.bff, grade, rows)
        print(f"scoring the {len(audits)} runs named in {a.grade}")
    else:
        audits = audits_latest(a.bff, a.agent, rows)
    res = score(rows, audits, pack=a.pack)
    vocab = None if a.predictions else resolve_vocabulary(a.vocabulary, a.pack)
    print(render(res, vocab, predictions=bool(a.predictions)))
    return 0
