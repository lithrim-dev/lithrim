"""PROVIDER-CENTER-A — cross-provider-per-role grading (the S-BS-MR1a-CROSSPROVIDER unlock).

Each judge role can run on ANY configured provider (risk→OpenAI, policy→Gemini,
faithfulness→Anthropic), and the provider set broadens to gemini / bedrock / openai-compatible
(the litellm path already speaks them). ``build_judge_lm`` gains a PER-ROLE provider override
layered ON TOP of the existing global path:

  * A — a MIXED council: per-role providers (risk→openai, policy→gemini, faithfulness→anthropic)
        build ``dspy.LM`` with model strings ``openai/…`` / ``gemini/…`` / ``anthropic/…`` and the
        per-role api_key. ``dspy.LM`` is MOCKED.
  * B — BYTE-IDENTICAL regression: with NO per-role provider set, ``build_judge_lm`` builds the
        SAME ``dspy.LM(...)`` as before (global openai + global azure paths unchanged); byo-claude
        routing intact.
  * C — ``_provider_supports_logprobs`` — openai/azure True; anthropic/gemini/bedrock False (so
        logprobs is OFF in the LM kwargs for those → honest confidence-dark).

Bare-CE, ``$0``/offline: ``dspy.LM`` is mocked (no network). Pattern = ``tests/test_byok_openai.py``
+ ``tests/test_byoc_provider.py``.
"""

from __future__ import annotations

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
    """Mock ``dspy.LM`` so construction is $0 and we read back the exact (model, kwargs)."""
    import dspy

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    return _FakeLM


def _clear_per_role(monkeypatch):
    """Zero out every per-role provider binding so the global path is the only one live."""
    for role in ("RISK", "POLICY", "FAITHFULNESS"):
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE"):
            monkeypatch.setattr(settings, f"LITHRIM_LLM_{kind}_{role}", "", raising=False)


# ── A: the MIXED council — risk→openai, policy→gemini, faithfulness→anthropic ──────────


def test_mixed_council_each_role_routes_to_its_own_provider(fake_dspy_lm, monkeypatch):
    """A: per-role providers build dspy.LM with the role's provider prefix + per-role api_key."""
    _clear_per_role(monkeypatch)
    # global stays openai (the fallback) — but each role's per-role provider overrides it
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-global-ignored")

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "sk-risk-openai")

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_POLICY", "gemini")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_POLICY", "gemini-1.5-pro")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_POLICY", "gk-policy-gemini")

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_FAITHFULNESS", "anthropic")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_FAITHFULNESS", "claude-3-5-sonnet-latest")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_FAITHFULNESS", "ak-faith-anthropic")

    risk = J.build_judge_lm("risk_judge")
    policy = J.build_judge_lm("policy_judge")
    faith = J.build_judge_lm("faithfulness_judge")

    assert risk.model == "openai/gpt-4o"
    assert risk.kwargs["api_key"] == "sk-risk-openai"

    assert policy.model == "gemini/gemini-1.5-pro"
    assert policy.kwargs["api_key"] == "gk-policy-gemini"

    assert faith.model == "anthropic/claude-3-5-sonnet-latest"
    assert faith.kwargs["api_key"] == "ak-faith-anthropic"


def test_per_role_openai_compatible_carries_api_base(fake_dspy_lm, monkeypatch):
    """A (openai-compatible): the prefix is ``openai`` but a per-role api_base routes the
    OpenAI-compatible endpoint (vLLM / Together / a local server) via litellm."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "openai_compatible")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "llama-3.1-70b")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "sk-compat")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_BASE_RISK", "https://my-vllm.local/v1")

    lm = J.build_judge_lm("risk_judge")
    assert lm.model == "openai/llama-3.1-70b"
    assert lm.kwargs["api_key"] == "sk-compat"
    assert lm.kwargs["api_base"] == "https://my-vllm.local/v1"


def test_per_role_bedrock_prefix(fake_dspy_lm, monkeypatch):
    """A (bedrock): the litellm ``bedrock/`` prefix is used for an AWS Bedrock model."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_POLICY", "bedrock")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_POLICY", "anthropic.claude-3-sonnet-v1")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_POLICY", "")
    lm = J.build_judge_lm("policy_judge")
    assert lm.model == "bedrock/anthropic.claude-3-sonnet-v1"


def test_per_role_logprobs_off_for_non_openai_providers(fake_dspy_lm, monkeypatch):
    """A/C wired: a confidence-dark provider (gemini/anthropic/bedrock) gets NO logprobs param
    AT ALL (DRYRUN-2026-07-03: litellm/anthropic reject the param's presence, even as False —
    which errored the judge into a silent needs_review); a per-role openai LM on a
    logprobs-capable MODEL keeps logprobs=True; a reasoning-family model (gpt-5*) is
    model-granular confidence-dark even on openai."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "sk-risk")
    assert J.build_judge_lm("risk_judge").kwargs["logprobs"] is True
    assert J.build_judge_lm("risk_judge").kwargs["drop_params"] is True

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_POLICY", "gemini")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_POLICY", "gemini-1.5-pro")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_POLICY", "gk")
    assert "logprobs" not in J.build_judge_lm("policy_judge").kwargs

    # model-granular: gpt-5* on openai rejects logprobs → omitted (confidence-dark, never an error)
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gpt-5.5")
    assert "logprobs" not in J.build_judge_lm("risk_judge").kwargs


# ── B: BYTE-IDENTICAL regression — no per-role provider → the global path is unchanged ─


def test_no_per_role_global_openai_path_unchanged(fake_dspy_lm, monkeypatch):
    """B: with NO per-role provider, the global openai branch builds the SAME LM as before."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-global")
    monkeypatch.setattr(settings, "OPENAI_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_POLICY", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_FAITHFULNESS", "gpt-4o")
    for role in J.V2_ROLES:
        lm = J.build_judge_lm(role)
        assert lm.model == "openai/gpt-4o"
        assert lm.kwargs["api_key"] == "sk-global"
        assert lm.kwargs["logprobs"] is True
        # the global path carries NO api_base (only the per-role/azure paths do)
        assert "api_base" not in lm.kwargs


def test_no_per_role_global_azure_path_unchanged(fake_dspy_lm, monkeypatch):
    """B: with NO per-role provider, the global azure trio builds the SAME azure/<deployment> LMs."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "azure")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-ignored")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "az-key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://az.example/")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "mistral-large-3")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK", "llama-4-maverick")
    assert J.build_judge_lm("risk_judge").model == "azure/gpt-4.1"
    assert J.build_judge_lm("policy_judge").model == "azure/mistral-large-3"
    assert J.build_judge_lm("faithfulness_judge").model == "azure/llama-4-maverick"
    assert J.build_judge_lm("risk_judge").kwargs["api_key"] == "az-key"


def test_no_per_role_byo_claude_routing_intact(monkeypatch):
    """B: with NO per-role provider, the byo-claude per-role selector still returns ClaudeCliLM
    (the BYOC-1 routing precedes the new per-role provider branch + the global branches)."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-byok")
    assert type(J.build_judge_lm("risk_judge", model="byo-claude")).__name__ == "ClaudeCliLM"
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "claude-cli")
    assert type(J.build_judge_lm("faithfulness_judge")).__name__ == "ClaudeCliLM"


def test_per_role_provider_does_not_perturb_the_unset_roles(fake_dspy_lm, monkeypatch):
    """B (isolation): setting ONLY risk's per-role provider leaves policy/faithfulness on the
    byte-identical global path — the override is strictly additive per role."""
    _clear_per_role(monkeypatch)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-global")
    monkeypatch.setattr(settings, "OPENAI_MODEL_POLICY", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_FAITHFULNESS", "gpt-4o")

    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "gemini")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gemini-1.5-pro")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "gk-risk")

    assert J.build_judge_lm("risk_judge").model == "gemini/gemini-1.5-pro"
    # the other two roles untouched — global openai path
    assert J.build_judge_lm("policy_judge").model == "openai/gpt-4o"
    assert J.build_judge_lm("policy_judge").kwargs["api_key"] == "sk-global"
    assert J.build_judge_lm("faithfulness_judge").model == "openai/gpt-4o"


# ── C: _provider_supports_logprobs — openai/azure True, else False ─────────────────────


def test_provider_supports_logprobs_helper():
    """C: only openai + azure expose token logprobs (calibrated confidence); the rest are dark."""
    assert J._provider_supports_logprobs("openai") is True
    assert J._provider_supports_logprobs("azure") is True
    assert J._provider_supports_logprobs("anthropic") is False
    assert J._provider_supports_logprobs("gemini") is False
    assert J._provider_supports_logprobs("bedrock") is False
    assert J._provider_supports_logprobs("openai_compatible") is False
    # case-insensitive + tolerant of an unknown provider (conservatively dark)
    assert J._provider_supports_logprobs("OpenAI") is True
    assert J._provider_supports_logprobs("whatever") is False


def test_litellm_prefix_helper():
    """C-adjacent: the litellm provider/model prefix per provider (openai_compatible → openai)."""
    assert J._litellm_prefix("openai") == "openai"
    assert J._litellm_prefix("azure") == "azure"
    assert J._litellm_prefix("anthropic") == "anthropic"
    assert J._litellm_prefix("gemini") == "gemini"
    assert J._litellm_prefix("bedrock") == "bedrock"
    assert J._litellm_prefix("openai_compatible") == "openai"
    assert J._litellm_prefix("OPENAI_COMPATIBLE") == "openai"
