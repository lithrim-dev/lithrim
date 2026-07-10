#!/usr/bin/env python
"""REL-OPS-1 / O3 CLI presenter — the longitudinal meta-eval timeline, in a terminal.

The SAME join ``GET /v1/meta-eval/timeline`` serves (it calls the BFF endpoint function
in-process — one code path, zero drift): the agent-scoped, oldest-first dated series of
runs with their ``grade_signature``, recorded models, verdict-vs-gold agreement, and
clinician meta-verdicts. A ``grade_signature`` change prints as an explicit series break.

Pure read, $0, no service required. Absent joins print ``-`` — never a fabricated value.

Usage:
    python scripts/meta_eval_timeline.py --agent ws0_default
    python scripts/meta_eval_timeline.py --agent my_agent \
        --config-db out/workspaces/default/config.sqlite \
        --collections-db out/workspaces/default/collections.sqlite
    python scripts/meta_eval_timeline.py --agent my_agent --json

Note: the gold join reads the ACTIVE workspace's ingested corpus (the same derivation
the cohort scorecard uses); when pointing --config-db/--collections-db at a non-active
workspace, gold labels still come from the active one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))


def build_timeline(
    agent: str, *, config_db: Path, collections_db: Path, limit: int = 500
) -> dict:
    """The O3 join, via the BFF endpoint function called in-process. Every parameter is
    passed EXPLICITLY (an omitted FastAPI Query/Depends default is a FieldInfo sentinel,
    not a value — S-BS-82)."""
    import app as bff  # the BFF module; imported lazily so --help stays instant

    return bff.meta_eval_timeline_endpoint(
        agent=agent, limit=limit, db_path=config_db, collections_db=collections_db
    )


def _dash(value) -> str:
    return "-" if value is None else str(value)


def render(body: dict) -> str:
    """The table view: one dated line per run; a signature change is an explicit
    ``--- series break ---`` separator (the numbers across it are not comparable)."""
    lines = [
        f"agent: {body['agent']}   runs: {body['n_runs']}   "
        f"signature segments: {len(body['signature_segments'])}",
        f"{'ts':<32} {'run_id':<14} {'signature':<12} {'path':<10} "
        f"{'verdict':<8} {'gold':<22} {'clinician':<12}",
    ]
    sentinel = object()  # the first row never prints a break
    prev_sig = sentinel
    for row in body["timeline"]:
        sig = row.get("grade_signature")
        if prev_sig is not sentinel and sig != prev_sig:
            lines.append(f"--- series break: grade_signature changed -> {_dash(sig)[:12]} ---")
        prev_sig = sig
        gold = row.get("gold")
        gold_cell = (
            "-"
            if gold is None
            else (
                f"{'match' if gold['verdict_match'] else 'MISMATCH'}"
                f" +{len(gold['caught'])}/-{len(gold['missed'])}/~{len(gold['spurious'])}"
            )
        )
        mv = row.get("meta_verdict")
        mv_cell = (
            "-"
            if mv is None
            else ("agrees" if mv.get("agrees_with_council") else "DISSENT")
            + f" x{mv.get('n_records')}"
        )
        lines.append(
            f"{_dash(row.get('ts')):<32} {_dash(row.get('run_id'))[:14]:<14} "
            f"{_dash(sig)[:12]:<12} {_dash(row.get('grade_path')):<10} "
            f"{_dash(row.get('verdict')):<8} {gold_cell:<22} {mv_cell:<12}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True, help="the agent whose timeline to read")
    parser.add_argument("--config-db", type=Path, default=None,
                        help="config-plane DB (default: the active workspace's)")
    parser.add_argument("--collections-db", type=Path, default=None,
                        help="run-history DB (default: the active workspace's)")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", action="store_true", help="dump the raw join as JSON")
    args = parser.parse_args(argv)

    config_db, collections_db = args.config_db, args.collections_db
    if config_db is None or collections_db is None:
        from lithrim_bench.harness import workspace

        ws = workspace.get_active_workspace()
        config_db = config_db or ws.config_db
        collections_db = collections_db or ws.collections_db

    try:
        body = build_timeline(
            args.agent, config_db=config_db, collections_db=collections_db, limit=args.limit
        )
    except Exception as exc:  # HTTPException(404) on an unknown agent, DB errors, ...
        detail = getattr(exc, "detail", None) or str(exc)
        print(f"ERROR: {detail}", file=sys.stderr)
        return 1

    print(json.dumps(body, indent=2) if args.json else render(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
