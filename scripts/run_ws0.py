#!/usr/bin/env python
"""WS-0 compat shim — kept green as a regression guard for tests/test_ws0.py.

WS-1 made ``scripts/run_eval.py`` the canonical config-driven entrypoint. This
script no longer owns any grounding logic (the old ``WS0_CONTRACTS`` path is gone);
it builds an *ephemeral* Agent eval-profile from its CLI args and delegates to the
SAME :func:`run_eval.run` core — two entry surfaces, one grounding path.

Defaults run the captured-baseline REPLAY path (zero new paid calls). ``--live``
opts into a real, paid ``:8002 /v1/pipeline/evaluate`` call and is OFF by default.

    python scripts/run_ws0.py
    python scripts/run_ws0.py --case <case_id> --baseline <path>
    python scripts/run_ws0.py --live          # paid; opt-in only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# scripts/ on path so the shim can import the canonical core by module name.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile  # noqa: E402

DEFAULT_CASE = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
DEFAULT_SOURCE = REPO_ROOT / "out" / "scribe_v1.jsonl"
DEFAULT_BASELINE = (
    REPO_ROOT
    / "out"
    / "scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json"
)
DEFAULT_ONTOLOGY = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"


def _ephemeral_agent(case: str, source: str, baseline: str) -> Agent:
    """Build an in-memory Agent from CLI args (the WS-0 compat profile)."""
    return Agent(
        name="ws0_cli",
        eval_profile=EvalProfile(
            judges=(),
            council_config={"disposition": "compose-over-live-v2", "via": "run_ws0 shim"},
            ontology_ref="clinical/1",
            ontology_path=str(DEFAULT_ONTOLOGY),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(case_id=case, source=source, baseline=baseline, mode="replay"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="WS-0 compat shim (delegates to run_eval)")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument(
        "--live",
        action="store_true",
        help="opt into a real, PAID :8002 call (default: replay the baseline)",
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    agent = _ephemeral_agent(args.case, args.source, args.baseline)
    record = run_eval.run(agent, live=args.live, out_dir=args.out_dir)
    run_eval._print(agent, record, live=args.live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
