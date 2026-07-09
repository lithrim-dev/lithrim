"""MODEL-REGISTRY-1a (backend) — the configured-model pool + capability-aware catalog.

A configured model becomes a first-class, reusable, capability-aware entity (the LiteLLM
``model_list`` pattern), decoupled from the judge role. This is the diverse-council thesis
(GPT/Mistral/Llama catch different errors) handed to the user: the user registers models into a
pool, each capability-annotated (esp. ``logprobs`` → calibrated confidence), then *binds* a role
to a pool entry instead of re-typing provider/model/key.

Reuses Build A's secret hygiene (``tests/bff/test_provider_config.py``): a read-only test-probe
gates the write; the key is written ONLY to the gitignored repo-root ``.provider_env`` (a
namespaced, write-only var) — never SQLite/manifest/the response/logs/the ``.models_registry.json``.

  * A — ``GET /v1/models/catalog`` returns presets with a ``logprobs`` flag per model (gpt ✓, claude ✗).
  * B — ``POST /v1/models`` (passing probe) → 200; metadata + capabilities stored; key NOT in the
        response, NOT in ``.models_registry.json``; key persisted WRITE-ONLY (read back via env file).
  * C — ``POST /v1/models`` (failing probe) → 400; nothing written.
  * D — ``GET /v1/models`` lists the pool, NEVER a key; ``DELETE`` removes the entry + its key.
  * E — ``capabilities_for("openai","gpt-4o")["logprobs"] is True`` and ``(...,"claude-3-5-sonnet")`` is False.
  * F — ``POST /v1/models/{id}/bind {role}`` writes the role's env so ``build_judge_lm`` reads it
        (mock the LM; assert the env; no restart).

Bare-CE, the probe is MOCKED (no network). Pattern = ``tests/bff/test_provider_config.py``.
"""

from __future__ import annotations

import json
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
def registry_env(tmp_path, monkeypatch):
    """Redirect ``.provider_env`` + ``.models_registry.json`` + the audit DB at tmp_path and isolate
    os.environ + the council settings singleton, so the test reads the on-disk write without touching
    the real repo root or leaking env mutations into the rest of the suite."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.setattr(bff, "_MODELS_REGISTRY_PATH", tmp_path / ".models_registry.json", raising=False)

    import importlib
    import os

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("model_registry", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    # ``_persist_and_reload_provider`` mutates the live council-settings singleton IN PLACE (and no
    # longer reassigns it — PROVIDER-CENTER-A) + sets the REAL os.environ. Snapshot the LLM provider
    # fields (global + the per-role LITHRIM_LLM_* bind writes) and os.environ keys, and fully restore
    # them so a bind doesn't leak into another test (e.g. test_byok_openai's azure regression).
    original = council_settings.settings
    _llm_fields = [
        f"LITHRIM_LLM_{kind}_{role}"
        for role in ("RISK", "POLICY", "FAITHFULNESS")
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE")
    ] + ["LITHRIM_LLM_PROVIDER", "OPENAI_API_KEY", "OPENAI_MODEL_POLICY", "OPENAI_MODEL_RISK",
         "OPENAI_MODEL_FAITHFULNESS"]
    _settings_snapshot = {f: getattr(original, f, "") for f in _llm_fields}
    _env_snapshot = {f: os.environ.get(f) for f in _llm_fields}
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


def _install_probe(monkeypatch, *, ok, error=None):
    """Patch the provider test-probe so no live LM/API call happens. Returns the captured calls."""
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


# A ──────────────────────────────────────────────────────────────────────────────────────────────
def test_catalog_returns_presets_with_logprobs_flag(registry_env):
    """A: GET /v1/models/catalog returns curated presets per provider, each with a ``logprobs``
    flag (the load-bearing capability). gpt-* → True (calibrated confidence); claude-* → False."""
    tmp_path, ws = registry_env
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    providers = body["providers"]

    # OpenAI presets carry a logprobs flag; at least one gpt model is logprobs-True
    openai_models = providers["openai"]
    assert openai_models, "no openai presets"
    by_model = {m["model"]: m for m in openai_models}
    assert "gpt-4o" in by_model
    assert by_model["gpt-4o"]["logprobs"] is True
    for m in openai_models:
        assert "logprobs" in m and isinstance(m["logprobs"], bool)
        assert "context_window" in m
        assert "cost_tier" in m

    # Anthropic presets are logprobs-False (confidence dark)
    anthropic_models = providers["anthropic"]
    assert anthropic_models, "no anthropic presets"
    for m in anthropic_models:
        assert m["logprobs"] is False

    # Azure is deployment-name-based — a model catalog doesn't apply
    azure = providers["azure"]
    assert azure.get("models") == []
    assert "note" in azure and azure["note"]


# E ──────────────────────────────────────────────────────────────────────────────────────────────
def test_capabilities_for_infers_logprobs_by_family():
    """E: capabilities_for infers a CUSTOM (non-preset) model's flags by family — gpt-*/o* are
    OpenAI-family (logprobs True); claude-* are Anthropic-family (logprobs False)."""
    assert bff.capabilities_for("openai", "gpt-4o")["logprobs"] is True
    assert bff.capabilities_for("openai", "gpt-4o-mini")["logprobs"] is True
    assert bff.capabilities_for("openai", "gpt-some-future-model")["logprobs"] is True
    assert bff.capabilities_for("anthropic", "claude-3-5-sonnet-latest")["logprobs"] is False
    assert bff.capabilities_for("anthropic", "claude-some-future")["logprobs"] is False
    # a capabilities dict always carries the three honest fields
    caps = bff.capabilities_for("openai", "gpt-4o")
    assert {"logprobs", "context_window", "cost_tier"} <= set(caps)


# B ──────────────────────────────────────────────────────────────────────────────────────────────
def test_register_clean_probe_stores_metadata_key_write_only(registry_env, monkeypatch):
    """B: POST /v1/models (passing probe) → 200; metadata + capabilities stored in
    ``.models_registry.json``; the key is NOT in the response, NOT in the registry json; the key IS
    persisted write-only to ``.provider_env`` under a namespaced var (read back via the env file)."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-model-DEADBEEF-do-not-leak"
    resp = client.post(
        "/v1/models",
        json={"id": "gpt4o-prod", "provider": "openai", "model": "gpt-4o", "api_key": secret},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "gpt4o-prod"
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"
    assert body["capabilities"]["logprobs"] is True
    assert body["last_tested"]
    assert secret not in resp.text  # the key NEVER round-trips

    # metadata + capabilities are in the registry json — but the key is NOT
    reg_path = bff._MODELS_REGISTRY_PATH
    assert reg_path.exists(), "the registry sidecar was not written"
    reg_text = reg_path.read_text()
    assert "gpt4o-prod" in reg_text
    assert "logprobs" in reg_text
    assert secret not in reg_text, "the key leaked into .models_registry.json"

    # the key IS persisted WRITE-ONLY to .provider_env under a namespaced var
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    namespaced = bff._model_key_var("gpt4o-prod")
    assert env.get(namespaced) == secret, "the key was not persisted write-only to the env file"


# C ──────────────────────────────────────────────────────────────────────────────────────────────
def test_register_failed_probe_writes_nothing(registry_env, monkeypatch):
    """C (non-vacuity): a failing probe → 400 and NOTHING written — proving the B write is
    conditional on a clean probe."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=False, error="invalid api key")
    client = TestClient(bff.app)

    secret = "sk-model-SHOULD-NOT-PERSIST"
    resp = client.post(
        "/v1/models",
        json={"id": "bad-model", "provider": "openai", "model": "gpt-4o", "api_key": secret},
    )
    assert resp.status_code == 400, resp.text
    assert secret not in resp.text

    # nothing persisted: no registry entry, no key in the env file
    reg_path = bff._MODELS_REGISTRY_PATH
    if reg_path.exists():
        assert "bad-model" not in reg_path.read_text()
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert bff._model_key_var("bad-model") not in env
    for v in env.values():
        assert secret != v


# D ──────────────────────────────────────────────────────────────────────────────────────────────
def test_list_never_returns_key_and_delete_removes_entry_and_key(registry_env, monkeypatch):
    """D: GET /v1/models lists the pool, NEVER a key; DELETE removes the entry + its key."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-model-LIST-DELETE-CHECK"
    reg = client.post(
        "/v1/models",
        json={"id": "haiku-cheap", "provider": "anthropic", "model": "claude-3-5-haiku-latest",
              "api_key": secret},
    )
    assert reg.status_code == 200, reg.text

    listing = client.get("/v1/models")
    assert listing.status_code == 200, listing.text
    models = listing.json()["models"]
    ids = {m["id"] for m in models}
    assert "haiku-cheap" in ids
    assert secret not in listing.text  # the pool NEVER leaks a key
    entry = next(m for m in models if m["id"] == "haiku-cheap")
    assert "api_key" not in entry and "key" not in entry
    assert entry["capabilities"]["logprobs"] is False  # claude → confidence dark

    # the key is on disk write-only before the delete
    env_before = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env_before.get(bff._model_key_var("haiku-cheap")) == secret

    deleted = client.delete("/v1/models/haiku-cheap")
    assert deleted.status_code == 200, deleted.text

    after = client.get("/v1/models").json()["models"]
    assert "haiku-cheap" not in {m["id"] for m in after}
    # the key is gone from the env file too
    env_after = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert bff._model_key_var("haiku-cheap") not in env_after


def test_delete_missing_model_is_404(registry_env, monkeypatch):
    """D (edge): deleting an unknown id → 404, not a 500."""
    tmp_path, ws = registry_env
    client = TestClient(bff.app)
    resp = client.delete("/v1/models/nope")
    assert resp.status_code == 404, resp.text


# F ──────────────────────────────────────────────────────────────────────────────────────────────
def test_bind_writes_role_env_so_build_judge_lm_reads_it(registry_env, monkeypatch):
    """F (the make-or-break): POST /v1/models/{id}/bind {role} maps the pool entry's
    {provider, model, key} to the role's env vars via the SAME mechanism as Build A's
    _provider_env_vars + _persist_and_reload_provider, so build_judge_lm routes that role to the
    chosen model with NO restart. The LM construction itself is not invoked; we assert the env."""
    tmp_path, ws = registry_env
    # CLEAN slate — no key/provider in the live singleton or env
    monkeypatch.setattr(council_settings.settings, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(council_settings.settings, "LITHRIM_LLM_PROVIDER", "azure", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITHRIM_LLM_PROVIDER", raising=False)
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-model-BIND-NO-RESTART"
    reg = client.post(
        "/v1/models",
        json={"id": "policy-gpt", "provider": "openai", "model": "gpt-4o-mini", "api_key": secret},
    )
    assert reg.status_code == 200, reg.text

    bound = client.post("/v1/models/policy-gpt/bind", json={"role": "policy_judge"})
    assert bound.status_code == 200, bound.text
    assert secret not in bound.text  # the bind response never leaks the key

    # os.environ updated → a freshly-spawned subprocess grade inherits it
    import os

    assert os.environ.get("OPENAI_API_KEY") == secret
    assert os.environ.get("LITHRIM_LLM_PROVIDER") == "openai"
    # the per-role model var build_judge_lm reads (policy_judge → OPENAI_MODEL_POLICY)
    assert os.environ.get("OPENAI_MODEL_POLICY") == "gpt-4o-mini"

    # the in-process council settings singleton refreshed → build_judge_lm reads it with NO restart
    from lithrim_bench.runtime.council import judges_dspy

    assert secret == judges_dspy.settings.OPENAI_API_KEY
    assert str(judges_dspy.settings.LITHRIM_LLM_PROVIDER).lower() == "openai"


def test_bind_unknown_model_is_404(registry_env, monkeypatch):
    """F (edge): binding an unknown model id → 404."""
    tmp_path, ws = registry_env
    client = TestClient(bff.app)
    resp = client.post("/v1/models/nope/bind", json={"role": "policy_judge"})
    assert resp.status_code == 404, resp.text


def test_bind_persists_in_registry_entry(registry_env, monkeypatch):
    """F (provenance): a bind records which role(s) the entry is bound to in the non-secret
    registry sidecar — so 1c (the UI) can show 'gpt4o-prod → policy_judge'."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    client.post(
        "/v1/models",
        json={"id": "risk-gpt", "provider": "openai", "model": "gpt-4o", "api_key": "sk-x"},
    )
    client.post("/v1/models/risk-gpt/bind", json={"role": "risk_judge"})
    reg = json.loads(bff._MODELS_REGISTRY_PATH.read_text())
    entry = next(m for m in reg["models"] if m["id"] == "risk-gpt")
    assert "risk_judge" in entry.get("bound_roles", [])
