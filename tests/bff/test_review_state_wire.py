"""REVIEW-STATE-1 (wire) — the review state rides the graded record through the BFF.

A real $0 replay grade of the neutral house fixture through ``POST /v1/run-eval`` must
carry ``composite.review`` (state, reason, evidence), and the pure read
``GET /v1/reports/{case_id}`` must serve that block unchanged, so the shell's report pane,
the inline card and the Reviewers tab render the same decision the CLI queue prints.

Written FIRST (RED): ``composite()`` carries no ``review`` block, so both reads miss it.
Hermetic: TestClient, a tmp out_dir, the committed replay baseline; no model call.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import HOUSE_CASE_ID, house_agent  # noqa: E402

_STATES = {"CLEARED", "FLAGGED", "ESCALATED"}
AGENT = "review_state_wire"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    fake_ws = types.SimpleNamespace(
        out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="review_ws"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_a_replay_grade_carries_the_review_state_and_the_report_read_serves_it(client):
    res = client.post("/v1/run-eval", json={"agent": AGENT})
    assert res.status_code == 200, res.text
    rec = res.json()
    review = (rec.get("composite") or {}).get("review")
    assert review, "composite must carry the review block on the wire"
    assert review["state"] in _STATES and review["reason"]
    # the invariant on the wire: CLEARED and FLAGGED need the floor; a vote never clears
    if review["state"] in {"CLEARED", "FLAGGED"}:
        assert review["floor_backstopped"] is True

    read = client.get(f"/v1/reports/{HOUSE_CASE_ID}", params={"agent": AGENT})
    assert read.status_code == 200, read.text
    assert read.json()["composite"]["review"] == review
