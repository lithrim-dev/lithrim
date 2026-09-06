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
from lithrim_bench.harness.report import composite  # noqa: E402

CASES = REPO_ROOT / "samples/ragtruth/cases.jsonl"
BASELINE_DIR = REPO_ROOT / "samples/ragtruth"
ONTOLOGY = REPO_ROOT / "packs/_core/ontology.json"
STATES = ("CLEARED", "FLAGGED", "ESCALATED")


def classify(grounded: Any, comp: dict[str, Any]) -> dict[str, Any]:
    """The three-state reviewer decision over a grounded result. CLEARED and FLAGGED require
    the deterministic layer to have materially supported the verdict (``floor_backstopped``);
    everything else is ESCALATED with the reason a person needs."""
    cov = grounded.coverage or {}
    verdict = str(grounded.verdict)
    backstopped = bool(cov.get("floor_backstopped"))
    judge_codes = sorted({f.get("code") for f in grounded.active if f.get("code") and not f.get("_floor")})
    out: dict[str, Any] = {
        "verdict": verdict,
        "verdict_no_floor": grounded.verdict_no_floor,
        "floor_backstopped": backstopped,
        "judge_codes": judge_codes,
    }
    if verdict == "BLOCK" and cov.get("grounded", 0) > 0:
        blocks = [b for b in grounded.floor_blocks if b["injected_finding"] is not None]
        ev = blocks[0]["result"].evidence or {}
        out.update(
            state="FLAGGED",
            check=blocks[0]["decl"].contract_type,
            evidence=f"{blocks[0]['decl'].contract_type}: {ev.get('reason', 'violation')}"
            + (f"; missing {ev['missing']}" if ev.get("missing") else ""),
            reason="a deterministic check contradicted the artifact",
        )
        return out
    if verdict == "PASS" and backstopped:
        if grounded.floor_passes:
            p = grounded.floor_passes[0]
            ev = p["result"].evidence or {}
            out.update(
                state="CLEARED",
                check=p["decl"].contract_type,
                evidence=f"{p['decl'].contract_type}: {ev.get('checked', 0)} value(s) checked, all present in the source",
                reason="a deterministic check confirmed the artifact",
            )
        else:
            s = grounded.suppressed[0]
            out.update(
                state="CLEARED",
                check=s["contract"].contract_type,
                evidence=f"{s['contract'].contract_type}: judge signal {s['finding'].get('code')} disproved ({s['verdict'].reason})",
                reason="the judges' signal was disproved with evidence",
            )
        return out
    leads = [
        b["result"].evidence.get("missing")
        for b in grounded.floor_blocks
        if b["injected_finding"] is None and (b["result"].evidence or {}).get("missing")
    ]
    if verdict == "BLOCK":
        reason = f"judges raised {judge_codes}; no check could confirm or refute it"
    elif verdict == "WARN":
        reason = f"judges were uncertain ({judge_codes or 'no code'}); no check settled it"
    elif leads:
        reason = f"value(s) {leads[0]} not found in the source; a lead for a person, not a proof"
    else:
        reason = "no deterministic check applied to this case; the PASS rests on judges alone"
    # what the checks DID establish rides along, so a person sees the confirmed part too
    confirmed = [
        f"{p['decl'].contract_type} confirmed {(p['result'].evidence or {}).get('checked', 0)} value(s) present"
        for p in grounded.floor_passes
    ]
    out.update(state="ESCALATED", check=None, evidence="; ".join(confirmed), reason=reason)
    return out


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
        comp = composite(grounded)
        row = classify(grounded, comp)
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
