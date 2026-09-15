"""CALIBRATE-KEY-1: `lithrim calibrate` hands the optimizer the SAME per-role provider env a
grade runs with.

Found 2026-09-15 reviewing v0.1.30: cli/loop.py's step_optimize spawned scripts/optimize_judge.py
with a bare os.environ copy — no --model, no per-role binding, no key from the provider file the
UI writes. The BFF hydrates all three before a grade or a calibration, so a key connected in the
app worked everywhere EXCEPT `lithrim calibrate`, which fell back to the role's default
deployment (often un-deployed) and failed after the human had already paid for the grade."""

from __future__ import annotations

import pytest

from lithrim_bench.cli.loop import judge_env_for
from lithrim_bench.harness import role_bindings

ROLE = "ragtruth_detector"


@pytest.fixture
def provider_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    return tmp_path


def test_the_model_pin_becomes_the_roles_provider_and_model(provider_dir):
    env = judge_env_for(ROLE, "azure/gpt-4.1-2025-04-14", base={})
    assert env["LITHRIM_LLM_PROVIDER_RAGTRUTH_DETECTOR"] == "azure"
    assert env["LITHRIM_LLM_MODEL_RAGTRUTH_DETECTOR"] == "gpt-4.1-2025-04-14"


def test_an_openai_dated_id_binds_the_openai_provider(provider_dir):
    env = judge_env_for(ROLE, "openai/gpt-4.1-2025-04-14", base={})
    assert env["LITHRIM_LLM_PROVIDER_RAGTRUTH_DETECTOR"] == "openai"
    assert env["LITHRIM_LLM_MODEL_RAGTRUTH_DETECTOR"] == "gpt-4.1-2025-04-14"


def test_the_persisted_binding_wins_over_the_model_flag(provider_dir):
    role_bindings.save_binding(
        ROLE,
        {"provider": "azure", "model": "gpt-4.1-2025-04-14", "endpoint": "https://x.openai.azure.com",
         "api_version": "2026-05-01"},
        db_path=provider_dir / "provider_config.sqlite",
    )
    env = judge_env_for(ROLE, "openai/gpt-4o", base={})
    assert env["LITHRIM_LLM_MODEL_RAGTRUTH_DETECTOR"] == "gpt-4.1-2025-04-14"
    assert env["LITHRIM_LLM_API_BASE_RAGTRUTH_DETECTOR"] == "https://x.openai.azure.com"
    assert env["LITHRIM_LLM_API_VERSION_RAGTRUTH_DETECTOR"] == "2026-05-01"


def test_the_key_connected_in_the_app_reaches_the_role(provider_dir):
    """The secret lives only on .provider_env; the optimizer gets it as the ROLE's key."""
    (provider_dir / ".provider_env").write_text(
        'LITHRIM_LLM_API_KEY="sk-from-the-app"\nLITHRIM_LLM_PROVIDER=azure\n'
    )
    env = judge_env_for(ROLE, "azure/gpt-4.1-2025-04-14", base={})
    assert env["LITHRIM_LLM_API_KEY_RAGTRUTH_DETECTOR"] == "sk-from-the-app"


def test_a_role_key_already_in_the_environment_is_not_overwritten(provider_dir):
    (provider_dir / ".provider_env").write_text("LITHRIM_LLM_API_KEY=sk-from-the-file\n")
    env = judge_env_for(
        ROLE, "azure/gpt-4.1-2025-04-14", base={"LITHRIM_LLM_API_KEY_RAGTRUTH_DETECTOR": "sk-explicit"}
    )
    assert env["LITHRIM_LLM_API_KEY_RAGTRUTH_DETECTOR"] == "sk-explicit"


def test_no_binding_no_file_no_model_leaves_the_environment_alone(provider_dir):
    assert judge_env_for(ROLE, None, base={"PATH": "/usr/bin"}) == {"PATH": "/usr/bin"}


def test_the_secret_never_reaches_the_binding_store(provider_dir):
    (provider_dir / ".provider_env").write_text("LITHRIM_LLM_API_KEY=sk-secret\n")
    judge_env_for(ROLE, "azure/gpt-4.1-2025-04-14", base={})
    db = provider_dir / "provider_config.sqlite"
    if db.exists():
        assert "sk-secret" not in db.read_bytes().decode("utf-8", "ignore")
