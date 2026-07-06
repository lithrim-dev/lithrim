"""Admissibility gate for the clinverdict MTS-grounded by-construction corpus.

The shipped lint (``scripts/lint_golden_against_taxonomy.py``) checks only D1 (flags ∈
taxonomy) and D8 (Tier-1 ⇒ reject/rationalized-set). This test enforces the *by-construction*
invariants the lint does not: recipe completeness, post_value literally present in the note,
clean-negative consistency, ontology-flag membership (rejecting the two declared-but-not-running
Tier-1 codes), owner-map residency, lens gradeability, and split balance — modeled on
``tests/test_clinical_scribe_sample.py`` but bound to the ``clinverdict`` drop-in pack.

Structural tests read the pack JSON + corpus directly (no pack discovery / env needed). The
$0 grade test needs the pack discoverable (``LITHRIM_BENCH_PACK=clinverdict`` +
``LITHRIM_BENCH_PACKS_DIR=<repo>/packs-dropin``) and the [council] extra; it skips otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "clinverdict"
PACK_DIR = REPO_ROOT / "packs-dropin" / "clinverdict"
SNAPSHOT = PACK_DIR / "taxonomy_snapshot.json"
ONTOLOGY = PACK_DIR / "ontology.json"
CORPUS = REPO_ROOT / "examples/clinverdict/clinverdict_mts_v1.jsonl"

_VALID_PROJECTIONS = {"transcript", "artifact_text", "artifact_structured", "hl7_segment"}
_VALID_ARTIFACT_VERDICTS = {"BLOCK", "WARN", "PASS"}
_VALID_COMPLIANCE = {"approve", "needs_review", "reject"}
# By-construction verification differs by defect class:
#  * ADDITIVE/ALTERING — the injected text exists in the note → assert post_value ⊆ note.
#  * OMISSION/ERASURE — the omitted fact existed in the source → assert pre_value ⊆ transcript.
_ADDITIVE_FLAGS = {
    "FABRICATED_CLAIM", "UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION",
    "VALUE_MISMATCH", "HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY", "STYLE_VIOLATION",
}
_OMISSION_FLAGS = {
    "HISTORY_OMISSION", "MISSING_CONTEXT", "DISSENT_ERASURE", "INTENT_ERASURE", "MISSED_ESCALATION",
}
# The two Tier-1 codes whose only owner is declared-but-not-running — absent from the
# ontology, so the corpus must NEVER use them (CLAUDE.md invariant #4).
_EXCLUDED_CODES = {"OUT_OF_SCOPE_ACTION", "SOURCE_MISATTRIBUTION"}


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text())


def _ontology() -> dict:
    return json.loads(ONTOLOGY.read_text())


def _ontology_flags() -> set[str]:
    return {f["flag"] for f in _ontology()["flags"]}


def _tier_union(snap: dict) -> set[str]:
    t = snap["tiers"]
    return set(t["TIER_1_NEVER_EVENTS"]) | set(t["TIER_2_HIGH_RISK"]) | set(t["TIER_3_MEDIUM"])


def _production_lens_union(snap: dict) -> set[str]:
    pj = set(snap["production_judges"])
    out: set[str] = set()
    for role, codes in snap["lenses"].items():
        if role in pj:
            out |= set(codes)
    return out


def _production_owners_of(snap: dict, flag: str) -> set[str]:
    return set(snap.get("tier1_owners", {}).get(flag, [])) & set(snap["production_judges"])


def _corpus() -> list[dict]:
    if not CORPUS.exists():
        pytest.fail(f"corpus not generated yet: {CORPUS} (run the generation workflow)")
    rows = [json.loads(ln) for ln in CORPUS.read_text().splitlines() if ln.strip()]
    assert rows, f"corpus is empty: {CORPUS}"
    return rows


def _note_text(case: dict) -> str:
    """All gradeable note text across artifacts (decode FHIR DocumentReference, concat plaintext)."""
    chunks: list[str] = []
    for art in case.get("artifacts", []):
        content = art.get("content", "")
        if art.get("type") == "fhir_document_reference":
            try:
                doc = json.loads(content)
                for c in doc.get("content", []):
                    data = (c.get("attachment") or {}).get("data")
                    if isinstance(data, str):
                        chunks.append(data)
            except (json.JSONDecodeError, AttributeError, TypeError):
                chunks.append(content)  # fall back to raw
        else:
            chunks.append(content if isinstance(content, str) else json.dumps(content))
    return "\n".join(chunks)


# ── pack sanity (the contract the corpus is authored against) ────────────────


def test_pack_ontology_is_gradeable_and_excludes_unrunnable_codes():
    snap = _snapshot()
    union = _tier_union(snap)
    ont_flags = _ontology_flags()
    assert ont_flags <= union, "an ontology flag is not in any snapshot tier"
    # every excluded Tier-1 code is genuinely absent from the ontology
    assert ont_flags.isdisjoint(_EXCLUDED_CODES), "ontology exposes a declared-but-not-running code"
    # every ontology flag is raiseable by at least one PRODUCTION judge (gradeable)
    prod_lens = _production_lens_union(snap)
    assert ont_flags <= prod_lens, f"ungradeable ontology flags: {ont_flags - prod_lens}"


# ── corpus admissibility by construction ─────────────────────────────────────


def test_every_case_well_formed():
    ont_flags = _ontology_flags()
    for row in _corpus():
        cid = row["case_id"]
        assert row.get("pack") == PACK, f"{cid}: wrong pack {row.get('pack')!r}"
        assert isinstance(row.get("transcript"), str) and row["transcript"].strip(), f"{cid}: empty transcript"
        arts = row.get("artifacts") or []
        assert arts and isinstance(arts, list), f"{cid}: no artifacts"
        assert any(a.get("type") == "fhir_document_reference" for a in arts), f"{cid}: no FHIR DocumentReference artifact"
        for code in row.get("expected_safety_flags", []):
            assert code in ont_flags, f"{cid}: flag {code!r} not in the 12 ontology flags"
            assert code not in _EXCLUDED_CODES, f"{cid}: uses excluded code {code!r}"
        assert row.get("split") in {"calibration", "test"}, f"{cid}: bad split {row.get('split')!r}"
        assert row.get("expected_artifact_verdict") in _VALID_ARTIFACT_VERDICTS, f"{cid}: bad artifact verdict"


def test_clean_negatives_carry_no_defect():
    for row in _corpus():
        if not row.get("clean_negative"):
            continue
        cid = row["case_id"]
        assert row.get("expected_safety_flags") == [], f"{cid}: clean negative carries flags"
        assert (row.get("injection_recipes") or []) == [], f"{cid}: clean negative carries a recipe"
        assert row.get("expected_compliance_verdict") == "approve", f"{cid}: clean negative not 'approve'"
        assert row.get("expected_artifact_verdict") == "PASS", f"{cid}: clean negative not 'PASS'"


def _norm_ws(s: str) -> str:
    return " ".join(s.split()).lower()


def test_defect_cases_have_a_complete_recipe_grounded_by_construction():
    """Every defect carries a complete recipe AND the mutation is verifiable by construction:
    additive/altering defects inject text that appears verbatim in the note; omission/erasure
    defects omit a fact that appears verbatim in the transcript."""
    for row in _corpus():
        if row.get("clean_negative"):
            continue
        cid = row["case_id"]
        recipes = row.get("injection_recipes") or []
        assert recipes, f"{cid}: defect case lacks an injection_recipe (label justification)"
        note = _norm_ws(_note_text(row))
        transcript = _norm_ws(row.get("transcript", ""))
        recipe_flags = set()
        for r in recipes:
            for fld in ("defect_type", "safety_flag", "mutated_projection", "mutated_field_or_span", "pre_value", "post_value"):
                assert r.get(fld), f"{cid}: recipe missing/empty field {fld!r}"
            assert r["mutated_projection"] in _VALID_PROJECTIONS, f"{cid}: bad mutated_projection {r['mutated_projection']!r}"
            flag = r["safety_flag"]
            recipe_flags.add(flag)
            if flag in _ADDITIVE_FLAGS:
                assert _norm_ws(r["post_value"]) in note, (
                    f"{cid}: additive defect {flag} post_value not verbatim in note (post_value={r['post_value']!r})"
                )
            elif flag in _OMISSION_FLAGS:
                assert _norm_ws(r["pre_value"]) in transcript, (
                    f"{cid}: omission defect {flag} pre_value not verbatim in transcript (pre_value={r['pre_value']!r})"
                )
            else:
                pytest.fail(f"{cid}: flag {flag!r} not classified additive/omission")
        assert set(row["expected_safety_flags"]) <= recipe_flags, f"{cid}: a flag is not justified by a recipe"
        assert set(row["expected_safety_flags"]), f"{cid}: defect case has no expected flags"


def test_verdicts_follow_the_worst_of_tier_rule():
    snap = _snapshot()
    tier1 = set(snap["tiers"]["TIER_1_NEVER_EVENTS"])
    for row in _corpus():
        if row.get("clean_negative"):
            continue
        cid = row["case_id"]
        flags = set(row["expected_safety_flags"])
        verdict = row.get("expected_compliance_verdict")
        if flags & tier1:
            if isinstance(verdict, str):
                assert verdict == "reject", f"{cid}: Tier-1 flag but verdict={verdict!r} (D8)"
            elif isinstance(verdict, list):
                assert row.get("verdict_set_rationale"), f"{cid}: set-valued verdict without rationale (D8)"
            else:
                pytest.fail(f"{cid}: missing verdict")
            assert row.get("expected_artifact_verdict") == "BLOCK", f"{cid}: Tier-1 but artifact verdict != BLOCK"
        else:
            # Tier-2/Tier-3 only
            if isinstance(verdict, str):
                assert verdict in _VALID_COMPLIANCE, f"{cid}: bad verdict {verdict!r}"


def test_owner_map_only_tier1_keys_with_production_owners():
    snap = _snapshot()
    tier1 = set(snap["tiers"]["TIER_1_NEVER_EVENTS"])
    for row in _corpus():
        cid = row["case_id"]
        omap = row.get("expected_owner_map") or {}
        flags = set(row.get("expected_safety_flags", []))
        for flag, owners in omap.items():
            assert flag in flags, f"{cid}: owner_map key {flag!r} not in expected_safety_flags"
            assert flag in tier1, f"{cid}: owner_map key {flag!r} is not Tier-1"
            prod_owners = _production_owners_of(snap, flag)
            assert owners, f"{cid}: owner_map[{flag!r}] empty"
            assert set(owners) <= prod_owners, (
                f"{cid}: owner_map[{flag!r}]={owners} not ⊆ production owners {prod_owners}"
            )
        # every Tier-1 flag present must have an owner_map entry
        for flag in flags & tier1:
            assert flag in omap, f"{cid}: Tier-1 flag {flag!r} missing from owner_map"


def test_expected_flags_are_lens_gradeable():
    """Every expected flag is raiseable by some production judge (else it can never be scored)."""
    prod_lens = _production_lens_union(_snapshot())
    for row in _corpus():
        for code in row.get("expected_safety_flags", []):
            assert code in prod_lens, f"{row['case_id']}: flag {code!r} is in no production judge's lens"


# ── coverage: the corpus actually demonstrates the USPs ──────────────────────


def test_corpus_size_and_split_balance():
    rows = _corpus()
    assert 100 <= len(rows) <= 200, f"corpus size {len(rows)} outside the 100-200 target"
    splits = {"calibration": 0, "test": 0}
    for r in rows:
        splits[r["split"]] += 1
    assert splits["test"] >= 25, f"held-out split too small: {splits}"
    # positives must appear in BOTH splits (don't starve the held-out set)
    for sp in ("calibration", "test"):
        pos = [r for r in rows if r["split"] == sp and not r.get("clean_negative")]
        assert pos, f"no positives in split {sp!r}"


def test_corpus_covers_flags_strata_and_grounding_shape():
    rows = _corpus()
    flags = {f for r in rows for f in r.get("expected_safety_flags", [])}
    assert len(flags & _ontology_flags()) >= 10, f"only {len(flags)} of 12 flags exercised"
    assert any(r.get("clean_negative") for r in rows), "no clean negatives"
    assert any(r.get("multi_defect") for r in rows), "no multi-defect cases"
    # the SNOMED-floor (subsumption) shape: at least some clean negatives carry a record oracle
    assert any(
        r.get("clean_negative") and (r.get("patient_profile") or {}).get("conditions")
        for r in rows
    ), "no subsumption-bait clean negatives carry a patient_profile.conditions oracle"


# ── [council] extra: $0 offline grade through the authored council ────────────

_GRADE_SCRIPT = r"""
import json
from lithrim_bench.harness.pack import active_pack, pack_ontology_path
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case
from lithrim_bench.harness.pack import pack_production_judges
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
from lithrim_bench.runtime.council.judges_dspy import build_judge_lm

ROLES = list(pack_production_judges())
CASE_ID = __CASE_ID__
CASE_SRC = __CASE_SRC__
ROLE = __ROLE__
FLAG = __FLAG__
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "case did not load"

QUOTE = __QUOTE__

def _predictor(role):
    def _p(*, role_key_questions="", **_kw):
        if role == ROLE and MARKER in role_key_questions:
            return {"decision": "reject", "findings": [{"taxonomy_code": FLAG, "evidence_spans": [{"quote": QUOTE, "turn_ids": []}]}]}
        return {"decision": "approve", "findings": []}
    return _p

stage = build_authored_semantic_stage(
    ontology=ont,
    assignments={ROLE: [FLAG]},
    predictors={r: _predictor(r) for r in ROLES},
)
r = grade_inprocess(case, semantic_stage=stage)
comp = composite(ground(r, case, ontology=ont))
print("__JSON__" + json.dumps({"active_pack": active_pack(), "verdict": comp["verdict"]}))
"""


def test_authored_council_grades_a_clinverdict_case_at_zero_cost():
    """A single positive grades through the authored council to reject at $0 (injected predictors).
    Proves the corpus is genuinely runnable against the pack, not merely well-formed."""
    pytest.importorskip("openai")
    pytest.importorskip("dspy")
    rows = _corpus()
    # pick a Tier-1 single-defect case owned by faithfulness_judge (SOURCE_CONTRADICTION) if present
    snap = _snapshot()
    tier1 = set(snap["tiers"]["TIER_1_NEVER_EVENTS"])
    target = next(
        (r for r in rows if not r.get("clean_negative") and len(r["expected_safety_flags"]) == 1
         and r["expected_safety_flags"][0] in tier1 and r.get("expected_owner_map")),
        None,
    )
    if target is None:
        pytest.skip("no single-flag Tier-1 case with an owner to grade")
    flag = target["expected_safety_flags"][0]
    role = next(iter(target["expected_owner_map"][flag]))
    quote = next((r["post_value"] for r in target["injection_recipes"] if r["safety_flag"] == flag), flag)
    script = (
        _GRADE_SCRIPT
        .replace("__CASE_ID__", json.dumps(target["case_id"]))
        .replace("__CASE_SRC__", json.dumps(str(CORPUS)))
        .replace("__ROLE__", json.dumps(role))
        .replace("__FLAG__", json.dumps(flag))
        .replace("__QUOTE__", json.dumps(quote))
    )
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = PACK
    env["LITHRIM_BENCH_PACKS_DIR"] = str(REPO_ROOT / "packs-dropin")
    env.setdefault("OPENAI_API_KEY", "test-offline-key")
    env.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    proc = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"grade subprocess failed:\n{proc.stdout}\n{proc.stderr}"
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    out = json.loads(line[len("__JSON__"):])
    assert out["active_pack"] == PACK
    assert out["verdict"] == "reject"
