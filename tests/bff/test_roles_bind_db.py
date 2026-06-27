"""ROLE-BINDINGS-DB (BFF) — the per-role binding lands in the config DB, not the .provider_env file.

The split: ``_persist_and_reload_provider`` writes the SECRET (api_key) to ``.provider_env`` and the
NON-SECRET binding ({provider, model, endpoint, api_version}) to the ``role_bindings`` config table;
``os.environ`` is hydrated from BOTH so the grade is unchanged. ``_read_role_bindings`` reads the DB.
A one-time startup migration carries any legacy per-role binding vars out of ``.provider_env`` into
the DB (so nothing is lost on the cut-over).

  * split: a judge env-var set → the binding in the DB, the key in the file, the binding NOT in the
    file, and os.environ carries the model (the grade's read).
  * readout: ``_read_role_bindings`` returns the DB binding.
  * chat: a chat_assistant env-var set splits the same way.
  * migration: a legacy ``.provider_env`` with per-role binding vars → imported to the DB; the
    non-secret vars are stripped from the file; the keys + global provider config stay.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

from lithrim_bench.harness import role_bindings as rb  # noqa: E402

_WATCH = [
    f"LITHRIM_LLM_{kind}_{role}"
    for role in ("RISK", "POLICY", "FAITHFULNESS")
    for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE", "API_VERSION")
] + [
    "LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_KEY",
    "LITHRIM_CHAT_API_BASE", "LITHRIM_CHAT_API_VERSION", "ANTHROPIC_API_KEY",
]


@pytest.fixture()
def split_env(tmp_path, monkeypatch):
    """Isolate the .provider_env sidecar + the role_bindings DB at tmp_path, force SQLite, and
    snapshot/restore the os.environ vars ``_persist_and_reload_provider`` writes globally."""
    monkeypatch.setattr(bff, "_PROVIDER_ENV_PATH", tmp_path / ".provider_env", raising=False)
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)  # → _PROVIDER_ENV_PATH (tmp)
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)  # force SQLite (the role_bindings db)
    snap = {k: os.environ.get(k) for k in _WATCH}
    try:
        yield tmp_path
    finally:
        for k, v in snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _file_env(tmp_path):
    return bff._parse_env_file(tmp_path / ".provider_env")


def test_judge_binding_lands_in_db_key_in_file(split_env):
    tmp_path = split_env
    bff._persist_and_reload_provider({
        "LITHRIM_LLM_PROVIDER_POLICY": "azure",
        "LITHRIM_LLM_MODEL_POLICY": "gpt-4.1",
        "LITHRIM_LLM_API_KEY_POLICY": "sk-POLICY-SECRET",
        "LITHRIM_LLM_API_BASE_POLICY": "https://az",
        "LITHRIM_LLM_API_VERSION_POLICY": "2024-08",
    })
    # the NON-SECRET binding is in the config DB
    out = rb.load_bindings(db_path=bff._role_bindings_db_path())
    assert out["policy_judge"]["provider"] == "azure"
    assert out["policy_judge"]["model"] == "gpt-4.1"
    assert out["policy_judge"]["endpoint"] == "https://az"
    assert "api_key" not in out["policy_judge"]
    # the SECRET key stays in the file; the binding vars do NOT
    env = _file_env(tmp_path)
    assert env.get("LITHRIM_LLM_API_KEY_POLICY") == "sk-POLICY-SECRET"
    assert "LITHRIM_LLM_MODEL_POLICY" not in env
    assert "LITHRIM_LLM_PROVIDER_POLICY" not in env
    # os.environ is hydrated (what build_judge_lm reads) — unchanged grade path
    assert os.environ.get("LITHRIM_LLM_MODEL_POLICY") == "gpt-4.1"
    assert os.environ.get("LITHRIM_LLM_API_KEY_POLICY") == "sk-POLICY-SECRET"


def test_read_role_bindings_reads_the_db(split_env):
    bff._persist_and_reload_provider({
        "LITHRIM_LLM_PROVIDER_RISK": "azure",
        "LITHRIM_LLM_MODEL_RISK": "gpt-4.1",
        "LITHRIM_LLM_API_KEY_RISK": "sk-RISK",
    })
    roles = bff._read_role_bindings()
    assert roles["risk_judge"] == {"provider": "azure", "model": "gpt-4.1"}
    assert roles["policy_judge"] is None  # unbound
    assert roles["faithfulness_judge"] is None


def test_chat_binding_stays_in_file_not_db(split_env):
    """The chat_assistant binding is NOT moved to the DB — loop.py reads it from .provider_env
    directly (council/dspy-free), so the whole chat binding stays file-based (a scope boundary)."""
    tmp_path = split_env
    bff._persist_and_reload_provider({
        "LITHRIM_CHAT_PROVIDER": "azure",
        "LITHRIM_CHAT_MODEL": "gpt-4.1",
        "LITHRIM_CHAT_API_KEY": "sk-CHAT-SECRET",
    })
    assert "chat_assistant" not in rb.load_bindings(db_path=bff._role_bindings_db_path())  # not a DB binding
    env = _file_env(tmp_path)
    assert env.get("LITHRIM_CHAT_PROVIDER") == "azure"  # provider/model stay in the file
    assert env.get("LITHRIM_CHAT_MODEL") == "gpt-4.1"
    assert env.get("LITHRIM_CHAT_API_KEY") == "sk-CHAT-SECRET"
    assert bff._read_role_bindings()["chat_assistant"] == {"provider": "azure", "model": "gpt-4.1"}


def test_migration_imports_legacy_file_bindings(split_env):
    tmp_path = split_env
    (tmp_path / ".provider_env").write_text(
        "AZURE_OPENAI_API_KEY=sk-GLOBAL\n"
        "AZURE_OPENAI_ENDPOINT=https://az\n"
        "LITHRIM_LLM_PROVIDER_RISK=azure\n"
        "LITHRIM_LLM_MODEL_RISK=gpt-4.1\n"
        "LITHRIM_LLM_API_KEY_RISK=sk-RISK\n"
        "LITHRIM_LLM_API_BASE_RISK=https://az\n"
    )
    bff._migrate_provider_env_bindings_to_db()
    # the binding moved to the DB
    out = rb.load_bindings(db_path=bff._role_bindings_db_path())
    assert out["risk_judge"]["model"] == "gpt-4.1"
    assert out["risk_judge"]["provider"] == "azure"
    # the non-secret per-role vars are stripped from the file; the key + global config stay
    env = _file_env(tmp_path)
    assert "LITHRIM_LLM_MODEL_RISK" not in env
    assert "LITHRIM_LLM_PROVIDER_RISK" not in env
    assert env.get("LITHRIM_LLM_API_KEY_RISK") == "sk-RISK"  # secret kept
    assert env.get("AZURE_OPENAI_API_KEY") == "sk-GLOBAL"  # global key kept
    assert env.get("AZURE_OPENAI_ENDPOINT") == "https://az"  # global config kept


def test_migration_is_idempotent_noop_when_db_has_bindings(split_env):
    tmp_path = split_env
    rb.save_binding("risk_judge", {"provider": "azure", "model": "already-here"}, db_path=bff._role_bindings_db_path())
    (tmp_path / ".provider_env").write_text("LITHRIM_LLM_MODEL_RISK=should-not-import\n")
    bff._migrate_provider_env_bindings_to_db()  # DB already populated → no-op
    out = rb.load_bindings(db_path=bff._role_bindings_db_path())
    assert out["risk_judge"]["model"] == "already-here"  # not clobbered by the legacy file
