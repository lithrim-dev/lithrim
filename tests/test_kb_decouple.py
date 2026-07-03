"""KB plane decoupling (release hygiene): the knowledge-base connector must be
environment-configurable, not hardwired to one deployment's catalog.

- ``LITHRIM_KB_BASE_URL`` points the KbRagTool at ANY KB service (default stays the
  historical :8002 when unset — byte-compat).
- ``LITHRIM_KB_NAMESPACE`` sets the default catalog namespace the chat context aid
  queries (default stays "hipaa" when unset — byte-compat with the existing
  normalization test in test_chatbind2_pane.py).

$0/offline — no network, handlers driven with fake ctx objects.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent.tools import kb_context_handler  # noqa: E402

from lithrim_bench.verification.tools import KbRagTool  # noqa: E402


def test_kb_rag_service_honors_env_override(monkeypatch):
    monkeypatch.setenv("LITHRIM_KB_BASE_URL", "http://kb.internal:9999/")
    assert KbRagTool()._service() == "http://kb.internal:9999"


def test_kb_rag_service_default_unchanged_without_env(monkeypatch):
    monkeypatch.delenv("LITHRIM_KB_BASE_URL", raising=False)
    assert KbRagTool()._service() == "http://localhost:8002"


def test_kb_context_default_namespace_honors_env(monkeypatch):
    monkeypatch.setenv("LITHRIM_KB_NAMESPACE", "acme_policies")
    captured: dict = {}

    class _Ctx:
        default_agent = "demo"

        def kb_context(self, **kw):
            captured.update(kw)
            return [{"text": "§ 4.2 ...", "score": 1.0}]

    res = asyncio.run(kb_context_handler(_Ctx(), {"query": "refund policy"}))
    assert captured["namespace"] == "acme_policies"
    assert not res.get("is_error")


def test_kb_context_unreachable_names_the_config_seam(monkeypatch):
    """A down/unconfigured KB must tell the model the KB isn't connected (and how to connect
    one) — not misdiagnose a credential problem — so the agent says so instead of retrying."""
    monkeypatch.delenv("LITHRIM_KB_BASE_URL", raising=False)

    class _Ctx:
        default_agent = "demo"

        def kb_context(self, **kw):
            raise ConnectionError("connection refused")

    res = asyncio.run(kb_context_handler(_Ctx(), {"query": "phi disclosure"}))
    assert res.get("is_error")
    msg = str(res)
    assert "LITHRIM_KB_BASE_URL" in msg
    assert "do not retry" in msg.lower() or "not connected" in msg.lower()
