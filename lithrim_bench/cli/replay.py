"""``lithrim replay``: one round of the loop at $0 (no key, no network, no stack).

Replays the committed judge baselines for a labeled sample corpus (``grade_replay``), runs the
LIVE deterministic grounding checks against each source (``ground``), settles every case into
its review state, and scores the round against the human labels in both vocabularies with the
same scorer a paid round uses (``lithrim score``). Any corpus with committed
``baseline.<case_id>.json`` files beside it replays this way; the tracked reference fixture is
the sample corpus under ``samples/`` that ``make loop-demo`` names.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lithrim_bench.harness.grade import grade_replay
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.report import review_state

from . import scoring

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONTOLOGY = REPO_ROOT / "packs/_core/ontology.json"


def audit_from_replay(result: dict[str, Any], grounded_verdict: str) -> dict[str, Any]:
    """Shape a replayed pipeline result like the run audit ``scoring.score`` reads: the verdict
    after the floor, each judge's vote/findings/errors, and its quoted evidence spans."""
    sem = result.get("semantic") or {}
    evidence = sem.get("evidence") or []
    judges = []
    for v in sem.get("judge_votes") or []:
        role = v.get("judge_role")
        judges.append(
            {
                "judge_role": role,
                "vote": v.get("vote"),
                "findings": list(v.get("findings") or []),
                "errors": [e for e in (v.get("errors") or []) if e],
                "evidence": [ev for ev in evidence if ev.get("judge") in (role, None)],
            }
        )
    return {"grounded_verdict": grounded_verdict, "judges": judges}


def replay_round(
    cases_path: Path, baseline_dir: Path, ontology_path: Path
) -> tuple[list[dict], dict[str, dict], list[dict]]:
    """Replay every case with a committed baseline: returns the cases, the audits keyed by
    case id, and the review-state rows. A case with no baseline is reported, never faked."""
    ontology = load_ontology(ontology_path)
    cases = [json.loads(line) for line in Path(cases_path).read_text().splitlines() if line.strip()]
    missing = [
        c["case_id"] for c in cases if not (baseline_dir / f"baseline.{c['case_id']}.json").exists()
    ]
    if missing:
        raise FileNotFoundError(
            "no committed judge baseline for: "
            + ", ".join(missing)
            + " (capture once with a model key, then the round replays at $0)"
        )
    audits: dict[str, dict] = {}
    rows: list[dict] = []
    for case in cases:
        result = grade_replay(case, baseline_dir / f"baseline.{case['case_id']}.json")
        grounded = ground(result, case, ontology=ontology)
        row = review_state(grounded)
        row["case_id"] = case["case_id"]
        row["human_flags"] = list(case.get("expected_safety_flags") or [])
        rows.append(row)
        audits[case["case_id"]] = audit_from_replay(result, row["verdict"])
    return cases, audits, rows


def render_states(rows: list[dict]) -> str:
    tally: dict[str, int] = {}
    lines = []
    for r in rows:
        tally[r["state"]] = tally.get(r["state"], 0) + 1
        lines.append(
            f"  {r['case_id']:16s} {r['verdict_no_floor'] or '-':5s} -> {r['verdict']:5s}  "
            f"{r['state']:9s} human: {', '.join(r['human_flags']) or 'clean'}"
        )
    head = "replayed round ($0): " + " · ".join(
        f"{k.lower()} {v}" for k, v in sorted(tally.items())
    )
    return "\n".join([head, *lines])


def add_arguments(ap) -> None:
    ap.add_argument("--cases", type=Path, required=True, help="the labeled sample corpus (JSONL)")
    ap.add_argument(
        "--baselines",
        type=Path,
        default=None,
        help="dir of baseline.<case_id>.json (default: beside --cases)",
    )
    ap.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    ap.add_argument(
        "--vocabulary",
        default=None,
        help="the kind:importer dataset (default: the pack's only importer)",
    )
    ap.add_argument("--pack", default=None)
    ap.add_argument("--json", action="store_true", help="machine-readable output")


def cmd_replay(a) -> int:
    baseline_dir = a.baselines or Path(a.cases).parent
    cases, audits, rows = replay_round(a.cases, baseline_dir, a.ontology)
    res = scoring.score(cases, audits, pack=a.pack)
    vocab = scoring.resolve_vocabulary(a.vocabulary, a.pack)
    if a.json:
        print(json.dumps({"states": rows, "score": res}, indent=1, sort_keys=True, default=str))
        return 0
    print(render_states(rows))
    print()
    print(scoring.render(res, vocab))
    return 0
