"""PROVIDER-CENTER-A (backend, BFF) — broader provider types + cross-provider-per-role bind.

The registry plane (Build A + MR-1a/1b/1c) is reused as substrate; the NET-NEW is:
  * the ``ProviderConfigRequest.provider`` Literal broadens to gemini / bedrock / openai_compatible;
  * ``_provider_env_vars`` writes the GENERIC per-role binding
    ``LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_<ROLE>`` when a per-role provider is given;
  * ``_probe_provider`` routes the new types via litellm;
  * the registry **bind** carries the entry's {provider, model, endpoint, key} into the role's
    per-role vars — so role A→gemini + role B→openai coexist (the cross-provider council).

  * D — POST /v1/provider/config (provider="gemini" + role) → probes via litellm + writes the
        per-role provider env; POST /v1/models accepts a gemini/bedrock/openai-compatible model.
  * E — POST /v1/models/{id}/bind {role} for a gemini entry writes LITHRIM_LLM_PROVIDER_<ROLE>=gemini
        + the per-role key/model — and a DIFFERENT role bound to an openai entry COEXISTS.
  * F — secret hygiene (non-vacuous): the per-role key is write-only on ``.provider_env``, NEVER in
        any response.

Bare-CE, the probe + litellm are MOCKED (no network / $0). Pattern = ``tests/bff/test_model_registry.py``
+ ``tests/bff/test_provider_config.py``.
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
def registry_env(tmp_path, monkeypatch):
    """Redirect the sidecars + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton (the pattern from tests/bff/test_model_registry.py)."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.setattr(bff, "_MODELS_REGISTRY_PATH", tmp_path / ".models_registry.json", raising=False)

    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("provider_center", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    original = council_settings.settings
    try:
        yield tmp_path, ws
    finally:
        council_settings.settings = original
        importlib.reload(ws_mod)


def _install_probe(monkeypatch, *, ok=True, error=None):
    calls: list[dict] = []

    def _fake_probe(*, plane, provider, api_key, endpoint=None, model=None, role=None):
        calls.append(
            {"plane": plane, "provider": provider, "api_key": api_key,
             "endpoint": endpoint, "model": model, "role": role}
        )
        if not ok:
            return {"ok": False, "error": error or "probe failed"}
        return {"ok": True}

    monkeypatch.setattr(bff, "_probe_provider", _fake_probe)
    return calls


# ── D: the broadened provider types ────────────────────────────────────────────────────


def test_provider_config_request_literal_broadened():
    """D: the ProviderConfigRequest.provider Literal now admits gemini/bedrock/openai_compatible
    (alongside the existing openai/azure/anthropic)."""
    for prov in ("gemini", "bedrock", "openai_compatible"):
        req = bff.ProviderConfigRequest(
            plane="grading", provider=prov, api_key="k", model="m", role="risk_judge"
        )
        assert req.provider == prov
    # a bogus provider is still rejected by the Literal
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        bff.ProviderConfigRequest(plane="grading", provider="not-a-provider", api_key="k")


def test_provider_config_gemini_with_role_writes_per_role_env(registry_env, monkeypatch):
    """D: POST /v1/provider/config provider=gemini + role probes (mocked) + writes the per-role
    binding LITHRIM_LLM_{PROVIDER,MODEL,API_KEY}_<ROLE> — never the global LITHRIM_LLM_PROVIDER."""
    tmp_path, ws = registry_env
    calls = _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "gk-gemini-DEADBEEF-do-not-leak"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "gemini", "api_key": secret,
              "model": "gemini-1.5-pro", "role": "policy_judge"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text  # never round-trips

    # the probe was routed with the gemini provider
    assert calls and calls[-1]["provider"] == "gemini"

    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_PROVIDER_POLICY") == "gemini"
    assert env.get("LITHRIM_LLM_MODEL_POLICY") == "gemini-1.5-pro"
    assert env.get("LITHRIM_LLM_API_KEY_POLICY") == secret
    # the GLOBAL provider selector is NOT touched by a per-role gemini config
    assert "LITHRIM_LLM_PROVIDER" not in env or env.get("LITHRIM_LLM_PROVIDER") != "gemini"


def test_register_gemini_bedrock_openai_compatible_models(registry_env, monkeypatch):
    """D: POST /v1/models accepts a gemini / bedrock / openai-compatible model (probe mocked)."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    for entry_id, prov, model in (
        ("gemini-pro", "gemini", "gemini-1.5-pro"),
        ("bedrock-claude", "bedrock", "anthropic.claude-3-sonnet-v1"),
        ("local-vllm", "openai_compatible", "llama-3.1-70b"),
    ):
        body = {"id": entry_id, "provider": prov, "model": model, "api_key": f"k-{entry_id}"}
        if prov == "openai_compatible":
            body["endpoint"] = "https://my-vllm.local/v1"
        resp = client.post("/v1/models", json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["provider"] == prov
        assert f"k-{entry_id}" not in resp.text

    listed = {m["id"] for m in client.get("/v1/models").json()["models"]}
    assert {"gemini-pro", "bedrock-claude", "local-vllm"} <= listed


def test_probe_routes_new_types_via_litellm(registry_env, monkeypatch):
    """D: _probe_provider routes gemini/bedrock/openai_compatible through litellm.completion with
    the right provider/model prefix (litellm MOCKED — $0/offline)."""
    import types

    seen: dict = {}

    def _fake_completion(*, model, messages, max_tokens, temperature, api_key=None, api_base=None):
        seen["model"] = model
        seen["api_key"] = api_key
        seen["api_base"] = api_base
        return {"ok": True}

    fake_litellm = types.SimpleNamespace(completion=_fake_completion)
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    out = bff._probe_provider(
        plane="grading", provider="gemini", api_key="gk", model="gemini-1.5-pro", role="policy_judge"
    )
    assert out["ok"] is True
    assert seen["model"] == "gemini/gemini-1.5-pro"
    assert seen["api_key"] == "gk"

    out = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk", model="llama-3.1-70b",
        endpoint="https://my-vllm.local/v1", role="risk_judge",
    )
    assert out["ok"] is True
    assert seen["model"] == "openai/llama-3.1-70b"
    assert seen["api_base"] == "https://my-vllm.local/v1"


# ── E: the cross-provider council — role A→gemini, role B→openai COEXIST ────────────────


def test_bind_gemini_and_openai_roles_coexist(registry_env, monkeypatch):
    """E (the make-or-break): bind policy_judge→a gemini entry + risk_judge→an openai entry; both
    per-role bindings coexist in the env so build_judge_lm routes a TRUE cross-provider council."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    gem_key = "gk-policy-DEADBEEF"
    oai_key = "sk-risk-CAFEBABE"
    assert client.post(
        "/v1/models",
        json={"id": "gemini-pro", "provider": "gemini", "model": "gemini-1.5-pro",
              "api_key": gem_key},
    ).status_code == 200
    assert client.post(
        "/v1/models",
        json={"id": "risk-gpt", "provider": "openai", "model": "gpt-4o", "api_key": oai_key},
    ).status_code == 200

    b1 = client.post("/v1/models/gemini-pro/bind", json={"role": "policy_judge"})
    assert b1.status_code == 200, b1.text
    b2 = client.post("/v1/models/risk-gpt/bind", json={"role": "risk_judge"})
    assert b2.status_code == 200, b2.text

    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    # role A → gemini
    assert env.get("LITHRIM_LLM_PROVIDER_POLICY") == "gemini"
    assert env.get("LITHRIM_LLM_MODEL_POLICY") == "gemini-1.5-pro"
    assert env.get("LITHRIM_LLM_API_KEY_POLICY") == gem_key
    # role B → openai — COEXISTS, did not clobber role A
    assert env.get("LITHRIM_LLM_PROVIDER_RISK") == "openai"
    assert env.get("LITHRIM_LLM_MODEL_RISK") == "gpt-4o"
    assert env.get("LITHRIM_LLM_API_KEY_RISK") == oai_key

    # and the live council settings singleton sees both per-role providers (no restart)
    from lithrim_bench.runtime.council import judges_dspy

    assert judges_dspy.settings.LITHRIM_LLM_PROVIDER_POLICY == "gemini"
    assert judges_dspy.settings.LITHRIM_LLM_PROVIDER_RISK == "openai"


def test_bind_cross_provider_builds_a_mixed_council(registry_env, monkeypatch):
    """E (end-to-end): after the two cross-provider binds, build_judge_lm constructs the mixed
    council — policy→gemini/…, risk→openai/… — reading the refreshed singleton (dspy.LM MOCKED)."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    client.post(
        "/v1/models",
        json={"id": "gemini-pro", "provider": "gemini", "model": "gemini-1.5-pro", "api_key": "gk"},
    )
    client.post(
        "/v1/models",
        json={"id": "risk-gpt", "provider": "openai", "model": "gpt-4o", "api_key": "sk"},
    )
    client.post("/v1/models/gemini-pro/bind", json={"role": "policy_judge"})
    client.post("/v1/models/risk-gpt/bind", json={"role": "risk_judge"})

    import dspy

    captured: dict = {}

    class _FakeLM:
        def __init__(self, model, **kwargs):
            self.model = model
            self.kwargs = kwargs

    monkeypatch.setattr(dspy, "LM", _FakeLM)

    from lithrim_bench.runtime.council import judges_dspy as J

    captured["policy"] = J.build_judge_lm("policy_judge")
    captured["risk"] = J.build_judge_lm("risk_judge")
    assert captured["policy"].model == "gemini/gemini-1.5-pro"
    assert captured["policy"].kwargs["logprobs"] is False  # gemini → confidence dark
    assert captured["risk"].model == "openai/gpt-4o"
    assert captured["risk"].kwargs["logprobs"] is True  # openai → calibrated


# ── F: secret hygiene (non-vacuous) — the per-role key is write-only ────────────────────


def test_per_role_key_is_write_only_never_in_a_response(registry_env, monkeypatch):
    """F: a per-role key written via config + bind lands on .provider_env but appears in NO
    response body (config response, models list, bind response, status). NON-VACUOUS: the key IS
    on disk (so a missing-write false-pass can't sneak through)."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "gk-SECRET-MUST-NOT-LEAK-anywhere"

    cfg = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "gemini", "api_key": secret,
              "model": "gemini-1.5-pro", "role": "policy_judge"},
    )
    assert cfg.status_code == 200, cfg.text
    assert secret not in cfg.text

    reg = client.post(
        "/v1/models",
        json={"id": "gemini-pro", "provider": "gemini", "model": "gemini-1.5-pro",
              "api_key": secret},
    )
    assert reg.status_code == 200, reg.text
    assert secret not in reg.text

    bound = client.post("/v1/models/gemini-pro/bind", json={"role": "policy_judge"})
    assert bound.status_code == 200, bound.text
    assert secret not in bound.text

    assert secret not in client.get("/v1/models").text
    assert secret not in client.get("/v1/provider/status").text

    # NON-VACUOUS: the per-role key IS persisted write-only on .provider_env
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_API_KEY_POLICY") == secret
    # and the per-model namespaced var carries it too (registry hygiene)
    assert env.get(bff._model_key_var("gemini-pro")) == secret
    # the model key var must NEVER land in the non-secret registry sidecar
    assert secret not in bff._MODELS_REGISTRY_PATH.read_text()


def test_existing_openai_global_config_unchanged(registry_env, monkeypatch):
    """F/B (regression): a NO-role openai config still writes the GLOBAL openai vars byte-identically
    (the per-role binding is strictly additive — the existing global path is untouched)."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": "sk-global", "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text
    env = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env.get("LITHRIM_LLM_PROVIDER") == "openai"
    assert env.get("OPENAI_API_KEY") == "sk-global"
    # no per-role vars written for a global (no-role) config
    assert "LITHRIM_LLM_PROVIDER_RISK" not in env
    assert "LITHRIM_LLM_PROVIDER_POLICY" not in env
