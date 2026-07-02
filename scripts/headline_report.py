"""The mean±range headline over banked grade passes (LAYER4-HEADLINE-1).

Recomputes each pass under the CURRENT scoring config (offline re-ground + descope +
family units — see lithrim_bench/harness/headline.py) and prints the honest headline:
mean ± spread per metric, pass count with the below-target flag, config signature.

  PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACK=clinverdict LITHRIM_BENCH_PACKS_DIR=packs-dropin \\
    pyenv exec python scripts/headline_report.py \\
      --ontology packs-dropin/clinverdict/ontology.json \\
      --corpus packs-dropin/clinverdict/examples/clinverdict_mts_v1.jsonl \\
      --pass-dir <records-dir-1> --pass-dir <records-dir-2> [...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lithrim_bench.harness.headline import config_signature, headline, pass_scores  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ontology", required=True, type=Path)
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--pass-dir", action="append", required=True, type=Path,
                    help="a directory of per-case grade records (repeatable, one per pass)")
    args = ap.parse_args()

    ontology_raw = json.loads(args.ontology.read_text())
    corpus = {}
    with args.corpus.open() as fh:
        for line in fh:
            row = json.loads(line)
            corpus[row["case_id"]] = row

    per_pass = []
    for d in args.pass_dir:
        loaded = [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]
        # a pass dir may carry non-record JSON (compiled demos, calib) — records only
        records = [r for r in loaded if isinstance(r, dict) and r.get("case_id")]
        s = pass_scores(records, corpus, ontology_raw)
        per_pass.append(s)
        print(f"[{d}] n_labeled={s['n_labeled']}")
        for block in ("strict", "units_exact", "units_family"):
            b = s[block]
            print(f"  {block:13} P={b['precision']:.3f} R={b['recall']:.3f} "
                  f"tp={b['tp']} fp={b['fp']} fn={b['fn']}")

    h = headline(per_pass, config_signature(ontology_raw))
    print("\n" + h["formatted"])
    if h["below_target_n"]:
        print(f"NOTE: {h['n_passes']} passes is below the ≥3-pass target — "
              f"treat the spread as provisional.")


if __name__ == "__main__":
    main()
