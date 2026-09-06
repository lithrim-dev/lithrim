"""QUEUE-DEMO-1 — ``make queue``: the reviewer works a five-case queue at $0.

The product invariant, as a test: a case is CLEARED only when the deterministic layer
materially supported the PASS (a recorded floor pass or a judge signal disproved with
evidence), FLAGGED only when a check injected the block, and everything else is ESCALATED
with the reason a person needs. A judge's confidence never clears a case.

Written FIRST (RED): ``scripts/queue_demo.py`` and the ``queue`` make target do not exist, and
no RAGTruth judge baselines are committed, so the end-to-end run cannot replay.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/queue_demo.py"
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import queue_demo  # noqa: E402

_STATES = {"CLEARED", "FLAGGED", "ESCALATED"}


# ── the state mapping, unit-level over grounded-result shapes ────────────────────────────

def _decl(ct):
    return SimpleNamespace(contract_type=ct, version="v1", flag_code="X")


def _res(conforms, **ev):
    return SimpleNamespace(conforms=conforms, evidence=ev, reason=ev.get("reason"))


def _grounded(verdict, no_floor, cov, active=(), blocks=(), passes=(), suppressed=()):
    return SimpleNamespace(
        verdict=verdict, verdict_no_floor=no_floor, coverage=cov, active=list(active),
        floor_blocks=list(blocks), floor_passes=list(passes), suppressed=list(suppressed),
    )


def test_flagged_requires_a_floor_injected_block():
    g = _grounded(
        "BLOCK", "PASS", {"grounded": 1, "cleared": 0, "floor_backstopped": True},
        active=[{"code": "SOURCE_CONTRADICTION", "_floor": True}],
        blocks=[{"decl": _decl("value_grounding"), "result": _res(False, missing=["4.5"], reason="absent from the record"),
                 "injected_finding": {"code": "SOURCE_CONTRADICTION"}}],
    )
    r = queue_demo.classify(g, {})
    assert r["state"] == "FLAGGED" and r["check"] == "value_grounding" and "4.5" in r["evidence"]


def test_a_judge_only_block_is_escalated_not_flagged():
    g = _grounded(
        "BLOCK", "BLOCK", {"grounded": 0, "cleared": 0, "judge_only": 1, "floor_backstopped": False},
        active=[{"code": "UNSUPPORTED_ASSERTION"}],
    )
    r = queue_demo.classify(g, {})
    assert r["state"] == "ESCALATED" and "UNSUPPORTED_ASSERTION" in r["reason"]


def test_cleared_requires_a_floor_pass_or_a_disproved_signal():
    g = _grounded(
        "PASS", "PASS", {"grounded": 0, "cleared": 0, "floor_passes": 1, "floor_backstopped": True},
        passes=[{"decl": _decl("value_grounding"), "result": _res(True, checked=3, present=["4", "312", "9:00"], missing=[])}],
    )
    assert queue_demo.classify(g, {})["state"] == "CLEARED"
    g2 = _grounded(
        "PASS", "BLOCK", {"grounded": 0, "cleared": 1, "floor_backstopped": True},
        suppressed=[{"finding": {"code": "UNSUPPORTED_ASSERTION"}, "contract": _decl("source_grounding"),
                     "verdict": SimpleNamespace(reason="fully grounded")}],
    )
    assert queue_demo.classify(g2, {})["state"] == "CLEARED"


def test_a_judge_only_pass_is_escalated_never_cleared():
    g = _grounded("PASS", "PASS", {"grounded": 0, "cleared": 0, "floor_backstopped": False})
    r = queue_demo.classify(g, {})
    assert r["state"] == "ESCALATED" and "judges alone" in r["reason"]


def test_a_prose_lead_is_escalated_with_the_value_named():
    g = _grounded(
        "PASS", "PASS", {"grounded": 0, "cleared": 0, "floor_backstopped": False},
        blocks=[{"decl": _decl("value_grounding"), "result": _res(None, missing=["84"], reason="lead"), "injected_finding": None}],
    )
    r = queue_demo.classify(g, {})
    assert r["state"] == "ESCALATED" and "84" in r["reason"]


# ── end to end: the committed queue replays at $0 ────────────────────────────────────────

def _run_json():
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith(("OPENAI", "AZURE_OPENAI", "ANTHROPIC", "LITHRIM_")))}
    env["LITHRIM_BENCH_PACK"] = "_core"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--json"], cwd=REPO_ROOT,
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout), proc.stdout


def test_queue_replays_five_cases_offline_with_the_invariant_held():
    out, raw = _run_json()
    assert out["n"] == 5 and len(out["cases"]) == 5
    assert sum(out["tally"].values()) == 5
    for r in out["cases"]:
        assert r["state"] in _STATES, r
        if r["state"] == "CLEARED":
            assert r["floor_backstopped"] is True and r["check"] and r["evidence"]
            assert r["verdict"] == "PASS"
        elif r["state"] == "FLAGGED":
            assert r["floor_backstopped"] is True and r["check"] and r["evidence"]
            assert r["verdict"] == "BLOCK"
        else:
            assert r["reason"]
        assert r["case_id"].startswith("ragtruth_")
        assert isinstance(r["human_flags"], list)
    # every state has evidence or a reason a person can act on
    assert all(r["evidence"] or r["reason"] for r in out["cases"])


def test_queue_is_byte_stable():
    _, a = _run_json()
    _, b = _run_json()
    assert a == b


def test_make_target_exists():
    out = subprocess.run(["make", "-n", "queue"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "scripts/queue_demo.py" in out.stdout
