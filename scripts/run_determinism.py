"""Run a pack through a backend N times per case.

Defaults to MockBackend with no decision flip and perfect flag
attachment (the "ideal backend" baseline). Tune --decision-flip-rate
and --flag-attachment-rate to reproduce the eval spec's bistability
patterns and validate the analysis pipeline before pointing at a real
backend.

Usage:
    # demo: ideal mock backend (all metrics should hit ceiling)
    python scripts/run_determinism.py --pack-path out/scribe_v1.jsonl --n 5

    # demo: code-attribution drift (the canonical hba1c failure mode)
    python scripts/run_determinism.py --pack-path out/scribe_v1.jsonl --n 10 \
        --flag-attachment-rate 0.6

    # real backend
    python scripts/run_determinism.py --pack-path out/scribe_v1.jsonl --n 10 \
        --backend http --base-url http://localhost:8002
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.backends import EtlpStructuralBackend, LithrimHttpBackend, MockBackend
from lithrim_bench.eval_runner import run_pack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-path", required=True, type=Path)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--backend", choices=["mock", "http", "etlp-structural"], default="mock")
    ap.add_argument("--decision-flip-rate", type=float, default=0.0)
    ap.add_argument("--flag-attachment-rate", type=float, default=1.0)
    ap.add_argument("--structural-drift-rate", type=float, default=0.0)
    ap.add_argument("--noise-seed", type=int, default=0)
    ap.add_argument("--base-url", default="http://localhost:8002")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--judge-model-version", default=None)
    args = ap.parse_args()

    if not args.pack_path.exists():
        sys.exit(f"pack not found: {args.pack_path}")

    out = args.out or args.pack_path.with_name(args.pack_path.stem + ".runs.ndjson")

    if args.backend == "mock":
        backend = MockBackend(
            decision_flip_rate=args.decision_flip_rate,
            flag_attachment_rate=args.flag_attachment_rate,
            structural_drift_rate=args.structural_drift_rate,
            noise_seed=args.noise_seed,
        )
    elif args.backend == "etlp-structural":
        etlp_url = args.base_url if args.base_url != "http://localhost:8002" else "http://localhost:3031"
        backend = EtlpStructuralBackend(base_url=etlp_url, api_key=args.api_key)
    else:
        backend = LithrimHttpBackend(
            base_url=args.base_url,
            api_key=args.api_key,
            judge_model=args.judge_model,
            judge_model_version=args.judge_model_version,
        )

    progress = {"i": 0}
    def _tick(case_id: str) -> None:
        progress["i"] += 1
        if progress["i"] % 10 == 0:
            print(f"  ... {progress['i']} cases done", flush=True)

    summary = run_pack(
        pack_path=args.pack_path,
        backend=backend,
        n=args.n,
        out_path=out,
        on_case=_tick,
    )
    print(json.dumps({"output": str(out), "summary": summary, "pin": backend.pin.__dict__}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
