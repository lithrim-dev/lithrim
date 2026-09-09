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
