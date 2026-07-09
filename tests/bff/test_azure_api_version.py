"""CONNECT-AI-AZURE-1 (backend) — thread Azure ``api_version`` through every NEW multi-provider path.

The global grading trio threads ``api_version`` (``judges_dspy.py``'s global azure branch); the
per-role grading bind, the chat loop, AND the probe DROPPED it — so a UI-bound Azure judge/chat hit
a litellm api-version / DeploymentNotFound wall. This file proves ``api_version`` now threads from
the connect store → per-role grading bind + chat bind → ``_probe_provider`` (the connect + roles-bind
re-probe), defaulting to ``settings.AZURE_OPENAI_API_VERSION``. The stored value is REUSED at bind
time (no re-entry) — the bind body carries NO key and NO version.

  * A — azure connect WITH ``api_version`` → stores ``AZURE_OPENAI_API_VERSION`` write-only.
  * B — a JUDGE bind to azure → writes ``LITHRIM_LLM_API_VERSION_RISK`` (the REUSED stored version);
        the bind body has NO version/key.
  * C — a ``chat_assistant`` bind to azure → writes ``LITHRIM_CHAT_API_VERSION`` (reused stored).
  * D — ``_probe_provider`` azure forwards ``api_version`` into the litellm kwargs (mock litellm);
        the connect probe + the roles-bind re-probe both pass it. NON-VACUOUS: drop the threading →
        the assertion goes red.
  * E — azure connect WITHOUT ``api_version`` defaults to ``settings.AZURE_OPENAI_API_VERSION``.
  * F — secret hygiene: the typed key/version never appear in any response.

Bare-CE, the probe is MOCKED (no network / $0). Pattern = tests/bff/test_roles_bind.py.
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
def azure_env(tmp_path, monkeypatch):
    """Redirect the sidecars + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton (mirrors tests/bff/test_roles_bind.py::roles_env). The chat + per-role +
    azure-global LITHRIM_*/AZURE_* env vars (which ``_persist_and_reload_provider`` writes to the
    REAL os.environ + mutates onto the live council-settings singleton in place) are snapshotted and
    fully restored so a bind doesn't leak across tests."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.setattr(bff, "_MODELS_REGISTRY_PATH", tmp_path / ".models_registry.json", raising=False)
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)  # ROLE-BINDINGS-DB: force SQLite at tmp
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)

    import importlib
    import os

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("azure_apiver", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    original = council_settings.settings
    _watch = [
        f"LITHRIM_LLM_{kind}_{role}"
        for role in ("RISK", "POLICY", "FAITHFULNESS")
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE", "API_VERSION")
    ] + [
        "LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_KEY",
        "LITHRIM_CHAT_API_BASE", "LITHRIM_CHAT_API_VERSION",
        "LITHRIM_LLM_PROVIDER", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_DEPLOYMENT_COUNCIL",
        "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
    ]
    _settings_snapshot = {f: getattr(original, f, "") for f in _watch if hasattr(original, f)}
    _env_snapshot = {f: os.environ.get(f) for f in _watch}
    try:
        yield tmp_path, ws
    finally:
        council_settings.settings = original
        for f, v in _settings_snapshot.items():
            if hasattr(original, f):
                setattr(original, f, v)
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
    """Patch the provider test-probe so no live LM/API call happens. Captures the api_version kwarg."""
    calls: list[dict] = []

    def _fake_probe(*, plane, provider, api_key, endpoint=None, model=None, role=None, api_version=None):
        calls.append(
            {"plane": plane, "provider": provider, "api_key": api_key, "endpoint": endpoint,
             "model": model, "role": role, "api_version": api_version}
        )
        if not ok:
            return {"ok": False, "error": error or "probe failed"}
        return {"ok": True}

    monkeypatch.setattr(bff, "_probe_provider", _fake_probe)
    return calls


_AZ_ENDPOINT = "https://my.openai.azure.com/"


def _connect_azure(client, secret, *, api_version=None, model="gpt-4.1-deploy"):
    body = {"plane": "grading", "provider": "azure", "api_key": secret,
            "endpoint": _AZ_ENDPOINT, "model": model}
    if api_version is not None:
        body["api_version"] = api_version
    return client.post("/v1/provider/config", json=body)


# ── A: azure connect with api_version stores AZURE_OPENAI_API_VERSION ─────────────────────


def test_azure_connect_with_api_version_stores_it(azure_env, monkeypatch):
    """A: an azure connect WITH an api_version writes AZURE_OPENAI_API_VERSION write-only; the key
    + version never round-trip."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "az-CONNECT-VER-do-not-leak"
    resp = _connect_azure(client, secret, api_version="2024-12-01-preview")
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("AZURE_OPENAI_API_KEY") == secret
    assert env.get("AZURE_OPENAI_ENDPOINT") == _AZ_ENDPOINT
    assert env.get("AZURE_OPENAI_API_VERSION") == "2024-12-01-preview"


def test_azure_connect_without_api_version_keeps_settings_default(azure_env, monkeypatch):
    """E: an azure connect with NO api_version leaves the settings default in force (no clobber to ""
    — the global grading path still threads settings.AZURE_OPENAI_API_VERSION)."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    resp = _connect_azure(client, "az-NOVER", api_version=None)
    assert resp.status_code == 200, resp.text
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    # NOT written empty — the council settings default (2024-10-21) remains authoritative
    assert env.get("AZURE_OPENAI_API_VERSION") in (None, council_settings.settings.AZURE_OPENAI_API_VERSION)
    assert env.get("AZURE_OPENAI_API_VERSION") != ""


# ── B: a JUDGE bind to azure writes LITHRIM_LLM_API_VERSION_RISK (reused stored) ──────────


def test_judge_bind_azure_writes_per_role_api_version(azure_env, monkeypatch):
    """B (the make-or-break): after an azure connect with a stored api_version, a risk_judge bind to
    azure writes LITHRIM_LLM_API_VERSION_RISK REUSING the stored version; the bind body carries NO
    version (and NO key)."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "az-JUDGEBIND-secret"
    assert _connect_azure(client, secret, api_version="2024-11-20").status_code == 200

    bind_body = {"role": "risk_judge", "provider": "azure", "model": "my-gpt-deploy"}
    assert "api_version" not in bind_body and "api_key" not in bind_body
    resp = client.post("/v1/roles/bind", json=bind_body)
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text
    assert "2024-11-20" not in resp.text  # the version stays server-side too

    env = dict(os.environ)  # ROLE-BINDINGS-DB: the binding is readable by build_judge_lm (DB + env)
    assert env.get("LITHRIM_LLM_PROVIDER_RISK") == "azure"
    assert env.get("LITHRIM_LLM_MODEL_RISK") == "my-gpt-deploy"
    assert env.get("LITHRIM_LLM_API_KEY_RISK") == secret
    assert env.get("LITHRIM_LLM_API_BASE_RISK") == _AZ_ENDPOINT
    # the REUSED stored api_version is wired into the per-role binding (no re-entry)
    assert env.get("LITHRIM_LLM_API_VERSION_RISK") == "2024-11-20"


def test_judge_bind_azure_defaults_api_version_when_none_stored(azure_env, monkeypatch):
    """B (default): a judge bind to an azure connected WITHOUT a stored api_version falls back to
    settings.AZURE_OPENAI_API_VERSION (the council default) — never an empty version."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert _connect_azure(client, "az-DEFVER", api_version=None).status_code == 200
    resp = client.post(
        "/v1/roles/bind",
        json={"role": "policy_judge", "provider": "azure", "model": "my-mistral-deploy"},
    )
    assert resp.status_code == 200, resp.text
    env = dict(os.environ)  # ROLE-BINDINGS-DB: the binding is readable by build_judge_lm (DB + env)
    assert env.get("LITHRIM_LLM_API_VERSION_POLICY") == council_settings.settings.AZURE_OPENAI_API_VERSION
    assert env.get("LITHRIM_LLM_API_VERSION_POLICY")  # non-empty


# ── C: a chat_assistant bind to azure writes LITHRIM_CHAT_API_VERSION ─────────────────────


def test_chat_bind_azure_writes_chat_api_version(azure_env, monkeypatch):
    """C: a chat_assistant bind on a connected azure writes LITHRIM_CHAT_API_VERSION (the reused
    stored version) alongside the LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY,API_BASE} contract."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "az-CHATBIND-secret"
    assert _connect_azure(client, secret, api_version="2025-01-01-preview").status_code == 200

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "chat_assistant", "provider": "azure", "model": "my-chat-deploy"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    env = dict(os.environ)  # ROLE-BINDINGS-DB: the binding is readable by build_judge_lm (DB + env)
    assert env.get("LITHRIM_CHAT_PROVIDER") == "azure"
    assert env.get("LITHRIM_CHAT_MODEL") == "my-chat-deploy"
    assert env.get("LITHRIM_CHAT_API_KEY") == secret
    assert env.get("LITHRIM_CHAT_API_BASE") == _AZ_ENDPOINT
    assert env.get("LITHRIM_CHAT_API_VERSION") == "2025-01-01-preview"


# ── D: _probe_provider forwards api_version into the litellm kwargs ───────────────────────


def test_probe_provider_azure_forwards_api_version_to_litellm(azure_env, monkeypatch):
    """D (the probe itself): _probe_provider for azure passes api_version into litellm.completion's
    kwargs — without it the Azure probe fails. MOCK litellm; assert the kwarg. NON-VACUOUS: drop the
    threading and this assertion goes red."""
    captured: dict = {}

    import types

    fake_litellm = types.ModuleType("litellm")

    def _completion(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    fake_litellm.completion = _completion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = bff._probe_provider(
        plane="grading", provider="azure", api_key="az-PROBE",
        endpoint=_AZ_ENDPOINT, model="my-deploy", api_version="2024-09-01-preview",
    )
    assert out == {"ok": True}
    assert captured.get("api_version") == "2024-09-01-preview"
    assert captured.get("api_base") == _AZ_ENDPOINT
    assert captured["model"] == "azure/my-deploy"


def test_probe_provider_azure_defaults_api_version_from_settings(azure_env, monkeypatch):
    """D (default): when api_version is not passed, the azure probe defaults to
    settings.AZURE_OPENAI_API_VERSION — never None (litellm needs a version)."""
    captured: dict = {}

    import types

    fake_litellm = types.ModuleType("litellm")

    def _completion(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    fake_litellm.completion = _completion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    bff._probe_provider(
        plane="grading", provider="azure", api_key="az", endpoint=_AZ_ENDPOINT, model="d",
    )
    assert captured.get("api_version") == council_settings.settings.AZURE_OPENAI_API_VERSION


def test_probe_provider_non_azure_does_not_send_api_version(azure_env, monkeypatch):
    """D (scoping): a NON-azure probe (openai) never sends an api_version kwarg — the threading is
    azure-only (a stray version on the openai path would be an error)."""
    captured: dict = {}

    import types

    fake_litellm = types.ModuleType("litellm")

    def _completion(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    fake_litellm.completion = _completion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    bff._probe_provider(plane="grading", provider="openai", api_key="sk", model="gpt-4o")
    assert "api_version" not in captured


def test_roles_bind_azure_reprobe_passes_api_version(azure_env, monkeypatch):
    """D (the roles-bind re-probe): the bind path re-probes with the stored api_version — the probe
    call receives it (so the bind's own probe doesn't fail on the api-version wall)."""
    tmp_path, ws = azure_env
    calls = _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert _connect_azure(client, "az-REPROBE", api_version="2024-08-01-preview").status_code == 200
    calls.clear()
    resp = client.post(
        "/v1/roles/bind",
        json={"role": "faithfulness_judge", "provider": "azure", "model": "my-llama-deploy"},
    )
    assert resp.status_code == 200, resp.text
    # exactly one re-probe; it carried the reused stored api_version
    azure_probes = [c for c in calls if c["provider"] == "azure"]
    assert azure_probes, "no azure re-probe captured"
    assert azure_probes[-1]["api_version"] == "2024-08-01-preview"
