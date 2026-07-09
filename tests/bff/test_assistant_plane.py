"""CONV-RUNTIME-1 (the un-gated assistant plane) — ``POST /v1/provider/config`` for the chat.

Today the assistant plane accepts ONLY ``provider="anthropic"`` (the Agent-SDK chat). CONV-RUNTIME-1
un-gates it: a non-anthropic provider (openai/azure/gemini/bedrock/openai_compatible) writes the chat
env-var contract ``LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY,API_BASE}`` so the litellm conversation loop
drives the chat for that provider. ``anthropic`` stays byte-identical (``ANTHROPIC_API_KEY`` +
``LITHRIM_CHAT_PROVIDER=anthropic`` — the SDK path keeps working).

Secret hygiene (non-vacuous): the chat ``api_key`` is WRITE-ONLY on ``.provider_env`` — the typed key
string is ABSENT from the JSON response. The probe is MOCKED (bare-CE, $0/offline). Pattern =
``tests/bff/test_provider_config.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

from lithrim_bench.runtime.council import settings as council_settings  # noqa: E402


@pytest.fixture()
def provider_env(tmp_path, monkeypatch):
    """Redirect ``.provider_env`` + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton (the pattern from tests/bff/test_provider_config.py). The chat env vars
    (LITHRIM_CHAT_*) + the anthropic key are snapshotted + restored so no config leaks across tests."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)  # ROLE-BINDINGS-DB: force SQLite at tmp
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)

    import importlib
    import os

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("assistant_cfg", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    original = council_settings.settings
    _chat_vars = [
        "LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_KEY",
        "LITHRIM_CHAT_API_BASE", "ANTHROPIC_API_KEY",
    ]
    _env_snapshot = {f: os.environ.get(f) for f in _chat_vars}
    try:
        yield tmp_path, ws
    finally:
        council_settings.settings = original
        for f, v in _env_snapshot.items():
            if v is None:
                os.environ.pop(f, None)
            else:
                os.environ[f] = v
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _install_probe(monkeypatch, *, ok=True, error=None):
    calls: list[dict] = []

    def _fake_probe(*, plane, provider, api_key, endpoint=None, model=None, role=None, api_version=None):
        calls.append({"plane": plane, "provider": provider, "api_key": api_key,
                      "endpoint": endpoint, "model": model, "role": role, "api_version": api_version})
        return {"ok": True} if ok else {"ok": False, "error": error or "probe failed"}

    monkeypatch.setattr(bff, "_probe_provider", _fake_probe)
    return calls


def test_assistant_openai_writes_the_chat_env_contract_key_write_only(provider_env, monkeypatch):
    """plane=assistant + provider=openai + model + key → writes LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY};
    the key is WRITE-ONLY on .provider_env and ABSENT from the JSON response (non-vacuous)."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-chat-openai-DO-NOT-LEAK"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "openai", "api_key": secret, "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert secret not in resp.text  # the chat key NEVER round-trips (secret hygiene)

    written = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert os.environ.get("LITHRIM_CHAT_PROVIDER") == "openai"  # binding (config DB + env)
    assert os.environ.get("LITHRIM_CHAT_MODEL") == "gpt-4o"
    assert written["LITHRIM_CHAT_API_KEY"] == secret  # the KEY is write-only on disk
    # an OpenAI chat provider does NOT write ANTHROPIC_API_KEY (that is the SDK path only)
    assert "ANTHROPIC_API_KEY" not in written


def test_assistant_anthropic_stays_byte_compatible(provider_env, monkeypatch):
    """plane=assistant + provider=anthropic → ANTHROPIC_API_KEY + LITHRIM_CHAT_PROVIDER=anthropic
    (byte-identical to today — the SDK / BYO-Claude path keeps working unchanged)."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-ant-DO-NOT-LEAK"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "anthropic", "api_key": secret},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    written = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert os.environ.get("LITHRIM_CHAT_PROVIDER") == "anthropic"  # binding (config DB + env)
    assert written["ANTHROPIC_API_KEY"] == secret  # the SDK key is write-only on disk
    # the anthropic SDK path uses ANTHROPIC_API_KEY, not the LITHRIM_CHAT_API_KEY var
    assert "LITHRIM_CHAT_API_KEY" not in written


def test_assistant_azure_requires_an_endpoint(provider_env, monkeypatch):
    """plane=assistant + provider=azure WITHOUT an endpoint → 400 before any probe/write (the chat
    loop needs the api_base to reach an Azure deployment)."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "azure", "api_key": "az", "model": "gpt-4.1"},
    )
    assert resp.status_code == 400, resp.text


def test_assistant_openai_compatible_requires_an_endpoint(provider_env, monkeypatch):
    """plane=assistant + provider=openai_compatible WITHOUT an endpoint → 400 (the api_base is
    required to reach a local/vLLM OpenAI-shaped server)."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "openai_compatible", "api_key": "k", "model": "m"},
    )
    assert resp.status_code == 400, resp.text


def test_assistant_azure_writes_the_api_base(provider_env, monkeypatch):
    """plane=assistant + provider=azure + endpoint → writes LITHRIM_CHAT_API_BASE so the litellm
    loop reaches the Azure deployment; key still write-only + absent from the response."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    secret = "az-chat-secret-DO-NOT-LEAK"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "azure", "api_key": secret,
              "model": "gpt-4.1", "endpoint": "https://my.openai.azure.com/"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text
    written = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert os.environ.get("LITHRIM_CHAT_PROVIDER") == "azure"  # binding (config DB + env)
    assert os.environ.get("LITHRIM_CHAT_API_BASE") == "https://my.openai.azure.com/"
    assert written["LITHRIM_CHAT_API_KEY"] == secret  # the KEY is write-only on disk


def test_assistant_non_anthropic_requires_a_model(provider_env, monkeypatch):
    """plane=assistant + a non-anthropic provider WITHOUT a model → 400 (the chat model is required
    to call litellm.completion)."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "assistant", "provider": "openai", "api_key": "k"},
    )
    assert resp.status_code == 400, resp.text


def test_assistant_non_anthropic_probes_via_litellm_not_anthropic(provider_env, monkeypatch):
    """``_probe_provider``: an assistant+<non-anthropic> probes via the litellm branch, not the
    anthropic ping. We assert the routing on the REAL _probe_provider by patching litellm.completion
    + anthropic so neither makes a network call; the litellm branch must be the one that fires."""
    tmp_path, ws = provider_env
    import litellm

    litellm_called = {"v": False}

    def _fake_completion(**kwargs):
        litellm_called["v"] = True
        return object()

    monkeypatch.setattr(litellm, "completion", _fake_completion)
    out = bff._probe_provider(plane="assistant", provider="openai", api_key="k", model="gpt-4o")
    assert out["ok"] is True
    assert litellm_called["v"] is True  # the litellm branch fired (not the anthropic ping)
