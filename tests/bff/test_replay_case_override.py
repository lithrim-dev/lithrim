"""Caught by the 2026-07-03 live Docker validation: a $0 replay of an INGESTED case on an
agent that carries a committed baseline FILE served the FILE's captured votes (a different
case!) under the ingested case's identity — a manufactured verdict, worse than stale, and it
bypassed the SIGNATURE-1 freshness guard entirely.

Rule: the file baseline speaks ONLY for the agent's own dataset case. A case-override grade
must drop it, so run_eval resolves replay-from-provenance (head + freshness guard) instead.

$0/offline — run_eval.run is captured, never executed.
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


def _capture_run(captured):
    def run(agent, **kw):
        captured["agent"] = agent
        raise SystemExit("stop-after-capture")

    return run


def _grade(monkeypatch, tmp_path, case_id):
    captured: dict = {}
    monkeypatch.setattr(bff.run_eval, "run", _capture_run(captured))
    ws = SimpleNamespace(pack=bff.workspace.DEFAULT_PACK, id="ws0", packs_dir=None)
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda *a, **k: ws)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):  # the SystemExit → 400 mapping fires after capture
        bff._grade_case(
            agent_name="ws0_default", case_id=case_id, live=False, in_process=False,
            db_path=tmp_path / "config.sqlite", out_dir=tmp_path / "out",
            workdir=tmp_path, collections_db=tmp_path / "collections.sqlite",
        )
    return captured["agent"]


def test_case_override_drops_the_foreign_file_baseline(monkeypatch, tmp_path):
    agent = _grade(monkeypatch, tmp_path, case_id="demo-001")
    assert agent.dataset.case_id == "demo-001"
    assert agent.dataset.baseline is None, (
        "a foreign case must NOT replay the agent's own baseline file"
    )


def test_own_case_keeps_the_file_baseline(monkeypatch, tmp_path):
    own = _grade(monkeypatch, tmp_path, case_id=None)
    assert own.dataset.baseline is not None  # the committed demo baseline still replays
    same = _grade(monkeypatch, tmp_path, case_id=own.dataset.case_id)
    assert same.dataset.baseline is not None  # explicit own-case id keeps it too


def test_stale_replay_refusal_maps_to_409_in_process(monkeypatch, tmp_path):
    """The drift-aware stale refusal is 409 on BOTH grade paths (the subprocess path already
    mapped it; the in-process path returned 400 — caught in the live Docker validation)."""
    def refuse(agent, **kw):
        raise SystemExit(
            "agent 'ws0_default': the config changed since case 'demo-001' was last graded "
            "— re-grade (run it live or in_process) to see the new verdict."
        )

    monkeypatch.setattr(bff.run_eval, "run", refuse)
    ws = SimpleNamespace(pack=bff.workspace.DEFAULT_PACK, id="ws0", packs_dir=None)
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda *a, **k: ws)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        bff._grade_case(
            agent_name="ws0_default", case_id="demo-001", live=False, in_process=False,
            db_path=tmp_path / "config.sqlite", out_dir=tmp_path / "out",
            workdir=tmp_path, collections_db=tmp_path / "collections.sqlite",
        )
    assert exc_info.value.status_code == 409
    assert "config changed" in str(exc_info.value.detail)
