"""SPLIT-HYGIENE-1 at the boundary: POST /v1/judges/{role}/optimize refuses the stride path.

The route's ``split`` is optional; omitted, the optimizer builds its corpus by striding over
every labelled case in the workspace and ignoring the ``split`` each was imported with. On a
workspace loaded from a labelled dataset that trains the demos on held-out rows. The route now
refuses with a 422 that names the tags it found, before any paid call and before a job exists."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROLE = "risk_judge"

TAGGED = [
    {"case_id": f"c{i}", "expected_safety_flags": [], "split": "calibration" if i < 3 else "test"}
    for i in range(5)
]
UNTAGGED = [{"case_id": f"u{i}", "expected_safety_flags": []} for i in range(5)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    ws = types.SimpleNamespace(
        out_dir=out, pack="_core", packs_dir=None, name="opt_ws",
        collections_db=tmp_path / "c.sqlite",
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: ws)
    monkeypatch.setattr(bff, "_JOBS", {})
    calls: list[dict] = []
    monkeypatch.setattr(bff, "_optimize_via_subprocess", lambda **kw: calls.append(kw) or {"ok": 1})
    corpus = {"rows": list(TAGGED)}
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda ws=None: corpus["rows"])
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "c.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: tmp_path / "config.sqlite"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    try:
        yield TestClient(bff.app), calls, corpus
    finally:
        bff.app.dependency_overrides.clear()


def _post(cli, **extra):
    return cli.post(f"/v1/judges/{ROLE}/optimize", json={"confirm": True, "agent": "a", **extra})


def test_omitting_the_split_on_a_tagged_workspace_is_a_422_naming_the_tags(env):
    cli, calls, _ = env
    res = _post(cli)
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert "calibration" in detail and "test" in detail and "split" in detail
    assert calls == [], "nothing paid may start"


def test_the_refusal_happens_before_a_background_job_exists(env):
    cli, calls, _ = env
    assert _post(cli, background=True).status_code == 422
    assert bff._JOBS == {} and calls == []


def test_naming_a_split_runs_as_before(env):
    cli, calls, _ = env
    assert _post(cli, split="calibration").status_code == 200
    assert calls[0]["split"] == "calibration"


def test_an_untagged_workspace_may_still_omit_the_split(env):
    cli, calls, corpus = env
    corpus["rows"] = list(UNTAGGED)
    assert _post(cli).status_code == 200
    assert calls[0]["split"] is None
