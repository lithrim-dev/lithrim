"""TOOL-2: the generic MCP-stdio-client execution primitive (domain-agnostic).

Hermetic — an INJECTED fake transport stands in for a real MCP server process (no
subprocess, no network), mirroring ``test_kb_grounding``'s ``FakeKbHttp``. The fake speaks
JSON-RPC 2.0 and answers a generic ``subsumed_by`` hierarchy tool, pinning the client's
``initialize`` handshake + ``tools/call`` decode against the exact MCP wire shape. (A
domain pack supplies the concrete server + the clinical grounding binding; the core client
knows nothing of any domain.)
"""

from __future__ import annotations

import json

import pytest

from lithrim_bench.verification import McpError, McpStdioClient


class _FakeMcpServer:
    """A fake MCP server as an injectable transport: records every request and answers
    ``initialize`` + ``tools/call`` (a generic ``subsumed_by`` hierarchy check / a deliberate
    isError / an unknown tool). Opaque integer concept ids — no domain semantics."""

    # A tiny is-a graph: 11 is-a 30; 12 is-a 11; 11 is NOT a 99.
    SUBSUMES = {(11, 30): True, (12, 11): True, (11, 99): False}

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def __call__(self, msg: dict) -> dict | None:
        self.requests.append(msg)
        if "id" not in msg:  # a notification (notifications/initialized)
            return None
        rid, method = msg["id"], msg.get("method")
        if method == "initialize":
            return _ok(
                rid,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake", "version": "0"},
                },
            )
        if method == "tools/list":
            return _ok(rid, {"tools": [{"name": "subsumed_by"}, {"name": "search"}]})
        if method == "tools/call":
            name, args = msg["params"]["name"], msg["params"]["arguments"]
            if name == "subsumed_by":
                val = self.SUBSUMES.get((args["concept_id"], args["subsumer_id"]), False)
                return _ok(
                    rid, {"content": [{"type": "text", "text": json.dumps({"subsumedBy": val})}]}
                )
            if name == "boom":
                return _ok(rid, {"isError": True, "content": [{"type": "text", "text": "kaboom"}]})
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": f"unknown tool {name}"},
            }
        return _ok(rid, {})


def _ok(rid: int, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def test_subsumed_by_decode():
    """call_tool decodes the JSON text content of a tools/call result — the subsumption
    facts round-trip to native Python (the grounding signal a contract would consume)."""
    client = McpStdioClient(transport=_FakeMcpServer())
    assert client.call_tool("subsumed_by", {"concept_id": 11, "subsumer_id": 30}) == {
        "subsumedBy": True
    }
    assert client.call_tool("subsumed_by", {"concept_id": 11, "subsumer_id": 99}) == {
        "subsumedBy": False
    }


def test_handshake_runs_once_before_the_first_call():
    """The MCP lifecycle: initialize → notifications/initialized → tools/call, and the
    handshake runs exactly ONCE across multiple calls."""
    fake = _FakeMcpServer()
    client = McpStdioClient(transport=fake)
    client.call_tool("subsumed_by", {"concept_id": 12, "subsumer_id": 11})
    client.call_tool("subsumed_by", {"concept_id": 11, "subsumer_id": 30})
    methods = [r.get("method") for r in fake.requests]
    assert methods[:2] == ["initialize", "notifications/initialized"]
    assert methods.count("initialize") == 1  # handshake once, not per call
    assert methods.count("tools/call") == 2


def test_iserror_tool_result_raises():
    client = McpStdioClient(transport=_FakeMcpServer())
    with pytest.raises(McpError, match="isError"):
        client.call_tool("boom", {})


def test_jsonrpc_error_raises():
    client = McpStdioClient(transport=_FakeMcpServer())
    with pytest.raises(McpError, match="error"):
        client.call_tool("nonexistent_tool", {})


def test_list_tools():
    client = McpStdioClient(transport=_FakeMcpServer())
    assert {t["name"] for t in client.list_tools()} == {"subsumed_by", "search"}


def test_no_command_and_no_transport_fails_clean():
    """A client with neither a command nor an injected transport fails clean (not a hang)."""
    with pytest.raises(McpError, match="no command"):
        McpStdioClient().call_tool("x", {})
