"""The $0-replay freshness refusal must reach the UI as an actionable 409, not a 500.

The drift-aware freshness guard (scripts/run_eval.py) REFUSES to replay a case whose
stored head was graded under a different config — correct, honesty-preserving. But the
BFF mapped every grade-subprocess failure to a generic 500 "Please try again", which is
wrong advice for this guard (retrying the replay refuses forever): the caller must
re-run PAID. Surface the guard's own message with 409 Conflict; every other subprocess
failure keeps the calm generic 500.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff_mod  # noqa: E402
from fastapi import HTTPException  # noqa: E402

_WS = SimpleNamespace(pack="clinverdict", packs_dir=None)

_STALE_STDERR = (
    "Traceback (most recent call last):\n  ...\nValueError: agent 'clinverdict_default': "
    "the config changed since case 'cv_mts_161' was last graded — re-grade "
    "(run it live or in_process) to see the new verdict."
)


def _fake_run(returncode: int, stderr: str):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return run


def _call():
    return bff_mod._grade_via_subprocess(
        agent_name="clinverdict_default", config_db="x.sqlite", ontology_path=None,
        collections_db=None, out_dir=None, live=False, in_process=False, ws=_WS,
    )


def test_stale_replay_refusal_is_409_with_the_guard_message(monkeypatch):
    monkeypatch.setattr(bff_mod.subprocess, "run", _fake_run(1, _STALE_STDERR))
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 409
    assert "config changed since" in exc.value.detail
    assert "re-grade" in exc.value.detail


def test_other_subprocess_failures_stay_generic_500(monkeypatch):
    monkeypatch.setattr(
        bff_mod.subprocess, "run", _fake_run(1, "SomeError: the disk is on fire")
    )
    with pytest.raises(HTTPException) as exc:
        _call()
    assert exc.value.status_code == 500
    assert "the disk is on fire" not in exc.value.detail  # raw stderr never leaks on 500
