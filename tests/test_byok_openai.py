"""Cycle 1 — single-provider BYOK: the multi-judge council runs on ONE OpenAI key (no Azure trio).

``build_judge_lm`` binds each role to a model on the user's ``OPENAI_API_KEY`` when
``LITHRIM_LLM_PROVIDER=openai`` and the key is set — preserving the 3-judge council, per-role
model diversity (KEEP THE MULTI-COUNCIL), and logprobs (so the calibrated-confidence read still
works, unlike BYO-Claude). ADDITIVE: the Azure trio path and the BYO-Claude path are untouched —
the new branch is gated on ``OPENAI_API_KEY`` being present, so the existing offline Azure-seam
tests (which set deployments but no OpenAI key) fall through to the byte-unchanged Azure path.

RED before the build_judge_lm openai-direct branch exists. Offline / $0 — dspy.LM construction
makes no network call; the assertions read the bound model id + kwargs, never invoke the LM.
"""
from __future__ import annotations

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.runtime.council import judges_dspy as J  # noqa: E402
from lithrim_bench.runtime.council.settings import settings  # noqa: E402


@pytest.fixture
def openai_byok(monkeypatch):
    """A single-provider OpenAI BYOK env: provider=openai + a key, NO Azure deployments."""
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-byok")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", None)
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK", None)
    monkeypatch.setattr(settings, "OPENAI_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_POLICY", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_FAITHFULNESS", "gpt-4o")


def _model(lm) -> str:
    return str(lm.model)


def test_all_three_roles_bind_openai_with_one_key(openai_byok):
    """The full trio binds openai/<model> on the single key — no Azure, no raise. The roles with
    no openai.com twin (policy/faithfulness, ex-Mistral/Llama) now bind an OpenAI model too."""
    for role in J.V2_ROLES:
        lm = J.build_judge_lm(role)
        assert type(lm).__name__ == "LM", f"{role} did not bind a dspy.LM"
        assert _model(lm) == "openai/gpt-4o", f"{role} bound {_model(lm)!r}, expected openai/gpt-4o"


def test_per_role_models_are_configurable_for_diversity(openai_byok, monkeypatch):
    """KEEP THE MULTI-COUNCIL: each role binds its OWN model on the one provider (model diversity
    on a single key), via OPENAI_MODEL_{RISK,POLICY,FAITHFULNESS}."""
    # logprobs-capable chat models only — the council needs logprobs for calibration, so o-series
    # reasoning models (no logprobs) are intentionally not a supported council model here.
    monkeypatch.setattr(settings, "OPENAI_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MODEL_POLICY", "gpt-4.1")
    monkeypatch.setattr(settings, "OPENAI_MODEL_FAITHFULNESS", "gpt-4o-mini")
    bound = {role: _model(J.build_judge_lm(role)) for role in J.V2_ROLES}
    assert bound == {
        "risk_judge": "openai/gpt-4o",
        "policy_judge": "openai/gpt-4.1",
        "faithfulness_judge": "openai/gpt-4o-mini",
    }


def test_openai_direct_keeps_logprobs_for_calibration(openai_byok):
    """The OpenAI path keeps logprobs ON — the calibrated-confidence read survives (the axis
    BYO-Claude loses)."""
    lm = J.build_judge_lm("risk_judge")
    assert lm.kwargs.get("logprobs") is True


def test_azure_path_unchanged_when_provider_is_azure(monkeypatch):
    """Regression: LITHRIM_LLM_PROVIDER=azure + deployments → azure/<deployment>, byte-unchanged
    (the new openai branch must not intercept the Azure trio even with an OpenAI key present)."""
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "azure")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-should-be-ignored")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "mistral-large-3")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK", "llama-4-maverick")
    assert _model(J.build_judge_lm("risk_judge")) == "azure/gpt-4.1"
    assert _model(J.build_judge_lm("policy_judge")) == "azure/mistral-large-3"
    assert _model(J.build_judge_lm("faithfulness_judge")) == "azure/llama-4-maverick"


def test_openai_provider_without_key_raises_clear_error(monkeypatch):
    """LITHRIM_LLM_PROVIDER=openai now MEANS direct OpenAI — a missing key is a CLEAR error that
    points at OPENAI_API_KEY (and the azure alternative), NOT a silent fall-through to Azure."""
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        J.build_judge_lm("risk_judge")


def test_byo_claude_selector_still_routes_to_claude(monkeypatch):
    """Regression: a byo-claude per-role selector still returns ClaudeCliLM even under the new
    openai-direct default (the BYOC-1 routing precedes the openai branch)."""
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-byok")
    lm = J.build_judge_lm("risk_judge", model="byo-claude")
    assert type(lm).__name__ == "ClaudeCliLM"
