"""WS-CRED-1 Defect A (live-caught, 2026-07-22): binding a second ``openai_compatible``
endpoint DESTROYED the first endpoint's stored credential.

``openai_compatible`` is a generic OpenAI-shaped shim fronting arbitrarily many distinct
services, but its stored secret and base URL live in ONE slot keyed by provider id alone
(``_PROVIDER_SECRET_VAR`` / ``_PROVIDER_ENDPOINT_VAR``). The in-code comment justifies the
global write as "additive (the bind reads it back)", which is true for openai/azure/anthropic
— one service each — and false for the shim.

Observed: two services behind the one slot, Azure AI Foundry
(``services.ai.azure.com/models``) and Featherless (``api.featherless.ai/v1``). Binding the
Azure-hosted models overwrote the Featherless key IN PLACE. ``.provider_env`` is write-only
with no history, so the value was unrecoverable; downstream it presented as HTTP 401
"You must be signed in", i.e. indistinguishable from a provider outage.

The property pinned here: a bind for one ``(provider, endpoint)`` must never mutate the stored
credential of a DIFFERENT ``(provider, endpoint)``. Rotation of the SAME pair stays allowed.
Single-endpoint providers keep their existing single slot byte-identically.

Offline: no network, no model calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

FEATHERLESS = "https://api.featherless.ai/v1"
AZURE_FOUNDRY = "https://zyng-work-resource.services.ai.azure.com/models"


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Point the provider plane at a throwaway .provider_env and neutralise the side effects
    of persisting (os.environ + the council settings singleton)."""
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    # the settings-singleton refresh imports the council; irrelevant here and slow
    monkeypatch.setattr(bff, "_split_provider_env_vars", lambda v: ({}, v))
    return tmp_path / bff._PROVIDER_ENV_NAME


def _connect(provider: str, api_key: str, endpoint: str | None = None) -> None:
    """A Section-1 provider connect: no role, just a key (+ endpoint where required)."""
    req = bff.ProviderConfigRequest(
        plane="grading", provider=provider, api_key=api_key, endpoint=endpoint
    )
    bff._persist_and_reload_provider(bff._provider_env_vars(req))


def _stored(env_file: Path) -> dict[str, str]:
    return bff._parse_env_file(env_file)


# ── the regression: two endpoints behind one provider id ──


def test_a_second_endpoint_does_not_destroy_the_first_key(env_file):
    """THE 2026-07-22 loss: Featherless connected, then Azure Foundry, key gone."""
    _connect("openai_compatible", "featherless-key", endpoint=FEATHERLESS)
    _connect("openai_compatible", "azure-foundry-key", endpoint=AZURE_FOUNDRY)

    assert bff._stored_provider_key("openai_compatible", endpoint=FEATHERLESS) == "featherless-key"
    assert (
        bff._stored_provider_key("openai_compatible", endpoint=AZURE_FOUNDRY)
        == "azure-foundry-key"
    )


def test_a_second_endpoint_does_not_destroy_the_first_base_url(env_file):
    _connect("openai_compatible", "featherless-key", endpoint=FEATHERLESS)
    _connect("openai_compatible", "azure-foundry-key", endpoint=AZURE_FOUNDRY)

    assert bff._stored_provider_endpoint("openai_compatible", endpoint=FEATHERLESS) == FEATHERLESS
    assert (
        bff._stored_provider_endpoint("openai_compatible", endpoint=AZURE_FOUNDRY) == AZURE_FOUNDRY
    )


def test_rebinding_the_same_endpoint_rotates_the_key(env_file):
    """Rotation is legitimate and must keep working; only a DIFFERENT pair is protected."""
    _connect("openai_compatible", "old-key", endpoint=FEATHERLESS)
    _connect("openai_compatible", "rotated-key", endpoint=FEATHERLESS)

    assert bff._stored_provider_key("openai_compatible", endpoint=FEATHERLESS) == "rotated-key"


def test_azure_is_scoped_too(env_file):
    """azure is the other provider carrying an endpoint, so it has the same exposure."""
    _connect("azure", "resource-a-key", endpoint="https://a.cognitiveservices.azure.com/")
    _connect("azure", "resource-b-key", endpoint="https://b.cognitiveservices.azure.com/")

    assert (
        bff._stored_provider_key("azure", endpoint="https://a.cognitiveservices.azure.com/")
        == "resource-a-key"
    )


# ── nothing else may change ──


def test_single_endpoint_providers_keep_one_slot(env_file):
    """anthropic has no endpoint var: one canonical service, one slot, unchanged behaviour."""
    _connect("anthropic", "anthropic-key")

    assert _stored(env_file).get("ANTHROPIC_API_KEY") == "anthropic-key"
    assert bff._stored_provider_key("anthropic") == "anthropic-key"


def test_the_bare_var_still_holds_the_most_recent_connect(env_file):
    """Back-compat: the unscoped var stays the 'last connected' default, so an endpoint-less
    lookup and _connected_providers() behave exactly as before."""
    _connect("openai_compatible", "featherless-key", endpoint=FEATHERLESS)
    _connect("openai_compatible", "azure-foundry-key", endpoint=AZURE_FOUNDRY)

    assert _stored(env_file).get("OPENAI_COMPATIBLE_API_KEY") == "azure-foundry-key"
    assert bff._stored_provider_key("openai_compatible") == "azure-foundry-key"


def test_a_legacy_install_with_only_the_bare_var_still_resolves(env_file):
    """An install that predates scoping has ONLY the bare var. An endpoint-scoped lookup must
    fall back to it rather than reporting the provider unconnected."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("OPENAI_COMPATIBLE_API_KEY=legacy-key\n")

    assert bff._stored_provider_key("openai_compatible", endpoint=FEATHERLESS) == "legacy-key"


def test_connected_providers_still_reports_the_shim(env_file):
    _connect("openai_compatible", "featherless-key", endpoint=FEATHERLESS)

    assert "openai_compatible" in bff._connected_providers()


def test_a_role_bind_reuses_the_key_for_ITS_endpoint(env_file):
    """The wiring half. NEW-G1 lets a role bind name its own endpoint; the reused key must be
    that endpoint's, not whichever provider connect happened to run last. Reading the key before
    resolving the endpoint is what silently handed a role another service's credential."""
    _connect("openai_compatible", "featherless-key", endpoint=FEATHERLESS)
    _connect("openai_compatible", "azure-foundry-key", endpoint=AZURE_FOUNDRY)

    # a role binding explicitly at Featherless must get the Featherless key
    resolved_endpoint = FEATHERLESS
    assert (
        bff._stored_provider_key("openai_compatible", endpoint=resolved_endpoint)
        == "featherless-key"
    )
    # and the endpoint-less path still yields the most-recent connect
    assert bff._stored_provider_key("openai_compatible") == "azure-foundry-key"


def test_the_bind_endpoint_is_resolved_before_the_key_is_read():
    """Pin the ORDER in the endpoint source: a helper that resolves per-endpoint is inert if the
    caller reads the key first. Source-level because the bind body is inline in a large endpoint.
    """
    import ast

    src = Path(bff.__file__).read_text()
    tree = ast.parse(src)
    def calls(fn):
        out = {}
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("_stored_provider_key", "_stored_provider_endpoint")
            ):
                out.setdefault(node.func.id, node.lineno)
        return out

    callers = [
        (fn.name, calls(fn)) for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and len(calls(fn)) == 2
    ]
    assert callers, "no function calls both readers — has the bind path been renamed?"
    for name, lines in callers:
        assert lines["_stored_provider_endpoint"] < lines["_stored_provider_key"], (
            f"{name}: the endpoint must be resolved BEFORE the key is read, "
            "or the key is not endpoint-scoped"
        )


def test_scoping_is_stable_and_collision_free(env_file):
    """Two endpoints that differ only in path must not land in the same slot."""
    a = bff._provider_slot_var("OPENAI_COMPATIBLE_API_KEY", "https://host.example/v1")
    b = bff._provider_slot_var("OPENAI_COMPATIBLE_API_KEY", "https://host.example/v2")
    again = bff._provider_slot_var("OPENAI_COMPATIBLE_API_KEY", "https://host.example/v1")

    assert a != b
    assert a == again  # stable across calls, or a restart loses the credential
    assert a.startswith("OPENAI_COMPATIBLE_API_KEY")
    assert all(c.isalnum() or c == "_" for c in a), "must be a legal env var name"
