"""A keyless install can build the council; only a real client USE fails, and clearly.

Observed 2026-09-09: with every judge bound to ``byo-claude`` (the local claude CLI, no API
key) a confirmed grade 500'd before any judge ran, because ``ComplianceCouncil.__init__``
eagerly constructs an OpenAI client and openai>=2 rejects an empty key. The authored grade
path never calls that client. The same eager construction made
``tests/test_neutral_default.py`` fail credential-free at HEAD, and made the documented
global switch ``LITHRIM_LLM_PROVIDER=claude-cli`` raise ``ValueError`` on construction.
"""

from __future__ import annotations

import pytest

from lithrim_bench.runtime.council import llm_provider
from lithrim_bench.runtime.council.settings import settings

MARKER = "is unset; required to bind"


@pytest.fixture(autouse=True)
def _fresh_clients():
    llm_provider.reset_clients()
    yield
    llm_provider.reset_clients()


def test_openai_provider_without_a_key_defers_the_failure_to_first_use(monkeypatch):
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    client, model = llm_provider.get_sync_openai_client(purpose="council")
    assert model == ""
    with pytest.raises(ValueError, match=MARKER):
        _ = client.chat
    with pytest.raises(ValueError, match="byo-claude"):
        _ = client.chat


def test_claude_cli_global_switch_builds_without_an_openai_client(monkeypatch):
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "claude-cli")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    client, _ = llm_provider.get_sync_openai_client(purpose="council")
    with pytest.raises(ValueError, match=MARKER):
        _ = client.chat


def test_compliance_council_constructs_keyless(monkeypatch):
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil, CouncilModel

    council = ComplianceCouncil(
        models=[CouncilModel(name="risk_judge", provider="authored", model="risk_judge")]
    )
    assert isinstance(council._openai, llm_provider._UnconfiguredClient)


def test_a_configured_openai_key_still_builds_a_real_client(monkeypatch):
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-not-used")
    client, model = llm_provider.get_sync_openai_client(purpose="council")
    assert type(client).__name__ == "OpenAI" and model == "gpt-4o"
