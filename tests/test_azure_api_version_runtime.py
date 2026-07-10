"""CONNECT-AI-AZURE-1 (runtime) — api_version on the PER-ROLE azure judge LM + the chat loop.

Two runtime threading points the connect store feeds:

  * ``build_judge_lm`` per-role azure branch — a per-role azure provider override now threads
    ``api_version`` into the constructed ``dspy.LM`` kwargs (read from
    ``LITHRIM_LLM_API_VERSION_<ROLE>``, default ``settings.AZURE_OPENAI_API_VERSION``). The GLOBAL
    azure / openai branches stay BYTE-IDENTICAL (the regression guard).
  * ``_chat_provider_config`` + ``_litellm_loop`` — the chat config returns ``api_version`` for an
    azure chat env, and the loop puts it in the litellm completion kwargs when set. The openai (no
    api_version) path is byte-unchanged.

Bare-CE, $0/offline: ``dspy.LM`` + ``litellm.completion`` are MOCKED (no network). Patterns =
``tests/test_provider_center_crossprovider.py`` + ``tests/test_conv_runtime.py``.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.runtime.council import judges_dspy as J  # noqa: E402
from lithrim_bench.runtime.council.settings import settings  # noqa: E402


class _FakeLM:
    """A ``dspy.LM`` stand-in capturing the model string (first positional arg) + kwargs."""

    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs


@pytest.fixture
def fake_dspy_lm(monkeypatch):
    import dspy

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    return _FakeLM


def _clear_per_role(monkeypatch):
    for role in ("RISK", "POLICY", "FAITHFULNESS"):
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE", "API_VERSION"):
            monkeypatch.setattr(settings, f"LITHRIM_LLM_{kind}_{role}", "", raising=False)


# ── build_judge_lm per-role azure threads api_version ──────────────────────────────────


def test_per_role_azure_threads_api_version_into_lm_kwargs(fake_dspy_lm, monkeypatch):
    """A per-role azure override builds dspy.LM with api_version in its kwargs (read from
    LITHRIM_LLM_API_VERSION_RISK). Without it, a UI-bound Azure judge hits the api-version wall."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "azure")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "my-gpt-deploy")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "az-role-key")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_BASE_RISK", "https://my.openai.azure.com/")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_VERSION_RISK", "2024-12-01-preview")

    lm = J.build_judge_lm("risk_judge")
    assert lm.model == "azure/my-gpt-deploy"
    assert lm.kwargs["api_key"] == "az-role-key"
    assert lm.kwargs["api_base"] == "https://my.openai.azure.com/"
    assert lm.kwargs["api_version"] == "2024-12-01-preview"
    # azure exposes logprobs → calibrated confidence stays on for the per-role azure judge
    assert lm.kwargs["logprobs"] is True


def test_per_role_azure_defaults_api_version_from_settings(fake_dspy_lm, monkeypatch):
    """A per-role azure override with NO LITHRIM_LLM_API_VERSION_<ROLE> falls back to
    settings.AZURE_OPENAI_API_VERSION (never an empty version)."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_VERSION", "2024-10-21")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_POLICY", "azure")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_POLICY", "my-mistral-deploy")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_POLICY", "az-key")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_BASE_POLICY", "https://my.openai.azure.com/")

    lm = J.build_judge_lm("policy_judge")
    assert lm.kwargs["api_version"] == "2024-10-21"


def test_per_role_non_azure_carries_no_api_version(fake_dspy_lm, monkeypatch):
    """The api_version threading is azure-ONLY: a per-role gemini/openai override carries NO
    api_version kwarg (a stray version would be wrong for a non-azure provider)."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "gemini")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gemini-1.5-pro")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "gk")
    assert "api_version" not in J.build_judge_lm("risk_judge").kwargs


def test_global_azure_branch_byte_identical_with_api_version(fake_dspy_lm, monkeypatch):
    """Regression: with NO per-role provider, the GLOBAL azure trio still builds azure/<deployment>
    with the global settings.AZURE_OPENAI_API_VERSION — unchanged by the per-role threading."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "azure")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "az-key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://az.example/")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_VERSION", "2024-10-21")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "mistral-large-3")
    lm = J.build_judge_lm("policy_judge")
    assert lm.model == "azure/mistral-large-3"
    assert lm.kwargs["api_version"] == "2024-10-21"
    assert lm.kwargs["api_key"] == "az-key"
    assert lm.kwargs["api_base"] == "https://az.example/"


# ── _chat_provider_config + _litellm_loop thread api_version (azure chat) ───────────────


def test_chat_provider_config_returns_api_version_for_azure(monkeypatch, tmp_path):
    """LITHRIM_CHAT_PROVIDER=azure → _chat_provider_config returns api_version from
    LITHRIM_CHAT_API_VERSION (the chat loop needs it for azure)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "bff"))
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "_provider_config_root", lambda: tmp_path, raising=False)
    monkeypatch.setenv("LITHRIM_CHAT_PROVIDER", "azure")
    monkeypatch.setenv("LITHRIM_CHAT_MODEL", "my-chat-deploy")
    monkeypatch.setenv("LITHRIM_CHAT_API_KEY", "az-chat-key")
    monkeypatch.setenv("LITHRIM_CHAT_API_BASE", "https://my.openai.azure.com/")
    monkeypatch.setenv("LITHRIM_CHAT_API_VERSION", "2024-12-01-preview")

    cfg = loop_mod._chat_provider_config()
    assert cfg["provider"] == "azure"
    assert cfg["model"] == "my-chat-deploy"
    assert cfg["api_key"] == "az-chat-key"
    assert cfg["api_base"] == "https://my.openai.azure.com/"
    assert cfg["api_version"] == "2024-12-01-preview"


def test_chat_provider_config_openai_has_no_api_version(monkeypatch, tmp_path):
    """The openai chat path carries no api_version (azure-only): the dict's api_version is empty/None
    so _litellm_loop never sends it on the openai path."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "bff"))
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "_provider_config_root", lambda: tmp_path, raising=False)
    monkeypatch.setenv("LITHRIM_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("LITHRIM_CHAT_MODEL", "gpt-4o")
    monkeypatch.setenv("LITHRIM_CHAT_API_KEY", "sk-chat")
    monkeypatch.delenv("LITHRIM_CHAT_API_VERSION", raising=False)
    cfg = loop_mod._chat_provider_config()
    assert not cfg.get("api_version")  # None / empty — not threaded for openai


def _build_ctx(tmp_path, monkeypatch):
    """A minimal ToolContext over a tmp config DB, pinned to the neutral _core workspace."""
    from lithrim_bench.harness.config import save_agent
    from tests._house_fixture import house_agent

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "bff"))
    import app as bff

    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name="azure_chat_test"), db_path=db)
    monkeypatch.setattr(
        bff.workspace, "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    return bff._build_tool_context(
        req_agent="azure_chat_test", db_path=db, out_dir=tmp_path / "out",
        workdir=tmp_path / "ont", collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"), x_actor=None,
    )


def _stub_completion():
    state = {"calls": []}

    def _completion(**kwargs):
        state["calls"].append(kwargs)
        choice = types.SimpleNamespace(
            delta=types.SimpleNamespace(content="hi", tool_calls=None), finish_reason="stop"
        )
        return iter([types.SimpleNamespace(choices=[choice])])

    _completion.state = state
    return _completion


def test_litellm_loop_azure_sends_api_version(monkeypatch, tmp_path):
    """_litellm_loop puts api_version in the litellm completion kwargs for an azure chat. MOCKED
    litellm — no network. NON-VACUOUS: drop the threading and the kwarg is absent."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    from agent.loop import _litellm_loop

    ctx = _build_ctx(tmp_path, monkeypatch)
    completion = _stub_completion()

    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                "hello", ctx, None, provider="azure", model="my-chat-deploy",
                api_key="az-chat-key", api_base="https://my.openai.azure.com/",
                api_version="2024-12-01-preview", _completion=completion,
            )
        ]

    asyncio.run(_drain())
    first = completion.state["calls"][0]
    assert first["model"] == "azure/my-chat-deploy"
    assert first["api_base"] == "https://my.openai.azure.com/"
    assert first["api_version"] == "2024-12-01-preview"


def test_litellm_loop_openai_omits_api_version(monkeypatch, tmp_path):
    """The openai chat path is byte-unchanged: no api_version reaches the completion kwargs."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    from agent.loop import _litellm_loop

    ctx = _build_ctx(tmp_path, monkeypatch)
    completion = _stub_completion()

    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                "hello", ctx, None, provider="openai", model="gpt-4o",
                api_key="sk-TEST", api_base=None, _completion=completion,
            )
        ]

    asyncio.run(_drain())
    first = completion.state["calls"][0]
    assert first["model"] == "openai/gpt-4o"
    assert "api_version" not in first
