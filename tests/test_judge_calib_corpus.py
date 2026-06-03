"""WS-6c-DSPy-3a: the judge-calibration corpus is admissible by construction.

Hermetic — reads the committed examples/judge_calib_v1.jsonl (no Synthea CSV).
Asserts the CLAUDE.md core invariant per case: every positive carries an
injection_recipes block (the recipe IS the label), every code is in-snapshot,
every Tier-1 code is owner-resident in a production judge, clean negatives are
[] + clean_negative, and the policy gap (FABRICATED_CONSENT + PHI) is covered.
This mirrors scripts/lint_golden_against_taxonomy.py at the unit-test layer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lithrim_bench.taxonomy import load_taxonomy

_CORPUS = Path(__file__).resolve().parent.parent / "examples" / "judge_calib_v1.jsonl"
_RECIPE_FIELDS = {
    "defect_type",
    "safety_flag",
    "mutated_projection",
    "mutated_field_or_span",
    "pre_value",
    "post_value",
}


@pytest.fixture(scope="module")
def rows():
    return [json.loads(line) for line in _CORPUS.read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


def test_corpus_nonempty(rows):
    assert len(rows) >= 40


def test_every_code_in_snapshot(rows, taxonomy):
    for row in rows:
        for code in row["expected_safety_flags"]:
            assert taxonomy.is_known(code), f"{row['case_id']}: {code} not in snapshot"


def test_positives_carry_a_recipe_label(rows):
    for row in rows:
        if row["clean_negative"]:
            continue
        recipes = row["injection_recipes"]
        assert recipes, f"{row['case_id']}: positive with no injection_recipes"
        raised = {r["safety_flag"] for r in recipes}
        assert raised == set(row["expected_safety_flags"])
        for r in recipes:
            assert set(r) >= _RECIPE_FIELDS, f"{row['case_id']}: recipe missing fields"


def test_clean_negatives_are_empty(rows):
    cleans = [r for r in rows if r["clean_negative"]]
    assert cleans, "corpus has no clean negatives to measure FP"
    for row in cleans:
        assert row["expected_safety_flags"] == []
        assert row["injection_recipes"] == []


def test_tier1_codes_are_owner_resident(rows, taxonomy):
    for row in rows:
        for code in row["expected_safety_flags"]:
            if code in taxonomy.tier1_owners:
                owners = taxonomy.production_owners_of(code)
                assert owners, f"{row['case_id']}: Tier-1 {code} has no production owner"
                assert row["expected_owner_map"][code] == sorted(owners)


def test_policy_gap_is_covered(rows):
    """The whole point: policy had ZERO positives before this cycle."""
    codes = {c for row in rows for c in row["expected_safety_flags"]}
    assert "FABRICATED_CONSENT" in codes
    assert "PHI_DISCLOSURE_PRE_VERIFICATION" in codes


def test_has_cross_owner_multi_defect(rows, taxonomy):
    """At least one multi-defect case spans two different Tier-1 owners (the
    co-raise lens fixture)."""
    for row in rows:
        if not row["multi_defect"]:
            continue
        owners = {
            owner
            for code in row["expected_safety_flags"]
            for owner in taxonomy.production_owners_of(code)
        }
        if len(owners) >= 2:
            return
    pytest.fail("no cross-owner multi-defect case found")
