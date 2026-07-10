"""FIRST-CONTACT-1: /v1/roles/bindings carries an honest `chat_ready` — can the composer's next
message actually be answered? Mirrors the chat runtime's own dispatch: a litellm chat provider is
configured, OR the SDK path is importable (host installs). The shell's first-paint "Connect AI"
signpost renders off this, so it must be false ONLY when a message would genuinely fail.

$0/offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def test_configured_litellm_chat_is_ready(monkeypatch):
    monkeypatch.setenv("LITHRIM_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("LITHRIM_CHAT_API_KEY", "sk-test")
    assert bff._chat_ready() is True


def test_no_provider_and_no_sdk_is_not_ready(monkeypatch):
    monkeypatch.delenv("LITHRIM_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Simulate the Docker image: the [agent] extra absent → the SDK import fails.
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    assert bff._chat_ready() is False


def test_bindings_endpoint_carries_chat_ready(monkeypatch):
    monkeypatch.setattr(bff, "_read_role_bindings", lambda: {})
    monkeypatch.setattr(bff, "_connected_providers", lambda: [])
    monkeypatch.setattr(bff, "_chat_ready", lambda: False)
    out = bff.roles_bindings_endpoint()
    assert out["chat_ready"] is False
