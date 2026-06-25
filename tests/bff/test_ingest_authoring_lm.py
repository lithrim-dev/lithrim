"""INGEST-LM-1 — the ingest JUTE-transform is authored with the CONFIGURED provider.

The confirmed live bug: ``_ingest_cases`` defaulted its generation LM to
``build_claude_cli_lm()`` whenever ``dspy.settings.lm`` was unset (the BFF sets no global
LM). In Docker the ``claude`` CLI binary is absent → ``FileNotFoundError: 'claude'`` BEFORE
the :3031 mapper is ever contacted, even though the user configured Azure.

The fix: ``_build_authoring_lm()`` resolves the ingest generation LM from the configured
provider in order — ``dspy.settings.lm`` (offline short-circuit) → the configured CHAT
provider (``_chat_provider_config()`` → a litellm ``dspy.LM``, azure threading api_version) →
the configured GRADING provider (``build_judge_lm("risk_judge")``, which respects byo-claude
/ azure) → a clear ``RuntimeError`` telling the human to configure a provider. The blind
``claude``-CLI default is REMOVED — ``claude`` is reachable ONLY via an explicit byo-claude
config through ``build_judge_lm``.

These tests are bare-CE / offline: ``dspy.LM`` / ``build_judge_lm`` / ``_chat_provider_config``
are mocked — NO network, NO ``claude`` binary. ``build_claude_cli_lm`` is patched to RAISE so
that reaching the old blind default is a test failure (the non-vacuous live-bug assertion).

Requires the ``[bff]`` extra (fastapi) — ``import app`` is the BFF surface; skipped cleanly
on a bare core. Pack-independent (no healthcare reads).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import loop as agent_loop  # noqa: E402


class _SpyLM:
    """A stand-in dspy.LM — records the model string + kwargs it was constructed with."""

    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs


def _no_global_lm(monkeypatch):
    """Force ``dspy.settings.lm`` to None for the 'BFF sets no global LM' precondition."""
    import dspy

    monkeypatch.setattr(dspy.settings, "lm", None, raising=False)


def _claude_default_must_not_fire(monkeypatch):
    """Patch ``build_claude_cli_lm`` to RAISE — reaching the old blind default fails the test."""
    import lithrim_bench.runtime.council.byo_claude_lm as B

    def _boom(*_a, **_k):
        raise AssertionError("the blind claude-CLI default was reached — it must be gone")

    monkeypatch.setattr(B, "build_claude_cli_lm", _boom)


# ── the live bug, non-vacuous: azure chat configured → the configured LM, never claude ──


def test_azure_chat_configured_builds_configured_lm_never_claude(monkeypatch):
    """With a configured azure CHAT provider and ``dspy.settings.lm=None``,
    ``_build_authoring_lm()`` builds a litellm ``dspy.LM`` for ``azure/gpt-4.1`` (model string
    + threaded ``api_version``) and NEVER calls ``build_claude_cli_lm`` (patched to raise)."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    monkeypatch.setattr(
        agent_loop,
        "_chat_provider_config",
        lambda: {
            "provider": "azure",
            "model": "gpt-4.1",
            "api_key": "sk-azure",
            "api_base": "https://my.openai.azure.com",
            "api_version": "2024-10-21",
        },
    )
    import dspy

    monkeypatch.setattr(dspy, "LM", _SpyLM)

    lm = bff._build_authoring_lm()

    assert isinstance(lm, _SpyLM)
    assert lm.model == "azure/gpt-4.1"  # litellm prefix + the configured model
    assert lm.kwargs.get("api_version") == "2024-10-21"  # azure api_version threaded
    assert lm.kwargs.get("api_key") == "sk-azure"
    assert lm.kwargs.get("api_base") == "https://my.openai.azure.com"


def test_azure_chat_api_version_defaults_to_council_default(monkeypatch):
    """An azure chat config WITHOUT an explicit api_version falls back to the council default
    (``settings.AZURE_OPENAI_API_VERSION``) — never empty (the litellm DeploymentNotFound wall)."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    from lithrim_bench.runtime.council.settings import settings

    monkeypatch.setattr(
        agent_loop,
        "_chat_provider_config",
        lambda: {
            "provider": "azure",
            "model": "gpt-4.1",
            "api_key": "sk-azure",
            "api_base": "https://my.openai.azure.com",
            "api_version": None,
        },
    )
    import dspy

    monkeypatch.setattr(dspy, "LM", _SpyLM)

    lm = bff._build_authoring_lm()

    assert lm.kwargs.get("api_version") == settings.AZURE_OPENAI_API_VERSION


def test_openai_chat_configured_omits_api_version(monkeypatch):
    """A non-azure (openai) chat config builds ``openai/<model>`` with NO api_version key."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    monkeypatch.setattr(
        agent_loop,
        "_chat_provider_config",
        lambda: {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-openai",
            "api_base": "",
            "api_version": None,
        },
    )
    import dspy

    monkeypatch.setattr(dspy, "LM", _SpyLM)

    lm = bff._build_authoring_lm()

    assert lm.model == "openai/gpt-4o"
    assert "api_version" not in lm.kwargs


# ── chat unset / anthropic → fall to the grading provider via build_judge_lm ──


def test_chat_unset_falls_to_grading_provider(monkeypatch):
    """When ``_chat_provider_config()`` returns None (anthropic-SDK chat / unset), the helper
    falls to the configured GRADING provider via ``build_judge_lm("risk_judge")`` and uses
    that as the authoring LM — never the blind claude default."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    monkeypatch.setattr(agent_loop, "_chat_provider_config", lambda: None)

    grading_lm = SimpleNamespace(model="azure/council-deployment")
    calls = {"role": None}

    import lithrim_bench.runtime.council.judges_dspy as J

    def _spy_build_judge_lm(role, **_k):
        calls["role"] = role
        return grading_lm

    monkeypatch.setattr(J, "build_judge_lm", _spy_build_judge_lm)

    lm = bff._build_authoring_lm()

    assert lm is grading_lm
    assert calls["role"] == "risk_judge"


def test_explicit_byo_claude_grading_still_works(monkeypatch):
    """Explicit byo-claude grading (``build_judge_lm`` returns the CLI LM) still works — the
    CLI is reachable ONLY via that explicit config, not the blind default. No BYO-Claude
    regression."""
    _no_global_lm(monkeypatch)
    monkeypatch.setattr(agent_loop, "_chat_provider_config", lambda: None)

    cli_lm = SimpleNamespace(model="byo-claude")  # what an explicit byo-claude build returns

    import lithrim_bench.runtime.council.judges_dspy as J

    monkeypatch.setattr(J, "build_judge_lm", lambda role, **_k: cli_lm)

    lm = bff._build_authoring_lm()

    assert lm is cli_lm  # explicit byo-claude grading flows through build_judge_lm, unchanged


# ── dspy.settings.lm set (injected predictor) → byte-identical short-circuit ──


def test_settings_lm_set_short_circuits(monkeypatch):
    """When ``dspy.settings.lm`` is set (offline tests / an explicit global LM) the helper
    returns it verbatim — neither the chat config nor build_judge_lm is consulted (the
    offline path is byte-identical)."""
    import dspy

    sentinel = object()
    monkeypatch.setattr(dspy.settings, "lm", sentinel, raising=False)

    def _chat_must_not_fire():
        raise AssertionError("_chat_provider_config consulted on the settings.lm short-circuit")

    monkeypatch.setattr(agent_loop, "_chat_provider_config", _chat_must_not_fire)

    assert bff._build_authoring_lm() is sentinel


# ── truly-unconfigured → a clear RuntimeError (not FileNotFoundError / 'claude') ──


def test_unconfigured_raises_actionable_runtimeerror(monkeypatch):
    """Nothing configured + no LM resolvable → a ``RuntimeError`` telling the human to
    configure a provider in Connect AI (NOT a bare ``FileNotFoundError``/``'claude'``)."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    monkeypatch.setattr(agent_loop, "_chat_provider_config", lambda: None)

    import lithrim_bench.runtime.council.judges_dspy as J

    def _grading_unconfigured(role, **_k):
        raise ValueError("AZURE_OPENAI_DEPLOYMENT_COUNCIL is unset")

    monkeypatch.setattr(J, "build_judge_lm", _grading_unconfigured)

    with pytest.raises(RuntimeError, match="(?i)configure a provider"):
        bff._build_authoring_lm()


# ── end-to-end wire: _ingest_cases drives the configured authoring LM, not claude ──


def _real_ctx(tmp_path):
    from lithrim_bench.harness.audit import Actor

    return bff._build_tool_context(
        req_agent="ws0_default",
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def test_ingest_cases_uses_configured_authoring_lm_end_to_end(tmp_path, monkeypatch):
    """The end-to-end wire: with ``dspy.settings.lm=None`` + an azure CHAT provider configured,
    ``_ingest_cases`` authors with the CONFIGURED LM (captured via the ``dspy.context(lm=...)``
    that wraps ``best_of_n_extractor``) and NEVER reaches the blind claude default — proving the
    wire, not just the helper."""
    _no_global_lm(monkeypatch)
    _claude_default_must_not_fire(monkeypatch)
    monkeypatch.setattr(
        agent_loop,
        "_chat_provider_config",
        lambda: {
            "provider": "azure",
            "model": "gpt-4.1",
            "api_key": "sk-azure",
            "api_base": "https://my.openai.azure.com",
            "api_version": "2024-10-21",
        },
    )
    import dspy

    monkeypatch.setattr(dspy, "LM", _SpyLM)

    captured = {"lm": None}

    def fake_bon(make_gen, rules, sample, n=3):
        captured["lm"] = dspy.settings.lm  # the dspy.context(lm=gen_lm) is active here
        return SimpleNamespace(accepted=True, jute_transform="t")

    cases = [{"case_id": "a", "response": "x"}]
    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr(
        "lithrim_bench.verification.score_extraction",
        lambda *a, **k: {"accepted": True, "count": 1, "nulls": 0, "cases": cases},
    )
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")

    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            return {"id": 777}

    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeClient)

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            pass

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )

    ctx = _real_ctx(tmp_path)
    out = ctx.ingest_cases('{"resource": {"id": "x"}}')

    assert out["count"] == 1 and out["mapping_id"] == 777
    assert isinstance(captured["lm"], _SpyLM)  # the configured azure LM authored the transform
    assert captured["lm"].model == "azure/gpt-4.1"
