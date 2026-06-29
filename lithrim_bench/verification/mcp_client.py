"""McpStdioClient — a minimal MCP (Model Context Protocol) client over a stdio JSON-RPC
2.0 transport (TOOL-2). The reusable EXECUTION primitive behind a ``kind: tool`` /
``transport: service`` MCP tool: spawn the server (``command``/``args`` — declared in a
tool manifest's ``service`` block), perform the MCP ``initialize`` handshake, then ``tools/call``.

Stdlib-only (``subprocess`` + ``json``) — **no new dependency**. The Agent SDK only *hosts*
an in-process MCP server (``create_sdk_mcp_server``); it provides no reverse client, so a
grade-time executor that calls an EXTERNAL MCP service needs this. A tool USES this; the
plugin registry only DECLARES the tool (TOOL-1, ``kind: tool``).

The transport is **injectable** (a ``request -> response`` callable) so the client is
hermetically testable and a pack can stub a fake server — mirroring ``KbRagTool``'s
injectable ``http_client``. MCP stdio framing is newline-delimited JSON-RPC.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

# The MCP protocol revision we advertise in ``initialize`` (the stable stdio revision).
_PROTOCOL_VERSION = "2024-11-05"

Transport = Callable[[dict[str, Any]], "dict[str, Any] | None"]


class McpError(RuntimeError):
    """An MCP server returned a JSON-RPC error, an ``isError`` tool result, or closed early."""


class McpStdioClient:
    """A minimal synchronous MCP stdio client. Lazily spawns the server (or uses an injected
    ``transport``), runs the ``initialize`` handshake on first use, then dispatches ``tools/call``.

    ``command``/``args`` name the MCP server process (from the tool manifest's ``service`` block).
    Pass ``transport`` to bypass the subprocess entirely (tests / fakes): a callable mapping a
    JSON-RPC request dict to a response dict (or ``None`` for a notification).
    """

    def __init__(
        self,
        command: str | list[str] | None = None,
        args: list[str] | tuple[str, ...] = (),
        *,
        env: dict[str, str] | None = None,
        transport: Transport | None = None,
        client_name: str = "lithrim",
        timeout: float = 30.0,
    ) -> None:
        base = [command] if isinstance(command, str) else list(command or [])
        self._argv = base + list(args)
        self._env = env
        self._client_name = client_name
        self._timeout = timeout
        self._transport = transport  # injected (tests/fakes) OR built on first use
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0
        self._initialized = False

    # ── lifecycle ──────────────────────────────────────────────────────────────────────
    def _ensure(self) -> None:
        if self._transport is None:
            if not self._argv:
                raise McpError("no command to launch an MCP server (and no injected transport)")
            self._proc = subprocess.Popen(  # noqa: S603 — argv is operator-configured (pack manifest)
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self._env,
                text=True,
                bufsize=1,
            )
            self._transport = self._subprocess_transport
        if not self._initialized:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": self._client_name, "version": "0.1.0"},
                },
            )
            self._notify("notifications/initialized", {})
            self._initialized = True

    def _subprocess_transport(self, message: dict[str, Any]) -> dict[str, Any] | None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise McpError("MCP server process is not running")
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        if "id" not in message:  # a notification — no response expected
            return None
        line = proc.stdout.readline()
        if not line:
            raise McpError("MCP server closed the stream without a response")
        return json.loads(line)

    # ── JSON-RPC ───────────────────────────────────────────────────────────────────────
    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        req = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        resp = self._transport(req)  # type: ignore[misc]
        if resp is None:
            raise McpError(f"no response to {method!r}")
        if resp.get("error"):
            raise McpError(f"{method} error: {resp['error']}")
        return resp.get("result", {})

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._transport({"jsonrpc": "2.0", "method": method, "params": params})  # type: ignore[misc]

    # ── public ─────────────────────────────────────────────────────────────────────────
    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool. Returns the parsed structured result (the JSON-decoded text of a
        ``tools/call`` text-content block, else the raw text, else ``structuredContent``/content).
        Raises :class:`McpError` on a JSON-RPC error or an ``isError`` tool result."""
        self._ensure()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            raise McpError(f"tool {name!r} returned isError: {result.get('content')}")
        return _extract_content(result)

    def list_tools(self) -> list[dict[str, Any]]:
        """The server's declared tool definitions (``tools/list``)."""
        self._ensure()
        return self._rpc("tools/list", {}).get("tools", [])

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()

    def __enter__(self) -> McpStdioClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _extract_content(result: dict[str, Any]) -> Any:
    """MCP ``tools/call`` returns ``{content: [{type:'text', text:...}], ...}``. Return the
    JSON-decoded text of the first text block when it parses as JSON, else the raw text, else
    ``structuredContent``/the content list (a transport-faithful shape for callers to read)."""
    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text", "")
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
    return result.get("structuredContent", content)
