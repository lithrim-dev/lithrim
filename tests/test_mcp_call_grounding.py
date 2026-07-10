"""TOOL-AUTHOR-1 (Stage 2c): the generic `mcp_call` grounding executor.

Any authored MCP tool (web-scraper, terminology, KB) wired into a judge's flag, generically — no
per-tool Python. Authority tiers decide the effect:
  - advisory      -> attach evidence, NEVER flip (the withstands-gate weighs it; the moat: the
                     agent narrates, the floor decides);
  - corroborated  -> clear the finding ONLY on a positive match, never by silence.
Graceful-absent is non-negotiable: an unresolvable/unreachable tool leaves the finding standing.

$0/offline: `plugins.resolve_tool` + `McpStdioClient` are mocked (no real MCP process).
"""

from __future__ import annotations

from lithrim_bench.harness import grounding
from lithrim_bench.harness.ontology import VerificationContractDecl
from lithrim_bench.harness.plugins import PluginManifest

_FINDING = {"code": "UNSUPPORTED_ASSERTION", "detail": "the sky is green"}
_CASE = {"case_id": "c1"}


def _decl(params):
    return VerificationContractDecl(
        flag_code="UNSUPPORTED_ASSERTION", question="grounded?",
        contract_type="mcp_call", params=params, version="v1",
    )


def _patch(monkeypatch, *, manifest, result=None, raises=False):
    """Stub resolve_tool to a stdio-MCP manifest and McpStdioClient to a fake transport."""
    monkeypatch.setattr(grounding_plugins(), "resolve_tool", lambda tool_id, **k: manifest)

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def call_tool(self, name, arguments=None):
            if raises:
                raise RuntimeError("MCP server unreachable")
            return result

        def close(self):
            pass

    import lithrim_bench.verification.mcp_client as mc

    monkeypatch.setattr(mc, "McpStdioClient", FakeClient)


def grounding_plugins():
    from lithrim_bench.harness import plugins

    return plugins


_MANIFEST = PluginManifest(
    id="my_scraper", kind="tool", transport="service", implements="tool.mcp_server",
    service={"mcp": {"command": "scraper", "args": ["mcp"]}},
)


def test_registered_as_a_core_suppress_executor():
    assert "mcp_call" in grounding._CONTRACT_EXECUTORS


def test_advisory_attaches_evidence_and_never_flips(monkeypatch):
    _patch(monkeypatch, manifest=_MANIFEST, result={"snippet": "found it"})
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "my_scraper", "call": "scrape", "authority": "advisory"})
    )
    v = c.check(_FINDING, _CASE)
    assert v.disproved is False  # advisory NEVER clears
    assert v.evidence and "found it" in v.evidence


def test_corroborated_clears_only_on_positive_match(monkeypatch):
    _patch(monkeypatch, manifest=_MANIFEST, result={"supported": True})
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "my_scraper", "call": "check", "authority": "corroborated", "match": "supported"})
    )
    assert c.check(_FINDING, _CASE).disproved is True


def test_corroborated_does_not_clear_on_negative(monkeypatch):
    _patch(monkeypatch, manifest=_MANIFEST, result={"supported": False})
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "my_scraper", "call": "check", "authority": "corroborated", "match": "supported"})
    )
    assert c.check(_FINDING, _CASE).disproved is False  # never cleared by a non-match


def test_absent_tool_is_graceful(monkeypatch):
    _patch(monkeypatch, manifest=None)  # resolve_tool -> None
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "ghost", "call": "scrape", "authority": "corroborated", "match": "x"})
    )
    v = c.check(_FINDING, _CASE)
    assert v.disproved is False  # finding STANDS when the tool is unavailable


def test_unreachable_tool_is_graceful(monkeypatch):
    _patch(monkeypatch, manifest=_MANIFEST, raises=True)
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "my_scraper", "call": "scrape", "authority": "corroborated", "match": "x"})
    )
    assert c.check(_FINDING, _CASE).disproved is False  # no 500, no silent flip
