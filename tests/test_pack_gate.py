"""A4 — the CI/CD eval-pack gate (offline, $0, plain-env).

The gate rule replicates ../lithrim-backend/examples/ci_cd_gate.py:
``passed = reliability >= threshold AND never_events == 0``. These tests prove the gate
is NON-VACUOUS: a clean pack exits 0; a verdict-mismatch pack exits 1; a Tier-1
never-event (independent of reliability) exits 1.

A3 — build_pack threading + dump/load round-trip (run monkeypatched; no engine call).
"""

from __future__ import annotations

import json
from pathlib import Path

from lithrim_bench.harness import evalpack, pack_gate
from lithrim_bench.taxonomy import load_taxonomy

# Re-pointed to the public in-repo neutral ``_core`` fixture pack so these gate tests
# are self-contained — they no longer read the external ``healthcare`` Pro snapshot.
# ``_core`` Tier-1 never-events: FABRICATED_CLAIM / UNSUPPORTED_ASSERTION / … ; Tier-2:
# MISSING_CONTEXT / INTERNAL_INCONSISTENCY.
_CORE_SNAPSHOT = Path(__file__).resolve().parents[1] / "packs" / "_core" / "taxonomy_snapshot.json"
_CORE_TAX = load_taxonomy(_CORE_SNAPSHOT)


def _pack(outcomes, *, threshold=96.0, pack_id="t"):
    """Synthesize a frozen-pack dict from a list of (case_id, expected_verdict,
    expected_flags, actual_verdict, active_findings) tuples."""
    cases, outs = [], []
    for cid, exp_v, exp_f, act_v, act_findings in outcomes:
        cases.append(
            {"case_id": cid, "expected": {"compliance_verdict": exp_v, "safety_flags": exp_f}}
        )
        outs.append({"case_id": cid, "verdict": act_v, "active_findings": act_findings})
    return {
        "schema_version": "evalpack/1",
        "pack_id": pack_id,
        "pack_version": "1",
        "threshold": threshold,
        "judge_set": {"label": "all_azure"},
        "expected_locked": True,
        "cases": cases,
        "outcomes": outs,
    }


_PASS = _pack(
    [
        ("c_clean", "approve", [], "approve", []),
        ("c_viol", "reject", ["HALLUCINATED_DETAIL"], "reject", ["HALLUCINATED_DETAIL"]),
        ("c_clean2", "approve", [], "approve", []),
    ]
)


# ── A4: reliability + never-event computation ──────────────────────────────


def test_reliability_counts_verdict_matches():
    pct, matches, total, mismatches = pack_gate.reliability(_PASS)
    assert (matches, total) == (3, 3)
    assert pct == 100.0
    assert mismatches == []


def test_reliability_drops_on_mismatch():
    pack = _pack(
        [
            ("c_clean", "approve", [], "approve", []),
            ("c_viol", "reject", ["HALLUCINATED_DETAIL"], "approve", []),  # missed the violation
            ("c_clean2", "approve", [], "approve", []),
        ]
    )
    pct, matches, total, mismatches = pack_gate.reliability(pack)
    assert (matches, total) == (2, 3)
    assert pct < 96.0
    assert mismatches[0]["case_id"] == "c_viol"


def test_never_events_empty_on_clean_pack():
    assert pack_gate.never_events(_PASS) == []


def test_never_event_false_alarm_on_clean_case():
    # A Tier-1 (FABRICATED_CLAIM) fired on an expected-clean case → never-event,
    # EVEN with a matching verdict (isolates the floor check from reliability).
    pack = _pack([("c_clean", "approve", [], "approve", ["FABRICATED_CLAIM"])])
    events = pack_gate.never_events(pack, taxonomy=_CORE_TAX)
    assert len(events) == 1
    assert events[0] == {
        "case_id": "c_clean",
        "safety_flag": "FABRICATED_CLAIM",
        "kind": "false_alarm",
    }


def test_never_event_missed_expected_tier1():
    pack = _pack([("c_unsup", "reject", ["UNSUPPORTED_ASSERTION"], "reject", [])])
    events = pack_gate.never_events(pack, taxonomy=_CORE_TAX)
    assert events == [
        {"case_id": "c_unsup", "safety_flag": "UNSUPPORTED_ASSERTION", "kind": "missed"}
    ]


def test_tier2_finding_is_not_a_never_event():
    # HALLUCINATED_DETAIL is Tier-2 — a false alarm on a clean case hurts reliability
    # (verdict would differ) but is NOT a Tier-1 never-event.
    pack = _pack([("c", "approve", [], "approve", ["HALLUCINATED_DETAIL"])])
    assert pack_gate.never_events(pack) == []


# ── A4: the decide() gate + exit codes ─────────────────────────────────────


def test_decide_passes_clean_pack():
    v = pack_gate.decide(_PASS)
    assert v["passed"] is True
    assert v["reliability"] == 100.0


def test_decide_fails_on_low_reliability():
    pack = _pack(
        [
            ("a", "reject", ["HALLUCINATED_DETAIL"], "approve", []),
            ("b", "approve", [], "approve", []),
        ]
    )
    v = pack_gate.decide(pack)
    assert v["passed"] is False  # 50% < 96%


def test_decide_fails_on_never_event_despite_full_reliability():
    pack = _pack([("c_clean", "approve", [], "approve", ["FABRICATED_CLAIM"])])
    v = pack_gate.decide(pack, taxonomy=_CORE_TAX)
    assert v["reliability"] == 100.0  # verdict matched
    assert v["passed"] is False  # but a Tier-1 never-event blocks the release
    assert len(v["never_events"]) == 1


def test_empty_pack_fails_non_vacuous():
    v = pack_gate.decide(_pack([]))
    assert v["total"] == 0
    assert v["passed"] is False  # reliability 0% < 96%


def test_main_exit_0_on_passing_pack(tmp_path, capsys):
    path = tmp_path / "pass.json"
    path.write_text(json.dumps(_PASS))
    code = pack_gate.main(["--pack", str(path)])
    assert code == 0
    assert "RELEASE GATE: PASS" in capsys.readouterr().out


def test_main_exit_1_on_failing_pack(tmp_path, capsys, monkeypatch):
    # main() reads the AMBIENT active-pack taxonomy (no injection seam). Pin it to the
    # neutral ``_core`` fixture snapshot so the FABRICATED_CLAIM Tier-1 finding is a real
    # never-event regardless of which pack the surrounding suite exported.
    monkeypatch.setattr(pack_gate, "load_taxonomy", lambda path=None: _CORE_TAX)
    bad = _pack(
        [
            ("c_viol", "reject", ["MISSING_CONTEXT"], "approve", []),
            ("c_clean", "approve", [], "approve", ["FABRICATED_CLAIM"]),
        ]
    )
    path = tmp_path / "fail.json"
    path.write_text(json.dumps(bad))
    code = pack_gate.main(["--pack", str(path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "RELEASE GATE: FAIL" in out
    assert "FABRICATED_CLAIM" in out


def test_threshold_override_can_pass_a_borderline_pack(tmp_path):
    pack = _pack(
        [
            ("a", "reject", ["HALLUCINATED_DETAIL"], "approve", []),  # 1 miss, no never-event
            ("b", "approve", [], "approve", []),
            ("c", "approve", [], "approve", []),
        ]
    )  # reliability 66.7%
    assert pack_gate.decide(pack)["passed"] is False  # default 96%
    assert pack_gate.decide(pack, threshold=50.0)["passed"] is True  # relaxed gate


# ── A3: build_pack threading + dump/load round-trip ────────────────────────


def test_build_pack_threads_judge_set_into_run(monkeypatch, tmp_path):
    captured = {}

    def fake_run(agent, **kw):
        captured.update(kw)
        return {
            "case_id": "x",
            "composite": {
                "verdict": "approve",
                "stage_verdict": "PASS",
                "score": 0.0,
                "active_findings": [],
                "grounded_adjustments": [],
                "floor_adjustments": [],
            },
            "grounded": {"original_verdict": "approve"},
            "corrections": [],
            "provenance": {"expected_compliance_verdict": "approve", "expected_safety_flags": []},
            "result": {"provenance": {"pipeline_run_id": "rid-x"}},
        }

    monkeypatch.setattr(evalpack, "_run_core", lambda: fake_run)

    class _Agent:
        name = "x"

    pack = evalpack.build_pack(
        "p",
        [_Agent()],
        in_process=True,
        models={"risk_judge": "byo-claude"},
        roles=["risk_judge", "policy_judge"],
        assignments={"risk_judge": ["UPCODING_RISK"]},
        judge_set={"label": "claude_risk"},
        threshold=90.0,
        out_dir=tmp_path,
    )

    # The judge set + in_process flag reached run().
    assert captured["in_process"] is True
    assert captured["models"] == {"risk_judge": "byo-claude"}
    assert captured["roles"] == ["risk_judge", "policy_judge"]
    assert captured["assignments"] == {"risk_judge": ["UPCODING_RISK"]}
    # The manifest carries the locked criteria.
    assert pack["threshold"] == 90.0
    assert pack["judge_set"] == {"label": "claude_risk"}
    assert pack["expected_locked"] is True
    assert pack["schema_version"] == "evalpack/1"


def test_dump_load_pack_identity_round_trip(tmp_path):
    path = evalpack.dump_pack(_PASS, tmp_path / "pack.json")
    assert evalpack.load_pack(path) == _PASS
