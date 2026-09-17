"""CACHE-TRAP-3: a PAID calibration must re-sample, like a paid grade does.

Found 2026-09-16 in the reproduction: a second `lithrim calibrate` finished in five seconds with
deltas identical to the previous round's (0.68 -> 0.70, 0.57 -> 0.65, 0.76 -> 0.76) while
/root/.dspy_cache held 16 entries. The grade path sets LITHRIM_JUDGE_CACHE=0 for exactly this
reason (CACHE-TRAP-1: the DSPy disk cache otherwise replays an identical re-run byte-for-byte at
tokens=0); the optimize path set only the cache DIRECTORY. A calibration is a paid round whose
held-out score decides the pin, so a cached round means the pin gate decided on replayed
numbers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402


def test_the_service_runs_the_optimizer_with_the_cache_off(monkeypatch, tmp_path):
    seen = {}

    class _Proc:
        returncode = 0
        stdout = '__OPTIMIZE_JSON__{"role": "r", "error": "stop here"}'
        stderr = ""

    def _run(cmd, env=None, **kw):
        seen["env"] = env or {}
        return _Proc()

    monkeypatch.setattr(bff.subprocess, "run", _run)
    ws = types.SimpleNamespace(name="w", pack="_core", packs_dir=None, out_dir=tmp_path)
    with pytest.raises(bff.HTTPException):  # the stub's error envelope → the calm 422
        bff._optimize_via_subprocess(
            role="risk_judge", ws=ws, collections_db=tmp_path / "c.db", out_dir=tmp_path,
            limit=None,
        )
    assert seen["env"].get("LITHRIM_JUDGE_CACHE") == "0", "a paid calibration replayed the cache"
    assert seen["env"].get("LITHRIM_JUDGE_CACHE_DIR")  # still scoped to this workspace


def test_the_cli_runs_the_optimizer_with_the_cache_off(monkeypatch):
    from lithrim_bench.cli import loop

    seen = {}
    monkeypatch.setattr(loop, "_run", lambda cmd, env=None, **kw: seen.update(env=env or {}))
    monkeypatch.setattr(loop, "summarize_optimize", lambda *a, **k: "")
    a = types.SimpleNamespace(
        judge_def={"role": "ragtruth_detector"}, out=Path("/tmp/loop_x"),
        out_optimize=Path("/tmp/loop_x/optimize"), calib=Path("/tmp/loop_x/calib.jsonl"),
        heldout_cap=0, model="openai/gpt-4.1-2025-04-14", optimize_extra=[],
    )
    monkeypatch.setattr(loop, "_read_jsonl", lambda p: [{"split": "dev"}])
    with pytest.raises((OSError, KeyError, ValueError)):  # stops at the missing result file,
        loop.step_optimize(a)                               # after the spawn this test reads
    assert seen["env"].get("LITHRIM_JUDGE_CACHE") == "0"
