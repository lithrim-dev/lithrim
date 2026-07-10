#!/usr/bin/env python3
"""Cost-gated live runner for the DSPy judge optimizer (WS-6c-DSPy-3b).

Optimizes ONE judge (default ``risk_judge``) with ``BootstrapFewShot`` on the
calibration split of the corpus passed via ``--corpus`` (required; the clinical
``judge_calib_v1.jsonl`` corpus relocated out of this repo per PACK-DIST-1 —
point ``--corpus`` at it in the pack repo, e.g.
``../lithrim-pack-healthcare/examples/judge_calib_v1.jsonl``) and measures the
compiled-vs-baseline held-out Δ on the test split. PAID — makes Azure calls only
when ``--confirm-cost`` is passed. Reaches Azure directly via the council
``settings`` / ``dspy.LM`` (the user owns ``../lithrim-backend/.env``), NOT the
:8002 service; no service is autostarted.

Protocol (the standing cost-confirm rule):

    # 1. smoke — 2 cases/split, report per-call cost, NO full run:
    python scripts/optimize_judge.py --corpus <path> --smoke --confirm-cost
    # 2. after an explicit cost-go, the full run (ONE run, $3 ceiling):
    python scripts/optimize_judge.py --corpus <path> --confirm-cost

Run under the council interpreter (the [council] extra + dspy):

    PYENV_VERSION=debuglithrim LITHRIM_LLM_PROVIDER=azure \\
    AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... \\
    AZURE_OPENAI_DEPLOYMENT_COUNCIL=gpt-4.1 \\
    python scripts/optimize_judge.py --smoke --confirm-cost
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lithrim_bench.runtime.council.judge_optimize import run_optimize  # noqa: E402


def filter_cases_by_ids(cases, case_ids):
    """optimize-on-subset: keep only the workspace cases whose ``case_id`` is in ``case_ids``,
    preserving input order; return ``(kept, dropped_ids)``.

    ``case_ids is None`` → the whole corpus, untouched (today's whole-workspace behaviour). Unknown
    ids are DROPPED (never fabricated) and surfaced in ``dropped_ids`` so the run can note them;
    an all-unknown set yields an empty ``kept`` → the caller's split-refusal fires (a subset that
    starves the calibration or held-out split is a clean refusal, never a silent no-op). Applied
    BEFORE ``build_calib_rows`` so the deterministic every-Nth split is unchanged for the subset."""
    if case_ids is None:
        return list(cases), []
    wanted = list(dict.fromkeys(case_ids))  # de-dup, order-preserving
    present = {str(c.get("case_id")) for c in cases}
    kept = [c for c in cases if str(c.get("case_id")) in set(wanted)]
    dropped = [cid for cid in wanted if cid not in present]
    return kept, dropped


def _print_table(result: dict) -> None:
    base, opt, delta = result["baseline"], result["optimized"], result["delta"]
    cfg = result["compile_config"]
    print()
    print(f"role={result['role']}  n_train={result['n_train']}  n_heldout={result['n_heldout']}")
    print(
        f"compile: max_bootstrapped_demos={cfg['max_bootstrapped_demos']} "
        f"max_labeled_demos={cfg['max_labeled_demos']} co_raise_aware={cfg['co_raise_aware']} "
        f"-> demos_bootstrapped={cfg['n_demos_bootstrapped']}"
    )
    print()
    print(f"{'metric':<12}{'baseline':>12}{'compiled':>12}{'delta':>12}")
    for k in ("graded", "precision", "recall"):
        print(f"{k:<12}{base[k]:>12}{opt[k]:>12}{delta[k]:>+12}")
    print(f"{'accepted':<12}{str(base['accepted']):>12}{str(opt['accepted']):>12}")
    base_cm = "{}/{}/{}".format(base["tp"], base["fp"], base["fn"])
    opt_cm = "{}/{}/{}".format(opt["tp"], opt["fp"], opt["fn"])
    print(f"{'tp/fp/fn':<12}{base_cm:>12}{opt_cm:>12}")
    if cfg["n_demos_bootstrapped"] == 0:
        print("\nNOTE: 0 demos bootstrapped under the exact-accept gate — Δ≈0 is the")
        print("honest loop-closure (the gate was NOT loosened to manufacture a win).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", default="risk_judge")
    # The corpus source — EXACTLY ONE: a pre-built calib JSONL (manual), OR build it IN-CORPUS from
    # a workspace's own graded cases (Phase 2, the BFF subprocess path — pack-bound, in-domain).
    parser.add_argument("--corpus", help="a pre-built calibration JSONL (manual path)")
    parser.add_argument(
        "--collections-db",
        help="build the calib IN-CORPUS from this workspace cases DB (Phase 2)",
    )
    parser.add_argument("--calib-out", help="where the in-corpus calib JSONL is written (with --collections-db)")
    parser.add_argument("--limit", type=int, default=None, help="cap each split (cost smoke)")
    parser.add_argument(
        "--case-ids",
        action="append",
        default=None,
        dest="case_ids",
        help="optimize-on-subset: scope the in-corpus calib to these case ids (repeatable). "
        "Omitted → the whole workspace. Unknown ids are dropped with a note.",
    )
    parser.add_argument("--test-stride", type=int, default=3, help="in-corpus split: every Nth case → test (≈70/30)")
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="cap each split to 2 cases (per-call cost check; not a real result)",
    )
    parser.add_argument("--out", default="docs/research/")
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="emit one __OPTIMIZE_JSON__ envelope (the BFF subprocess contract) instead of the table",
    )
    args = parser.parse_args()

    def _emit_json(payload: dict) -> None:
        print("__OPTIMIZE_JSON__" + json.dumps(payload, default=str))

    def _fail(msg: str, *, extra: dict | None = None) -> None:
        # In --emit-json mode a degenerate corpus / refusal is DATA (the BFF maps it to a calm 422),
        # never a stack trace; the manual CLI keeps its stderr+exit behaviour.
        if args.emit_json:
            _emit_json({"error": msg, **(extra or {})})
            sys.exit(0)
        print(f"REFUSING: {msg}", file=sys.stderr)
        sys.exit(2)

    if not args.confirm_cost:
        _fail(
            "run_optimize makes paid Azure calls. Re-run with --confirm-cost (smoke first: "
            "--smoke --confirm-cost).",
        )

    out_dir = Path(args.out)
    if args.smoke:
        out_dir = out_dir / "smoke"

    # ── resolve the corpus: in-corpus (workspace cases) OR a pre-built file ────────────────────
    split_counts_payload: dict | None = None
    if args.collections_db:
        # Pack-bound (LITHRIM_BENCH_PACK set by the spawner): the role lens resolves the ACTIVE pack.
        from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE

        if args.role not in LENS_BY_ROLE:
            _fail(f"unknown reviewer {args.role!r} for this pack")

        from lithrim_bench.harness import cases_store
        from lithrim_bench.harness.calib_corpus import (
            build_calib_rows,
            split_counts,
            write_calib_jsonl,
        )

        cases = [r["payload"] for r in cases_store.list_cases(db_path=args.collections_db)]
        # optimize-on-subset: scope to the chosen ids BEFORE the split (unknown ids dropped w/ a
        # note; an all-unknown / split-starving subset falls through to the split refusal below —
        # never a silent no-op). None (no --case-ids) → the whole corpus, unchanged.
        cases, dropped_ids = filter_cases_by_ids(cases, args.case_ids)
        rows = build_calib_rows(cases, test_stride=args.test_stride)
        split_counts_payload = split_counts(rows)
        if split_counts_payload["calibration"] == 0 or split_counts_payload["test"] == 0:
            subset_msg = (
                " (the chosen case subset is too small to split — pick more cases or clear the "
                "selection to use the whole workspace)"
                if args.case_ids is not None
                else ""
            )
            _fail(
                "Not enough graded cases to calibrate yet — need cases on BOTH the calibration and "
                "held-out splits. Grade more of this workspace's corpus first." + subset_msg,
                extra={
                    "split_counts": split_counts_payload,
                    "n_cases": len(cases),
                    "dropped_case_ids": dropped_ids,
                },
            )
        corpus = str(args.calib_out or (out_dir / "calib.jsonl"))
        write_calib_jsonl(rows, corpus)
    elif args.corpus:
        corpus = args.corpus
    else:
        parser.error("one of --corpus or --collections-db is required")

    try:
        result = run_optimize(
            args.role,
            corpus_path=corpus,
            confirm_cost=True,
            out_dir=out_dir,
            limit=2 if args.smoke else args.limit,
            coverage_aware=True,
        )
    except Exception as exc:  # surface the live Azure/dspy failure as data in --emit-json mode
        if args.emit_json:
            _emit_json({"error": f"optimize run failed: {exc}", "split_counts": split_counts_payload})
            sys.exit(0)
        raise
    if split_counts_payload is not None:
        result["split_counts"] = split_counts_payload
        result["corpus"] = "workspace"
        if args.case_ids is not None:  # optimize-on-subset: record the scope + any dropped ids
            result["case_ids"] = list(dict.fromkeys(args.case_ids))
            result["dropped_case_ids"] = dropped_ids

    if args.emit_json:
        _emit_json(result)
        return
    _print_table(result)
    if args.smoke:
        print("\nSMOKE ONLY (2 cases/split) — divide your Azure spend by the call count")
        print("to get per-call cost, then get the explicit cost-go before the full run.")
    print(f"\nartifacts -> {out_dir}/")
    print(json.dumps(result["delta"], indent=2, default=str))


if __name__ == "__main__":
    main()
