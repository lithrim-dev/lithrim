"""QUEUE-DEMO-1 — ``make queue``: the reviewer works a five-case queue at $0.

The product invariant, as a test (the state mapping itself is pinned in
``tests/test_review_state.py`` since REVIEW-STATE-1 moved it into the engine): a case is CLEARED only when the deterministic layer
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

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/queue_demo.py"
_STATES = {"CLEARED", "FLAGGED", "ESCALATED"}


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
