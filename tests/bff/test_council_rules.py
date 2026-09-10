"""UI-JOURNEY-1 (B10): how the council decides, readable from the shell. A description of the
frozen rules, never an edit of them."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def test_council_rules_read_names_the_rules_and_the_roster(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_BENCH_PACK_OVERLAY_DIR", str(tmp_path / "overlay"))
    res = TestClient(bff.app).get("/v1/council/rules")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pack"] and isinstance(body["panel"], list) and body["panel"]
    assert body["min_valid_judges"] == 2 and body["gate_mode_min_valid_judges"] == 1
    names = [r["name"] for r in body["rules"]]
    assert "the hesitant or contradicted judge (withstands)" in names
    assert "tier rules" in names and "the floor" in names
    assert all(r["text"] for r in body["rules"])
