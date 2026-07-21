"""READ-ATTRIB-1 at the scorecard: the pre/post band must not bill rule disagreement to the floor.

``verdict_pre_floor`` is the COUNCIL's tier verdict; ``verdict`` is ``severity_map.rescore``.
They are different rules, so they disagree on cases the floor never touched, and the band read
that gap as the floor's work (observed 2026-07-21: an 85% -> 69% "drop" on a batch where the
floor flipped the binary verdict on exactly zero labeled cases).

The scorecard therefore reports a THIRD number, ``verdict_accuracy_no_floor``: the same rescore
over the counterfactual finding set, carried on each row as ``verdict_no_floor``. The floor's
honest contribution is post minus no-floor; the rest is the rule change and is labeled as such.

Pure over the cohort rows, $0/offline. Requires the [bff] extra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_NO_FLOOR = {"cleared": [], "enforced": [], "inconclusive": []}

# c1 reproduces the observed bug: the council blocked, rescore warned, the floor did NOTHING.
# c2 is a real floor rescue: no-floor would have passed, the injected finding blocks it.
_ROWS = [
    {
        "case_id": "c1",
        "verdict": "WARN",
        "verdict_pre_floor": "BLOCK",
        "verdict_no_floor": "WARN",
        "findings": [],
        "floor": dict(_NO_FLOOR),
        "votes": [],
    },
    {
        "case_id": "c2",
        "verdict": "BLOCK",
        "verdict_pre_floor": "PASS",
        "verdict_no_floor": "PASS",
        "findings": ["FABRICATED_CLAIM"],
        "floor": {"cleared": [], "enforced": ["FABRICATED_CLAIM"], "inconclusive": []},
        "votes": [],
    },
]
_GOLDS = {"c1": {"MISSING_CONTEXT"}, "c2": {"FABRICATED_CLAIM"}}
_LABELED = {"c1", "c2"}


def _floor():
    return bff._cohort_scorecard(_ROWS, _GOLDS, _LABELED)["floor"]


def test_scorecard_reports_the_no_floor_counterfactual():
    f = _floor()
    # council rule: c1 BLOCK (match), c2 PASS (miss) -> 1/2
    assert f["verdict_accuracy_pre_floor"] == 0.5
    # rescore with the floor: c1 WARN (miss), c2 BLOCK (match) -> 1/2
    assert f["verdict_accuracy_post_floor"] == 0.5
    # rescore WITHOUT the floor: c1 WARN (miss), c2 PASS (miss) -> 0/2
    assert f["verdict_accuracy_no_floor"] == 0.0


def test_the_floor_delta_credits_only_the_floor():
    f = _floor()
    # the floor rescued exactly one case; the flat pre/post band hides that entirely
    assert f["verdict_accuracy_post_floor"] - f["verdict_accuracy_no_floor"] == 0.5
    assert f["verdict_accuracy_post_floor"] - f["verdict_accuracy_pre_floor"] == 0.0


def test_an_idle_floor_scores_no_delta_at_all():
    """The regression proper: floor untouched on every row -> zero floor delta, even though
    the council-vs-rescore gap is large."""
    rows = [
        dict(r, verdict="WARN", verdict_no_floor="WARN", floor=dict(_NO_FLOOR), findings=[])
        for r in _ROWS
    ]
    f = bff._cohort_scorecard(rows, _GOLDS, _LABELED)["floor"]

    assert f["verdict_accuracy_post_floor"] == f["verdict_accuracy_no_floor"]
    assert f["verdict_accuracy_pre_floor"] > f["verdict_accuracy_post_floor"]


def test_missing_counterfactual_is_absent_not_faked():
    """Rows graded before READ-ATTRIB-1 carry no ``verdict_no_floor``; never invent one."""
    rows = [{k: v for k, v in r.items() if k != "verdict_no_floor"} for r in _ROWS]
    f = bff._cohort_scorecard(rows, _GOLDS, _LABELED)["floor"]

    assert f["verdict_accuracy_no_floor"] is None


def test_bff_never_reads_a_grounded_key_the_harness_does_not_write():
    """The cohort row builder reads the grounded blob by string key. A typo there (or a key
    renamed harness-side) makes the feature silently inert: the row carries None, the cohort
    denominator shrinks, and the scorecard honestly reports "no counterfactual" forever.

    Nothing else pins the two sides together, so pin them here: every ``g.get("...")`` the
    endpoint performs must name a key ``_grounded_block`` actually produces.
    """
    import ast
    import sys as _sys
    from pathlib import Path as _Path

    _scripts = _Path(__file__).resolve().parents[2] / "scripts"
    if str(_scripts) not in _sys.path:
        _sys.path.insert(0, str(_scripts))
    from run_eval import _grounded_block

    class _G:  # a GroundedResult stand-in: _grounded_block only reads attributes
        verdict = "WARN"
        verdict_no_floor = "WARN"
        original_verdict = "BLOCK"
        active = []
        suppressed = []
        ungrounded = []
        skipped_non_gradeable = []
        floor_blocks = []

    written = set(_grounded_block(_G()))

    src = (_Path(bff.__file__)).read_text()
    tree = ast.parse(src)
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "grade_cases_endpoint"
    )
    read = {
        node.args[0].value
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "g"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    assert read, "expected the row builder to read the grounded blob by key"
    assert "verdict_no_floor" in read, "the counterfactual must reach the cohort row"
    assert read <= written, f"BFF reads grounded keys the harness never writes: {read - written}"


def test_a_partly_counterfactual_cohort_reports_nothing_not_a_partial_denominator():
    """Honesty: mixing pre- and post-READ-ATTRIB-1 rows must yield None, never a rate scored
    over the subset that happens to carry the key. A subset rate reads as a whole-cohort
    number and would silently overstate or understate the floor's contribution."""
    mixed = [
        _ROWS[0],  # carries verdict_no_floor
        {k: v for k, v in _ROWS[1].items() if k != "verdict_no_floor"},  # legacy row
    ]
    f = bff._cohort_scorecard(mixed, _GOLDS, _LABELED)["floor"]

    assert f["verdict_accuracy_pre_floor"] is not None  # the cohort still scores normally
    assert f["verdict_accuracy_post_floor"] is not None
    assert f["verdict_accuracy_no_floor"] is None
