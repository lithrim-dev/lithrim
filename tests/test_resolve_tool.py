"""TOOL-AUTHOR-1 (Stage 2a): per-workspace tool resolution.

`resolve_tool(tool_id)` is the single grade-time resolver: a workspace's **authored** tool wins,
else the active pack ∪ core `tool_plugins()`, else None. License-gated (a `tier: pro` tool is
ABSENT under a denying license). This is what lets a UI-authored MCP tool drive the grade.
"""

from __future__ import annotations

from types import SimpleNamespace

from lithrim_bench.harness import plugins, tools_store
from lithrim_bench.harness.plugins import License


def _stub_active_ws(monkeypatch, db, name="ws_a"):
    from lithrim_bench.harness import workspace as _ws

    monkeypatch.setattr(
        _ws, "get_active_workspace",
        lambda: SimpleNamespace(name=name, config_db=db, collections_db=db, pack="_core"),
    )


def test_authored_tool_resolves_for_the_active_workspace(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    m = {"id": "my_scraper", "kind": "tool", "transport": "service", "implements": "tool.mcp_server",
         "service": {"default_base_url": "http://localhost:8585"}}
    tools_store.save_tool("my_scraper", m, db_path=db, workspace_id="ws_a")
    _stub_active_ws(monkeypatch, db)

    got = plugins.resolve_tool("my_scraper")
    assert got is not None and got.id == "my_scraper"
    assert got.implements == "tool.mcp_server"


def test_authored_is_per_workspace(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    tools_store.save_tool("my_scraper", {"id": "my_scraper", "kind": "tool"}, db_path=db, workspace_id="ws_a")
    _stub_active_ws(monkeypatch, db, name="ws_b")  # different workspace
    assert plugins.resolve_tool("my_scraper") is None


def test_falls_through_to_core_declared_tool(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    _stub_active_ws(monkeypatch, db)
    got = plugins.resolve_tool("web_search")  # a core _CORE_TOOL_PLUGINS id
    assert got is not None and got.id == "web_search"


def test_unknown_tool_is_none(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    _stub_active_ws(monkeypatch, db)
    assert plugins.resolve_tool("does_not_exist") is None


def test_pro_authored_tool_absent_under_denying_license(tmp_path, monkeypatch):
    db = tmp_path / "config.sqlite"
    m = {"id": "pro_tool", "kind": "tool", "tier": "pro"}
    tools_store.save_tool("pro_tool", m, db_path=db, workspace_id="ws_a")
    _stub_active_ws(monkeypatch, db)
    assert plugins.resolve_tool("pro_tool", license=License("deny-all")) is None
    assert plugins.resolve_tool("pro_tool", license=License("permit-all")) is not None
