"""``lithrim``: the product loop from a terminal, against a running stack.

    lithrim load       --adapter examples/ragtruth/adapter.py --data-dir out/loop/data --per-task 30
    lithrim configure  --judge examples/ragtruth/judge.ragtruth_detector.json --model azure/gpt-4.1-2025-04-14
    lithrim grade      --judge ... --model ...                       # the baseline row
    lithrim calibrate  --judge ... --model ... --confirm-cost         # optimize + the gated pin
    lithrim regrade    --judge ... --model ...                       # the optimized row
    lithrim export     --slice out/loop/slice_train.jsonl --split calibration --out out/loop/export.jsonl
    lithrim score      --slice out/loop/slice_full.jsonl [--grade out/loop/grade_after.json]
    lithrim spend
    lithrim run        --from load --to regrade ...                  # the loop end to end

Every verb talks to the BFF (``--bff``, default http://localhost:8787) and writes under
``--out`` (default out/loop). Nothing here names a dataset: ``--adapter`` slices it,
``--judge`` defines the reviewer, and the pack's importer manifest maps its vocabulary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import export as _export
from . import loop as _loop
from . import scoring as _scoring
from . import spend as _spend

REPO_ROOT = Path(__file__).resolve().parents[2]

VERBS = {
    "load": ("download", "ingest"),
    "configure": ("judge", "judge"),
    "grade": ("before", "before"),
    "calibrate": ("optimize", "pin"),
    "regrade": ("after", "after"),
    "calib": ("calib", "calib"),
    "enrich": ("enrich", "enrich"),
}


def _loop_arguments(ap: argparse.ArgumentParser, *, needs_model: bool) -> None:
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "loop")
    ap.add_argument(
        "--workspace-out", type=Path, default=REPO_ROOT / "out" / "workspaces" / "default" / "out"
    )
    ap.add_argument("--adapter", default=None, help="dataset adapter (.py path or module)")
    ap.add_argument("--data-dir", type=Path, default=None, help="the dataset's files")
    ap.add_argument("--judge", type=Path, default=None, help="judge definition JSON")
    ap.add_argument(
        "--model",
        required=needs_model,
        default="unpinned",
        help="the judge model to pin, e.g. a DATED Azure deployment",
    )
    ap.add_argument(
        "--model-version", default=None, help="the deployment's model version (attested)"
    )
    ap.add_argument(
        "--upgrade-policy", default=None, help="the deployment's version-upgrade policy"
    )
    ap.add_argument("--per-task", type=int, default=30)
    ap.add_argument("--heldout-cap", type=int, default=150, help="optimizer --limit (0 = no cap)")
    ap.add_argument(
        "--tag", default="after", help="name of the final grade's output (grade_<tag>.json)"
    )
    ap.add_argument(
        "--vocabulary", default=None, help="the kind:importer dataset for the scorecard"
    )
    ap.add_argument("--pack", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--contrastive", action="store_true", help="enrich: trainset from both sides")
    ap.add_argument("--force-pin", dest="force_pin", action="store_true")
    ap.add_argument("--confirm-cost", action="store_true", help="acknowledge a paid step")
    ap.add_argument("--resume-job", default=None, help="continue an interrupted grade job by id")


def _prepare(a: argparse.Namespace, todo: tuple[str, ...]) -> None:
    a.slice = a.out / "slice_full.jsonl"
    a.calib = a.out / "calib.jsonl"
    a.data_dir = a.data_dir or a.out / "data"
    needs_judge = {"judge", "before", "optimize", "pin", "after", "calib", "enrich"}
    if needs_judge & set(todo):
        if not a.judge:
            raise SystemExit("this verb needs --judge <definition.json>")
        a.judge_def = _loop.load_judge(a.judge)
    else:
        a.judge_def = {"role": None}
    paid = {"before", "optimize", "after", "calib", "enrich"}
    if paid & set(todo) and not a.confirm_cost and not a.dry_run:
        raise SystemExit(
            f"REFUSING a paid step ({', '.join(sorted(paid & set(todo)))}): grading and optimizing "
            "spend model calls; resend with --confirm-cost"
        )


def _model_optional(todo: tuple[str, ...]) -> bool:
    return not ({"judge", "before", "optimize", "pin", "after", "calib", "enrich"} & set(todo))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lithrim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="verb", required=True)
    for verb, (start, stop) in VERBS.items():
        p = sub.add_parser(verb, help=f"steps {' -> '.join(_loop.plan(start, stop))}")
        _loop_arguments(p, needs_model=not _model_optional(_loop.plan(start, stop)))
        p.set_defaults(_start=start, _stop=stop)
    p = sub.add_parser("run", help="a range of steps (--from/--to; verbs accepted)")
    _loop_arguments(p, needs_model=True)
    p.add_argument("--from", dest="start", default=_loop.STEPS[0])
    p.add_argument("--to", dest="stop", default="after")
    p = sub.add_parser("score", help="score a graded slice in both vocabularies")
    _scoring.add_arguments(p)
    p.set_defaults(_fn=_scoring.cmd_score)
    p = sub.add_parser("export", help="export graded labeled rows (split gate, tiers)")
    _export.add_arguments(p)
    p.set_defaults(_fn=_export.cmd_export)
    p = sub.add_parser("spend", help="the running list-price spend line")
    _spend.add_arguments(p)
    p.set_defaults(_fn=_spend.cmd_spend)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if getattr(a, "_fn", None):
        return a._fn(a)
    todo = _loop.plan(a.start, a.stop) if a.verb == "run" else _loop.plan(a._start, a._stop)
    _prepare(a, todo)
    if a.model == "unpinned" and not _model_optional(todo):
        raise SystemExit("this verb needs --model")
    if _model_optional(todo) and a.model == "unpinned":
        # a load-only run has no arm to attest; print the plan and go
        print(f"plan: {' -> '.join(todo)} | per task {a.per_task}")
        if a.dry_run:
            return 0
        a.out.mkdir(parents=True, exist_ok=True)
        for name in todo:
            print(f"\n=== {name} ===", flush=True)
            getattr(_loop, f"step_{name}")(a)
        return 0
    return _loop.run_steps(a, todo)


if __name__ == "__main__":
    sys.exit(main())
