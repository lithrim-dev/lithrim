"""NO-CASE-GUARD — a single-case grade with no resolvable case returns a friendly 400, not a 500.

The live bug (hit 3x): an ingested-corpus agent has an EMPTY ``dataset.case_id`` (the cases live
in the corpus, not bound to the agent). When the chat agent mis-picks the single-run tool for a
"grade all" message, ``/v1/run-eval`` reached the grade subprocess with case_id='' → the subprocess
``case '' not found`` → an opaque 500. The guard fires FIRST: a clear, actionable 400 that points
the SME at "grade all cases" (when a corpus exists) or at picking a case. The cohort path is
unaffected — it always passes an explicit case_id per case.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from fastapi import HTTPException  # noqa: E402

from lithrim_bench.harness.config import save_agent  # noqa: E402
from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _nocase_agent(name: str = "nocase"):
    """A house agent with an EMPTY dataset.case_id — the ingested-corpus shape."""
    ag = house_agent(name=name)
    return replace(ag, dataset=replace(ag.dataset, case_id=""))


def _kw(tmp_path, db):
    return dict(
        agent_name="nocase", live=False, in_process=False, db_path=db,
        out_dir=tmp_path / "out", workdir=tmp_path / "ont", collections_db=tmp_path / "coll.sqlite",
    )


def test_no_case_no_corpus_yields_friendly_400(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    save_agent(_nocase_agent(), db_path=db)
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: [])
    with pytest.raises(HTTPException) as ei:
        bff._grade_case(case_id=None, **_kw(tmp_path, db))
    assert ei.value.status_code == 400
    detail = str(ei.value.detail).lower()
    assert "select a case" in detail
    assert "not found" not in detail  # NOT the raw subprocess 500 text


def test_no_case_with_corpus_points_to_grade_all(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    save_agent(_nocase_agent(), db_path=db)
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: [{"case_id": "c1"}])
    with pytest.raises(HTTPException) as ei:
        bff._grade_case(case_id=None, **_kw(tmp_path, db))
    assert ei.value.status_code == 400
    assert "grade all cases" in str(ei.value.detail).lower()


def test_explicit_case_id_bypasses_the_guard(tmp_path, monkeypatch):
    """Non-vacuous: WITH a case_id, the guard is bypassed and execution reaches the next step
    (ontology resolution) — proving the guard sits exactly between load-agent and grade, and only
    fires on the no-case path."""
    db = tmp_path / "config.sqlite"
    save_agent(_nocase_agent(), db_path=db)
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: [])

    class _PastGuard(Exception):
        pass

    def _boom(*a, **k):
        raise _PastGuard()

    monkeypatch.setattr(bff, "_resolve_ontology_path", _boom)
    # no case → the guard fires (never reaches _resolve_ontology_path)
    with pytest.raises(HTTPException) as ei:
        bff._grade_case(case_id=None, **_kw(tmp_path, db))
    assert ei.value.status_code == 400
    # WITH a case → guard bypassed → reaches _resolve_ontology_path (the sentinel)
    with pytest.raises(_PastGuard):
        bff._grade_case(case_id="some_case", **_kw(tmp_path, db))
