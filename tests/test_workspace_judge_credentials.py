"""WS-CRED-1 Defect B: the workspace overlay must resolve the CREDENTIAL too, not just the
provider/model/endpoint.

WS-JUDGE-BIND scoped ``provider``/``model``/``endpoint``/``api_version`` per workspace and
deliberately left ``api_key`` out, so the frozen resolver still read one global slot per role:

    # lithrim_bench/runtime/council/judges_dspy.py:390  (FROZEN)
    role_api_key = _role_setting(role_keys["api_key"])     # LITHRIM_LLM_API_KEY_<ROLE>

Two workspaces binding the same role to different providers therefore shared one credential,
which is what blocked per-model comparison arms: ``arm-opus`` needs
``LITHRIM_LLM_API_KEY_RISK`` to hold an Anthropic key while ``arm-medgemma`` needs the same
variable to hold a Featherless key.

WS-CRED-1a made provider credentials addressable by ``(provider, endpoint)``. A workspace
binding already names both, so the overlay can resolve the right credential from that slot —
no new secret store, no new API field, no new surface a key could leak through. That is the
whole of this cycle.

Asserted through :func:`judges_dspy._role_setting`, the frozen reader, for the same reason as
``test_workspace_judge_bindings.py``: an overlay writing the wrong plane must fail here rather
than pass against its own bookkeeping.

Out of scope: two workspaces on the SAME provider AND endpoint needing DIFFERENT accounts.
That genuinely needs a per-workspace secret store; nothing here pretends to cover it.

Offline: no network, no model calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import judges as J
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
KEY_PROVIDER = "LITHRIM_LLM_PROVIDER_RISK"
KEY_MODEL = "LITHRIM_LLM_MODEL_RISK"
KEY_API_KEY = "LITHRIM_LLM_API_KEY_RISK"
KEY_API_BASE = "LITHRIM_LLM_API_BASE_RISK"
KEY_API_VERSION = "LITHRIM_LLM_API_VERSION_RISK"
_ALL_KEYS = (KEY_PROVIDER, KEY_MODEL, KEY_API_KEY, KEY_API_BASE, KEY_API_VERSION)

FEATHERLESS = "https://api.featherless.ai/v1"
AZURE_FOUNDRY = "https://zyng-work-resource.services.ai.azure.com/models"


@pytest.fixture
def cred_env(tmp_path, monkeypatch):
    env_path = tmp_path / "provider" / ".provider_env"
    monkeypatch.setattr(W, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(bff, "_provider_env_path", lambda: env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    for key in _ALL_KEYS:
        # setenv, not delenv: the hydration WRITES these, and only a recorded prior state is
        # restored at teardown — a delenv of an absent var records nothing and the write leaks.
        monkeypatch.setenv(key, "")
        monkeypatch.setattr(settings, key, "", raising=False)
    return env_path


def _seed_provider_slots(env_path: Path, entries: dict[str, str]) -> None:
    """Write endpoint-scoped provider credentials straight to .provider_env (endpoint -> key)."""
    lines = []
    for endpoint, key in entries.items():
        lines.append(f"{bff._provider_slot_var('OPENAI_COMPATIBLE_API_KEY', endpoint)}={key}")
        lines.append(f"{bff._provider_slot_var('OPENAI_COMPATIBLE_API_BASE', endpoint)}={endpoint}")
    env_path.write_text("\n".join(lines) + "\n")


def _bind(ws, **binding) -> None:
    J.save_judge(
        J.JudgeConfig(role=ROLE, assigned_flags=(), validator_refs=(), **binding),
        db_path=ws.config_db,
    )


def _hydrate(ws) -> None:
    bff._hydrate_role_bindings_into_env()
    bff._hydrate_workspace_judge_bindings_into_env(ws)


# ── THE KEY PROPERTY ──────────────────────────────────────────────────────────


def test_two_workspaces_resolve_their_own_credential(cred_env):
    """The arm campaign in one test: same role, two providers, two credentials."""
    _seed_provider_slots(
        cred_env, {FEATHERLESS: "featherless-key", AZURE_FOUNDRY: "azure-foundry-key"}
    )
    ws_a = W.create_workspace("arm-medgemma", pack="_core")
    ws_b = W.create_workspace("arm-mistral", pack="_core")
    _bind(ws_a, model="google/medgemma-27b-text-it",
          provider="openai_compatible", endpoint=FEATHERLESS)
    _bind(ws_b, model="Mistral-Large-3",
          provider="openai_compatible", endpoint=AZURE_FOUNDRY)

    _hydrate(ws_a)
    assert _role_setting(KEY_API_KEY) == "featherless-key"
    assert _role_setting(KEY_API_BASE) == FEATHERLESS

    _hydrate(ws_b)
    assert _role_setting(KEY_API_KEY) == "azure-foundry-key"
    assert _role_setting(KEY_API_BASE) == AZURE_FOUNDRY


def test_switching_back_does_not_leak_the_other_workspaces_credential(cred_env):
    """settings + env are process-global; B's key must not survive into A's next grade."""
    _seed_provider_slots(
        cred_env, {FEATHERLESS: "featherless-key", AZURE_FOUNDRY: "azure-foundry-key"}
    )
    ws_a = W.create_workspace("arm-medgemma", pack="_core")
    ws_b = W.create_workspace("arm-mistral", pack="_core")
    _bind(ws_a, model="m", provider="openai_compatible", endpoint=FEATHERLESS)
    _bind(ws_b, model="m", provider="openai_compatible", endpoint=AZURE_FOUNDRY)

    _hydrate(ws_b)
    _hydrate(ws_a)

    assert _role_setting(KEY_API_KEY) == "featherless-key"


# ── nothing else may change ───────────────────────────────────────────────────


def test_no_matching_provider_slot_leaves_the_global_key_alone(cred_env):
    """A workspace whose endpoint has no stored credential must NOT clear the global per-role
    key — that is the pre-existing fallback and clearing it would 401 a working setup."""
    cred_env.write_text("")  # no provider slots at all
    ws = W.create_workspace("ws-unbound-cred", pack="_core")
    _bind(ws, model="m", provider="openai_compatible", endpoint=FEATHERLESS)
    bff._set_role_binding_value(KEY_API_KEY, "pre-existing-global-key")

    _hydrate(ws)

    assert _role_setting(KEY_API_KEY) == "pre-existing-global-key"


def test_a_workspace_binding_nothing_is_a_no_op(cred_env):
    """No provider on the judge row → the overlay must not touch the credential plane."""
    _seed_provider_slots(cred_env, {FEATHERLESS: "featherless-key"})
    ws = W.create_workspace("ws-no-binding", pack="_core")
    _bind(ws, model="m")  # model only, no provider
    bff._set_role_binding_value(KEY_API_KEY, "global-key")

    _hydrate(ws)

    assert _role_setting(KEY_API_KEY) == "global-key"


# ── the credential must never surface ─────────────────────────────────────────


def test_the_judge_record_never_carries_a_credential(cred_env):
    """The judges table is versioned in judges_history, returned by API surfaces, and COPIED
    when a workspace is cloned. A key must never enter it."""
    jc = J.JudgeConfig(
        role=ROLE, assigned_flags=(), validator_refs=(),
        model="m", provider="openai_compatible", endpoint=FEATHERLESS,
    )
    blob = J.judge_to_dict(jc)

    assert not any("key" in k.lower() or "secret" in k.lower() for k in blob), blob.keys()
    assert not hasattr(jc, "api_key")


class _StubOntology:
    """Minimal ontology surface `_judge_summary` touches — it is not what is under test here."""

    def flag(self, code):
        return None

    def questions_for(self, role):
        return []


def test_the_judge_summary_never_carries_a_credential(cred_env, monkeypatch):
    _seed_provider_slots(cred_env, {FEATHERLESS: "featherless-key"})
    monkeypatch.setattr(bff, "_active_lens_by_role", lambda: {ROLE: set()})
    jc = J.JudgeConfig(
        role=ROLE, assigned_flags=(), validator_refs=(),
        model="m", provider="openai_compatible", endpoint=FEATHERLESS,
    )
    summary = bff._judge_summary(ROLE, jc, _StubOntology(), bindings={})

    assert "featherless-key" not in repr(summary)
    assert not any("key" in k.lower() or "secret" in k.lower() for k in summary), summary.keys()
