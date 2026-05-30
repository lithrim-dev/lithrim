"""Run scribe_v1 through the in-process LocalPipelineBackend (salvaged council).

The acceptance probe for M1: prove the salvaged council, running locally with no
Mongo / Pinecone / etlp / Celery, reproduces the recorded scribe_v1 verdicts.

Usage (BYOK):
    PYENV_VERSION=debuglithrim COMPLIANCE_COUNCIL_VERSION=v1 \
    LITHRIM_LLM_PROVIDER=openai OPENAI_API_KEY=sk-... \
    pyenv exec python scripts/run_local_scribe.py --limit 1

  (or LITHRIM_LLM_PROVIDER=azure with AZURE_OPENAI_ENDPOINT / _API_KEY /
   _DEPLOYMENT_COUNCIL set.)

Cost note: each case = 3 council judge calls (v1). --limit keeps the first run tiny.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lithrim_bench.backends.local_pipeline import LocalPipelineBackend
from lithrim_bench.eval_runner import read_pack, run_pack


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="out/scribe_v1.jsonl")
    ap.add_argument("--out", default="out/scribe_v1.local.ndjson")
    ap.add_argument("--limit", type=int, default=1, help="number of cases (cost guard)")
    ap.add_argument("--n", type=int, default=1, help="runs per case")
    args = ap.parse_args()

    cases = list(read_pack(Path(args.pack)))[: args.limit]
    case_ids = {c["case_id"] for c in cases}
    by_id = {c["case_id"]: c for c in cases}

    backend = LocalPipelineBackend()
    summary = run_pack(
        pack_path=Path(args.pack),
        backend=backend,
        n=args.n,
        out_path=Path(args.out),
        case_filter=case_ids,
        on_case=lambda cid: print("  ran", cid),
    )
    print("summary:", summary)

    print("\n--- verdict vs recorded baseline ---")
    hits = 0
    rows = [json.loads(line) for line in Path(args.out).read_text().splitlines()]
    for r in rows:
        c = by_id.get(r["case_id"], {})
        exp = c.get("expected_compliance_verdict")
        exp_set = exp if isinstance(exp, list) else [exp]
        match = r["compliance_verdict"] in exp_set
        hits += int(bool(match))
        print(
            f"{r['case_id'][:40]} got={r['compliance_verdict']} "
            f"exp={exp} flags={r['flags']} exp_flags={c.get('expected_safety_flags')} "
            f"{'OK' if match else 'MISS'}"
        )
    print(f"\nverdict match: {hits}/{len(rows)}")


if __name__ == "__main__":
    main()
