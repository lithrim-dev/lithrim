import json

import pytest

from repro.ragtruth.bootstrap_arms import compare


def _rec(state, no_floor="BLOCK", raw="BLOCK"):
    return {
        "result": {"verdict": raw},
        "grounded": {"verdict_no_floor": no_floor},
        "composite": {"review": {"state": state}},
    }


def _write_runs(d, recs):
    d.mkdir()
    for cid, r in recs.items():
        (d / f"{cid}.json").write_text(json.dumps(r))


@pytest.fixture
def arms(tmp_path):
    labels = tmp_path / "labels.jsonl"
    rows = []
    golds = {"c1": True, "c2": False, "c3": True, "c4": False}
    for i, (cid, halu) in enumerate(golds.items()):
        rows.append(
            {
                "case_id": cid,
                "expected_safety_flags": ["X"] if halu else [],
                "ragtruth": {"source_id": f"s{i // 2}", "model": "m"},
            }
        )
    labels.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    # frozen arm b: escalates everything; pack arm c: clears the two clean records, flags one hallucination
    _write_runs(tmp_path / "b", {c: _rec("ESCALATED") for c in golds})
    _write_runs(
        tmp_path / "c",
        {
            "c1": _rec("FLAGGED"),
            "c2": _rec("CLEARED"),
            "c3": _rec("ESCALATED"),
            "c4": _rec("CLEARED"),
        },
    )
    return labels, tmp_path / "b", tmp_path / "c"


def test_point_deltas_are_exact_and_paired_by_source(arms):
    labels, b, c = arms
    out = compare([str(b)], [str(c)], labels=str(labels), draws=50, seed=0)
    assert out["n"] == 4 and out["sources"] == 2 and out["unit"] == "source_id"
    ts = out["arms"]["three_state"]
    assert ts["b"]["coverage"] == 0.0 and ts["c"]["coverage"] == 0.75
    assert ts["delta"]["coverage"]["point"] == 0.75
    assert ts["delta"]["false_clears"]["point"] == 0
    lo, hi = ts["delta"]["coverage"]["ci"]
    assert lo <= 0.75 <= hi


def test_refuses_arms_that_do_not_cover_the_same_records(arms, tmp_path):
    labels, b, c = arms
    (c / "c4.json").unlink()
    with pytest.raises(ValueError, match="same records"):
        compare([str(b)], [str(c)], labels=str(labels), draws=5, seed=0)


def test_cross_family_pair_maps_each_arm_with_its_own_reading(arms, tmp_path):
    labels, b, _ = arms
    p = tmp_path / "paper"
    p.mkdir()
    for cid, raw in {
        "c1": '{"hallucination list": ["x"]}',
        "c2": '{"hallucination list": []}',
        "c3": "garbage",
        "c4": '{"hallucination list": [{"span": "y"}]}',
    }.items():
        (p / f"{cid}.json").write_text(json.dumps({"case_id": cid, "raw": raw}))
    out = compare(
        [str(b)],
        [str(p)],
        labels=str(labels),
        draws=20,
        seed=0,
        b_map="escalate_is_halu",
        c_map="paper_prompt",
    )
    (name,) = out["arms"]
    assert name == "escalate_is_halu_vs_paper_prompt"
    arm = out["arms"][name]
    assert arm["b"]["recall"] == 1.0 and arm["c"]["recall"] == 0.5  # c3 unparseable = not detected
    assert arm["c"]["false_blocks"] == 1  # c4 flagged, gold clean
