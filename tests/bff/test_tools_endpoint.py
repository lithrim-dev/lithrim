"""TOOL-AUTHOR-1 (Stage 1): POST/GET/DELETE /v1/tools — author an MCP/API tool into the
per-workspace config plane (mirror the judges author path; audited; manifest-validated).

Real tmp DB (the endpoint+store+audit integrate); the active workspace is stubbed to a tmp-scoped
namespace. Requires the [bff] extra (fastapi). Pack-independent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_MANIFEST = {
    "id": "my_hermes",
    "kind": "tool",
    "transport": "service",
    "implements": "tool.terminology",
    "service": {"mcp": {"command": "hermes", "args": ["--db", "/x/snomed.db", "mcp"]}},
}
_BIND = {"flag_code": "FABRICATED_HISTORY", "authority": "floor",
         "contract_type": "snomed_subsumption", "params": {"tool": "my_hermes"}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    ws = SimpleNamespace(name="ws_test", config_db=db, collections_db=db, pack="healthcare", packs_dir=None)
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: ws)
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: db
    c = TestClient(bff.app)
    try:
        yield c
    finally:
        bff.app.dependency_overrides.clear()


def test_post_authors_a_tool_then_get_lists_it(client):
    res = client.post("/v1/tools", json={"manifest": _MANIFEST, "bind": _BIND})
    assert res.status_code == 200, res.text
    assert res.json()["tool_id"] == "my_hermes"

    got = client.get("/v1/tools")
    assert got.status_code == 200
    body = got.json()
    authored = {t["tool_id"]: t for t in body["authored"]}
    assert "my_hermes" in authored
    assert authored["my_hermes"]["manifest"]["implements"] == "tool.terminology"
    assert authored["my_hermes"]["bind"]["flag_code"] == "FABRICATED_HISTORY"
    # declared core tools (etlp_jute / web_search) are surfaced alongside authored
    assert any(t["id"] == "web_search" for t in body["declared"])


def test_get_lists_declared_core_tools_when_none_authored(client):
    body = client.get("/v1/tools").json()
    assert body["authored"] == []
    declared_ids = {t["id"] for t in body["declared"]}
    assert {"etlp_jute", "web_search"} <= declared_ids  # the api_connector + mcp_server examples


def test_post_rejects_a_non_tool_manifest(client):
    bad = {**_MANIFEST, "kind": "provider"}
    res = client.post("/v1/tools", json={"manifest": bad})
    assert res.status_code == 422
    assert "tool" in res.json()["detail"].lower()


def test_post_rejects_a_malformed_manifest(client):
    bad = {"id": "x", "kind": "tool", "bogus_field": 1}  # extra='forbid' on PluginManifest
    res = client.post("/v1/tools", json={"manifest": bad})
    assert res.status_code == 422


def test_delete_removes_the_authored_tool(client):
    client.post("/v1/tools", json={"manifest": _MANIFEST})
    res = client.request("DELETE", "/v1/tools/my_hermes")
    assert res.status_code == 200
    assert res.json()["removed"] is True
    assert client.get("/v1/tools").json()["authored"] == []
    # idempotent: deleting again is a clean removed=false
    again = client.request("DELETE", "/v1/tools/my_hermes")
    assert again.status_code == 200 and again.json()["removed"] is False
