"""BIND-CLEAR-1 (live-caught, 2026-07-22): a per-role binding field could be SET but never CLEARED.

``_provider_env_vars`` writes the per-role api_base only ``if req.endpoint:``, and
``_persist_and_reload_provider`` MERGES into the stored row. So a rebind that legitimately has
no endpoint leaves the PREVIOUS provider's endpoint in place, silently, under the new
provider's name.

Observed: ``generalist_reviewer`` was bound to ``openai_compatible`` at the Azure Foundry
endpoint during a per-model comparison campaign, then rebound to ``composo``/``composo-reward``
with no endpoint. The Azure URL survived the merge, so the reward-model judge called Azure and
every vote came back ``HTTP Error 404: Resource Not Found``. The repair itself caused the
damage, because the API offers no way to say "this provider has no endpoint".

The rule pinned here distinguishes ABSENT from EXPLICITLY EMPTY:

  * field omitted / ``null``  -> leave the stored value alone (today's merge, unchanged)
  * field present and ``""``  -> CLEAR the stored value

Symmetric for ``endpoint`` and ``api_version``, because the same merge stranded a stale
``api_version`` on a role that had moved providers.

Offline: no network, no model calls.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

ROLE = "generalist_reviewer"
AZURE_FOUNDRY = "https://zyng-work-resource.services.ai.azure.com/models"

@pytest.fixture(autouse=True)
def _no_settings_leak(monkeypatch):
    """``_persist_and_reload_provider`` rebuilds EVERY declared field on the council settings
    singleton in place, from a fresh env read. Tests elsewhere in the suite depend on values a
    previous test left on that singleton, so a provider-config test that does not restore it
    silently breaks whatever sorts after it — caught live: this module wiped the Azure deployment
    settings and failed tests/test_grading_context_fields.py two files later, green in isolation
    and red in CI. Snapshot and restore, so ordering can never matter again.
    """
    from lithrim_bench.runtime.council import settings as council_settings

    live = council_settings.settings
    saved = {f: getattr(live, f, None) for f in type(live).model_fields}
    saved_env = dict(os.environ)
    yield
    for f, v in saved.items():
        setattr(live, f, v)
    for k in set(os.environ) - set(saved_env):
        del os.environ[k]
    os.environ.update(saved_env)



@pytest.fixture
def env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    monkeypatch.setattr(bff, "_split_provider_env_vars", lambda v: ({}, v))
    (tmp_path / bff._PROVIDER_ENV_NAME).parent.mkdir(parents=True, exist_ok=True)
    return tmp_path / bff._PROVIDER_ENV_NAME


def _bind(role, provider, model, endpoint=None, api_version=None, key="k"):
    kwargs = dict(plane="grading", provider=provider, api_key=key, model=model, role=role)
    if endpoint is not None:
        kwargs["endpoint"] = endpoint
    if api_version is not None:
        kwargs["api_version"] = api_version
    req = bff.ProviderConfigRequest(**kwargs)
    bff._persist_and_reload_provider(bff._provider_env_vars(req))


def _stored(env_file):
    return bff._parse_env_file(env_file)


def _names():
    return bff._role_binding_env_names(ROLE)


# ── the regression ─────────────────────────────────────────────────────────────


def test_an_explicit_empty_endpoint_clears_a_stale_one(env_file):
    """THE composo 404: openai_compatible@azure, then composo with no endpoint."""
    _bind(ROLE, "openai_compatible", "Mistral-Large-3", endpoint=AZURE_FOUNDRY)
    assert _stored(env_file)[_names()["api_base"]] == AZURE_FOUNDRY

    _bind(ROLE, "composo", "composo-reward", endpoint="")

    assert not _stored(env_file).get(_names()["api_base"]), (
        "composo kept the previous provider's Azure endpoint and will 404"
    )


def test_an_omitted_endpoint_still_merges(env_file):
    """Back-compat: absent means 'leave it alone', which is what every existing caller does.

    Uses composo for the second bind because ``openai_compatible`` legitimately REFUSES a
    missing endpoint — so the merge can only be observed on a provider that permits one.
    """
    _bind(ROLE, "openai_compatible", "Mistral-Large-3", endpoint=AZURE_FOUNDRY)
    _bind(ROLE, "composo", "composo-reward")  # no endpoint key at all

    assert _stored(env_file)[_names()["api_base"]] == AZURE_FOUNDRY, (
        "absent must merge — this is the pre-existing behaviour and the source of the bug, "
        "but changing it silently would break every caller that relies on reuse"
    )


def test_an_explicit_empty_api_version_clears_a_stale_one(env_file):
    """Same merge stranded an api_version on a role that had changed providers."""
    _bind(ROLE, "azure", "gpt-5.4", endpoint="https://a.openai.azure.com",
          api_version="2024-05-01-preview")
    assert _stored(env_file).get(_names()["api_version"])

    _bind(ROLE, "composo", "composo-reward", endpoint="", api_version="")

    assert not _stored(env_file).get(_names()["api_version"])


def test_clearing_then_reading_reports_unset(env_file):
    """The readers must agree with the store — a cleared endpoint is None, not ''."""
    _bind(ROLE, "openai_compatible", "Mistral-Large-3", endpoint=AZURE_FOUNDRY)
    _bind(ROLE, "composo", "composo-reward", endpoint="")

    assert bff._stored_provider_endpoint("composo") is None


# ── nothing else may change ────────────────────────────────────────────────────


def test_setting_an_endpoint_still_works(env_file):
    _bind(ROLE, "openai_compatible", "OpenBioLLM", endpoint="https://api.featherless.ai/v1")

    assert _stored(env_file)[_names()["api_base"]] == "https://api.featherless.ai/v1"


def test_a_provider_level_openai_compatible_still_requires_an_endpoint(env_file):
    """The existing guard: a provider-level connect with no endpoint is a 400, unchanged.
    An explicit empty string must be refused the same way a missing one is — it is not a
    licence to bind a shim with nowhere to call."""
    for endpoint in (None, ""):
        with pytest.raises(ValueError, match="requires `endpoint`"):
            req = bff.ProviderConfigRequest(
                plane="grading", provider="openai_compatible", api_key="k",
                **({} if endpoint is None else {"endpoint": endpoint}),
            )
            bff._provider_env_vars(req)


def test_azure_per_role_still_gets_a_version_when_none_is_given(env_file):
    """CONNECT-AI-AZURE-1: an azure role with NO api_version key still falls back to a real
    one — never empty — because litellm hits the DeploymentNotFound wall without it."""
    _bind(ROLE, "azure", "gpt-5.4", endpoint="https://a.openai.azure.com")

    assert _stored(env_file).get(_names()["api_version"])
