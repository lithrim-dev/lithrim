"""PIN-GATE-2: a compiled demo set reaches the production judge only through the gate.

Observed 2026-09-10: POST /v1/judges/{role}/optimize wrote compiled demos straight into the
workspace out dir the next grade reads, even when the held-out score fell; the refuse-on-loss
gate lived only in the pilot's cycle script. The gate now lives in the engine and the BFF
stages the optimizer's files, pinning only a set that does not regress."""

from __future__ import annotations

import json

from lithrim_bench.runtime.council import judge_optimize as jo

ROLE = "some_judge"
TAG = f"dspy3b_{ROLE}"


def _stage(tmp_path, graded: float):
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    (staging / f"compiled_demos_{TAG}.json").write_text(json.dumps([{"artifact": "a"}]))
    (staging / f"score_optimized_{TAG}.json").write_text(json.dumps({"graded": graded}))
    return staging


def test_pin_gate_decides_without_raising():
    assert jo.pin_gate(0.76, None) == (True, "pinned (no pinned score to compare against)")
    assert jo.pin_gate(0.76, 0.52)[0] and jo.pin_gate(0.69, 0.69)[0]
    ok, reason = jo.pin_gate(0.69, 0.76)
    assert not ok and "below the pinned set's" in reason
    ok, reason = jo.pin_gate(0.69, 0.76, force=True)
    assert ok and "force" in reason.lower()


def test_pin_demos_copies_a_non_regressing_set_and_writes_the_score_sidecar(tmp_path):
    ws_out = tmp_path / "ws"
    pin = jo.pin_demos(_stage(tmp_path, 0.7), ws_out, ROLE)
    assert pin["pinned"] is True and pin["pinned_graded"] is None and pin["candidate_graded"] == 0.7
    assert (ws_out / f"compiled_demos_{TAG}.json").exists()
    assert json.loads((ws_out / f"compiled_demos_{TAG}.score.json").read_text())["graded"] == 0.7
    assert jo.load_compiled_demos(ws_out, ROLE)  # the next grade picks it up


def test_pin_demos_refuses_a_regressing_set_and_leaves_the_pinned_one_in_place(tmp_path):
    ws_out = tmp_path / "ws"
    jo.pin_demos(_stage(tmp_path / "r1", 0.8), ws_out, ROLE)
    before = (ws_out / f"compiled_demos_{TAG}.json").read_text()
    pin = jo.pin_demos(_stage(tmp_path / "r2", 0.6), ws_out, ROLE)
    assert pin["pinned"] is False and pin["pinned_graded"] == 0.8 and "REFUSING" in pin["reason"]
    assert (ws_out / f"compiled_demos_{TAG}.json").read_text() == before
    forced = jo.pin_demos(_stage(tmp_path / "r3", 0.6), ws_out, ROLE, force=True)
    assert forced["pinned"] is True and "force" in forced["reason"].lower()
    assert json.loads((ws_out / f"compiled_demos_{TAG}.score.json").read_text())["graded"] == 0.6


def test_pin_demos_with_no_staged_files_is_an_honest_no_pin(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    pin = jo.pin_demos(empty, tmp_path / "ws", ROLE)
    assert pin["pinned"] is False and "no compiled demos" in pin["reason"]
    missing = jo.pin_demos(tmp_path / "missing", tmp_path / "ws", ROLE)
    assert missing["pinned"] is False and not (tmp_path / "ws").exists()


def _result(staging, out_of_sample: bool) -> None:
    (staging / f"result_{TAG}.json").write_text(
        json.dumps({"manifest": {"demos_out_of_sample": out_of_sample, "demo_source_ids": ["x"]}})
    )


def test_pin_refuses_demos_that_are_not_out_of_sample_unless_forced(tmp_path):
    """UI-JOURNEY-1 (B6): the out-of-sample refusal the pilot's CLI made lives in the gate."""
    staging = _stage(tmp_path, 0.9)
    _result(staging, False)
    pin = jo.pin_demos(staging, tmp_path / "ws", ROLE)
    assert pin["pinned"] is False and "out of sample" in pin["reason"]
    assert pin["out_of_sample"] is False
    assert not (tmp_path / "ws" / f"compiled_demos_{TAG}.json").exists()
    forced = jo.pin_demos(staging, tmp_path / "ws", ROLE, force=True)
    assert forced["pinned"] is True and "not out of sample" in forced["reason"]


def test_pin_reports_out_of_sample_when_the_manifest_says_so_and_none_without_one(tmp_path):
    staging = _stage(tmp_path, 0.7)
    _result(staging, True)
    pin = jo.pin_demos(staging, tmp_path / "ws", ROLE)
    assert pin["pinned"] is True and pin["out_of_sample"] is True
    bare = jo.pin_demos(_stage(tmp_path / "b", 0.7), tmp_path / "ws2", ROLE)
    assert bare["pinned"] is True and bare["out_of_sample"] is None


# ── HOLDOUT-DEV-1 follow-up: a score is only comparable on the same held-out set ─────────
def _result_with_heldout(staging, split, ids, out_of_sample=True):
    (staging / f"result_{TAG}.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "demos_out_of_sample": out_of_sample,
                    "demo_source_ids": ["x"],
                    "heldout_split": split,
                    "heldout_case_ids": ids,
                }
            }
        )
    )


def test_the_sidecar_records_which_held_out_set_the_score_came_from(tmp_path):
    staging = _stage(tmp_path, 0.7)
    _result_with_heldout(staging, "dev", ["d2", "d1"])
    pin = jo.pin_demos(staging, tmp_path / "ws", ROLE)
    side = json.loads((tmp_path / "ws" / f"compiled_demos_{TAG}.score.json").read_text())
    assert pin["pinned"] is True and side["graded"] == 0.7
    assert side["heldout"] == jo.heldout_identity("dev", ["d1", "d2"])
    assert (
        side["heldout"]["split"] == "dev"
        and side["heldout"]["n"] == 2
        and len(side["heldout"]["digest"]) == 64
    )


def test_a_score_from_a_different_held_out_set_is_not_compared(tmp_path):
    """A set pinned before the dev slice (its score from the test cut, no identity) against a
    new dev-slice round: two held-out sets, so no comparison; the round pins with that reason."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / f"compiled_demos_{TAG}.json").write_text("[]")
    (ws / f"compiled_demos_{TAG}.score.json").write_text(
        json.dumps({"graded": 0.76, "source": "old"})
    )
    staging = _stage(tmp_path, 0.6)
    _result_with_heldout(staging, "dev", ["d1", "d2"])
    pin = jo.pin_demos(staging, ws, ROLE)
    assert pin["pinned"] is True and pin["comparable"] is False
    assert "no comparable" in pin["reason"] and "different held-out set" in pin["reason"]
    assert (
        json.loads((ws / f"compiled_demos_{TAG}.score.json").read_text())["heldout"]["split"]
        == "dev"
    )


def test_the_same_held_out_set_is_still_gated_and_a_changed_one_is_not(tmp_path):
    ws = tmp_path / "ws"
    first = _stage(tmp_path / "a", 0.76)
    _result_with_heldout(first, "dev", ["d1", "d2"])
    jo.pin_demos(first, ws, ROLE)
    lower = _stage(tmp_path / "b", 0.6)
    _result_with_heldout(lower, "dev", ["d2", "d1"])  # same set, other order
    refused = jo.pin_demos(lower, ws, ROLE)
    assert (
        refused["pinned"] is False
        and refused["comparable"] is True
        and "REFUSING" in refused["reason"]
    )
    moved = _stage(tmp_path / "c", 0.6)
    _result_with_heldout(moved, "dev", ["d1", "d3"])  # the dev slice changed (a new load)
    pinned = jo.pin_demos(moved, ws, ROLE)
    assert pinned["pinned"] is True and pinned["comparable"] is False


def test_with_no_identity_on_either_side_the_legacy_comparison_holds(tmp_path):
    ws = tmp_path / "ws"
    jo.pin_demos(_stage(tmp_path / "a", 0.8), ws, ROLE)
    refused = jo.pin_demos(_stage(tmp_path / "b", 0.7), ws, ROLE)
    assert refused["pinned"] is False and refused["comparable"] is True
