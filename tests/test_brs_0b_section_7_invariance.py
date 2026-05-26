"""Snapshot test locking pre-BRS-0b §7 numerical outputs against future drift.

# Regenerate snapshot ONLY when section 7 numbers intentionally change
# (e.g., BRS-0a.5 re-run, a new N=10 sweep, or a deliberate analysis.py
# semantic change). Otherwise a snapshot diff is a regression signal,
# not a maintenance task.

# Usage to regenerate the fixture (intentional update only):
#   python3 -c "
#   import json, sys; sys.path.insert(0, '.')
#   from pathlib import Path
#   from lithrim_bench.analysis import analyze_pack, analyze_per_case, read_runs
#   snap = {}
#   for p in ['scribe_v1','scheduling_v1','coding_v1','triage_v1']:
#       rows = read_runs(Path(f'out/{p}.n10.ndjson'))
#       pack_rows = [json.loads(L) for L in Path(f'out/{p}.n10.jsonl').read_text().splitlines() if L.strip()]
#       keep = {r['case_id'] for r in pack_rows if r.get('split')=='test'}
#       rows = [r for r in rows if r['case_id'] in keep]
#       pack_rows = [r for r in pack_rows if r['case_id'] in keep]
#       snap[p] = analyze_pack(analyze_per_case(rows), pack_rows=pack_rows)
#   Path('tests/fixtures/brs_0b_section7_snapshot.json').write_text(json.dumps(snap, indent=2, sort_keys=True)+'\\n')
#   "

The snapshot was generated against the N=10 test-split NDJSON outputs in
`out/<pack>.n10.ndjson` + `out/<pack>.n10.jsonl` at commit 85901d8
(post-BRS-0a). It captures the §7.1 paper-anchor pack-level metrics
(`mean_verdict_match_rate`, `verdict_match_rate_ci95`, `instability_rate`,
`false_block_rate`, `mean_decision_layer_kappa`, `mean_structural_match_rate`,
`structural_cases`, `cases`, `n_per_case`) for the four FHIR packs.

Per BRS-0a §3: 2,009/2,009 FHIR rows in this sweep have
`structural_verdict="PASS"`; the BRS-0b
`_STAGE_STATUS_NORMALIZE` change therefore must not perturb these
numbers (no row has `not_applicable` to be re-normalized differently).
This test is the load-bearing regression guard for that invariance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lithrim_bench.analysis import analyze_pack, analyze_per_case, read_runs

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "brs_0b_section7_snapshot.json"
_OUT_DIR = _REPO_ROOT / "out"
_PACKS = ("scribe_v1", "scheduling_v1", "coding_v1", "triage_v1")


def _ndjson_present() -> bool:
    return all(
        (_OUT_DIR / f"{p}.n10.ndjson").exists() and (_OUT_DIR / f"{p}.n10.jsonl").exists()
        for p in _PACKS
    )


@pytest.mark.skipif(
    not _ndjson_present(),
    reason=(
        "Skipping §7 invariance check: N=10 NDJSON outputs not present in out/. "
        "Run the BRS sweep locally to enable this regression guard."
    ),
)
def test_section_7_pack_summary_invariance_against_brs_0b_baseline():
    """Re-deriving §7.1 pack_summary against the existing N=10 NDJSON must
    produce numbers byte-identical to the committed BRS-0b baseline snapshot.

    Failure means either:
      (a) `lithrim_bench/analysis.py` or `_STAGE_STATUS_NORMALIZE` changed in
          a way that perturbs §7 numbers — surface to monitor before commit;
      (b) the NDJSON was regenerated and the baseline is intentionally stale
          — regenerate the fixture per the regeneration command in this
          file's docstring, name the change in the commit body.
    """
    assert _FIXTURE_PATH.exists(), (
        f"baseline fixture missing at {_FIXTURE_PATH}; "
        "regenerate per docstring before relying on this test"
    )
    expected = json.loads(_FIXTURE_PATH.read_text())

    actual = {}
    for pack in _PACKS:
        runs_path = _OUT_DIR / f"{pack}.n10.ndjson"
        pack_path = _OUT_DIR / f"{pack}.n10.jsonl"
        rows = read_runs(runs_path)
        pack_rows = [
            json.loads(line) for line in pack_path.read_text().splitlines() if line.strip()
        ]
        keep = {r["case_id"] for r in pack_rows if r.get("split") == "test"}
        rows = [r for r in rows if r["case_id"] in keep]
        pack_rows = [r for r in pack_rows if r["case_id"] in keep]
        per_case = analyze_per_case(rows)
        actual[pack] = analyze_pack(per_case, pack_rows=pack_rows)

    assert actual == expected, (
        "BRS-0b §7 invariance violated: re-derived pack_summary differs from "
        f"baseline at {_FIXTURE_PATH}.\n"
        f"diff per pack:\n"
        + "\n".join(
            f"  {p}: actual={actual[p]} expected={expected[p]}"
            for p in _PACKS
            if actual[p] != expected[p]
        )
    )
