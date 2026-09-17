"""MODEL-BIND-1: the model a judge is configured with is the model that grades it.

Found 2026-09-16 in the paid OpenAI reproduction of v0.1.31: `lithrim configure --model
openai/gpt-4.1-2025-04-14` PUTs the model onto the judge record, but the council resolves a
role's model from the per-role binding env (`LITHRIM_LLM_MODEL_<ROLE>`), which only
`_hydrate_workspace_judge_bindings_into_env` writes — and that skips any judge whose `provider`
field is empty. The CLI never sets `provider` (it puts the whole `provider/model` string in
`model`), so every vote ran on the provider default: 90 cases graded on gpt-4o while the arm
manifest said gpt-4.1-2025-04-14. The Azure pilot was masked because the default deployment
happened to be gpt-4.1.

A `provider/model` string on the judge record IS a provider binding — the prefix names it."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402

ROLE = "ragtruth_detector"
MODEL_VAR = "LITHRIM_LLM_MODEL_RAGTRUTH_DETECTOR"
PROVIDER_VAR = "LITHRIM_LLM_PROVIDER_RAGTRUTH_DETECTOR"


def _judge(**kw):
    fields = {"role": ROLE, "model": "", "provider": "", "endpoint": "", "api_version": ""}
    fields.update(kw)
    return types.SimpleNamespace(**fields)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv(MODEL_VAR, raising=False)
    monkeypatch.delenv(PROVIDER_VAR, raising=False)
    return types.SimpleNamespace(config_db=tmp_path / "cfg.sqlite", out_dir=tmp_path, name="w")


def _hydrate(monkeypatch, ws, judges):
    monkeypatch.setattr("lithrim_bench.harness.judges.list_judges", lambda **kw: judges)
    bff._hydrate_workspace_judge_bindings_into_env(ws)


def test_a_cli_configured_judge_grades_on_the_model_it_was_configured_with(monkeypatch, ws):
    """What `lithrim configure --model openai/gpt-4.1-2025-04-14` leaves on the record."""
    _hydrate(monkeypatch, ws, {ROLE: _judge(model="openai/gpt-4.1-2025-04-14")})
    import os

    assert os.environ.get(PROVIDER_VAR) == "openai"
    assert os.environ.get(MODEL_VAR) == "gpt-4.1-2025-04-14"


def test_an_azure_deployment_string_binds_the_same_way(monkeypatch, ws):
    _hydrate(monkeypatch, ws, {ROLE: _judge(model="azure/my-gpt41-deployment")})
    import os

    assert os.environ.get(PROVIDER_VAR) == "azure"
    assert os.environ.get(MODEL_VAR) == "my-gpt41-deployment"


def test_an_explicit_provider_field_still_wins(monkeypatch, ws):
    """The UI's bind writes provider + a bare model; that path is unchanged."""
    _hydrate(
        monkeypatch, ws,
        {ROLE: _judge(provider="azure", model="gpt-4.1", endpoint="https://x.openai.azure.com")},
    )
    import os

    assert os.environ.get(PROVIDER_VAR) == "azure" and os.environ.get(MODEL_VAR) == "gpt-4.1"


def test_a_bare_model_with_no_provider_binds_nothing(monkeypatch, ws):
    """Unchanged: a model with no provider to resolve it leaves the global row winning."""
    _hydrate(monkeypatch, ws, {ROLE: _judge(model="gpt-4.1")})
    import os

    assert os.environ.get(PROVIDER_VAR) is None and os.environ.get(MODEL_VAR) is None


def test_an_unknown_prefix_is_not_treated_as_a_provider(monkeypatch, ws):
    """`ft:gpt-4.1-mini:org::id` and friends are model ids, not provider/model pairs."""
    _hydrate(monkeypatch, ws, {ROLE: _judge(model="ft:gpt-4.1-mini:acme::abc123")})
    import os

    assert os.environ.get(PROVIDER_VAR) is None


def test_the_judge_read_reports_the_provider_the_prefix_names():
    """The read said provider "" for a CLI-configured judge, so the surface could not show which
    deployment the grade would reach — while claiming the model it would not use."""
    model, provider, source = bff._effective_model(
        _judge(model="openai/gpt-4.1-2025-04-14"), ROLE, {}
    )
    assert (model, provider, source) == ("gpt-4.1-2025-04-14", "openai", "override")


def test_the_read_and_the_hydration_agree_on_what_grades(monkeypatch, ws):
    jc = _judge(model="openai/gpt-4.1-2025-04-14")
    _hydrate(monkeypatch, ws, {ROLE: jc})
    import os

    model, provider, _ = bff._effective_model(jc, ROLE, {})
    assert (provider, model) == (os.environ[PROVIDER_VAR], os.environ[MODEL_VAR])
