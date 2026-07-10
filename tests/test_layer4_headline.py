"""LAYER4-HEADLINE-1 — the reproducible mean±range headline.

The headline is a SURFACE, not a pasted number: recomputed from stored pass records under
the CURRENT scoring config (offline re-ground + descope + family units), config-hash
pinned, mean ± spread with N stated (owner target >=3 passes; below-target is said
in-band, never hidden).

Comparability: passes were GRADED under different floor configs, so stored
``grounded.active`` is not averageable. ``pass_scores`` reconstructs each pass's active
set under the CURRENT config: pre-floor findings − stored SERVICE-transport suppressions
(Hermes: baked-in, cannot re-run offline) − a fresh offline re-ground with the current
pure-stdlib contracts (so pass 2's observation-form/v1 gold false-clear is CORRECTED,
matching what v2 does live).
"""

from __future__ import annotations

import pytest

from lithrim_bench.harness.headline import config_signature, headline, pass_scores


# ── a minimal ontology-raw fixture (from_dict shape) ─────────────────────────────────────
def _flag(code, gradeable=True):
    return {"flag": code, "category": "c", "definition": "d", "when_to_use": "w",
            "when_NOT_to_use": "n", "owner_roles": ["r"], "gradeable": gradeable}


def _ont(contracts=(), families=None, gradeable_b=False, question="q1"):
    return {
        "ontology_version": "t/1", "domain": "t",
        "flags": [_flag("A"), _flag("B", gradeable=gradeable_b), _flag("D")],
        "questions": [{"role": "r", "ordinal": 1, "text": question}],
        "verification_contracts": list(contracts),
        "severity_map": {"weights": {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2},
                         "block_at_or_above": 0.6, "warn_above": 0.2},
        "code_families": families or {},
    }


# ── H1: the config signature moves on scoring surface only ──────────────────────────────
def test_h1_signature_deterministic_and_scoring_surface_only():
    base = _ont()
    assert config_signature(base) == config_signature(_ont())
    # prose (a question edit) does NOT move the signature
    assert config_signature(base) == config_signature(_ont(question="reworded"))
    # gradeable partition moves it
    assert config_signature(base) != config_signature(_ont(gradeable_b=True))
    # a contract moves it
    ct = {"contract_type": "evidence_presence", "flag_code": "A", "params": {"mode": "any"},
          "question": "q", "version": "v1"}
    assert config_signature(base) != config_signature(_ont(contracts=[ct]))
    # code_families move it
    assert config_signature(base) != config_signature(_ont(families={"fam": ["A", "D"]}))


# ── H2: pass_scores math on a hermetic mini-pass ─────────────────────────────────────────
_CORPUS = {
    "c1": {"case_id": "c1", "expected_safety_flags": ["A"], "transcript": "the sky is blue today"},
    "c2": {"case_id": "c2", "expected_safety_flags": ["B"], "transcript": "x"},  # fully descoped
    "c3": {"case_id": "c3", "expected_safety_flags": [],
           "expected_compliance_verdict": "approve", "transcript": "x"},
}


def _rec(cid, codes, quotes_by_code=None, suppressed=(), active=None):
    ev = [{"violation_code": c, "spans": [{"quote": q} for q in (quotes_by_code or {}).get(c, ["some quote text"])]}
          for c in codes]
    # mirror real records: a fully-suppressed code is NOT in the stored active set
    if active is None:
        active = [c for c in codes if c not in {s[0] for s in suppressed}]
    return {
        "case_id": cid,
        "result": {"findings": [{"code": c, "severity": "HIGH"} for c in codes],
                   "semantic": {"evidence": ev}, "verdict": "reject"},
        "grounded": {"suppressed": [{"code": c, "contract": v} for c, v in suppressed],
                     "active": [{"code": c} for c in active]},
    }


def test_h2_descope_family_and_strict_math():
    # c1: gold {A}, judge raised the family-sibling D only; c2 fully descoped -> leaves labeled.
    records = [_rec("c1", ["D"]), _rec("c2", ["A"]), _rec("c3", [])]
    s = pass_scores(records, _CORPUS, _ont(families={"fam": ["A", "D"]}))
    assert s["n_labeled"] == 2  # c1 + c3 (c2's only gold is descoped)
    assert (s["strict"]["tp"], s["strict"]["fp"], s["strict"]["fn"]) == (0, 1, 1)
    assert (s["units_exact"]["tp"], s["units_exact"]["fp"], s["units_exact"]["fn"]) == (0, 1, 1)
    # family-aware: the sibling catch credits the gold
    assert (s["units_family"]["tp"], s["units_family"]["fp"], s["units_family"]["fn"]) == (1, 0, 0)
    assert s["units_family"]["recall"] == 1.0


def test_h2b_offline_reground_applies_current_contracts():
    # evidence_presence (core, in_process) on D, any-mode; D's quote is verbatim in c1's
    # transcript -> the CURRENT config suppresses D offline -> no active finding remains.
    ct = {"contract_type": "evidence_presence", "flag_code": "D",
          "params": {"mode": "any"}, "question": "q", "version": "evidence-presence/v1"}
    records = [_rec("c1", ["D"], quotes_by_code={"D": ["the sky is blue today"]})]
    s = pass_scores(records, {"c1": _CORPUS["c1"]}, _ont(contracts=[ct]))
    assert (s["strict"]["tp"], s["strict"]["fp"], s["strict"]["fn"]) == (0, 0, 1)


def test_h2c_stored_service_suppressions_stay_baked_in():
    # a SERVICE-transport contract's stored suppression (Hermes-style) is respected, never re-run:
    # D was suppressed by the declared kb_grounding (service) version -> D leaves the active set.
    ct = {"contract_type": "kb_grounding", "flag_code": "D",
          "params": {"namespace": "x"}, "question": "q", "version": "svc/v1"}
    records = [_rec("c1", ["D"], suppressed=(("D", "svc/v1"),))]
    s = pass_scores(records, {"c1": _CORPUS["c1"]}, _ont(contracts=[ct]))
    assert (s["strict"]["tp"], s["strict"]["fp"], s["strict"]["fn"]) == (0, 0, 1)


def test_h2d_partially_suppressed_code_survives_service_subtraction():
    """Critic close-out: floors are span-gated (SPAN-BIND-1), so a code can be suppressed on
    one finding yet ACTIVE on another. A code still in the stored active set was not fully
    cleared — the service subtraction must not over-subtract it."""
    ct = {"contract_type": "kb_grounding", "flag_code": "D",
          "params": {"namespace": "x"}, "question": "q", "version": "svc/v1"}
    rec = _rec("c1", ["D"], suppressed=(("D", "svc/v1"),), active=["D"])  # partial: D survives
    s = pass_scores([rec], {"c1": _CORPUS["c1"]}, _ont(contracts=[ct]))
    assert (s["strict"]["tp"], s["strict"]["fp"], s["strict"]["fn"]) == (0, 1, 1)


# ── H3: aggregation honesty ──────────────────────────────────────────────────────────────
def _score(p, r):
    return {"n_labeled": 10,
            "strict": {"precision": p, "recall": r, "tp": 1, "fp": 1, "fn": 1},
            "units_exact": {"precision": p, "recall": r, "tp": 1, "fp": 1, "fn": 1, "matched_gold": 1},
            "units_family": {"precision": p, "recall": r, "tp": 1, "fp": 1, "fn": 1, "matched_gold": 1}}


def test_h3_mean_min_max_spread_and_below_target():
    h = headline([_score(0.30, 0.55), _score(0.32, 0.59)], "abc123")
    m = h["metrics"]["strict.precision"]
    assert (round(m["mean"], 3), m["min"], m["max"], round(m["spread"], 3)) == (0.31, 0.30, 0.32, 0.02)
    assert h["n_passes"] == 2
    assert h["below_target_n"] is True  # owner target >=3, said in-band
    assert h["config_signature"] == "abc123"
    assert "2 passes" in h["formatted"] or "n=2" in h["formatted"]


def test_h3_single_pass_spread_zero_and_target_met_at_three():
    h1 = headline([_score(0.3, 0.5)], "s")
    assert h1["metrics"]["strict.recall"]["spread"] == 0.0
    h3 = headline([_score(0.3, 0.5)] * 3, "s")
    assert h3["below_target_n"] is False


# ── H4: the real banked passes (env-gated; exact pins land with the measurement) ────────
import json as _json  # noqa: E402
import os as _os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_P1 = _os.environ.get("LITHRIM_BENCH_CLEANRUN_DIR", "")
_P2 = _os.environ.get("LITHRIM_BENCH_PASS2_DIR", "")
_P3 = _os.environ.get("LITHRIM_BENCH_PASS3_DIR", "")
_DROPIN = _Path(__file__).resolve().parents[1] / "packs-dropin" / "clinverdict"


@pytest.mark.skipif(
    not (_P1 and _P2 and _P3
         and all(_Path(p).is_dir() for p in (_P1, _P2, _P3)) and _DROPIN.is_dir()),
    reason="needs the three banked pass dirs + the clinverdict drop-in",
)
def test_h4_real_three_pass_headline(monkeypatch):
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "clinverdict")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(_DROPIN.parent))
    ont = _json.loads((_DROPIN / "ontology.json").read_text())
    corpus = {}
    with open(_DROPIN / "examples" / "clinverdict_mts_v1.jsonl") as fh:
        for line in fh:
            row = _json.loads(line)
            corpus[row["case_id"]] = row
    per_pass = []
    for d in (_P1, _P2, _P3):
        records = [_json.loads(p.read_text()) for p in sorted(_Path(d).glob("cv_mts_*.json"))]
        per_pass.append(pass_scores(records, corpus, ont))
    h = headline(per_pass, config_signature(ont))
    assert h["n_passes"] == 3 and h["below_target_n"] is False  # the ≥3 target is MET
    for s in per_pass:
        assert s["n_labeled"] == 161  # descope drops the fully-descoped cases
        # family-aware recall must dominate exact recall on EVERY pass (the sibling credit)
        assert s["units_family"]["recall"] > s["units_exact"]["recall"]
    # LIVE-AGREEMENT pin: pass 3 was graded NATIVELY under this config — its recompute must
    # equal the BFF's own at-grade scorecard (strict tp=69 fp=150 fn=50, measured 2026-07-02).
    p3 = per_pass[2]
    assert (p3["strict"]["tp"], p3["strict"]["fp"], p3["strict"]["fn"]) == (69, 150, 50)
    # exact pins from the 2026-07-02 3-pass measurement (config=3bf461c210cb14c4):
    # strict recall is BYTE-STABLE across all three passes (tp=69 fn=50 each).
    m = h["metrics"]
    assert m["strict.recall"]["mean"] == pytest.approx(0.580, abs=1e-3)
    assert m["strict.recall"]["spread"] == pytest.approx(0.0, abs=1e-9)
    assert m["strict.precision"]["mean"] == pytest.approx(0.309, abs=1e-3)
    assert m["units_family.recall"]["mean"] == pytest.approx(0.7143, abs=1e-3)
