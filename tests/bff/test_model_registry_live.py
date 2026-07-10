"""MODEL-REGISTRY-1b (backend) — the live ``/models`` axis of the capability-aware catalog.

``GET /v1/models/catalog`` gains an opt-in ``?live=true`` fetch: for the providers that expose a
``/models`` API (OpenAI, Anthropic), fetch the live model list using the ALREADY-CONFIGURED key (read
server-side from ``.provider_env`` — Build A's ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``), annotate
each via ``capabilities_for``, and MERGE with the presets (dedup by model id, tag ``source``).

Graceful-absent is the contract: no key / network error / 401 → that provider falls back to presets
only, a 200 (NEVER a 500), with a per-provider status note. Azure stays deployment-based — never
fetched. The key is read SERVER-SIDE — NEVER a query param, NEVER in the response, NEVER logged.

  * A — ``?live=true`` + a configured OpenAI key + a mocked list → live gpt-* ids present (logprobs
        True, ``source`` set), embeddings/whisper EXCLUDED, ``live.openai.ok``, ``fetched>=2``.
  * B — ``?live=true`` + a configured Anthropic key + a mocked list → claude-* present (logprobs
        False, ``source:"live"``), ``live.anthropic.ok``.
  * C — ``?live=true`` + NO key → that provider = presets only, ``live.<p>.ok is False``, HTTP 200.
  * D — ``?live=true`` + the SDK list RAISING → graceful presets-only + ``live.<p>`` ``ok False`` +
        ``error``, HTTP 200.
  * E — ``?live=true`` → azure STILL ``{models: [], note}`` and never fetched.
  * F — ``GET /v1/models/catalog`` (no ``?live``) → byte-identical to 1a (no ``source``/``live`` keys).
  * G — the configured key string is NEVER present anywhere in the ``?live=true`` response body.

Bare-CE, MOCK the SDK list calls (no network, $0). Pattern = ``tests/bff/test_model_registry.py``.
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
    os.environ + the council settings singleton (reuse of the 1a fixture)."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.setattr(bff, "_PROVIDER_STATUS_PATH", tmp_path / ".provider_status.json", raising=False)
    monkeypatch.setattr(bff, "_MODELS_REGISTRY_PATH", tmp_path / ".models_registry.json", raising=False)

    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("model_registry_live", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    original = council_settings.settings
    try:
        yield tmp_path, ws
    finally:
        council_settings.settings = original
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _write_provider_env(tmp_path, **vars):
    """Write the configured provider key(s) write-only to .provider_env, the same store Build A
    writes — the server reads them back server-side. Keys are NEVER passed as a query param."""
    (tmp_path / ".provider_env").write_text("".join(f"{k}={v}\n" for k, v in vars.items()))


def _install_live(monkeypatch, mapping):
    """Patch ``_fetch_live_models`` so no SDK/network call happens. ``mapping`` maps a provider to
    either a list of RAW provider model ids (as a real ``/models`` call would return them) or an
    Exception instance to RAISE (simulate network/401). The mock MIRRORS the real helper's
    documented contract — it applies the SAME chat-model filter (OpenAI ``_is_openai_chat_model`` /
    Anthropic ``claude-*``) + capability annotation + ``source:"live"`` tag — so the endpoint-level
    tests assert the merge/filter contract, while the two ``test_fetch_live_models_*`` tests pin the
    real helper against a mocked SDK. Returns the captured calls."""
    calls: list[dict] = []

    def _fake_fetch(provider, api_key):
        calls.append({"provider": provider, "api_key": api_key})
        outcome = mapping.get(provider)
        if isinstance(outcome, Exception):
            raise outcome
        rows = []
        for mid in (outcome or []):
            if provider == "openai" and not bff._is_openai_chat_model(mid):
                continue
            if provider == "anthropic" and not str(mid).lower().startswith("claude-"):
                continue
            rows.append({"model": mid, **bff.capabilities_for(provider, mid), "source": "live"})
        return rows

    monkeypatch.setattr(bff, "_fetch_live_models", _fake_fetch)
    return calls


# A ──────────────────────────────────────────────────────────────────────────────────────────────
def test_live_openai_merges_filtered_models(registry_env, monkeypatch):
    """A: ?live=true with a configured OPENAI_API_KEY + a mocked list including non-chat ids →
    the openai catalog CONTAINS gpt-4o + gpt-5-x (each ``source`` set, gpt-* logprobs True) and
    EXCLUDES the embedding/whisper ids; live.openai.ok True, fetched>=2."""
    tmp_path, ws = registry_env
    _write_provider_env(tmp_path, OPENAI_API_KEY="sk-openai-LIVE-DO-NOT-LEAK")
    calls = _install_live(
        monkeypatch,
        {"openai": ["gpt-4o", "gpt-5-x", "text-embedding-3-large", "whisper-1"]},
    )
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    openai_models = body["providers"]["openai"]
    by_model = {m["model"]: m for m in openai_models}
    assert "gpt-4o" in by_model
    assert "gpt-5-x" in by_model
    assert by_model["gpt-5-x"]["logprobs"] is True
    assert by_model["gpt-5-x"]["source"] == "live"
    # every row carries a source tag (preset ⊕ live)
    for m in openai_models:
        assert m["source"] in ("preset", "live")
    # the non-chat ids are filtered out by _fetch_live_models
    assert "text-embedding-3-large" not in by_model
    assert "whisper-1" not in by_model

    live = body["live"]["openai"]
    assert live["ok"] is True
    assert live["fetched"] >= 2
    # the configured key was read server-side and handed to the fetch, never via the URL
    assert any(c["provider"] == "openai" and c["api_key"] == "sk-openai-LIVE-DO-NOT-LEAK" for c in calls)


# B ──────────────────────────────────────────────────────────────────────────────────────────────
def test_live_anthropic_merges_claude(registry_env, monkeypatch):
    """B: ?live=true with a configured ANTHROPIC_API_KEY + a mocked claude list → present,
    logprobs False, source:"live"; live.anthropic.ok True."""
    tmp_path, ws = registry_env
    _write_provider_env(tmp_path, ANTHROPIC_API_KEY="sk-ant-LIVE-DO-NOT-LEAK")
    _install_live(monkeypatch, {"anthropic": ["claude-4-x"]})
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    anthropic_models = body["providers"]["anthropic"]
    by_model = {m["model"]: m for m in anthropic_models}
    assert "claude-4-x" in by_model
    assert by_model["claude-4-x"]["logprobs"] is False
    assert by_model["claude-4-x"]["source"] == "live"
    assert body["live"]["anthropic"]["ok"] is True
    assert body["live"]["anthropic"]["fetched"] >= 1


# C ──────────────────────────────────────────────────────────────────────────────────────────────
def test_live_no_key_falls_back_to_presets_only(registry_env, monkeypatch):
    """C: ?live=true with NO configured key for a provider → that provider = presets only (every
    source:"preset"), live.<p>.ok is False, HTTP 200 (graceful, not 500). The fetch is NOT called."""
    tmp_path, ws = registry_env
    # no .provider_env written at all → no key for either provider
    calls = _install_live(monkeypatch, {})
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    openai_models = body["providers"]["openai"]
    assert openai_models, "presets should still be present"
    for m in openai_models:
        assert m["source"] == "preset"
    anthropic_models = body["providers"]["anthropic"]
    for m in anthropic_models:
        assert m["source"] == "preset"

    assert body["live"]["openai"]["ok"] is False
    assert body["live"]["anthropic"]["ok"] is False
    # no key → the fetch helper is never invoked
    assert calls == []


# D ──────────────────────────────────────────────────────────────────────────────────────────────
def test_live_fetch_error_is_graceful_presets_only(registry_env, monkeypatch):
    """D: ?live=true with the SDK list RAISING (network/401 simulated) → graceful presets-only +
    live.<p> carries ok False + an error, HTTP 200 (NEVER a 500)."""
    tmp_path, ws = registry_env
    _write_provider_env(tmp_path, OPENAI_API_KEY="sk-openai-WILL-RAISE")
    # The exception MESSAGE embeds the key — the realistic "SDK echoes the api_key in its error"
    # vector — so the `key not in error` assert below is NON-VACUOUS: it goes RED if the code ever
    # regresses from `type(exc).__name__` to `str(exc)` (critic MR1b-Q2, hardening test D).
    _install_live(monkeypatch, {"openai": RuntimeError("401 Unauthorized: invalid api_key sk-openai-WILL-RAISE")})
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    openai_models = body["providers"]["openai"]
    for m in openai_models:
        assert m["source"] == "preset"
    live = body["live"]["openai"]
    assert live["ok"] is False
    assert live.get("error")  # a non-empty per-provider error note
    assert "sk-openai-WILL-RAISE" not in live["error"]  # the key never lands in an error string


# E ──────────────────────────────────────────────────────────────────────────────────────────────
def test_live_azure_never_fetched(registry_env, monkeypatch):
    """E: ?live=true → azure is STILL {models: [], note}, never fetched (the fetch helper is never
    invoked for azure even if a key is present)."""
    tmp_path, ws = registry_env
    _write_provider_env(tmp_path, OPENAI_API_KEY="sk-x", AZURE_OPENAI_API_KEY="sk-azure-x")
    calls = _install_live(monkeypatch, {"openai": ["gpt-4o"]})
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    azure = body["providers"]["azure"]
    assert azure.get("models") == []
    assert azure.get("note") == bff._MODEL_CATALOG_AZURE_NOTE
    assert all(c["provider"] != "azure" for c in calls), "azure must never be fetched"


# F (regression) ──────────────────────────────────────────────────────────────────────────────────
def test_no_live_path_is_byte_identical_to_1a(registry_env, monkeypatch):
    """F: GET /v1/models/catalog (no ?live) → byte-identical to 1a (no source/live keys). The
    additive 1b axis must not perturb the default response."""
    tmp_path, ws = registry_env
    # configure a key + a live mock; with no ?live they must be ignored entirely
    _write_provider_env(tmp_path, OPENAI_API_KEY="sk-x", ANTHROPIC_API_KEY="sk-y")
    _install_live(monkeypatch, {"openai": ["gpt-4o"], "anthropic": ["claude-4-x"]})
    client = TestClient(bff.app)

    expected = {
        "providers": {
            "openai": [dict(m) for m in bff._MODEL_CATALOG_PRESETS["openai"]],
            "anthropic": [dict(m) for m in bff._MODEL_CATALOG_PRESETS["anthropic"]],
            "azure": {"models": [], "note": bff._MODEL_CATALOG_AZURE_NOTE},
        }
    }
    resp = client.get("/v1/models/catalog")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == expected
    assert "live" not in body
    for m in body["providers"]["openai"] + body["providers"]["anthropic"]:
        assert "source" not in m

    # ?live=false is also the 1a shape (explicit-false == absent)
    resp_false = client.get("/v1/models/catalog?live=false")
    assert resp_false.json() == expected


# G (secret hygiene — non-vacuous) ────────────────────────────────────────────────────────────────
def test_live_response_never_contains_the_key(registry_env, monkeypatch):
    """G: the configured key string is NEVER present anywhere in the ?live=true response body
    (assert the literal key absent from json.dumps(body)). Non-vacuous: the key IS configured + the
    fetch IS reached, so a leak would be observable."""
    tmp_path, ws = registry_env
    openai_key = "sk-openai-SECRET-1234567890-LEAK-CANARY"
    anthropic_key = "sk-ant-SECRET-0987654321-LEAK-CANARY"
    _write_provider_env(tmp_path, OPENAI_API_KEY=openai_key, ANTHROPIC_API_KEY=anthropic_key)
    calls = _install_live(monkeypatch, {"openai": ["gpt-4o"], "anthropic": ["claude-4-x"]})
    client = TestClient(bff.app)

    resp = client.get("/v1/models/catalog?live=true")
    assert resp.status_code == 200, resp.text
    serialized = json.dumps(resp.json())
    assert openai_key not in serialized
    assert anthropic_key not in serialized
    assert openai_key not in resp.text
    assert anthropic_key not in resp.text
    # non-vacuity: the keys were genuinely configured + handed to the fetch (so a leak was possible)
    keys_seen = {c["api_key"] for c in calls}
    assert openai_key in keys_seen
    assert anthropic_key in keys_seen


# _fetch_live_models helper (the chat-model filter contract, mocked SDK) ───────────────────────────
def test_fetch_live_models_openai_filters_chat_models(monkeypatch):
    """The OpenAI filter: keep gpt-*, o1*/o3*/o4*, chatgpt-*; DROP embeddings/whisper/tts/dall-e/
    moderation/text-*. Mock the lazy ``openai`` module so no network call happens."""
    import types

    listed = [
        "gpt-4o", "gpt-4o-mini", "o1-preview", "o3-mini", "o4-mini", "chatgpt-4o-latest",
        "text-embedding-3-large", "text-embedding-ada-002", "whisper-1", "tts-1",
        "dall-e-3", "text-moderation-latest", "omni-moderation-latest",
    ]

    class _Model:
        def __init__(self, mid):
            self.id = mid

    class _Models:
        def list(self_inner):
            return types.SimpleNamespace(data=[_Model(m) for m in listed])

    class _FakeOpenAI:
        def __init__(self, api_key=None):
            assert api_key == "sk-test"
            self.models = _Models()

    fake_mod = types.ModuleType("openai")
    fake_mod.OpenAI = _FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_mod)

    out = bff._fetch_live_models("openai", "sk-test")
    ids = {m["model"] for m in out}
    assert {"gpt-4o", "gpt-4o-mini", "o1-preview", "o3-mini", "o4-mini", "chatgpt-4o-latest"} <= ids
    assert "text-embedding-3-large" not in ids
    assert "text-embedding-ada-002" not in ids
    assert "whisper-1" not in ids
    assert "tts-1" not in ids
    assert "dall-e-3" not in ids
    assert "text-moderation-latest" not in ids
    assert "omni-moderation-latest" not in ids
    for m in out:
        assert m["source"] == "live"
        assert "logprobs" in m
    # gpt-* / chatgpt-* keep logprobs True; o-series reasoning → False
    by_model = {m["model"]: m for m in out}
    assert by_model["gpt-4o"]["logprobs"] is True
    assert by_model["o3-mini"]["logprobs"] is False


def test_fetch_live_models_anthropic_keeps_claude(monkeypatch):
    """Anthropic keeps claude-* ids and annotates each (logprobs False). Mock the lazy
    ``anthropic`` module."""
    import types

    class _Model:
        def __init__(self, mid):
            self.id = mid

    class _Models:
        def list(self_inner):
            return types.SimpleNamespace(
                data=[_Model("claude-3-5-sonnet-latest"), _Model("claude-4-opus")]
            )

    class _FakeAnthropic:
        def __init__(self, api_key=None):
            assert api_key == "sk-ant"
            self.models = _Models()

    fake_mod = types.ModuleType("anthropic")
    fake_mod.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    out = bff._fetch_live_models("anthropic", "sk-ant")
    ids = {m["model"] for m in out}
    assert ids == {"claude-3-5-sonnet-latest", "claude-4-opus"}
    for m in out:
        assert m["source"] == "live"
        assert m["logprobs"] is False
