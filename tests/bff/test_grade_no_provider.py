"""FIRST-CONTACT-1: a grade fired with NO provider configured must return an actionable 422
("connect a provider in Connect AI"), not the generic 500 "Please try again" — retrying can
never fix a missing key, so that advice is wrong.

The subprocess is simulated: build_judge_lm's real ValueError text on stderr, returncode 1.
$0/offline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from fastapi import HTTPException  # noqa: E402

_NO_KEY_STDERR = (
    "Traceback (most recent call last):\n"
    '  File "scripts/run_eval.py", line 445, in run\n'
    "ValueError: OPENAI_API_KEY is unset; required to bind role='risk_judge' on the "
    "single-provider path (set LITHRIM_LLM_PROVIDER=azure for the Azure trio).\n"
)


def _fake_run(stderr: str):
    def run(cmd, env=None, capture_output=True, text=True, timeout=600):
        return SimpleNamespace(returncode=1, stdout="", stderr=stderr)

    return run


def _ws():
    return SimpleNamespace(pack="_core", id="ws0", packs_dir=None)


def _call(tmp_path):
    return dict(
        agent_name="ws0_default", config_db=tmp_path / "config.sqlite",
        ontology_path=None, collections_db=None, out_dir=None,
        live=True, in_process=True, ws=_ws(), case_id="c1",
    )


def test_no_provider_grade_is_422_connect_ai(monkeypatch, tmp_path):
    monkeypatch.setattr(bff.subprocess, "run", _fake_run(_NO_KEY_STDERR))
    with pytest.raises(HTTPException) as exc_info:
        bff._grade_via_subprocess(**_call(tmp_path))
    assert exc_info.value.status_code == 422
    detail = str(exc_info.value.detail)
    assert "Connect AI" in detail and "provider" in detail.lower(), detail
    assert "try again" not in detail.lower(), detail


def test_other_subprocess_failure_stays_500(monkeypatch, tmp_path):
    monkeypatch.setattr(bff.subprocess, "run", _fake_run("boom: unrelated explosion\n"))
    with pytest.raises(HTTPException) as exc_info:
        bff._grade_via_subprocess(**_call(tmp_path))
    assert exc_info.value.status_code == 500
