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
def registry_env(tmp_path, monkeypatch):
    """Redirect the sidecars + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton (the pattern from tests/bff/test_model_registry.py). The per-role
    LITHRIM_LLM_* env vars (which ``_persist_and_reload_provider`` writes to the REAL os.environ +
    mutates onto the live council-settings singleton IN PLACE) are snapshotted and fully restored so
    no per-role binding leaks across tests (the cross-provider binds touch many env keys)."""
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
    ws = ws_mod.create_workspace("provider_center", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    # ``_persist_and_reload_provider`` mutates the live council-settings singleton IN PLACE + sets the
    # REAL os.environ (the no-restart path), neither of which monkeypatch tracks. Snapshot the per-role
    # LITHRIM_LLM_* fields + os.environ keys the cross-provider binds touch and fully restore them so
    # nothing leaks across tests.
    original = council_settings.settings
    _per_role_fields = [
        f"LITHRIM_LLM_{kind}_{role}"
        for role in ("RISK", "POLICY", "FAITHFULNESS")
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE")
    ]
    _settings_snapshot = {
        f: getattr(original, f, "")
        for f in [*_per_role_fields, "LITHRIM_LLM_PROVIDER", "OPENAI_API_KEY"]
    }
    _env_snapshot = {f: os.environ.get(f) for f in [*_per_role_fields, "LITHRIM_LLM_PROVIDER"]}
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

    env = dict(os.environ)  # ROLE-BINDINGS-DB: the binding is readable by build_judge_lm (DB + env)
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

    # DRYRUN-2026-07-03: the probe is parameter-minimal now (no temperature override — modern
    # reasoning models reject it); the fake accepts-without-requiring it.
    def _fake_completion(*, model, messages, max_tokens, temperature=None, api_key=None, api_base=None):
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

    env = dict(os.environ)  # ROLE-BINDINGS-DB: bindings readable by build_judge_lm (DB + env)
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
    # DRYRUN-2026-07-03: a confidence-dark provider gets NO logprobs param at all (litellm
    # rejects the param's presence, even as False) + drop_params so per-model-unsupported
    # params (e.g. gpt-5.5's temperature) are dropped instead of erroring the judge.
    assert "logprobs" not in captured["policy"].kwargs
    assert captured["policy"].kwargs["drop_params"] is True
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


# ── REPRO-1 R2a: AUTHORED roles bind like pack roles (the 3→N unlock) ────────────────────

_AUTHORED_ENV_KEYS = [
    f"LITHRIM_LLM_{kind}_REVIEWER_GPT41"
    for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE", "API_VERSION")
]


@pytest.fixture()
def _authored_env_cleanup():
    yield
    for k in _AUTHORED_ENV_KEYS:
        os.environ.pop(k, None)


@pytest.fixture()
def _authored_role_declared(monkeypatch):
    """Declare `reviewer_gpt41` as a pack lens role — the state a JudgeBuilder splice leaves
    behind (POST /v1/judges writes production_judges/lenses); binding validates against it
    (the typo-guard: an UNDECLARED role still 422s — test_roles_bind_unknown_role_422)."""
    import lithrim_bench.harness.pack as pack_mod

    real = pack_mod.pack_lenses

    def _with_authored(pack=None):
        return {**real(pack), "reviewer_gpt41": ("FABRICATED_CLAIM",)}

    monkeypatch.setattr(pack_mod, "pack_lenses", _with_authored)


def test_bind_an_authored_role_via_the_model_registry(registry_env, monkeypatch, _authored_env_cleanup, _authored_role_declared):
    """R2a end-to-end: a JudgeBuilder-authored role (NOT the v2 trio) binds via the registry —
    the generic per-role env lands under the sanitized suffix, the role_bindings DB carries it,
    GET /v1/roles/bindings lists it, and build_judge_lm resolves the per-role provider for it
    (dspy.LM mocked). The N-clone council's binding plane."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert client.post(
        "/v1/models",
        json={"id": "clone-41", "provider": "openai", "model": "gpt-4.1", "api_key": "sk-clone"},
    ).status_code == 200
    r = client.post("/v1/models/clone-41/bind", json={"role": "reviewer_gpt41"})
    assert r.status_code == 200, r.text

    env = dict(os.environ)
    assert env.get("LITHRIM_LLM_PROVIDER_REVIEWER_GPT41") == "openai"
    assert env.get("LITHRIM_LLM_MODEL_REVIEWER_GPT41") == "gpt-4.1"
    assert env.get("LITHRIM_LLM_API_KEY_REVIEWER_GPT41") == "sk-clone"

    # the role_bindings DB + the bindings read surface carry the authored role
    from lithrim_bench.harness import role_bindings as _rb

    stored = _rb.load_bindings(db_path=bff._role_bindings_db_path())
    assert (stored.get("reviewer_gpt41") or {}).get("provider") == "openai"
    listed = client.get("/v1/roles/bindings").json()
    roles = listed.get("roles") or listed
    assert (roles.get("reviewer_gpt41") or {}).get("provider") == "openai"

    # runtime: build_judge_lm routes the authored role to its own provider (per-role override)
    import dspy

    class _FakeLM:
        def __init__(self, model, **kwargs):
            self.model = model
            self.kwargs = kwargs

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    from lithrim_bench.runtime.council import judges_dspy as J

    lm = J.build_judge_lm("reviewer_gpt41")
    assert lm.model == "openai/gpt-4.1"
    assert lm.kwargs["logprobs"] is True


def test_roles_bind_authored_role_never_clobbers_the_chat_binding(registry_env, monkeypatch, _authored_env_cleanup, _authored_role_declared):
    """R2a regression (the live bug): /v1/roles/bind dispatched judge-vs-chat by membership in the
    HARDCODED trio, so an authored role fell into the CHAT branch and silently overwrote
    LITHRIM_CHAT_*. An authored role must bind as a JUDGE; the chat binding stays untouched."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    # store the provider key once (Section 1), then bind the authored role (Section 2)
    assert client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": "sk-shared"},
    ).status_code == 200
    r = client.post(
        "/v1/roles/bind",
        json={"role": "reviewer_gpt41", "provider": "openai", "model": "gpt-4.1"},
    )
    assert r.status_code == 200, r.text

    env_file = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert env_file.get("LITHRIM_CHAT_PROVIDER") is None  # chat untouched
    assert os.environ.get("LITHRIM_LLM_PROVIDER_REVIEWER_GPT41") == "openai"


def test_bind_rejects_a_malformed_role_id(registry_env, monkeypatch):
    """The role becomes an env-var suffix — a malformed id (spaces/uppercase/symbols) is refused
    at the boundary (422), never written into the env plane."""
    tmp_path, ws = registry_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": "sk-shared"},
    )
    for bad in ("Bad Role", "UPPER", "role;rm", "9starts_with_digit"):
        r = client.post(
            "/v1/roles/bind", json={"role": bad, "provider": "openai", "model": "gpt-4.1"}
        )
        assert r.status_code == 422, (bad, r.status_code, r.text)


def test_legacy_trio_suffixes_are_preserved():
    """Back-compat: the v2 trio keeps its SHORT env suffixes (RISK/POLICY/FAITHFULNESS) so every
    existing .provider_env / role_bindings row keeps working; an authored role gets its sanitized
    uppercase id."""
    from lithrim_bench.runtime.council import judges_dspy as J

    assert J._role_provider_keys("risk_judge")["provider"] == "LITHRIM_LLM_PROVIDER_RISK"
    assert (
        J._role_provider_keys("reviewer_gpt41")["provider"]
        == "LITHRIM_LLM_PROVIDER_REVIEWER_GPT41"
    )
    assert bff._role_env_suffix("faithfulness_judge") == "FAITHFULNESS"
    assert bff._role_env_suffix("reviewer_gpt41") == "REVIEWER_GPT41"


# ── F8-PROVIDER: a reward-model eval service (composo) as a judge provider ─────────────


def test_provider_config_composo_literal():
    """F8: the provider Literal admits composo (a reward-model judge provider)."""
    req = bff.ProviderConfigRequest(
        plane="grading", provider="composo", api_key="k", role="risk_judge"
    )
    assert req.provider == "composo"


def test_provider_config_composo_with_role_writes_per_role_env(registry_env, monkeypatch):
    """F8: POST /v1/provider/config provider=composo + role probes (mocked) + writes the generic
    per-role binding (PROVIDER=composo + the per-role SECRET) — build_judge_lm's dispatch input."""
    tmp_path, ws = registry_env
    calls = _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "ck-composo-DEADBEEF-do-not-leak"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "composo", "api_key": secret, "role": "risk_judge"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text  # never round-trips

    assert calls and calls[-1]["provider"] == "composo"
    env = dict(os.environ)
    assert env.get("LITHRIM_LLM_PROVIDER_RISK") == "composo"
    assert env.get("LITHRIM_LLM_API_KEY_RISK") == secret
    # the GLOBAL provider selector is NOT touched by a per-role composo config
    assert env.get("LITHRIM_LLM_PROVIDER") != "composo"


def test_provider_config_composo_global_stores_reusable_secret():
    """F8: a provider-level composo connect (no role) stores the reusable global secret, like the
    other per-role-only providers (gemini/bedrock/openai_compatible/anthropic)."""
    env = bff._provider_env_vars(
        bff.ProviderConfigRequest(plane="grading", provider="composo", api_key="ck-global")
    )
    assert env.get("COMPOSO_API_KEY") == "ck-global"
    assert "LITHRIM_LLM_PROVIDER" not in env  # never a global selector


def test_probe_composo_routes_via_the_reward_endpoint(monkeypatch):
    """F8: the read-only probe exercises the SAME reward wire the judge grades through — a trivial
    message pair scored; ok iff a numeric score comes back; a transport error → ok=False, never a
    raise."""
    import lithrim_bench.runtime.council.reward_lm as rlm

    seen: list[tuple[str, dict, dict]] = []

    def _fake_transport(url, headers, payload):
        seen.append((url, headers, payload))
        return {"score": 0.9, "explanation": "polite"}

    monkeypatch.setattr(rlm, "_http_transport", _fake_transport)
    out = bff._probe_provider(plane="grading", provider="composo", api_key="ck-probe")
    assert out == {"ok": True}
    assert seen and seen[0][0].endswith("/api/v1/evals/reward")
    assert seen[0][1]["API-Key"] == "ck-probe"

    def _boom(url, headers, payload):
        raise RuntimeError("network down")

    monkeypatch.setattr(rlm, "_http_transport", _boom)
    out = bff._probe_provider(plane="grading", provider="composo", api_key="ck-probe")
    # CONNECT-AI-COMPAT-1: the probe's error contract is the exception type name LEADING, then
    # the provider's message one-line/bounded with the api key REDACTED (_probe_error) — the WHY
    # reaches the user without the secret; the same shape every other provider branch returns
    assert out["ok"] is False and out["error"] == "RuntimeError: network down"
    assert "ck-probe" not in out["error"]
