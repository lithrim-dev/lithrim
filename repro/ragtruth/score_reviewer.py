"""Reviewer-benchmark scorer over persisted council records (offline, $0). Gold is read ONLY from
the offline labelled file; a record that carries any gold key is refused. Mapping and prediction
are pre-registered in EXPERIMENT_PLAN.md §12."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from lithrim_bench.reliability import wilson_proportion

GOLD_KEYS = {
    "expected_safety_flags",
    "expected_artifact_verdict",
    "expected_compliance_verdict",
    "labels",
}
EXCLUDED_CODES = {"MISSING_CONTEXT"}  # no RAGTruth counterpart (§3.5a); reported, never scored


def load_records(dirs) -> dict[str, dict]:
    out = {}
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            rec = json.loads(p.read_text())
            out[rec.get("case_id") or p.stem] = rec
    return out


def load_labels(path, only=None) -> dict[str, dict]:
    out = {}
    for ln in Path(path).read_text().splitlines():
        if not ln.strip():
            continue
        c = json.loads(ln)
        if only is not None and c["case_id"] not in only:
            continue
        rt = c.get("ragtruth") or {}
        out[c["case_id"]] = {
            "halu": bool(c.get("expected_safety_flags")),
            "source_id": rt.get("source_id"),
            "model": rt.get("model"),
            "labels": rt.get("labels") or [],
        }
    return out


def council_alone(rec: dict, *, warn_is_halu: bool = False) -> str:
    v = (rec.get("grounded") or {}).get("verdict_no_floor")
    if v == "BLOCK":
        return "halu"
    if v == "WARN" and warn_is_halu:
        return "halu"
    return "clean"


def combined(rec: dict, *, escalate_is_halu: bool = False) -> str:
    s = ((rec.get("composite") or {}).get("review") or {}).get("state")
    if s == "FLAGGED":
        return "halu"
    if s == "CLEARED":
        return "clean"
    return "halu" if escalate_is_halu else "abstain"


def raw_consensus(rec: dict) -> str:
    return "halu" if (rec.get("result") or {}).get("verdict") == "BLOCK" else "clean"


def prf(preds, golds) -> dict:
    tp = fp = fn = tn = abst = 0
    for p, g in zip(preds, golds, strict=True):
        if p == "abstain":
            abst += 1
            fn += g
            continue
        if p == "halu":
            tp += g
            fp += not g
        else:
            fn += g
            tn += not g
    n = len(preds)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "abstained": abst,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
        "coverage": round(1 - abst / n, 4) if n else 0.0,
        "false_clears": fn
        - sum(1 for p, g in zip(preds, golds, strict=True) if p == "abstain" and g),
        "false_blocks": fp,
    }


def _f1_from_counts(rows, key):
    return prf([r[key] for r in rows], [r["gold"] for r in rows])["f1"]


def paired_bootstrap(rows, *, n: int = 1000, seed: int = 0) -> dict:
    by_src = defaultdict(list)
    for r in rows:
        by_src[r["source_id"]].append(r)
    srcs = sorted(by_src)
    rng = random.Random(seed)
    deltas, bf, cf = [], [], []
    for _ in range(n):
        draw = [row for s in (rng.choice(srcs) for _ in srcs) for row in by_src[s]]
        b, c = _f1_from_counts(draw, "b"), _f1_from_counts(draw, "c")
        deltas.append(c - b)
        bf.append(b)
        cf.append(c)

    def ci(xs):
        xs = sorted(xs)
        return [round(xs[int(0.025 * (len(xs) - 1))], 4), round(xs[int(0.975 * (len(xs) - 1))], 4)]

    return {
        "unit": "source_id",
        "sources": len(srcs),
        "draws": n,
        "seed": seed,
        "delta_f1_point": round(_f1_from_counts(rows, "c") - _f1_from_counts(rows, "b"), 4),
        "delta_f1_ci": ci(deltas),
        "b_f1_ci": ci(bf),
        "c_f1_ci": ci(cf),
    }


def _wilson_bounds(hits: int, n: int) -> tuple[float, float]:
    w = wilson_proportion(hits, n)
    for v in w.values():
        if (
            isinstance(v, (tuple, list))
            and len(v) == 2
            and all(isinstance(x, (int, float)) for x in v)
        ):
            return float(v[0]), float(v[1])
    raise RuntimeError(f"wilson_proportion returned no (lo, hi) pair: {w}")


def _signals(rec: dict):
    # Real records carry findings as code STRINGS; synthetic fixtures may carry {"code": ...}.
    for v in ((rec.get("result") or {}).get("semantic") or {}).get("judge_votes") or []:
        for f in v.get("findings") or []:
            code = f if isinstance(f, str) else (f or {}).get("code")
            if code:
                yield v.get("judge_role"), code


def ledger(recs: dict, golds: dict) -> list[dict]:
    hits, n = defaultdict(int), defaultdict(int)
    for cid, rec in recs.items():
        g = golds[cid] if isinstance(golds[cid], bool) else golds[cid]["halu"]
        seen = set()
        for role, code in _signals(rec):
            if code in EXCLUDED_CODES:
                continue
            seen.add(f"{role}:{code}")
        for fb in (rec.get("grounded") or {}).get("floor_blocks") or []:
            # Real shape: flat {contract_type, injected, evidence, ...}; only an INJECTED block is a signal.
            ct = fb.get("contract_type") or (
                (fb.get("decl") or {}).get("contract_type")
                if isinstance(fb.get("decl"), dict)
                else None
            )
            if ct and fb.get("injected", True):
                seen.add(f"floor:{ct}")
        for chk in seen:
            n[chk] += 1
            hits[chk] += bool(g)
    out = []
    for chk in sorted(n):
        lo, hi = _wilson_bounds(hits[chk], n[chk])
        out.append(
            {
                "check": chk,
                "n": n[chk],
                "hits": hits[chk],
                "precision": round(hits[chk] / n[chk], 4),
                "wilson_low": round(lo, 4),
                "wilson_high": round(hi, 4),
            }
        )
    return out


def excluded_signals(recs: dict) -> list[dict]:
    cnt = defaultdict(int)
    for rec in recs.values():
        codes = {code for _, code in _signals(rec)}
        for c in codes & EXCLUDED_CODES:
            cnt[c] += 1
    return [{"check": f"{c}(excluded)", "n": k} for c, k in sorted(cnt.items())]


def score(recs: dict, golds: dict) -> dict:
    for cid, rec in recs.items():
        if GOLD_KEYS & set(rec):
            raise ValueError(
                f"record {cid} carries gold keys {sorted(GOLD_KEYS & set(rec))}; refusing to score"
            )
        if cid not in golds:
            raise ValueError(f"no offline label for {cid}")
    ids = sorted(recs)
    g = [golds[c]["halu"] for c in ids]
    arms = {
        "council_alone_primary": prf([council_alone(recs[c]) for c in ids], g),
        "council_alone_warn_is_halu": prf(
            [council_alone(recs[c], warn_is_halu=True) for c in ids], g
        ),
        "combined_primary": prf([combined(recs[c]) for c in ids], g),
        "combined_escalate_is_halu": prf(
            [combined(recs[c], escalate_is_halu=True) for c in ids], g
        ),
        "raw_consensus_block_is_halu": prf([raw_consensus(recs[c]) for c in ids], g),
        "trivial_always_halu": prf(["halu"] * len(ids), g),
    }
    pos = sum(g)
    per_gen = {}
    for m in sorted({golds[c]["model"] for c in ids}):
        sub = [c for c in ids if golds[c]["model"] == m]
        gg = [golds[c]["halu"] for c in sub]
        per_gen[m] = {
            "n": len(sub),
            "base_rate": round(sum(gg) / len(sub), 4),
            "council_alone_f1": prf([council_alone(recs[c]) for c in sub], gg)["f1"],
            "combined_f1": prf([combined(recs[c]) for c in sub], gg)["f1"],
            "combined_coverage": prf([combined(recs[c]) for c in sub], gg)["coverage"],
        }
    rows = [
        {
            "source_id": golds[c]["source_id"],
            "gold": golds[c]["halu"],
            "b": council_alone(recs[c]),
            "c": combined(recs[c]),
        }
        for c in ids
    ]
    return {
        "n": len(ids),
        "positives": pos,
        "base_rate": round(pos / len(ids), 4),
        "arms": arms,
        "per_generator": per_gen,
        "ledger": ledger(recs, golds),
        "excluded_signals": excluded_signals(recs),
        "paired_bootstrap_combined_vs_council_alone": paired_bootstrap(rows)
        if len(rows) > 1
        else None,
        "limitation": "Human response-level gold; abstention scored as a miss; precision reported with base rate.",
    }


def render(rep: dict) -> str:
    L = [
        f"# Reviewer benchmark — n={rep['n']}, positives={rep['positives']}, base rate={rep['base_rate']}",
        "",
        "| arm | P | R | F1 | coverage | abstained | false clears | false blocks |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k, a in rep["arms"].items():
        L.append(
            f"| {k} | {a['precision']} | {a['recall']} | {a['f1']} | {a['coverage']} | {a['abstained']} | {a['false_clears']} | {a['false_blocks']} |"
        )
    bs = rep.get("paired_bootstrap_combined_vs_council_alone")
    if bs:
        L += [
            "",
            f"Δ F1 (combined − council alone) = {bs['delta_f1_point']}, 95% CI {bs['delta_f1_ci']} "
            f"(bootstrap by {bs['unit']}, {bs['sources']} sources, {bs['draws']} draws)",
        ]
    L += [
        "",
        "## Ledger (precision vs human gold, Wilson 95%)",
        "",
        "| check | n | hits | precision | low | high |",
        "|---|---|---|---|---|---|",
    ]
    L += [
        f"| {r['check']} | {r['n']} | {r['hits']} | {r['precision']} | {r['wilson_low']} | {r['wilson_high']} |"
        for r in rep["ledger"]
    ]
    L += [
        "",
        "Excluded signals: "
        + ", ".join(f"{e['check']} n={e['n']}" for e in rep["excluded_signals"])
        or "none",
    ]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", action="append", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    recs = load_records(a.runs)
    rep = score(recs, load_labels(a.labels, only=set(recs)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "report.json").write_text(json.dumps(rep, indent=1))
    (out / "REPORT.md").write_text(render(rep))
    print(
        json.dumps(
            {
                "n": rep["n"],
                "base_rate": rep["base_rate"],
                "council_alone_f1": rep["arms"]["council_alone_primary"]["f1"],
                "combined_f1": rep["arms"]["combined_primary"]["f1"],
                "combined_coverage": rep["arms"]["combined_primary"]["coverage"],
                "out": str(out),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
