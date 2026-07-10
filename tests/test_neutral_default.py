"""CE-PACK-NEUTRAL-DEFAULT — the healthcare-ABSENT proof (the "ship without healthcare" gate).

Proves the OSS Core boots + grades STANDALONE on its neutral ``_core`` DEFAULT pack with
``LITHRIM_BENCH_PACK`` UNSET (the SHIPPED default) — reading ZERO ``packs/healthcare/`` files,
not even the canonical-roster metadata. This is the strict resolution of S-BS-130 (which left
``council_roster()`` reading healthcare's ``pack.json`` + ``taxonomy_snapshot.json`` for canonical
validation under ANY active pack, because ``DEFAULT_PACK='healthcare'``) and retires the S-BS-125
tripwire (``council_roster()`` reading a non-active pack).

The grade runs the AUTHORED path ($0, injected mock predictors — the ``test_standalone_ce`` /
``test_uap3_grade`` pattern; no provider, no spend) to a composite verdict. An ``sys.addaudithook``
records every file opened during the whole boot+grade and asserts NONE is under ``packs/healthcare/``.

Why a subprocess: pack resolution is frozen at module import (``judge_assignment._ROLE_PROMPTS_DIR``,
``judge_metric.LENS_BY_ROLE``) and ``tests/conftest.py`` pins ``LITHRIM_BENCH_PACK=healthcare`` for
the in-process suite — so the shipped default is reachable ONLY in a fresh interpreter with the var
explicitly UNSET. Honest-Δ: if any leg fails it pinpoints a residual healthcare coupling in the
shipped default — that is the point of the test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# build_authored_semantic_stage → build_trio (dspy) + ComplianceCouncil (openai); gate the file on
# the [council] extra (run in debuglithrim), matching test_standalone_ce.
pytest.importorskip("openai")
pytest.importorskip("dspy")

REPO_ROOT = Path(__file__).resolve().parents[1]

_NEUTRAL_DEFAULT_SCRIPT = r"""
import json
import sys

# Record every file opened during boot + grade, to prove ZERO healthcare reads under the
# shipped (env-unset) default — the strict CE-PACK-NEUTRAL-DEFAULT / S-BS-130 gate.
_opened = []


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        p = args[0].decode() if isinstance(args[0], bytes) else args[0]
        _opened.append(p)


sys.addaudithook(_audit)

from lithrim_bench.harness.pack import active_pack, council_roster, pack_ontology_path, pack_prompts_path
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_judge_lm

CASE_ID = "_core_fabricated_claim"
CASE_SRC = "tests/fixtures/standalone/case._core_fabricated_claim.jsonl"
ROLE = "policy_judge"
FLAG = "FABRICATED_CLAIM"
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

roster = sorted(council_roster())
ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "case did not load"


def _predictor(role):
    # $0/offline: BLOCK with FLAG iff this judge carries the authored refinement (same
    # marker-keyed predictor as test_standalone_ce) — so the FLIP is the authoring.
    def _p(*, role_key_questions="", **_kw):
        if role == ROLE and MARKER in role_key_questions:
            return {
                "decision": "reject",
                "findings": [{
                    "taxonomy_code": FLAG,
                    "evidence_spans": [{"quote": "unlimited storage for life", "turn_ids": []}],
                }],
            }
        return {"decision": "approve", "findings": []}

    return _p


stage = build_authored_semantic_stage(
    ontology=ont,
    assignments={ROLE: [FLAG]},
    predictors={r: _predictor(r) for r in V2_ROLES},
)
r = grade_inprocess(case, semantic_stage=stage)
comp = composite(ground(r, case, ontology=ont))

votes = {
    v["judge_role"]: {"vote": v["vote"], "findings": list(v.get("findings") or [])}
    for v in r["semantic"]["judge_votes"]
}


def _norm(p):
    return p.replace("\\", "/")


healthcare_reads = sorted({_norm(p) for p in _opened if "packs/healthcare" in _norm(p)})

print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "roster": roster,
    "prompts_dir": _norm(str(pack_prompts_path())),
    "ontology_path": _norm(str(pack_ontology_path())),
    "n_verification_contracts": len(ont.contracts),
    "verdict": comp["verdict"],
    "votes": votes,
    "healthcare_reads": healthcare_reads,
    "build_judge_lm_callable": callable(build_judge_lm),
}))
"""


@pytest.fixture(scope="module")
def neutral_out() -> dict:
    """The $0 authored-path E2E under the SHIPPED default (env unset), run once (subprocess)."""
    env = dict(os.environ)
    # The shipped default is env-UNSET — the conftest pin set this in the pytest process, so the
    # child would inherit healthcare; pop it to exercise the genuine DEFAULT_PACK=_core path.
    env.pop("LITHRIM_BENCH_PACK", None)
    proc = subprocess.run(
        [sys.executable, "-c", _NEUTRAL_DEFAULT_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"neutral-default subprocess failed:\n--- STDOUT ---\n{proc.stdout}\n"
        f"--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_shipped_default_is_the_neutral_core_pack(neutral_out):
    """A1: with ``LITHRIM_BENCH_PACK`` unset, the active pack is the neutral ``_core`` default and
    its domain content resolves entirely from ``packs/_core/``."""
    assert neutral_out["active_pack"] == "_core"
    assert "/packs/_core/" in neutral_out["prompts_dir"]
    assert "/packs/_core/" in neutral_out["ontology_path"]


def test_council_roster_is_canonical_under_the_neutral_default(neutral_out):
    """A1/A3: ``council_roster()`` is identity-stable under the neutral default — it still yields the
    full canonical role set (the deployable trio + the owner-only behavior/source_message roles), so
    every real pack still subset-validates against it. The roster came from ``packs/_core/`` metadata,
    NOT a Pro pack."""
    assert neutral_out["roster"] == [
        "behavior_judge",
        "faithfulness_judge",
        "policy_judge",
        "risk_judge",
        "source_message_judge",
    ]


def test_generic_grade_reaches_a_verdict(neutral_out):
    """A1: the generic case grades through the authored path to a verdict. Assigning FABRICATED_CLAIM
    to its owner (policy_judge) → that judge BLOCKs → Tier-1 one-strike → composite reject; the
    unassigned roles do not block, so the move is the AUTHORING."""
    assert neutral_out["verdict"] == "reject"
    policy = neutral_out["votes"]["policy_judge"]
    assert policy["vote"] == "BLOCK"
    assert "FABRICATED_CLAIM" in policy["findings"]
    assert neutral_out["votes"]["risk_judge"]["vote"] != "BLOCK"
    assert neutral_out["votes"]["faithfulness_judge"]["vote"] != "BLOCK"
    # the generic ontology declares no verification_contracts → no external grounding call.
    assert neutral_out["n_verification_contracts"] == 0


def test_zero_healthcare_reads_under_the_shipped_default(neutral_out):
    """A1 (the headline gate): the ENTIRE boot+grade under the shipped default reads ZERO
    ``packs/healthcare/`` files — not even the canonical-roster metadata (``pack.json`` /
    ``taxonomy_snapshot.json``) that S-BS-130 left leaking under the healthcare default. The core
    ships without healthcare on disk."""
    assert neutral_out["healthcare_reads"] == [], (
        f"the shipped neutral default read healthcare files (S-BS-130 not fully closed): "
        f"{neutral_out['healthcare_reads']}"
    )


def test_provider_seam_present_and_bypassed_at_zero_cost(neutral_out):
    """A1: the BYO provider seam (``build_judge_lm``) exists; the $0 CI path binds injected
    predictors instead of a live LM, so no provider is constructed and no spend occurs."""
    assert neutral_out["build_judge_lm_callable"] is True
