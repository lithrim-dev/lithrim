"""LAYER4-HEADLINE-1 — the reproducible mean±range headline over banked passes.

Judges are stochastic across passes; a single-pass headline is a coin-flip presented as a
fact. The honest headline is mean ± spread over N frozen-config passes, recomputed from
stored grade records under the CURRENT scoring config and pinned to a config signature —
a SURFACE anyone can rerun (scripts/headline_report.py), not a pasted number.

Comparability: the banked passes were GRADED under different floor configs, so stored
``grounded.active`` is not averageable. :func:`pass_scores` reconstructs each pass's
active set under the CURRENT config:

    post = (pre-floor findings − stored SERVICE-transport suppressions)   # Hermes: baked-in
           − offline re-ground with the current pure-stdlib contracts    # real ground()

Service contracts (out-of-process terminology) cannot re-run offline — their stored effect
rides; the in_process contracts re-derive, so a superseded contract version's mistake
(observation-form/v1's gold false-clear) is CORRECTED in the recompute, matching what the
current version does live. Scoring then mirrors Layers 1–3 exactly: descope-filtered gold
(a fully-descoped case leaves the labeled set), strict flag P/R, and the units clerk's
exact + family-aware scores.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from lithrim_bench.harness import ontology as ontology_mod
from lithrim_bench.harness.finding_units import consolidate, score_units
from lithrim_bench.harness.grounding import contract_plugins, ground

# the owner's stated bar for a headline: at least this many frozen-config passes.
TARGET_PASSES = 3


def config_signature(ontology_raw: dict[str, Any]) -> str:
    """A short hash of the SCORING-relevant config surface: the verification contracts,
    the per-flag gradeable partition, and the code families. Prose (definitions, judge
    questions) deliberately does NOT move it — the signature answers "were these numbers
    produced by the same scoring rules", not "is the ontology byte-identical"."""
    surface = {
        "contracts": sorted(
            (
                c.get("contract_type", ""),
                c.get("flag_code", ""),
                c.get("version", ""),
                json.dumps(c.get("params") or {}, sort_keys=True),
            )
            for c in ontology_raw.get("verification_contracts") or ()
        ),
        "gradeable": sorted(
            (f.get("flag", ""), bool(f.get("gradeable", True)))
            for f in ontology_raw.get("flags") or ()
        ),
        "code_families": {
            fam: sorted(members or ())
            for fam, members in (ontology_raw.get("code_families") or {}).items()
        },
    }
    blob = json.dumps(surface, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _transport_split() -> tuple[set[str], set[str]]:
    """(in_process suppress contract_types, service suppress contract_types) from the
    declared plugin registry — the same enumeration provenance records."""
    in_process: set[str] = set()
    service: set[str] = set()
    for p in contract_plugins():
        if getattr(p, "implements", "") != "grounding.suppress":
            continue
        bucket = in_process if getattr(p, "transport", "") == "in_process" else service
        bucket.update(getattr(p, "contract_types", ()) or ())
    return in_process, service


def _codes(findings: Any) -> set[str]:
    return {
        (f.get("code") or f.get("flag_code"))
        for f in (findings or ())
        if isinstance(f, dict) and (f.get("code") or f.get("flag_code"))
    }


def pass_scores(
    records: list[dict[str, Any]],
    corpus: dict[str, dict[str, Any]],
    ontology_raw: dict[str, Any],
) -> dict[str, Any]:
    """One pass's scorecard under the CURRENT scoring config (see the module docstring)."""
    in_process_types, service_types = _transport_split()
    decls = ontology_raw.get("verification_contracts") or []
    offline_raw = dict(ontology_raw)
    offline_raw["verification_contracts"] = [
        c for c in decls if c.get("contract_type") in in_process_types
    ]
    offline_ont = ontology_mod.from_dict(offline_raw)
    service_versions = {
        c.get("version") for c in decls if c.get("contract_type") in service_types
    }

    flags = ontology_raw.get("flags") or []
    gradeable = {f["flag"] for f in flags if f.get("gradeable", True)} if flags else None

    strict_tp = strict_fp = strict_fn = 0
    units_by_case: dict[str, list] = {}
    gold_by_case: dict[str, set[str]] = {}
    n_labeled = 0
    by_id = {r.get("case_id"): r for r in records if r.get("case_id")}

    for cid, case in corpus.items():
        raw_gold = set(case.get("expected_safety_flags") or ())
        labeled = bool(case.get("expected_compliance_verdict")) or bool(raw_gold)
        gold = raw_gold & gradeable if gradeable is not None else raw_gold
        # LAYER3 descope semantics: a case whose only gold was descoped is unscoreable
        # on this panel — it leaves the labeled set, it is NOT rescored clean.
        if not labeled or (raw_gold and not gold):
            continue
        rec = by_id.get(cid)
        if rec is None:
            continue
        n_labeled += 1
        result = rec.get("result") or {}
        pre = _codes(result.get("findings"))
        grounded = rec.get("grounded") or {}
        stored_suppressed = grounded.get("suppressed") or ()
        # code-level guard (critic close-out): the floors are span-gated post SPAN-BIND-1,
        # so a code can be suppressed on one finding yet survive on another — a code still
        # present in the stored ACTIVE set was not fully cleared and must not be subtracted.
        stored_active = _codes(grounded.get("active"))
        svc_suppressed = {
            s.get("code")
            for s in stored_suppressed
            if s.get("contract") in service_versions
        } - stored_active
        g = ground(result, case, ontology=offline_ont)
        new_active = _codes(g.active)
        offline_suppressed = {
            e["finding"].get("code") for e in g.suppressed
        } - new_active
        post = {
            c
            for c in (pre - svc_suppressed) - offline_suppressed
            if not offline_ont.is_reference(c)
        }
        strict_tp += len(post & gold)
        strict_fp += len(post - gold)
        strict_fn += len(gold - post)
        evidence = ((result.get("semantic") or {}).get("evidence")) or []
        units_by_case[cid] = consolidate(
            sorted(post), evidence, ontology_raw.get("code_families") or {}
        )
        gold_by_case[cid] = gold

    def _pr(tp: int, fp: int, fn: int) -> dict[str, Any]:
        return {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
        }

    return {
        "n_labeled": n_labeled,
        "strict": _pr(strict_tp, strict_fp, strict_fn),
        "units_exact": score_units(units_by_case, gold_by_case),
        "units_family": score_units(
            units_by_case, gold_by_case,
            code_families=ontology_raw.get("code_families") or None,
        ),
    }


_METRICS = (
    "strict.precision", "strict.recall",
    "units_exact.precision", "units_exact.recall",
    "units_family.precision", "units_family.recall",
)


def headline(per_pass: list[dict[str, Any]], config_sig: str) -> dict[str, Any]:
    """Aggregate N pass scorecards into the honest headline: per metric mean/min/max/spread,
    the pass count with the below-target flag said in-band, and the config signature."""
    metrics: dict[str, dict[str, float]] = {}
    for name in _METRICS:
        block, key = name.split(".")
        values = [float(s[block][key]) for s in per_pass]
        metrics[name] = {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "spread": max(values) - min(values),
        }
    n = len(per_pass)

    def _fmt(name: str) -> str:
        m = metrics[name]
        return f"{m['min']:.1%}–{m['max']:.1%} (mean {m['mean']:.1%})"

    formatted = (
        f"strict P {_fmt('strict.precision')} · R {_fmt('strict.recall')} | "
        f"units(family) P {_fmt('units_family.precision')} · R {_fmt('units_family.recall')} | "
        f"n={n} passes (target ≥{TARGET_PASSES}) · config={config_sig}"
    )
    return {
        "config_signature": config_sig,
        "n_passes": n,
        "below_target_n": n < TARGET_PASSES,
        "metrics": metrics,
        "formatted": formatted,
    }
