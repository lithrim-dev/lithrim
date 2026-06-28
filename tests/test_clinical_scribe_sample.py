"""B7 / PACK-DIST-1 amendment — the synthetic clinical SAMPLE pack (``packs/clinical_scribe/``).

A small, SYNTHETIC, by-construction clinical teaser shipped in CE (the ambient-scribe note-review
domain) — NOT the curated Pro ``healthcare`` pack. Two layers of proof:

  * **Bare-CE (no extras):** the pack is internally consistent and the corpus is admissible
    (every ``expected_safety_flags`` code is in the snapshot; every case is a clean negative or
    carries an ``injection_recipe`` label justification). These run with base deps only.
  * **[council] extra:** the authored council grades a clinical case end-to-end to a verdict at
    $0 via injected predictors (the ``test_standalone_ce`` pattern) — proving the clinical pack
    is genuinely runnable, not just well-formed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "clinical_scribe"
SNAPSHOT = REPO_ROOT / "packs/clinical_scribe/taxonomy_snapshot.json"
ONTOLOGY = REPO_ROOT / "packs/clinical_scribe/ontology.json"
CORPUS = REPO_ROOT / "examples/clinical_scribe/clinical_scribe_v1.jsonl"


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text())


def _known_codes(snap: dict) -> set[str]:
    t = snap["tiers"]
    return set(t["TIER_1_NEVER_EVENTS"]) | set(t["TIER_2_HIGH_RISK"]) | set(t["TIER_3_MEDIUM"])


def _corpus() -> list[dict]:
    return [json.loads(ln) for ln in CORPUS.read_text().splitlines() if ln.strip()]


# ── bare-CE: well-formed + admissible (no extras) ────────────────────────────


def test_pack_snapshot_is_internally_consistent():
    """Every Tier-1 code has an owning role; every lens code is in a tier; owners + lens roles are
    production judges — the same contract the frozen council reads at runtime."""
    snap = _snapshot()
    union = _known_codes(snap)
    pj = set(snap["production_judges"])
    owners = snap["tier1_owners"]
    assert set(snap["tiers"]["TIER_1_NEVER_EVENTS"]) <= set(owners), "a Tier-1 code has no owner"
    for code, roles in owners.items():
        assert roles and all(r in pj for r in roles), (code, "owner not a production judge")
    for role, codes in snap["lenses"].items():
        assert role in pj, (role, "lens role not a production judge")
        assert set(codes) <= union, (role, "lens code not in any tier")


def test_pack_questions_cover_every_production_role():
    """The ontology poses at least one refinement question for each production judge."""
    ont = json.loads(ONTOLOGY.read_text())
    roles_with_questions = {q["role"] for q in ont["questions"]}
    assert set(_snapshot()["production_judges"]) <= roles_with_questions


def test_corpus_is_admissible_by_construction():
    """Every case's flags are known taxonomy codes, and every case is either a clean negative
    (no defect, no flags) or carries an ``injection_recipe`` as its label justification."""
    known = _known_codes(_snapshot())
    rows = _corpus()
    assert rows, "the clinical_scribe corpus is empty"
    for row in rows:
        cid = row["case_id"]
        for code in row.get("expected_safety_flags", []):
            assert code in known, f"{cid}: flag {code!r} not in the snapshot taxonomy"
        if row.get("clean_negative"):
            assert row["expected_safety_flags"] == [], f"{cid}: clean negative carries flags"
            assert row.get("injection_recipes") == [], f"{cid}: clean negative carries a recipe"
        else:
            recipes = row.get("injection_recipes") or []
            assert recipes, f"{cid}: defect case lacks an injection_recipe (label justification)"
            recipe_flags = {r["safety_flag"] for r in recipes}
            assert set(row["expected_safety_flags"]) <= recipe_flags, (
                f"{cid}: expected flags not all justified by a recipe"
            )


def test_corpus_covers_the_headline_failure_modes():
    """The sample demonstrates the named clinical failure modes + at least one clean negative."""
    flags = {f for row in _corpus() for f in row.get("expected_safety_flags", [])}
    assert {"MISSING_ALLERGY", "WRONG_DOSAGE", "FABRICATED_HISTORY"} <= flags
    assert any(row.get("clean_negative") for row in _corpus()), "no clean negative in the sample"


# ── [council] extra: the authored council grades a clinical case at $0 ────────

_GRADE_SCRIPT = r"""
import json
from lithrim_bench.harness.pack import active_pack, pack_ontology_path
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_judge_lm

CASE_ID = "clinical_scribe_01_missing_allergy"
CASE_SRC = "tests/fixtures/standalone/case.clinical_scribe_missing_allergy.jsonl"
ROLE = "risk_judge"
FLAG = "MISSING_ALLERGY"
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "case did not load"


def _predictor(role):
    def _p(*, role_key_questions="", **_kw):
        if role == ROLE and MARKER in role_key_questions:
            return {
                "decision": "reject",
                "findings": [{
                    "taxonomy_code": FLAG,
                    "evidence_spans": [{"quote": "Allergies: None documented", "turn_ids": []}],
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
print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "n_verification_contracts": len(ont.contracts),
    "verdict": comp["verdict"],
    "votes": votes,
    "build_judge_lm_callable": callable(build_judge_lm),
}))
"""


def _run_grade() -> dict:
    import os

    pytest.importorskip("openai")
    pytest.importorskip("dspy")
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = PACK
    env.setdefault("OPENAI_API_KEY", "test-offline-key")
    env.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    proc = subprocess.run(
        [sys.executable, "-c", _GRADE_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"grade subprocess failed:\n{proc.stdout}\n{proc.stderr}"
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_authored_council_grades_a_clinical_case_at_zero_cost():
    """The clinical sample grades through the authored council to a verdict at $0. Assigning
    MISSING_ALLERGY to its owner (risk_judge) → that judge BLOCKs → Tier-1 one-strike → composite
    reject; the unassigned roles do not block, so the move is the AUTHORING. No :8002 (the pack
    declares no verification_contracts), no provider constructed (injected predictors)."""
    out = _run_grade()
    assert out["active_pack"] == PACK
    assert out["n_verification_contracts"] == 0
    assert out["verdict"] == "reject"
    risk = out["votes"]["risk_judge"]
    assert risk["vote"] == "BLOCK"
    assert "MISSING_ALLERGY" in risk["findings"]
    assert out["votes"]["policy_judge"]["vote"] != "BLOCK"
    assert out["votes"]["faithfulness_judge"]["vote"] != "BLOCK"
    assert out["build_judge_lm_callable"] is True
