#!/usr/bin/env python
"""`make queue` — the reviewer works a five-case queue at $0 (no keys, no network, no pack).

Five public RAGTruth cases (``samples/ragtruth/cases.jsonl``: news summaries, a QA answer, and
two Yelp data-to-text descriptions, each paired with its source and a HUMAN hallucination label)
arrive as a queue. For each case the reviewer replays the committed judge-ensemble baseline (no
LLM call), runs the LIVE deterministic grounding checks against the source, and settles the
case into one of three states with its evidence attached:

    CLEARED    a check confirmed the artifact (a recorded floor pass, or a judge signal disproved
               with evidence): the deterministic layer materially supports the PASS
    FLAGGED    a check contradicted the artifact: a floor injected the block, the value is named
    ESCALATED  nothing could settle it: a judge signal no check could confirm or refute, a value
               absent from a prose source (a named lead), or no check applied at all

A judge's confidence never clears a case. The human RAGTruth label is printed next to every
state so the reader can score the reviewer, not just read it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.grade import grade_replay  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.report import review_state  # noqa: E402

CASES = REPO_ROOT / "samples/ragtruth/cases.jsonl"
BASELINE_DIR = REPO_ROOT / "samples/ragtruth"
ONTOLOGY = REPO_ROOT / "packs/_core/ontology.json"
STATES = ("CLEARED", "FLAGGED", "ESCALATED")


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]


def review_queue() -> dict[str, Any]:
    ontology = load_ontology(ONTOLOGY)
    cases = load_cases()
    missing = [c["case_id"] for c in cases if not (BASELINE_DIR / f"baseline.{c['case_id']}.json").exists()]
    if missing:
        raise FileNotFoundError(
            "no committed judge baseline for: " + ", ".join(missing)
            + " (capture once with a model key, then the queue replays at $0)"
        )
    rows = []
    for case in cases:
        result = grade_replay(case, BASELINE_DIR / f"baseline.{case['case_id']}.json")
        grounded = ground(result, case, ontology=ontology)
        row = review_state(grounded)
        rt = case.get("ragtruth") or {}
        votes = result.get("semantic", {}).get("judge_votes") or []
        row.update(
            case_id=case["case_id"],
            task=rt.get("task_type"),
            model=rt.get("model"),
            source_kind=case.get("source_kind"),
            human_flags=list(case.get("expected_safety_flags") or []),
            # a judge that errored is shown AS an error, never as a quiet vote (dead-judge visibility)
            judges=[
                f"{v.get('judge_role')}={v.get('vote')}"
                + (f"!ERROR({str((v.get('errors') or [''])[0]).split(':')[0]})" if v.get("errors") else "")
                for v in votes
            ],
        )
        rows.append(row)
    tally = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    return {"cases": rows, "tally": tally, "n": len(rows)}


def render(out: dict[str, Any]) -> str:
    lines = ["=" * 76, "  Lithrim — reviewer queue demo  ($0 · no keys · no network · no pack)", "=" * 76]
    lines.append("  corpus: RAGTruth (human-labeled LLM hallucinations; MIT) · judges replayed · checks LIVE")
    for i, r in enumerate(out["cases"], 1):
        lines += [
            "",
            f"  {i}. {r['case_id']}   [{r['task']} · {r['model']} · source={r['source_kind']}]",
            f"     judges: {', '.join(r['judges']) or '(none)'}  ->  verdict {r['verdict_no_floor']} before checks, {r['verdict']} after",
            f"     STATE:  {r['state']:9s} {r['reason'] if r['state'] == 'ESCALATED' else r['evidence']}",
        ]
        if r["state"] == "ESCALATED" and r["evidence"]:
            lines.append(f"             checks: {r['evidence']}")
        elif r["state"] != "ESCALATED":
            lines.append(f"             {r['reason']}")
        lines.append(f"     human label: {', '.join(r['human_flags']) or 'clean'}")
    t = out["tally"]
    lines += [
        "",
        "-" * 76,
        f"  QUEUE: {out['n']} cases  ->  cleared {t['CLEARED']} · flagged {t['FLAGGED']} · escalated {t['ESCALATED']}",
        "  a judge's confidence cleared nothing; every cleared or flagged case names its check",
        "-" * 76,
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    try:
        out = review_queue()
    except FileNotFoundError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    print(json.dumps(out, indent=1, sort_keys=True) if args.json else render(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
