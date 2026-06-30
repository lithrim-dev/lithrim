"""TOOL-AUTHOR-1 (Stage 1): the per-workspace authored-tools store.

A user-authored MCP/API tool stops being a maintainer-edited pack `tools.json` and becomes a row
in the one SSOT DB (`LITHRIM_DB_URL` → Postgres, else local SQLite — the SAME selector as the
config plane / cases / run blobs), scoped by `workspace_id`:

    authored_tools(workspace_id, tool_id, manifest_json, bind_json, created_at)  PK(workspace_id, tool_id)

`manifest_json` is the `kind: tool` PluginManifest (no secrets); `bind_json` is the optional
flag-bind {flag_code, authority, contract_type, params}. Mirrors `cases_store.py` exactly.
Per-workspace isolation is the headline invariant (one workspace's tools never leak into another).
Stdlib + the db layer only — no council/dspy import; runs in any interpreter.
"""

from __future__ import annotations

from lithrim_bench.harness import tools_store

_MANIFEST = {
    "id": "my_hermes",
    "kind": "tool",
    "tier": "core",
    "transport": "service",
    "implements": "tool.terminology",
    "service": {"mcp": {"command": "hermes", "args": ["--db", "/x/snomed.db", "mcp"]}},
}
_BIND = {
    "flag_code": "FABRICATED_HISTORY",
    "authority": "floor",
    "contract_type": "snomed_subsumption",
    "params": {"tool": "my_hermes", "oracle_path": "patient_profile.conditions"},
}


def test_save_then_load_round_trips_manifest_and_bind(tmp_path):
    db = tmp_path / "config.sqlite"
    tools_store.save_tool("my_hermes", _MANIFEST, bind=_BIND, db_path=db, workspace_id="ws_a")
    row = tools_store.load_tool("my_hermes", db_path=db, workspace_id="ws_a")
    assert row is not None
    assert row["manifest"] == _MANIFEST
    assert row["bind"] == _BIND


def test_save_is_idempotent_upsert(tmp_path):
    db = tmp_path / "config.sqlite"
    tools_store.save_tool("my_hermes", _MANIFEST, bind=_BIND, db_path=db, workspace_id="ws_a")
    updated = {**_MANIFEST, "version": "1.2.3"}
    tools_store.save_tool("my_hermes", updated, bind=None, db_path=db, workspace_id="ws_a")
    rows = tools_store.list_tools(db_path=db, workspace_id="ws_a")
    assert len(rows) == 1  # overwrote, did not duplicate
    assert rows[0]["manifest"]["version"] == "1.2.3"
    assert rows[0]["bind"] is None


def test_per_workspace_isolation(tmp_path):
    db = tmp_path / "config.sqlite"
    tools_store.save_tool("my_hermes", _MANIFEST, bind=_BIND, db_path=db, workspace_id="ws_a")
    tools_store.save_tool("scraper", {**_MANIFEST, "id": "scraper", "implements": "tool.mcp_server"},
                          bind=None, db_path=db, workspace_id="ws_b")
    a = tools_store.list_tools(db_path=db, workspace_id="ws_a")
    b = tools_store.list_tools(db_path=db, workspace_id="ws_b")
    assert [r["tool_id"] for r in a] == ["my_hermes"]
    assert [r["tool_id"] for r in b] == ["scraper"]
    # cross-workspace load is a miss
    assert tools_store.load_tool("scraper", db_path=db, workspace_id="ws_a") is None


def test_delete_removes_only_that_tool(tmp_path):
    db = tmp_path / "config.sqlite"
    tools_store.save_tool("my_hermes", _MANIFEST, db_path=db, workspace_id="ws_a")
    tools_store.save_tool("scraper", {**_MANIFEST, "id": "scraper"}, db_path=db, workspace_id="ws_a")
    assert tools_store.delete_tool("my_hermes", db_path=db, workspace_id="ws_a") is True
    assert [r["tool_id"] for r in tools_store.list_tools(db_path=db, workspace_id="ws_a")] == ["scraper"]
    # deleting a missing tool is a clean False, not an error
    assert tools_store.delete_tool("nope", db_path=db, workspace_id="ws_a") is False
