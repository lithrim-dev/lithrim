"""Replay persisted council results through the CURRENT floor at $0.

The council votes (the paid, stochastic part) are copied byte-identically; only ``grounded`` and
``composite.review`` are recomputed, exactly the way ``scripts/run_eval.py`` writes them. Used to
re-score a frozen batch after a floor bug fix. The output is POST-HOC by construction and says so."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.report import review_state

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = ROOT / "packs/_core/ontology.json"
TOOLS = ROOT / "lithrim_bench/verification/tools.py"


def _grounded_block():
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "scripts/run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._grounded_block


def replay(records: dict, cases: dict, *, out_dir: Path, ontology_path: Path | None = None) -> dict:
    out_dir = Path(out_dir)
    (out_dir / "runs").mkdir(parents=True, exist_ok=False)
    ontology_path = Path(ontology_path) if ontology_path else ONTOLOGY
    ontology = load_ontology(ontology_path)
    block = _grounded_block()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    tools_sha = hashlib.sha256(TOOLS.read_bytes()).hexdigest()
    out = {}
    for cid, rec in records.items():
        case = cases[cid]
        grounded = ground(rec["result"], case, ontology=ontology)
        new = dict(rec)
        new["grounded"] = block(grounded)
        composite = dict(new.get("composite") or {})
        composite["review"] = review_state(grounded)
        new["composite"] = composite
        new["refloor"] = {
            "kind": "post_hoc_floor_replay",
            "council_calls": 0,
            "tools_py_sha256": tools_sha,
            "git_head": head,
            "ontology": str(ontology_path),
            "source_pipeline_run_id": ((rec.get("result") or {}).get("provenance") or {}).get(
                "pipeline_run_id"
            ),
        }
        (out_dir / "runs" / f"{cid}.json").write_text(json.dumps(new, indent=1))
        out[cid] = new
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "kind": "post_hoc_floor_replay",
                "records": len(out),
                "council_calls": 0,
                "tools_py_sha256": tools_sha,
                "git_head": head,
                "note": "council votes byte-identical to the source records; grounded + review recomputed with the current floor",
            },
            indent=1,
        )
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", action="append", required=True, help="dirs of persisted eval records")
    ap.add_argument("--cases", required=True, help="gold-free case rows (jsonl) keyed by case_id")
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--ontology", default=None, help="variant ontology (e.g. lead_codes); default packs/_core"
    )
    a = ap.parse_args()
    records = {}
    for d in a.runs:
        for p in sorted(Path(d).glob("*.json")):
            rec = json.loads(p.read_text())
            records[rec.get("case_id") or p.stem] = rec
    cases = {
        json.loads(ln)["case_id"]: json.loads(ln)
        for ln in Path(a.cases).read_text().splitlines()
        if ln.strip()
    }
    missing = [c for c in records if c not in cases]
    if missing:
        raise SystemExit(f"no case row for {len(missing)} records, e.g. {missing[:3]}")
    out = replay(records, cases, out_dir=Path(a.out), ontology_path=a.ontology)
    from collections import Counter

    print(
        json.dumps(
            {
                "replayed": len(out),
                "states": dict(Counter(r["composite"]["review"]["state"] for r in out.values())),
                "out": a.out,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
