"""REPRO-1 R3 — the research scorecard: per-reviewer accuracy vs gold, the cross-model
majority, the case × reviewer matrix, and the floor tallies with pre/post-floor accuracy.

What one cohort grade must make READABLE (the thesis tables, generated live):
  * by_judge — each reviewer's matches-gold / silent-misses / over-flags (per-model rows);
  * majority — the cross-model majority scored like a reviewer (ties reported, never spun);
  * judge_matrix — per case: gold, each reviewer's vote (+ raw K-split), the majority;
  * floor — cleared / enforced / cannot-ground counts, gold-defect clears (MUST be zero —
    the safety property, asserted visibly), and verdict accuracy PRE vs POST floor (the
    headline delta from ONE run — the pre/post verdicts ride the same blob);
  * gold verdicts honor a declared expected_compliance_verdict (a reject-labeled case with
    no flag labels is still a gold BLOCK — the verdict-only-label corpus).

Pure over the cohort rows — $0/offline. Requires the [bff] extra.
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


def _vote(role, vote, model="m", scores_raw=None):
    v = {"judge_role": role, "vote": vote, "confidence": 0.9, "model": model}
    if scores_raw is not None:
        v["scores_raw"] = scores_raw
    return v


# Two labeled cases: c1 = gold BLOCK (flag-labeled), c2 = gold PASS (verdict-labeled approve,
# empty flags). Reviewer A catches c1 and passes c2 (2/2); reviewer B misses c1 and
# over-flags c2 (0/2). Majority: c1 tie (1B/1P), c2 tie.
_ROWS = [
    {
        "case_id": "c1", "verdict": "reject", "findings": ["FABRICATED_CLAIM"],
        "verdict_pre_floor": "approve",
        "floor": {"cleared": [], "enforced": ["FABRICATED_CLAIM"], "inconclusive": []},
        "votes": [
            _vote("reviewer_a", "BLOCK", "gpt-4.1", [0.0, 0.0, 0.0, 0.0, 0.0]),
            _vote("reviewer_b", "PASS", "claude-opus-4-8", [1.0, 1.0, 1.0, 1.0, 1.0]),
        ],
    },
    {
        "case_id": "c2", "verdict": "approve", "findings": [],
        "verdict_pre_floor": "approve",
        "floor": {"cleared": [], "enforced": [], "inconclusive": ["LEG_SWELLING_CALL"]},
        "votes": [
            _vote("reviewer_a", "PASS", "gpt-4.1"),
            _vote("reviewer_b", "BLOCK", "claude-opus-4-8"),
        ],
    },
]
_GOLDS = {"c1": {"FABRICATED_CLAIM"}, "c2": set()}
_LABELED = {"c1", "c2"}
_GOLD_VERDICTS = {"c1": True, "c2": False}  # True = should BLOCK


def _card():
    return bff._cohort_scorecard(
        _ROWS, _GOLDS, _LABELED, gold_verdicts=_GOLD_VERDICTS
    )


def test_by_judge_scores_each_reviewer_against_gold():
    by_judge = {j["judge_role"]: j for j in _card()["by_judge"]}
    a, b = by_judge["reviewer_a"], by_judge["reviewer_b"]
    assert a["model"] == "gpt-4.1"
    assert (a["matches_gold"], a["misses"], a["over_flags"]) == (2, 0, 0)
    assert (b["matches_gold"], b["misses"], b["over_flags"]) == (0, 1, 1)
    assert a["n"] == 2


def test_majority_reports_ties_honestly():
    m = _card()["majority"]
    # both cases split 1B/1P → 2 ties, 0 matches (a tie is never spun as a match)
    assert m["ties"] == 2 and m["matches_gold"] == 0


def test_judge_matrix_carries_gold_votes_and_splits():
    matrix = {r["case_id"]: r for r in _card()["judge_matrix"]}
    c1 = matrix["c1"]
    assert c1["gold"] == "BLOCK"
    cells = {c["judge_role"]: c for c in c1["cells"]}
    assert cells["reviewer_a"]["vote"] == "BLOCK"
    assert cells["reviewer_a"]["scores_raw"] == [0.0, 0.0, 0.0, 0.0, 0.0]
    assert cells["reviewer_b"]["model"] == "claude-opus-4-8"
    assert c1["majority"] == "TIE"
    assert matrix["c2"]["gold"] == "PASS"


def test_floor_tallies_and_pre_post_accuracy():
    f = _card()["floor"]
    assert f["enforced"] == 1 and f["cleared"] == 0 and f["inconclusive"] == 1
    assert f["gold_defect_clears"] == []  # the safety property holds on this cohort
    # pre-floor: c1 approve (wrong), c2 approve (right) → 1/2; post: reject+approve → 2/2
    assert f["verdict_accuracy_pre_floor"] == 0.5
    assert f["verdict_accuracy_post_floor"] == 1.0


def test_a_gold_defect_clear_is_named_never_hidden():
    rows = [
        {
            "case_id": "c1", "verdict": "approve", "findings": [],
            "verdict_pre_floor": "reject",
            "floor": {"cleared": ["FABRICATED_CLAIM"], "enforced": [], "inconclusive": []},
            "votes": [_vote("reviewer_a", "PASS")],
        }
    ]
    card = bff._cohort_scorecard(rows, _GOLDS, {"c1"}, gold_verdicts={"c1": True})
    assert card["floor"]["gold_defect_clears"] == [
        {"case_id": "c1", "code": "FABRICATED_CLAIM"}
    ]


def test_verdict_only_label_scores_the_declared_verdict():
    """A reject-labeled case with NO flag labels is a gold BLOCK — the old bool(flags)
    derivation silently scored it as should-PASS."""
    rows = [
        {"case_id": "v1", "verdict": "reject", "findings": [], "votes": []},
    ]
    card = bff._cohort_scorecard(
        rows, {"v1": set()}, {"v1"}, gold_verdicts={"v1": True}
    )
    assert card["verdict_accuracy"] == "1/1"  # reject vs gold-BLOCK = a match
    assert card["cases"][0]["verdict_match"] is True


def test_corpus_gold_verdicts_derivation():
    rows = [
        {"case_id": "a", "expected_compliance_verdict": "reject", "expected_safety_flags": []},
        {"case_id": "b", "expected_compliance_verdict": "approve", "expected_safety_flags": []},
        {"case_id": "c", "expected_safety_flags": ["X"]},  # flags-only → blocked
        {"case_id": "d"},  # unlabeled → absent
    ]
    gv = bff._corpus_gold_verdicts(rows)
    assert gv == {"a": True, "b": False, "c": True}


def test_grade_cases_rows_carry_the_research_fields(tmp_path, monkeypatch):
    """The cohort row projection: votes carry model + scores_raw; the row carries the
    pre-floor verdict + the floor events (what the tallies aggregate)."""
    import json
    from types import SimpleNamespace

    ws = SimpleNamespace(
        name="r3", pack=bff.workspace.DEFAULT_PACK, packs_dir=None,
        out_dir=tmp_path / "out", collections_db=tmp_path / "coll.sqlite",
        config_db=tmp_path / "cfg.sqlite", ontology_dir=tmp_path / "ont", dir=tmp_path,
    )
    ws.out_dir.mkdir(parents=True)
    (ws.out_dir / "ingested_cases.jsonl").write_text(
        json.dumps({"case_id": "c1", "expected_compliance_verdict": "reject",
                    "expected_safety_flags": ["FABRICATED_CLAIM"], "transcript": "t",
                    "artifacts": [{"type": "n", "content": "x"}]}) + "\n"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda *a, **k: ws)

    rec = {
        "case_id": "c1", "pipeline_run_id": "r-1",
        "composite": {"verdict": "reject", "stage_verdict": "FAIL", "active_findings": ["FABRICATED_CLAIM"]},
        "grounded": {
            "verdict": "reject", "original_verdict": "approve",
            "active": [{"code": "FABRICATED_CLAIM"}],
            "suppressed": [{"code": "STYLE_VIOLATION", "contract": "v1"}],
            "floor_blocks": [
                {"flag": "FABRICATED_CLAIM", "injected": True, "contract_type": "value_presence"},
                {"flag": "OTHER", "injected": False, "contract_type": "fact_preservation"},
            ],
        },
        "council": {"votes": [
            {"judge_role": "reviewer_a", "vote": "BLOCK", "confidence": 0.8,
             "model": "gpt-4.1", "scores_raw": [0.0, 0.0, 1.0]},
        ]},
        "result": {"semantic": {"evidence": []}},
    }
    monkeypatch.setattr(bff, "_grade_case", lambda **kw: rec)
    monkeypatch.setattr(bff, "_agent_code_families", lambda *a, **k: {})
    monkeypatch.setattr(bff, "_agent_gradeable_codes", lambda *a, **k: None)
    monkeypatch.setattr(bff, "_load_agent", lambda *a, **k: SimpleNamespace(name="ws0_default"))

    from fastapi.testclient import TestClient

    client = TestClient(bff.app)
    resp = client.post("/v1/cases/grade", json={"agent": "ws0_default", "in_process": True})
    assert resp.status_code == 200, resp.text
    row = resp.json()["matrix"][0]
    assert row["votes"][0]["model"] == "gpt-4.1"
    assert row["votes"][0]["scores_raw"] == [0.0, 0.0, 1.0]
    assert row["verdict_pre_floor"] == "approve"
    assert row["floor"] == {
        "cleared": ["STYLE_VIOLATION"], "enforced": ["FABRICATED_CLAIM"], "inconclusive": ["OTHER"],
    }
    sc = resp.json()["scorecard"]
    assert sc["floor"]["enforced"] == 1
    assert {j["judge_role"] for j in sc["by_judge"]} == {"reviewer_a"}
