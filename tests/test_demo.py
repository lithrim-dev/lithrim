"""RELEASE-4 — the shippable bar: `make demo` runs the flagship loop $0 on a clean clone.

A stranger does ``git clone`` → ``make demo`` and sees the flagship loop at $0 (no keys,
no network, no external pack): the council votes, the deterministic floor flips the verdict
PASS→BLOCK, and the audit surfaces the findings. These tests are the acceptance gate for that:

  * A1  — the demo replays the flagship loop with ZERO config (clean-clone simulation).
  * A3a — the demo's CASE + BASELINE inputs are git-tracked (so a fresh clone has them).
  * A3b — secrets (.env/.live_env/.connector_env) are gitignored + untracked; .env.example tracked.
  * A2  — README.md is the honest, current product README (no personal paths; the right anchors).

A1 runs the demo's underlying replay in a SUBPROCESS with a hermetic, blank environment so it
genuinely simulates a clean clone: no ``.env``, no ``LITHRIM_BENCH_PACKS_DIR`` /
``LITHRIM_BENCH_PACK`` (so the pack stays on the neutral ``_core`` default — the suite's
``conftest.py`` pins ``healthcare``, which a real clone never has), and ``OPENAI_API_KEY=""``
(proving no LLM call). It asserts the replay path (``$0``), never a paid grade.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# The demo replay reads a captured baseline and runs ground()/composite() (no LLM). But the
# in-process imports pull in the council (openai/dspy); gate the file on them so it runs in the
# debuglithrim env like the rest of the grade-touching suite.
pytest.importorskip("openai")

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_CONFIG = REPO_ROOT / "data/config/agents/ws0_default.json"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def _is_tracked(rel: str) -> bool:
    return (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _is_ignored(rel: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", rel], cwd=REPO_ROOT, capture_output=True, text=True
        ).returncode
        == 0
    )


# ── A1 — the flagship loop, $0, zero config ──────────────────────────────────

# The replay body run in a hermetic subprocess: load the demo agent, replay its committed
# baseline, ground + composite. NO --live / --in-process — the $0 replay path only.
_DEMO_REPLAY_SCRIPT = r"""
import json, sys
from pathlib import Path
from lithrim_bench.harness.config import agent_from_dict
from lithrim_bench.harness.grade import grade_replay
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.picklist import load_case

REPO = Path(sys.argv[1])
agent = agent_from_dict(json.loads((REPO / "data/config/agents/ws0_default.json").read_text()))
assert agent.dataset.baseline, "demo agent has no committed baseline (clean clone would fail)"

ont = load_ontology(agent.ontology_abspath())
case = load_case(agent.dataset.case_id, source=agent.source_abspath())
assert case is not None, "demo case did not load"

result = grade_replay(case, agent.baseline_abspath())
g = ground(result, case, ontology=ont)
comp = composite(g)
votes = {
    v["judge_role"]: v["vote"] for v in result["semantic"]["judge_votes"]
}
print("__JSON__" + json.dumps({
    "verdict": comp["verdict"],
    "stage_verdict": comp["stage_verdict"],
    "original_verdict": g.original_verdict,
    "grounded_verdict": str(g.verdict),
    "active_findings": comp["active_findings"],
    "votes": votes,
}))
"""


@pytest.fixture(scope="module")
def demo_replay_clean_clone():
    """Run the demo's replay body in a hermetic subprocess that simulates a clean clone."""
    env = {
        k: v
        for k, v in os.environ.items()
        # strip every pack / provider env a fresh clone never has
        if k
        not in {
            "LITHRIM_BENCH_PACK",
            "LITHRIM_BENCH_PACKS_DIR",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "LITHRIM_LLM_PROVIDER",
        }
    }
    env["OPENAI_API_KEY"] = ""  # prove ZERO LLM call — the replay needs no key
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    proc = subprocess.run(
        [sys.executable, "-c", _DEMO_REPLAY_SCRIPT, str(REPO_ROOT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"demo replay failed on a clean-clone sim:\n--- STDOUT ---\n{proc.stdout}\n"
        f"--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_make_demo_replays_the_flagship_loop_zero_config(demo_replay_clean_clone):
    """A1: the demo replays the flagship loop at $0 with zero config (no .env, no pack, no key).

    The composite rejects; the deterministic floor flips PASS→BLOCK; the three council judges
    voted; the audit findings carry the fabricated-claim signals. ZERO network / LLM."""
    out = demo_replay_clean_clone
    assert out["verdict"] == "reject"
    # the floor flip — the headline of the loop
    assert out["original_verdict"] == "PASS"
    assert out["grounded_verdict"] == "BLOCK"
    assert out["stage_verdict"] == "BLOCK"
    # three judge votes present (the council)
    assert set(out["votes"]) == {"risk_judge", "policy_judge", "faithfulness_judge"}
    # the by-construction findings on the fabricated-claim case
    assert "UNSUPPORTED_ASSERTION" in out["active_findings"]
    assert "SOURCE_CONTRADICTION" in out["active_findings"]


# ── A3a — the demo inputs are tracked for a clean clone ───────────────────────


def test_demo_inputs_are_tracked_for_a_clean_clone():
    """A3a: the CASE + BASELINE files the demo agent config points at are git-tracked, so a
    fresh ``git clone`` → ``make demo`` has everything it needs (no gitignored ``out/`` dep)."""
    cfg = json.loads(AGENT_CONFIG.read_text())
    ds = cfg["dataset"]
    case_rel = ds["source"]
    baseline_rel = ds["baseline"]
    assert baseline_rel, "demo agent dataset.baseline is empty — a clean clone has no baseline"
    assert _is_tracked(case_rel), f"demo case is not git-tracked: {case_rel}"
    assert _is_tracked(baseline_rel), f"demo baseline is not git-tracked: {baseline_rel}"
    # and the baseline must NOT live under a gitignored dir (out/)
    assert not _is_ignored(baseline_rel), f"demo baseline is gitignored: {baseline_rel}"


# ── A3b — secrets are gitignored, the template is tracked ─────────────────────


@pytest.mark.parametrize("secret", [".env", ".live_env", ".connector_env"])
def test_secrets_are_gitignored(secret):
    """A3b: the live-credential files are gitignored AND untracked — a stranger's keys stay local."""
    assert _is_ignored(secret), f"{secret} is not gitignored — secrets could be committed"
    assert not _is_tracked(secret), f"{secret} is git-tracked — a secret leaked into the repo"


def test_env_example_is_tracked():
    """A3b: the committed template IS tracked, so a clone has a documented .env to copy."""
    assert _is_tracked(".env.example"), ".env.example must be tracked (the BYOK template)"


# ── A2 — the README is the honest, current product README ─────────────────────


def test_readme_is_clean_and_current():
    """A2: README.md is the honest product README — no hardcoded personal path, the right
    anchors (the demo, the BYOK provider env, the honesty boundary phrase)."""
    readme = (REPO_ROOT / "README.md").read_text()
    assert "/Users/" not in readme, "README.md still contains a hardcoded /Users/ personal path"
    assert "make demo" in readme, "README.md must document the make demo quickstart"
    assert "LITHRIM_LLM_PROVIDER" in readme, "README.md must document the BYOK provider env"
    # the honesty boundary — the part most tools omit; it IS the product
    assert "does NOT" in readme or "does not" in readme, (
        "README.md must preserve the honest 'where the floor does / does NOT generalize' boundary"
    )
