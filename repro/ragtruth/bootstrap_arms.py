"""Paired bootstrap of one reviewer arm against another on the same records, resampling by source_id.

Two run directories (or sets of them) hold persisted eval records for the same case ids; the labels file
is the gold-free case row set carrying `expected_safety_flags` and `ragtruth.source_id`. For each
verdict mapping of `score_reviewer` the point delta (c - b) and a percentile interval are reported for
F1, precision, recall, coverage, false clears and false blocks.
"""

from __future__ import annotations

import argparse
import glob
import json
import random
from collections import defaultdict
from pathlib import Path

from repro.ragtruth.paper_prompt_arm import parse_output, response_level
from repro.ragtruth.score_reviewer import (
    combined,
    council_alone,
    load_labels,
    prf,
    raw_consensus,
)

MAPPINGS = {
    "council_alone": lambda r: council_alone(r),
    "three_state": lambda r: combined(r),
    "escalate_is_halu": lambda r: combined(r, escalate_is_halu=True),
    "raw_consensus": lambda r: raw_consensus(r),
    # a paper-prompt record: the paper's rule, unparseable output = not detected
    "paper_prompt": lambda r: (
        "halu" if response_level(parse_output(r.get("raw"))) == "halu" else "clean"
    ),
}
METRICS = ("f1", "precision", "recall", "coverage", "false_clears", "false_blocks")


def _load(dirs: list[str]) -> dict[str, dict]:
    recs = {}
    for d in dirs:
        for p in glob.glob(str(Path(d) / "*.json")):
            recs[Path(p).stem] = json.loads(Path(p).read_text())
    return recs


def _ci(xs: list[float]) -> list[float]:
    xs = sorted(xs)
    return [round(xs[int(0.025 * (len(xs) - 1))], 4), round(xs[int(0.975 * (len(xs) - 1))], 4)]


def compare(
    b_dirs, c_dirs, *, labels: str, draws: int = 1000, seed: int = 0, b_map=None, c_map=None
) -> dict:
    golds = load_labels(labels)
    b, c = _load(b_dirs), _load(c_dirs)
    if set(b) != set(c):
        raise ValueError(
            f"arms must cover the same records: {len(set(b) - set(c))} only in b, "
            f"{len(set(c) - set(b))} only in c"
        )
    ids = sorted(set(b) & set(golds))
    by_src = defaultdict(list)
    for cid in ids:
        by_src[golds[cid]["source_id"]].append(cid)
    srcs = sorted(by_src)
    out = {
        "unit": "source_id",
        "sources": len(srcs),
        "draws": draws,
        "seed": seed,
        "n": len(ids),
        "arms": {},
    }
    pairs = (
        [(f"{b_map}_vs_{c_map}", MAPPINGS[b_map], MAPPINGS[c_map])]
        if b_map or c_map
        else [(n, f, f) for n, f in MAPPINGS.items() if n != "paper_prompt"]
    )
    for name, fb, fc in pairs:
        pb = {cid: fb(b[cid]) for cid in ids}
        pc = {cid: fc(c[cid]) for cid in ids}

        def stats(sel, pb=pb, pc=pc):
            g = [golds[x]["halu"] for x in sel]
            return prf([pb[x] for x in sel], g), prf([pc[x] for x in sel], g)

        sb, sc = stats(ids)
        rng = random.Random(seed)
        deltas = defaultdict(list)
        for _ in range(draws):
            sel = [x for s in (rng.choice(srcs) for _ in srcs) for x in by_src[s]]
            db, dc = stats(sel)
            for m in METRICS:
                deltas[m].append(dc[m] - db[m])
        out["arms"][name] = {
            "b": {m: sb[m] for m in METRICS},
            "c": {m: sc[m] for m in METRICS},
            "delta": {m: {"point": round(sc[m] - sb[m], 4), "ci": _ci(deltas[m])} for m in METRICS},
        }
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--b", action="append", required=True, help="baseline arm run dir(s)")
    ap.add_argument("--c", action="append", required=True, help="comparison arm run dir(s)")
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--b-map", choices=sorted(MAPPINGS), help="reading for arm b")
    ap.add_argument("--c-map", choices=sorted(MAPPINGS), help="reading for arm c")
    a = ap.parse_args(argv)
    out = compare(
        a.b, a.c, labels=a.labels, draws=a.draws, seed=a.seed, b_map=a.b_map, c_map=a.c_map
    )
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    for name, v in out["arms"].items():
        d = v["delta"]
        print(
            f"{name:17s} dF1 {d['f1']['point']:+.4f} {d['f1']['ci']}  "
            f"dP {d['precision']['point']:+.4f} {d['precision']['ci']}  "
            f"dcov {d['coverage']['point']:+.4f} {d['coverage']['ci']}  "
            f"dfalse_clears {d['false_clears']['point']:+.0f} {d['false_clears']['ci']}"
        )


if __name__ == "__main__":
    main()
