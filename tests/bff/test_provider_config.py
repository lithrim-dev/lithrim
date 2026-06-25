"""CE-PROVIDER-BACKEND (Build A) — ``POST /v1/provider/config`` + ``GET /v1/provider/status``.

The CE's core build: let a user configure their LLM provider key IN-APP. Mirrors the proven
``connector/config`` secret hygiene (``app.py:3060``): a read-only test-probe gates the write;
on a clean probe the key is written ONLY to a gitignored repo-root ``.provider_env`` (never to
SQLite, the manifest, the response, or the logs); the audit record carries the key REDACTED.

The make-or-break (SPEC §3.1): a key written via the endpoint takes effect on the **next grade
with NO BFF restart** — both for subprocess grades (which inherit ``os.environ``) and for the
in-process council (whose ``build_judge_lm`` reads the cached ``settings`` singleton). So the
endpoint sets ``os.environ`` AND refreshes the council ``settings`` singleton.

  * A  — a passing (mocked) probe → 200; the key is written to ``.provider_env``; not in the response.
  * B  — a failing probe → 4xx; nothing written.
  * C  — the key NEVER appears in the audit record / SQLite / response / logs.
  * D  — (the make-or-break) after a POST, the council ``settings`` singleton + ``os.environ`` carry
         the new key/provider with NO restart — what ``build_judge_lm`` reads.
  * E  — ``GET /v1/provider/status`` reflects configured/not, never leaking the key.

Bare-CE, the probe is MOCKED (no network). Pattern = ``tests/bff/test_connector_config.py``.
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
def provider_env(tmp_path, monkeypatch):
    """Redirect ``.provider_env`` + the audit DB at tmp_path and isolate os.environ + the council
    settings singleton, so the test reads the on-disk write without touching the real repo root or
    leaking env mutations into the rest of the suite."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)

    # an isolated audit DB so the redaction assertion reads exactly this test's records
    import importlib
    import os

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("provider_cfg", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    # snapshot + restore the council settings singleton (test D mutates it). ``_persist_and_reload_
    # provider`` mutates the live singleton IN PLACE (PROVIDER-CENTER-A: no longer reassigned) + sets
    # the REAL os.environ, so also restore the LLM provider fields/env so a config doesn't leak across.
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


def test_provider_config_clean_probe_writes_key_only_to_provider_env(provider_env, monkeypatch):
    """A: a passing probe → 200; the key lands in ``.provider_env`` and NEVER in the response."""
    tmp_path, ws = provider_env
    monkeypatch.setattr(council_settings.settings, "OPENAI_API_KEY", "", raising=False)
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-provider-DEADBEEF-do-not-leak"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret, "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["plane"] == "grading"
    assert body["provider"] == "openai"
    assert body["last_tested"]
    assert secret not in resp.text  # the key NEVER round-trips

    env_file = bff._PROVIDER_ENV_PATH
    assert env_file.exists(), "the key was not written to .provider_env"
    env_text = env_file.read_text()
    assert f"OPENAI_API_KEY={secret}" in env_text
    assert "LITHRIM_LLM_PROVIDER=openai" in env_text


def test_provider_config_failed_probe_writes_nothing(provider_env, monkeypatch):
    """B (non-vacuity): a failing probe → 4xx and NOTHING written — proving the A write is
    conditional on a clean probe."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=False, error="invalid api key")
    client = TestClient(bff.app)

    secret = "sk-provider-SHOULD-NOT-PERSIST"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret},
    )
    assert resp.status_code in (400, 401, 502), resp.text
    assert secret not in resp.text

    env_file = bff._PROVIDER_ENV_PATH
    if env_file.exists():
        assert secret not in env_file.read_text(), "the key was written despite a failed probe"


def test_provider_config_key_never_in_audit_or_sqlite(provider_env, monkeypatch):
    """C: the key NEVER appears in the audit record, any SQLite DB, or the response."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-provider-AUDIT-LEAK-CHECK"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text

    # the audit record exists for the action but carries no key
    import json as _json

    from lithrim_bench.harness.audit import AuditLog

    records = AuditLog(db_path=ws.config_db).query()
    assert any(r.get("action") == "provider_config" for r in records), "no audit record written"
    for r in records:
        assert secret not in _json.dumps(r, default=str), "the key leaked into the audit record"

    # the key never reaches any SQLite DB (the config plane)
    for db in ws.dir.rglob("*.sqlite"):
        assert secret.encode() not in db.read_bytes(), f"the key leaked into {db}"


def test_provider_config_takes_effect_with_no_restart(provider_env, monkeypatch):
    """D — the make-or-break: after a POST, the council ``settings`` singleton + ``os.environ`` carry
    the new key/provider with NO restart, so the NEXT in-process grade's ``build_judge_lm`` reads it
    (subprocess grades inherit os.environ). The LM construction itself is not invoked here."""
    tmp_path, ws = provider_env
    # start from a CLEAN slate: no key in the live singleton or env
    monkeypatch.setattr(council_settings.settings, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(council_settings.settings, "LITHRIM_LLM_PROVIDER", "azure", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITHRIM_LLM_PROVIDER", raising=False)
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "sk-provider-NO-RESTART-PROOF"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret, "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text

    # 1) os.environ updated → a freshly-spawned subprocess grade inherits it
    import os

    assert os.environ.get("OPENAI_API_KEY") == secret
    assert os.environ.get("LITHRIM_LLM_PROVIDER") == "openai"

    # 2) the in-process council settings singleton refreshed → build_judge_lm reads the new key
    #    with NO restart (this is exactly the field build_judge_lm reads at judges_dspy.py:260/267)
    from lithrim_bench.runtime.council import judges_dspy

    assert secret == judges_dspy.settings.OPENAI_API_KEY
    assert str(judges_dspy.settings.LITHRIM_LLM_PROVIDER).lower() == "openai"


def test_provider_status_reflects_config_without_leaking_key(provider_env, monkeypatch):
    """E: GET /v1/provider/status reflects configured/not and NEVER leaks the key."""
    tmp_path, ws = provider_env
    client = TestClient(bff.app)

    # before any config: the grading plane is not configured
    pre = client.get("/v1/provider/status")
    assert pre.status_code == 200, pre.text
    pre_body = pre.json()
    assert pre_body["planes"]["grading"]["configured"] is False

    _install_probe(monkeypatch, ok=True)
    secret = "sk-provider-STATUS-LEAK-CHECK"
    cfg = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret, "model": "gpt-4o"},
    )
    assert cfg.status_code == 200, cfg.text

    post = client.get("/v1/provider/status")
    assert post.status_code == 200, post.text
    body = post.json()
    grading = body["planes"]["grading"]
    assert grading["configured"] is True
    assert grading["provider"] == "openai"
    assert grading["model"] == "gpt-4o"
    assert grading["last_tested"]
    assert secret not in post.text  # the key NEVER leaks via status


def test_parse_env_file_skips_a_directory(tmp_path):
    """CE-DOCKER hotfix: a ``docker compose`` bind-mount of a non-existent host file creates the
    target as a DIRECTORY; ``_parse_env_file`` must skip it (the ``is_file`` guard), not raise
    ``IsADirectoryError`` — which crashed BFF startup on a plain ``docker compose up``."""
    d = tmp_path / ".provider_env"
    d.mkdir()
    assert bff._parse_env_file(d) == {}  # no IsADirectoryError


def test_load_provider_env_noop_when_path_is_a_directory(tmp_path, monkeypatch):
    """The startup provider-env loader must not crash when ``.provider_env`` is a directory."""
    d = tmp_path / ".provider_env"
    d.mkdir()
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", d, raising=False)
    bff._load_provider_env()  # must return cleanly, not raise


def test_azure_per_role_deployment_wires_the_heterogeneous_trio(provider_env, monkeypatch):
    """Connect AI → Advanced (Azure): provider=azure + role=policy_judge + model=<deployment> must
    write AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3 so the council routes the policy judge to that
    Azure deployment (the heterogeneous GPT/Mistral/Llama trio). Previously the Azure branch set only
    the key + endpoint and DROPPED the per-role deployment."""
    tmp_path, ws = provider_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    secret = "az-secret-do-not-leak"
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "azure", "api_key": secret,
              "endpoint": "https://my.openai.azure.com/", "role": "policy_judge",
              "model": "my-mistral-large-deployment"},
    )
    assert resp.status_code == 200, resp.text
    written = bff._parse_env_file(bff._PROVIDER_ENV_PATH)
    assert written["LITHRIM_LLM_PROVIDER"] == "azure"
    assert written["AZURE_OPENAI_ENDPOINT"] == "https://my.openai.azure.com/"
    assert written["AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3"] == "my-mistral-large-deployment"
    assert secret not in resp.text  # the key never leaks


def test_azure_endpoint_required(provider_env, monkeypatch):
    """provider=azure without an endpoint → 400 before any probe/write (mirrors _provider_env_vars)."""
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)
    resp = client.post("/v1/provider/config",
                       json={"plane": "grading", "provider": "azure", "api_key": "az"})
    assert resp.status_code == 400, resp.text
