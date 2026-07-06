"""NEW-G1 (backend) — a per-role ``endpoint`` + ``api_version`` rides the ``/v1/roles/bind`` body.

Before this, a per-role Azure / OpenAI-compatible judge could ONLY use the provider's GLOBAL stored
endpoint + api_version (``_stored_provider_endpoint`` / ``_stored_provider_api_version``). Two judges
on the SAME provider but DIFFERENT Azure deployments (distinct endpoints / api-versions) were
un-authorable from the UI without re-editing the connect env. NEW-G1 widens ``RoleBindRequest`` with
OPTIONAL ``endpoint`` + ``api_version`` so a bind can OVERRIDE the stored global per role; the runtime
already reads ``LITHRIM_LLM_API_BASE_<ROLE>`` / ``LITHRIM_LLM_API_VERSION_<ROLE>`` (``judges_dspy.py``).

  * A — a per-role ``endpoint`` in the bind body writes ``LITHRIM_LLM_API_BASE_<ROLE>`` (NOT the
        stored global); the re-probe receives the per-role endpoint.
  * B — a per-role ``api_version`` writes ``LITHRIM_LLM_API_VERSION_<ROLE>`` (NOT the stored global).
  * C — omitting both FALLS BACK to the stored global (back-compat: the existing binds are unchanged).
  * D — secret hygiene: neither the endpoint nor the version is a secret, but the stored key still
        never round-trips.

Bare-CE, the probe is MOCKED (no network / $0). Reuses the azure_env fixture + probe stub from
tests/bff/test_azure_api_version.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

_BFF = Path(__file__).resolve().parents[2] / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.bff.test_azure_api_version import (  # noqa: E402
    _AZ_ENDPOINT,
    _connect_azure,
    _install_probe,
    azure_env,  # noqa: F401 — pytest fixture, imported for reuse
)

_PER_ROLE_ENDPOINT = "https://role-specific.openai.azure.com/"
_PER_ROLE_VERSION = "2025-03-01-preview"


def test_per_role_endpoint_overrides_stored_global(azure_env, monkeypatch):  # noqa: F811
    """A: a bind carrying its own ``endpoint`` writes LITHRIM_LLM_API_BASE_RISK to THAT endpoint,
    not the global _AZ_ENDPOINT stored at connect."""
    tmp_path, ws = azure_env
    calls = _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert _connect_azure(client, "az-PERROLE-EP", api_version="2024-11-20").status_code == 200
    calls.clear()

    resp = client.post(
        "/v1/roles/bind",
        json={
            "role": "risk_judge", "provider": "azure", "model": "my-deploy",
            "endpoint": _PER_ROLE_ENDPOINT,
        },
    )
    assert resp.status_code == 200, resp.text

    env = dict(os.environ)
    assert env.get("LITHRIM_LLM_API_BASE_RISK") == _PER_ROLE_ENDPOINT
    assert env.get("LITHRIM_LLM_API_BASE_RISK") != _AZ_ENDPOINT
    # the re-probe ran against the per-role endpoint, not the stored global
    azure_probes = [c for c in calls if c["provider"] == "azure"]
    assert azure_probes and azure_probes[-1]["endpoint"] == _PER_ROLE_ENDPOINT


def test_per_role_api_version_overrides_stored_global(azure_env, monkeypatch):  # noqa: F811
    """B: a bind carrying its own ``api_version`` writes LITHRIM_LLM_API_VERSION_RISK to THAT
    version, not the stored 2024-11-20."""
    tmp_path, ws = azure_env
    calls = _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert _connect_azure(client, "az-PERROLE-VER", api_version="2024-11-20").status_code == 200
    calls.clear()

    resp = client.post(
        "/v1/roles/bind",
        json={
            "role": "risk_judge", "provider": "azure", "model": "my-deploy",
            "api_version": _PER_ROLE_VERSION,
        },
    )
    assert resp.status_code == 200, resp.text

    env = dict(os.environ)
    assert env.get("LITHRIM_LLM_API_VERSION_RISK") == _PER_ROLE_VERSION
    assert env.get("LITHRIM_LLM_API_VERSION_RISK") != "2024-11-20"
    azure_probes = [c for c in calls if c["provider"] == "azure"]
    assert azure_probes and azure_probes[-1]["api_version"] == _PER_ROLE_VERSION


def test_omitting_endpoint_and_version_falls_back_to_stored_global(azure_env, monkeypatch):  # noqa: F811
    """C (back-compat): a bind with NEITHER field reuses the stored global endpoint + version —
    the existing binds are byte-identical to before NEW-G1."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    assert _connect_azure(client, "az-FALLBACK", api_version="2024-11-20").status_code == 200
    resp = client.post(
        "/v1/roles/bind",
        json={"role": "policy_judge", "provider": "azure", "model": "my-deploy"},
    )
    assert resp.status_code == 200, resp.text

    env = dict(os.environ)
    assert env.get("LITHRIM_LLM_API_BASE_POLICY") == _AZ_ENDPOINT
    assert env.get("LITHRIM_LLM_API_VERSION_POLICY") == "2024-11-20"


def test_per_role_endpoint_and_version_not_secret_but_key_stays(azure_env, monkeypatch):  # noqa: F811
    """D: the endpoint + version are non-secret (they may appear), but the stored key still never
    round-trips in the response."""
    tmp_path, ws = azure_env
    _install_probe(monkeypatch, ok=True)
    client = TestClient(bff.app)

    secret = "az-PERROLE-KEY-do-not-leak"
    assert _connect_azure(client, secret, api_version="2024-11-20").status_code == 200
    resp = client.post(
        "/v1/roles/bind",
        json={
            "role": "faithfulness_judge", "provider": "azure", "model": "my-deploy",
            "endpoint": _PER_ROLE_ENDPOINT, "api_version": _PER_ROLE_VERSION,
        },
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text
