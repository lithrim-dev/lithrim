"""WS-JUDGE-BIND: the per-role model binding becomes WORKSPACE-scoped.

Today ``role_bindings`` is keyed on role ALONE (a single global row per role — the store's own
docstring calls per-workspace bindings "a deliberate later enhancement"), so two workspaces that
use the same judge roles always resolve to the same model AND the same endpoint. That blocks
running per-model comparison arms as separate workspaces.

The per-workspace ``judges`` table is already correctly scoped on ``(workspace_id, role)`` and
already carries ``model`` — but ``model`` alone is a bare selector string, so it cannot express a
per-workspace base URL. This cycle adds ``provider`` / ``endpoint`` / ``api_version`` next to it
and hydrates the ACTIVE workspace's judge binding AHEAD of the global row.

Asserted through :func:`judges_dspy._role_setting` — the FROZEN resolver ``build_judge_lm``
actually calls (``judges_dspy.py:387-393``) — not through the hydration's own bookkeeping, so a
hydration that writes the wrong plane fails here rather than passing vacuously.

  * roundtrip + back-compat: the new fields persist; a legacy row without them still loads.
  * THE KEY PROPERTY: two workspaces, same role, different bindings → different model AND
    different endpoint at resolution time.
  * fallback: a workspace with NO per-workspace binding resolves exactly as it does today (the
    global ``role_bindings`` row still wins over nothing).
  * STALE-ENDPOINT TRAP: a workspace binding must set the endpoint EXPLICITLY, never inherit the
    previously-hydrated global one. A provider rebind that keeps a stale endpoint makes the judge
    404 and abstain silently as an empty WARN under the NEW model's label.
  * SETTINGS-HOLDER TRAP: the trio's binding keys are DECLARED ``Settings`` fields and
    ``_role_setting`` reads the holder BEFORE os.environ, so an overlay that only writes
    ``os.environ`` is silently inert for the trio once any global bind has populated the holder.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import judges as J
from lithrim_bench.harness import role_bindings as rb
from lithrim_bench.harness import workspace as W

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

from lithrim_bench.runtime.council.judges_dspy import _role_setting  # noqa: E402
from lithrim_bench.runtime.council.settings import settings  # noqa: E402

ROLE = "risk_judge"
# the 4 non-secret per-role binding keys the frozen resolver reads for ``risk_judge``
KEY_PROVIDER = "LITHRIM_LLM_PROVIDER_RISK"
KEY_MODEL = "LITHRIM_LLM_MODEL_RISK"
KEY_API_BASE = "LITHRIM_LLM_API_BASE_RISK"
KEY_API_VERSION = "LITHRIM_LLM_API_VERSION_RISK"
_ALL_KEYS = (KEY_PROVIDER, KEY_MODEL, KEY_API_BASE, KEY_API_VERSION)


@pytest.fixture
def bind_env(tmp_path, monkeypatch):
    """Isolate BOTH binding planes + BOTH resolution planes.

    Workspaces, the global ``role_bindings`` DB and the provider sidecar all move under tmp; the
    per-role env vars and the declared ``Settings`` fields are cleared so nothing leaks in from the
    developer's real environment (or from a previously-run test in the same process).
    """
    monkeypatch.setattr(W, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(bff, "_provider_env_path", lambda: tmp_path / "provider" / ".provider_env")
    (tmp_path / "provider").mkdir(parents=True, exist_ok=True)
    for key in _ALL_KEYS:
        # setenv (not delenv) on purpose: the hydration WRITES these vars, and only a monkeypatch
        # that recorded the prior state restores them at teardown — a delenv of an already-absent
        # var records nothing, so the write would leak into every later test in the process.
        monkeypatch.setenv(key, "")
        monkeypatch.setattr(settings, key, "", raising=False)
    return tmp_path


def _resolved() -> dict[str, str]:
    """What the FROZEN ``build_judge_lm`` would resolve for ROLE, via its own reader."""
    return {
        "provider": _role_setting(KEY_PROVIDER),
        "model": _role_setting(KEY_MODEL),
        "endpoint": _role_setting(KEY_API_BASE),
        "api_version": _role_setting(KEY_API_VERSION),
    }


def _bind_workspace_judge(ws, **binding) -> None:
    J.save_judge(
        J.JudgeConfig(role=ROLE, assigned_flags=(), validator_refs=(), **binding),
        db_path=ws.config_db,
    )


def _hydrate(ws) -> None:
    """The BFF's boot/grade hydration order: the GLOBAL row first, then the workspace overlay."""
    bff._hydrate_role_bindings_into_env()
    bff._hydrate_workspace_judge_bindings_into_env(ws)


# ── the config model carries the binding ──────────────────────────────────────


def test_judge_config_roundtrips_provider_endpoint_api_version(bind_env):
    ws = W.get_active_workspace()
    _bind_workspace_judge(
        ws,
        model="gpt-4.1",
        provider="azure",
        endpoint="https://ws-a.openai.azure.com",
        api_version="2024-08-01-preview",
    )
    jc = J.list_judges(db_path=ws.config_db)[ROLE]
    assert jc.model == "gpt-4.1"
    assert jc.provider == "azure"
    assert jc.endpoint == "https://ws-a.openai.azure.com"
    assert jc.api_version == "2024-08-01-preview"


def test_legacy_judge_row_without_the_new_fields_still_loads(bind_env):
    """Back-compat: every row written before this cycle lacks the 3 new keys."""
    jc = J.judge_from_dict({"role": ROLE, "model": "gpt-4.1", "assigned_flags": ["X"]})
    assert jc.model == "gpt-4.1"
    assert jc.provider == "" and jc.endpoint == "" and jc.api_version == ""


# ── THE KEY PROPERTY ──────────────────────────────────────────────────────────


def test_two_workspaces_same_role_resolve_to_different_model_and_endpoint(bind_env):
    """The whole point: per-model comparison arms as separate workspaces."""
    a = W.get_active_workspace()
    b = W.create_workspace("arm-b", pack=a.pack)
    _bind_workspace_judge(
        a, provider="openai_compatible", model="llama-3.1-70b",
        endpoint="https://arm-a.vllm.local/v1",
    )
    _bind_workspace_judge(
        b, provider="openai_compatible", model="qwen-2.5-72b",
        endpoint="https://arm-b.vllm.local/v1",
    )

    _hydrate(a)
    got_a = _resolved()
    _hydrate(b)
    got_b = _resolved()

    assert got_a["model"] == "llama-3.1-70b"
    assert got_b["model"] == "qwen-2.5-72b"
    assert got_a["endpoint"] == "https://arm-a.vllm.local/v1"
    assert got_b["endpoint"] == "https://arm-b.vllm.local/v1"
    # non-vacuous: the two arms differ on BOTH axes, which is exactly what the global store
    # (keyed on role alone) could not express.
    assert got_a["model"] != got_b["model"]
    assert got_a["endpoint"] != got_b["endpoint"]


# ── the global row stays the fallback ─────────────────────────────────────────


def test_workspace_without_a_binding_resolves_exactly_as_today(bind_env):
    """No per-workspace binding → the global row wins, byte-identical to before this cycle."""
    rb.save_binding(
        ROLE,
        {"provider": "azure", "model": "gpt-4.1", "endpoint": "https://global.azure.com",
         "api_version": "2024-08-01-preview"},
        db_path=bff._role_bindings_db_path(),
    )
    ws = W.get_active_workspace()  # authored NOTHING for this role

    _hydrate(ws)

    assert _resolved() == {
        "provider": "azure", "model": "gpt-4.1",
        "endpoint": "https://global.azure.com", "api_version": "2024-08-01-preview",
    }


def test_workspace_binding_wins_over_the_global_row(bind_env):
    rb.save_binding(
        ROLE,
        {"provider": "azure", "model": "gpt-4.1", "endpoint": "https://global.azure.com"},
        db_path=bff._role_bindings_db_path(),
    )
    ws = W.get_active_workspace()
    _bind_workspace_judge(
        ws, provider="openai_compatible", model="qwen-2.5-72b",
        endpoint="https://ws.vllm.local/v1",
    )

    _hydrate(ws)

    assert _resolved()["model"] == "qwen-2.5-72b"
    assert _resolved()["provider"] == "openai_compatible"


# ── the two traps ─────────────────────────────────────────────────────────────


def test_workspace_binding_never_inherits_the_global_endpoint(bind_env):
    """STALE-ENDPOINT TRAP. The global row is azure with an endpoint; the workspace binds plain
    ``openai``, which has NO endpoint. If the hydration only SETS present fields, the azure
    endpoint survives in the env and the judge 404s against it — silently, as an empty WARN
    abstain under the NEW model's label. The overlay must write the endpoint EXPLICITLY."""
    rb.save_binding(
        ROLE,
        {"provider": "azure", "model": "gpt-4.1",
         "endpoint": "https://STALE.azure.com", "api_version": "2024-08-01-preview"},
        db_path=bff._role_bindings_db_path(),
    )
    ws = W.get_active_workspace()
    _bind_workspace_judge(ws, provider="openai", model="gpt-4o")  # no endpoint, no api_version

    _hydrate(ws)

    got = _resolved()
    assert got["model"] == "gpt-4o"
    assert got["endpoint"] == "", f"stale global endpoint leaked: {got['endpoint']!r}"
    assert got["api_version"] == "", f"stale global api_version leaked: {got['api_version']!r}"


def test_overlay_beats_a_populated_settings_holder(bind_env):
    """SETTINGS-HOLDER TRAP. ``_role_setting`` reads the declared ``Settings`` field BEFORE
    os.environ, and ``_persist_and_reload_provider`` mutates that holder in place on every global
    bind. An overlay that writes only ``os.environ`` is therefore silently INERT for the trio."""
    monkey_holder = "gpt-4.1-from-a-previous-global-bind"
    settings.LITHRIM_LLM_PROVIDER_RISK = "azure"
    settings.LITHRIM_LLM_MODEL_RISK = monkey_holder
    settings.LITHRIM_LLM_API_BASE_RISK = "https://STALE.azure.com"

    ws = W.get_active_workspace()
    _bind_workspace_judge(
        ws, provider="openai_compatible", model="qwen-2.5-72b",
        endpoint="https://ws.vllm.local/v1",
    )

    _hydrate(ws)

    got = _resolved()
    assert got["model"] == "qwen-2.5-72b", "the settings holder shadowed the workspace overlay"
    assert got["endpoint"] == "https://ws.vllm.local/v1"


# ── the PUT surface ───────────────────────────────────────────────────────────


def test_put_judge_persists_the_workspace_binding(bind_env, monkeypatch):
    """The authoring path the judge-configuration form posts to."""
    ws = W.get_active_workspace()
    monkeypatch.setattr(bff, "_validate_judge_assignment", lambda *a, **k: None)
    bff.put_judge_endpoint(
        role=ROLE,
        judge={"model": "qwen-2.5-72b", "provider": "openai_compatible",
               "endpoint": "https://ws.vllm.local/v1", "assigned_flags": []},
        rationale="arm B", agent=None, db_path=ws.config_db,
        default_actor=bff.Actor(type="human", id="t@x"), x_actor=None,
    )
    jc = J.list_judges(db_path=ws.config_db)[ROLE]
    assert (jc.provider, jc.model, jc.endpoint) == (
        "openai_compatible", "qwen-2.5-72b", "https://ws.vllm.local/v1",
    )


def test_put_judge_refuses_an_endpointless_azure_binding(bind_env, monkeypatch):
    """STALE-ENDPOINT TRAP at the authoring boundary: azure/openai_compatible without an explicit
    endpoint would bind to an empty base URL (the overlay never inherits the global one) and 404
    the judge into a silent abstain. Mirrors the /v1/roles/bind guard."""
    ws = W.get_active_workspace()
    monkeypatch.setattr(bff, "_validate_judge_assignment", lambda *a, **k: None)
    with pytest.raises(bff.HTTPException) as exc:
        bff.put_judge_endpoint(
            role=ROLE,
            judge={"model": "gpt-4.1", "provider": "azure", "assigned_flags": []},
            rationale="", agent=None, db_path=ws.config_db,
            default_actor=bff.Actor(type="human", id="t@x"), x_actor=None,
        )
    assert exc.value.status_code == 422
    assert "endpoint" in str(exc.value.detail)
