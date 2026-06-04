"""UAP-4 corpus-widening guard (driver "go" #1 + the CLAUDE.md "labels true by
construction" invariant). $0, hermetic.

The S-BS-49 lead lever widened ``examples/judge_calib_v1.jsonl`` (more positives per
code). Because the generator emits sorted by case_id, the regenerated file INTERLEAVES
the new rows rather than literally appending — so a programmatic check (not an eyeball)
protects the invariant under the line-order shift.

The pre-widening v1 (47 rows) is frozen as a committed fixture
(``tests/fixtures/uap4/judge_calib_v1_pre_widen.jsonl``) so this guard stays DURABLE
and re-runnable (a git-show-HEAD diff degenerates once the widening commit lands). We
assert, keying both files by case_id:

  1. STRICT SUPERSET — every pre-widening case_id still exists; nothing removed.
  2. EXISTING ROWS BYTE-IDENTICAL — every pre-existing row is unchanged (canonical-JSON
     compare; no relabel, no content edit).
  3. ADDITIONS ARE POSITIVES PINNED TO CALIBRATION — every new case_id is a positive on
     the calibration/trainset split.
  4. HELD-OUT FROZEN — the `test`-split case_id set equals the pre-widening one (both
     optimize arms measure on the IDENTICAL test set; a lift can't be a test-set artifact).
  5. ADMISSIBLE — every expected flag resolves to the taxonomy snapshot.

Plus a determinism guard: the committed corpus is byte-identical to a fresh generator
run (no hand-edit / no non-deterministic drift).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "examples" / "judge_calib_v1.jsonl"
PRE_WIDEN = REPO_ROOT / "tests" / "fixtures" / "uap4" / "judge_calib_v1_pre_widen.jsonl"
SNAPSHOT = REPO_ROOT / "taxonomy" / "taxonomy_snapshot.json"
COHORT = REPO_ROOT / "data" / "synthea_sample_data_csv_latest"


def _canon(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True)


def _rows(path: Path) -> dict[str, dict]:
    return {
        json.loads(line)["case_id"]: json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def test_widened_corpus_is_a_strict_superset_of_pre_widen():
    old, new = _rows(PRE_WIDEN), _rows(CORPUS)
    removed = set(old) - set(new)
    assert removed == set(), f"rows removed (not additive): {sorted(removed)}"
    assert set(old) <= set(new)
    assert len(new) > len(old), "widening should add positives"


def test_pre_existing_rows_are_byte_identical():
    old, new = _rows(PRE_WIDEN), _rows(CORPUS)
    changed = [cid for cid in old if _canon(old[cid]) != _canon(new[cid])]
    assert changed == [], f"existing rows changed content/label (relabel forbidden): {changed}"


def test_added_rows_are_positives_pinned_to_calibration():
    old, new = _rows(PRE_WIDEN), _rows(CORPUS)
    added = set(new) - set(old)
    assert added, "expected widening additions"
    for cid in sorted(added):
        row = new[cid]
        assert row["split"] == "calibration", f"new row {cid} leaked into the held-out split"
        assert row.get("expected_safety_flags"), f"new row {cid} is not a positive"


def test_held_out_test_split_is_frozen():
    old, new = _rows(PRE_WIDEN), _rows(CORPUS)
    old_test = {cid for cid, r in old.items() if r["split"] == "test"}
    new_test = {cid for cid, r in new.items() if r["split"] == "test"}
    assert old_test == new_test, "the held-out `test` split must be frozen (driver go #2)"


def test_every_expected_flag_resolves_to_the_snapshot():
    tiers = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["tiers"]
    known = {code for codes in tiers.values() for code in codes}
    for cid, row in _rows(CORPUS).items():
        for code in row.get("expected_safety_flags") or []:
            assert code in known, f"{cid}: {code} not in the taxonomy snapshot"


def test_committed_corpus_matches_a_fresh_generator_run(tmp_path):
    """Determinism / no-hand-edit: regenerate and assert byte-identical to committed."""
    if not COHORT.exists():
        pytest.skip("Synthea cohort CSVs absent (offline-fixture env)")
    out = tmp_path / "regen.jsonl"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_judge_calib.py"),
         "--out", str(out), "--cohort", str(COHORT)],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )
    assert out.read_bytes() == CORPUS.read_bytes(), "committed corpus != deterministic regen"
