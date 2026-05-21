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

from lithrim_bench.backends import (
    EtlpStructuralBackend,
    LithrimHttpBackend,
    LithrimPipelineBackend,
    LithrimValidateArtifactBackend,
    MockBackend,
    TunedMockBackend,
    WorstOfBackend,
)
from lithrim_bench.eval_runner import run_pack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-path", required=True, type=Path)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--backend",
        choices=[
            "mock",
            "http",
            "etlp-structural",
            "lithrim-validate-artifact",
            "lithrim-pipeline",
            "worst-of",
            "tuned-mock",
        ],
        default="mock",
    )
    ap.add_argument("--org-id", default=None, help="Org ID for /v1/pipeline/evaluate (read from .live_env if omitted)")
    ap.add_argument("--gate-mode", action="store_true", help="Enable /v1/pipeline/evaluate fast-path gate mode")
    ap.add_argument(
        "--etlp-mapping-id",
        type=int,
        default=None,
        help="Override etlp-mapper mapping ID for structural validation (e.g. 26 for HL7 ADT^A04).",
    )
    ap.add_argument(
        "--worst-of-semantic",
        choices=["mock", "tuned-mock", "http", "lithrim-pipeline"],
        default="mock",
        help="Sub-backend used as the semantic side of --backend worst-of.",
    )
    ap.add_argument("--tuned-ensemble-size", type=int, default=3)
    ap.add_argument("--tuned-per-member-accuracy", type=float, default=0.85)
    ap.add_argument("--tuned-flag-attachment-rate", type=float, default=0.80)
    ap.add_argument(
        "--worst-of-structural",
        choices=["mock", "etlp", "lithrim-validate-artifact"],
        default="mock",
        help="Sub-backend used as the structural side of --backend worst-of.",
    )
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

    def _build_tuned_mock():
        return TunedMockBackend(
            ensemble_size=args.tuned_ensemble_size,
            per_member_semantic_accuracy=args.tuned_per_member_accuracy,
            per_member_flag_attachment_rate=args.tuned_flag_attachment_rate,
            noise_seed=args.noise_seed,
        )

    def _read_live_env() -> dict[str, str]:
        env_path = Path(__file__).resolve().parent.parent / ".live_env"
        if not env_path.exists():
            return {}
        return dict(
            line.split("=", 1) for line in env_path.read_text().splitlines() if "=" in line
        )

    def _live_creds():
        import os
        live = _read_live_env()
        key = args.api_key or os.environ.get("LITHRIM_API_KEY") or live.get("LITHRIM_API_KEY")
        org = args.org_id or os.environ.get("LITHRIM_ORG_ID") or live.get("LITHRIM_ORG_ID")
        return key, org

    def _build_pipeline():
        key, org = _live_creds()
        if not key or not org:
            sys.exit("--api-key/--org-id required (or set LITHRIM_API_KEY/LITHRIM_ORG_ID, or .live_env)")
        return LithrimPipelineBackend(
            base_url=args.base_url, api_key=key, org_id=org, gate_mode=args.gate_mode,
        )

    def _build_semantic():
        if args.worst_of_semantic == "tuned-mock":
            return _build_tuned_mock()
        if args.worst_of_semantic == "lithrim-pipeline":
            return _build_pipeline()
        if args.worst_of_semantic == "mock":
            return MockBackend(
                decision_flip_rate=args.decision_flip_rate,
                flag_attachment_rate=args.flag_attachment_rate,
                structural_drift_rate=1.0,  # blind on the structural axis by construction
                noise_seed=args.noise_seed,
            )
        return LithrimHttpBackend(
            base_url=args.base_url,
            api_key=args.api_key,
            judge_model=args.judge_model,
            judge_model_version=args.judge_model_version,
        )

    def _build_structural():
        if args.worst_of_structural == "mock":
            return MockBackend(
                decision_flip_rate=0.0,
                flag_attachment_rate=0.0,
                structural_drift_rate=args.structural_drift_rate,
                noise_seed=args.noise_seed + 1,
            )
        if args.worst_of_structural == "lithrim-validate-artifact":
            key, _ = _live_creds()
            if not key:
                sys.exit("--api-key/.live_env required for lithrim-validate-artifact structural side")
            return LithrimValidateArtifactBackend(
                base_url=args.base_url,
                api_key=key,
                etlp_mapping_id=args.etlp_mapping_id,
            )
        etlp_url = (
            args.base_url
            if args.base_url != "http://localhost:8002"
            else "http://localhost:3031"
        )
        return EtlpStructuralBackend(base_url=etlp_url, api_key=args.api_key)

    if args.backend == "mock":
        backend = MockBackend(
            decision_flip_rate=args.decision_flip_rate,
            flag_attachment_rate=args.flag_attachment_rate,
            structural_drift_rate=args.structural_drift_rate,
            noise_seed=args.noise_seed,
        )
    elif args.backend == "tuned-mock":
        backend = _build_tuned_mock()
    elif args.backend == "etlp-structural":
        etlp_url = (
            args.base_url
            if args.base_url != "http://localhost:8002"
            else "http://localhost:3031"
        )
        backend = EtlpStructuralBackend(base_url=etlp_url, api_key=args.api_key)
    elif args.backend == "lithrim-pipeline":
        backend = _build_pipeline()
    elif args.backend == "lithrim-validate-artifact":
        import os
        key = args.api_key or os.environ.get("LITHRIM_API_KEY")
        if not key:
            env_path = Path(__file__).resolve().parent.parent / ".live_env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("LITHRIM_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        if not key:
            sys.exit("--api-key required (or LITHRIM_API_KEY env, or .live_env file)")
        backend = LithrimValidateArtifactBackend(
            base_url=args.base_url,
            api_key=key,
            etlp_mapping_id=args.etlp_mapping_id,
        )
    elif args.backend == "worst-of":
        backend = WorstOfBackend(semantic=_build_semantic(), structural=_build_structural())
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
