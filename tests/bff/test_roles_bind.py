"""CONNECT-AI-CONSOLIDATE-1 (backend) — provider-level connect + the bind-reuses-stored-key enabler.

The 2-section Connect AI panel needs a backend that (1) lets a provider be connected with JUST a key
(no role, no model) for the broadened set, and (2) binds an already-configured provider's model to ONE
consumer REUSING the stored key — never re-keying. The bind request body carries NO key; the response
carries NO key.

  * A — provider-level connect: POST /v1/provider/config {provider:"gemini", api_key} (NO role) stores
        GEMINI_API_KEY write-only, 200, key absent from the response. (Was a 400 before — the genuine RED.)
  * B — POST /v1/roles/bind {role:"risk_judge", provider:"openai", model:"gpt-4o"} AFTER an openai connect
        writes LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_RISK reusing the stored OPENAI_API_KEY; the
        request body has NO api_key field; the response has NO key.
  * C — POST /v1/roles/bind {role:"chat_assistant", provider:"openai", ...} writes
        LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY}; for anthropic it ALSO writes ANTHROPIC_API_KEY.
  * D — 422s (non-vacuous): bind to an UN-connected provider; unknown role; azure/openai_compatible bind
        with no stored endpoint.
  * E — GET /v1/roles/bindings returns the 4 consumers' {provider, model} + the connected-provider list,
        NO key.
  * F — secret hygiene (non-vacuous): the distinctive typed key string is absent from every /v1/roles/*
        and /v1/provider/status response, while the key IS persisted on .provider_env.

Bare-CE, the probe is MOCKED (no network / $0). Pattern = tests/bff/test_provider_config.py.
"""

from __future__ import annotations

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
def roles_env(tmp_path, monkeypatch):
    """Redirect the sidecars + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton (the pattern from tests/bff/test_provider_center_types.py). The chat +
    per-role LITHRIM_* env vars (which ``_persist_and_reload_provider`` writes to the REAL
    os.environ + mutates onto the live council-settings singleton in place) are snapshotted and
    fully restored so a bind doesn't leak across tests."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.setattr(bff, "_MODELS_REGISTRY_PATH", tmp_path / ".models_registry.json", raising=False)
    # ROLE-BINDINGS-DB: the non-secret binding now persists to the config DB resolved from the
    # sidecar dir. Force SQLite (no managed PG) + the local sidecar dir so a bind writes a tmp db.
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)

    import importlib
    import os

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("roles_bind", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    original = council_settings.settings
    _per_role_fields = [
        f"LITHRIM_LLM_{kind}_{role}"
        for role in ("RISK", "POLICY", "FAITHFULNESS")
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE")
    ]
    _chat_fields = [
        "LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_KEY", "LITHRIM_CHAT_API_BASE",
    ]
    # ``_persist_and_reload_provider`` writes to the REAL os.environ + mutates the live
    # council-settings singleton IN PLACE (the no-restart path), neither of which monkeypatch
    # tracks. A role-less azure/openai connect sets the GLOBAL azure deployment vars + endpoint; an
    # openai connect sets the per-role OPENAI_MODEL_* vars. Snapshot EVERY field a connect/bind in
    # this file can touch and fully restore them so nothing leaks across tests (it bit
    # tests/test_byok_openai.py::test_azure_path_unchanged via AZURE_OPENAI_DEPLOYMENT_COUNCIL).
    _global_fields = [
        "LITHRIM_LLM_PROVIDER", "OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_COUNCIL", "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3",
        "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
        "OPENAI_MODEL_RISK", "OPENAI_MODEL_POLICY", "OPENAI_MODEL_FAITHFULNESS",
        "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_API_BASE", "AWS_ACCESS_KEY_ID",
    ]
    _watch = [*_per_role_fields, *_chat_fields, *_global_fields]
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
    calls: list[dict] = []

    def _fake_probe(*, plane, provider, api_key, endpoint=None, model=None, role=None, api_version=None):
        calls.append(
            {"plane": plane, "provider": provider, "api_key": api_key,
             "endpoint": endpoint, "model": model, "role": role, "api_version": api_version}
        )
        if not ok:
            return {"ok": False, "error": error or "probe failed"}
        return {"ok": True}

    monkeypatch.setattr(bff, "_probe_provider", _fake_probe)
    return calls


def _connect(client, provider, secret, **extra):
    body = {"plane": "grading", "provider": provider, "api_key": secret, **extra}
    if provider == "anthropic":
        body["plane"] = "assistant"
    return client.post("/v1/provider/config", json=body)


# ── A: provider-level connect (no role) for the broadened set ───────────────────────────


def test_provider_level_connect_gemini_no_role_stores_key(roles_env, monkeypatch):
    """A (the genuine RED): a provider-level connect for gemini WITHOUT a role used to 400. It now
    stores GEMINI_API_KEY write-only + a 200; the key is absent from the response."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "gk-PROVIDER-LEVEL-DEADBEEF-do-not-leak"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "gemini", "api_key": secret},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text  # never round-trips

    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("GEMINI_API_KEY") == secret
    # no per-role binding written for a provider-level (role-less) connect
    assert "LITHRIM_LLM_PROVIDER_POLICY" not in env
    assert "LITHRIM_LLM_PROVIDER_RISK" not in env


def test_provider_level_connect_openai_global_byte_identical(roles_env, monkeypatch):
    """A (regression): a NO-role openai connect still writes the GLOBAL openai vars exactly as
    before — the relaxation is strictly additive for the per-role-only providers."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    resp = _connect(client, "openai", "sk-global-openai", model="gpt-4o")
    assert resp.status_code == 200, resp.text
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_PROVIDER") == "openai"
    assert env.get("OPENAI_API_KEY") == "sk-global-openai"


# ── B: bind a JUDGE role reusing the stored key (body has NO key) ────────────────────────


def test_roles_bind_judge_reuses_stored_openai_key(roles_env, monkeypatch):
    """B (the make-or-break): after an openai connect, POST /v1/roles/bind {risk_judge, openai,
    gpt-4o} writes LITHRIM_LLM_{PROVIDER,MODEL,API_KEY}_RISK REUSING the stored OPENAI_API_KEY. The
    request body has NO api_key field; the response has NO key."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-openai-STORED-CAFEBABE"
    assert _connect(client, "openai", secret, model="gpt-4o").status_code == 200

    # the bind body carries NO api_key (keys entered once)
    bind_body = {"role": "risk_judge", "provider": "openai", "model": "gpt-4o"}
    assert "api_key" not in bind_body
    resp = client.post("/v1/roles/bind", json=bind_body)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"ok": True, "role": "risk_judge", "provider": "openai", "model": "gpt-4o"} or (
        body.get("ok") and body.get("role") == "risk_judge"
    )
    assert secret not in resp.text  # NO key in the response

    # ROLE-BINDINGS-DB: the NON-SECRET binding lands in the config DB; the key stays in the file.
    from lithrim_bench.harness import role_bindings as rb

    binding = rb.load_bindings(db_path=bff._role_bindings_db_path())["risk_judge"]
    assert binding["provider"] == "openai"
    assert binding["model"] == "gpt-4o"
    assert "api_key" not in binding
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_API_KEY_RISK") == secret  # the REUSED stored key (no re-keying)
    assert "LITHRIM_LLM_MODEL_RISK" not in env  # the binding moved OUT of the loose file


def test_roles_bind_judge_reuses_azure_endpoint(roles_env, monkeypatch):
    """B: an azure provider-level connect stores the endpoint; a judge bind reuses BOTH the stored
    key AND the stored endpoint into the per-role api_base — no re-keying, no re-endpointing."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "az-STORED-secret"
    assert _connect(
        client, "azure", secret, endpoint="https://my.openai.azure.com/", model="gpt-4.1-deploy",
    ).status_code == 200

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "faithfulness_judge", "provider": "azure", "model": "my-llama-deploy"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    from lithrim_bench.harness import role_bindings as rb

    binding = rb.load_bindings(db_path=bff._role_bindings_db_path())["faithfulness_judge"]
    assert binding["provider"] == "azure"
    assert binding["model"] == "my-llama-deploy"
    assert binding["endpoint"] == "https://my.openai.azure.com/"  # reused stored endpoint
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_API_KEY_FAITHFULNESS") == secret  # key reused, stays in the file


# ── C: bind the chat_assistant role (the compulsory cross-provider chat) ─────────────────


def test_roles_bind_chat_assistant_writes_chat_env(roles_env, monkeypatch):
    """C: a chat_assistant bind on a connected openai writes LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY}
    (the CONV-RUNTIME-1 contract) reusing the stored OPENAI_API_KEY — cross-provider chat."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-openai-CHAT-STORED"
    assert _connect(client, "openai", secret, model="gpt-4o").status_code == 200

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "chat_assistant", "provider": "openai", "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    # the chat_assistant binding stays file-based (loop.py reads .provider_env directly)
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_CHAT_PROVIDER") == "openai"
    assert env.get("LITHRIM_CHAT_MODEL") == "gpt-4o"
    assert env.get("LITHRIM_CHAT_API_KEY") == secret


def test_roles_bind_chat_assistant_anthropic_also_writes_anthropic_key(roles_env, monkeypatch):
    """C: a chat_assistant bind on a connected anthropic ALSO writes ANTHROPIC_API_KEY (the SDK
    path), exactly as the assistant plane does today."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-ant-CHAT-STORED"
    assert _connect(client, "anthropic", secret).status_code == 200

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "chat_assistant", "provider": "anthropic", "model": "claude-3-5-sonnet-latest"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    # the chat_assistant binding stays file-based (loop.py reads .provider_env directly)
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_CHAT_PROVIDER") == "anthropic"
    assert env.get("ANTHROPIC_API_KEY") == secret


# ── D: 422s (non-vacuous) ────────────────────────────────────────────────────────────────


def test_roles_bind_unconnected_provider_422(roles_env, monkeypatch):
    """D: binding a role to a provider with NO stored key → 422 (not connected). Non-vacuous vs the
    happy path: nothing is written."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "risk_judge", "provider": "gemini", "model": "gemini-1.5-pro"},
    )
    assert resp.status_code == 422, resp.text
    from lithrim_bench.harness import role_bindings as rb

    assert "risk_judge" not in rb.load_bindings(db_path=bff._role_bindings_db_path())  # nothing written


def test_roles_bind_unknown_role_422(roles_env, monkeypatch):
    """D: an unknown role → 422."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    assert _connect(client, "openai", "sk-x", model="gpt-4o").status_code == 200

    resp = client.post(
        "/v1/roles/bind",
        json={"role": "not_a_consumer", "provider": "openai", "model": "gpt-4o"},
    )
    assert resp.status_code == 422, resp.text


def test_roles_bind_azure_without_stored_endpoint_422(roles_env, monkeypatch):
    """D: an azure connect can store a key without an endpoint? No — azure requires an endpoint at
    connect. To exercise the bind-side guard we simulate a stored azure key with no endpoint and bind
    → 422 (azure needs a stored endpoint)."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    # write only the azure secret to .provider_env (no AZURE_OPENAI_ENDPOINT) to simulate the gap
    bff._PROVIDER_ENV_PATH.write_text("AZURE_OPENAI_API_KEY=az-no-endpoint\n")
    resp = client.post(
        "/v1/roles/bind",
        json={"role": "policy_judge", "provider": "azure", "model": "my-deploy"},
    )
    assert resp.status_code == 422, resp.text


# ── E: GET /v1/roles/bindings ────────────────────────────────────────────────────────────


def test_roles_bindings_readout(roles_env, monkeypatch):
    """E: GET /v1/roles/bindings returns the 4 consumers' {provider, model} + the connected-provider
    list. After binding risk→openai + chat→anthropic, both show; the others are unbound; NO key."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    sk = "sk-openai-BINDINGS"
    ak = "sk-ant-BINDINGS"
    assert _connect(client, "openai", sk, model="gpt-4o").status_code == 200
    assert _connect(client, "anthropic", ak).status_code == 200
    assert client.post(
        "/v1/roles/bind", json={"role": "risk_judge", "provider": "openai", "model": "gpt-4o"},
    ).status_code == 200
    assert client.post(
        "/v1/roles/bind",
        json={"role": "chat_assistant", "provider": "anthropic", "model": "claude-3-5-sonnet-latest"},
    ).status_code == 200

    resp = client.get("/v1/roles/bindings")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    roles = body["roles"]
    assert roles["risk_judge"] == {"provider": "openai", "model": "gpt-4o"}
    assert roles["chat_assistant"]["provider"] == "anthropic"
    # the unbound judges are present as null/empty consumers
    assert roles["policy_judge"] in (None, {"provider": None, "model": None})
    assert roles["faithfulness_judge"] in (None, {"provider": None, "model": None})
    # the connected-provider list (those with a stored key) — openai + anthropic
    connected = set(body["connected_providers"])
    assert {"openai", "anthropic"} <= connected
    # NO key anywhere
    assert sk not in resp.text
    assert ak not in resp.text


# ── F: secret hygiene (non-vacuous) ──────────────────────────────────────────────────────


def test_stored_key_absent_from_every_roles_and_status_response(roles_env, monkeypatch):
    """F (non-vacuous): a typed key written via connect appears in NO /v1/roles/* or
    /v1/provider/status response, while the key IS on .provider_env (so a missing-write false-pass
    can't sneak through)."""
    tmp_path, ws = roles_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-openai-MUST-NOT-LEAK-anywhere-9z"
    assert _connect(client, "openai", secret, model="gpt-4o").status_code == 200
    bind = client.post(
        "/v1/roles/bind", json={"role": "policy_judge", "provider": "openai", "model": "gpt-4o"},
    )
    assert bind.status_code == 200, bind.text

    assert secret not in bind.text
    assert secret not in client.get("/v1/roles/bindings").text
    assert secret not in client.get("/v1/provider/status").text

    # NON-VACUOUS: the key IS persisted write-only on .provider_env
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("OPENAI_API_KEY") == secret
    assert env.get("LITHRIM_LLM_API_KEY_POLICY") == secret
