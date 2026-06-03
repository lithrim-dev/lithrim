#!/usr/bin/env python3
"""Cost-gated live runner for the DSPy judge optimizer (WS-6c-DSPy-3b).

Optimizes ONE judge (default ``risk_judge``) with ``BootstrapFewShot`` on the
calibration split of ``examples/judge_calib_v1.jsonl`` and measures the compiled-
vs-baseline held-out Δ on the test split. PAID — makes Azure calls only when
``--confirm-cost`` is passed. Reaches Azure directly via the council ``settings`` /
``dspy.LM`` (the user owns ``../lithrim-backend/.env``), NOT the :8002 service; no
service is autostarted.

Protocol (the standing cost-confirm rule):

    # 1. smoke — 2 cases/split, report per-call cost, NO full run:
    python scripts/optimize_judge.py --smoke --confirm-cost
    # 2. after an explicit cost-go, the full run (ONE run, $3 ceiling):
    python scripts/optimize_judge.py --confirm-cost

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
    parser.add_argument("--corpus", default="examples/judge_calib_v1.jsonl")
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="cap each split to 2 cases (per-call cost check; not a real result)",
    )
    parser.add_argument("--out", default="docs/research/")
    args = parser.parse_args()

    if not args.confirm_cost:
        print(
            "REFUSING: run_optimize makes paid Azure calls. Re-run with --confirm-cost "
            "(smoke first: --smoke --confirm-cost).",
            file=sys.stderr,
        )
        sys.exit(2)

    out_dir = Path(args.out)
    if args.smoke:
        out_dir = out_dir / "smoke"

    result = run_optimize(
        args.role,
        corpus_path=args.corpus,
        confirm_cost=True,
        out_dir=out_dir,
        limit=2 if args.smoke else None,
    )
    _print_table(result)
    if args.smoke:
        print("\nSMOKE ONLY (2 cases/split) — divide your Azure spend by the call count")
        print("to get per-call cost, then get the explicit cost-go before the full run.")
    print(f"\nartifacts -> {out_dir}/")
    print(json.dumps(result["delta"], indent=2, default=str))


if __name__ == "__main__":
    main()
