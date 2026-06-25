"""CONFIG-PERSIST-1 — the in-app provider keys + per-role/chat bindings must persist across
``docker compose down``/``up`` (volume-kept, container-gone), wiped only by ``down -v``.

The live bug: ``.provider_env`` (the in-app-configured provider KEYS + the per-role bindings
``LITHRIM_LLM_*_<ROLE>`` + the chat binding ``LITHRIM_CHAT_*``) was at ``REPO_ROOT/.provider_env``
= ``/app/.provider_env`` in the container — the container's writable layer, NOT the ``/app/out``
named volume. So ``docker compose down`` (which removes the container) WIPES it: after ``up`` the
judge roster persists (config DB is in the volume) but every role is unbound + keyless. The fix
relocates ``.provider_env`` (+ the model-registry sidecar) into a configurable dir
(``LITHRIM_PROVIDER_ENV_DIR``, default ``REPO_ROOT`` for dev back-compat), defaulted to ``/app/out``
in docker-compose so it lives in the named volume.

These tests pin WHERE the file lives (the resolver + the round-trip + the boot restore + byte-compat
+ secret hygiene unchanged) — NOT what is written (that is ``test_provider_config.py``). Offline,
bare-CE: a tmp dir + ``LITHRIM_PROVIDER_ENV_DIR`` simulate the container-gone-but-volume-kept
``down``/``up``.
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

_AGENT = _BFF / "agent"
if str(_AGENT) not in sys.path:
    sys.path.insert(0, str(_AGENT))


def _isolate_provider_env(monkeypatch):
    """Drop the provider/LLM/chat env keys these tests touch so a write doesn't leak into the rest of
    the suite (monkeypatch restores them on teardown)."""
    keys = [
        "OPENAI_API_KEY", "LITHRIM_LLM_PROVIDER", "LITHRIM_LLM_PROVIDER_RISK",
        "LITHRIM_LLM_MODEL_RISK", "LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_API_KEY",
        "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_BASE",
    ]
    for k in keys:
        if k in os.environ:
            monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# 1) the resolver honors the env var and falls back to REPO_ROOT unset (non-vacuous)
# ---------------------------------------------------------------------------
def test_provider_env_dir_honors_the_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    assert bff._provider_env_dir() == tmp_path
    assert bff._provider_env_path() == tmp_path / ".provider_env"
    assert bff._models_registry_path() == tmp_path / ".models_registry.json"


def test_provider_env_dir_falls_back_to_repo_root_when_unset(monkeypatch):
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)
    # back-compat: unset → every path is byte-identical to today (REPO_ROOT/.provider_env)
    assert bff._provider_env_dir() == bff.REPO_ROOT
    assert bff._provider_env_path() == bff.REPO_ROOT / ".provider_env"
    assert bff._models_registry_path() == bff.REPO_ROOT / ".models_registry.json"


def test_provider_env_dir_non_vacuous(tmp_path, monkeypatch):
    """The env path and the repo-root path are genuinely different — the test is not vacuous."""
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)
    unset = bff._provider_env_path()
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    setp = bff._provider_env_path()
    assert unset != setp
    assert setp.parent == tmp_path


# ---------------------------------------------------------------------------
# 2) the persistence round-trip (the regression for the live bug)
# ---------------------------------------------------------------------------
def test_persistence_round_trip_volume_kept_container_gone(tmp_path, monkeypatch):
    """With ``LITHRIM_PROVIDER_ENV_DIR=<tmp>``, a write lands in ``<tmp>/.provider_env`` and a FRESH
    read returns the same vars — simulating ``down`` (container/os.environ gone) then ``up`` (volume
    kept). MUTATION (the RED): point the dir back at REPO_ROOT → the <tmp> read returns empty."""
    _isolate_provider_env(monkeypatch)
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))

    bff._persist_and_reload_provider(
        {
            "OPENAI_API_KEY": "sk-persist-ROUNDTRIP-do-not-leak",
            "LITHRIM_LLM_PROVIDER": "openai",
            "LITHRIM_LLM_PROVIDER_RISK": "openai",
            "LITHRIM_LLM_MODEL_RISK": "gpt-4o",
        }
    )

    written = tmp_path / ".provider_env"
    assert written.is_file(), "the write did not land in <tmp>/.provider_env (the named volume)"

    # FRESH read from the SAME dir — the only state is the on-disk file (the container is "gone")
    fresh = bff._parse_env_file(bff._provider_env_path())
    assert fresh["OPENAI_API_KEY"] == "sk-persist-ROUNDTRIP-do-not-leak"
    assert fresh["LITHRIM_LLM_PROVIDER"] == "openai"
    assert fresh["LITHRIM_LLM_PROVIDER_RISK"] == "openai"
    assert fresh["LITHRIM_LLM_MODEL_RISK"] == "gpt-4o"

    # MUTATION proof (would-be RED): a read keyed at REPO_ROOT (the OLD location, the container's
    # writable layer) returns NONE of the persisted vars — i.e. the bug.
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)
    repo_root_read = bff._parse_env_file(bff._provider_env_path())
    assert "sk-persist-ROUNDTRIP-do-not-leak" not in repo_root_read.values()


# ---------------------------------------------------------------------------
# 3) app + loop agree — the chat binding round-trips through the relocated file
# ---------------------------------------------------------------------------
def test_app_and_loop_agree_on_the_relocated_provider_env(tmp_path, monkeypatch):
    """loop.py's ``.provider_env`` fallback resolves to the SAME <tmp> dir when
    ``LITHRIM_PROVIDER_ENV_DIR`` is set: a ``LITHRIM_CHAT_*`` bind written by the app round-trips to
    ``_chat_provider_config()`` reading the relocated file (os.environ cleared first to force the
    file path). loop.py cannot import app.py — it reads the env var directly."""
    _isolate_provider_env(monkeypatch)
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))

    import loop  # apps/bff/agent/loop.py

    bff._persist_and_reload_provider(
        {
            "LITHRIM_CHAT_PROVIDER": "openai",
            "LITHRIM_CHAT_MODEL": "gpt-4o",
            "LITHRIM_CHAT_API_KEY": "sk-chat-RELOCATED-do-not-leak",
        }
    )

    # clear os.environ for these so loop.py MUST read the on-disk relocated file
    for k in ("LITHRIM_CHAT_PROVIDER", "LITHRIM_CHAT_MODEL", "LITHRIM_CHAT_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    cfg = loop._chat_provider_config()
    assert cfg is not None, "loop.py did not find the relocated chat binding"
    assert cfg["provider"] == "openai"
    assert cfg["model"] == "gpt-4o"
    assert cfg["api_key"] == "sk-chat-RELOCATED-do-not-leak"


def test_loop_keeps_reading_dev_env_files_at_repo_root(tmp_path, monkeypatch):
    """Only ``.provider_env`` relocates — ``.env`` / ``.live_env`` (dev-author files) stay read at the
    repo root. loop.py's repo-root resolver is unchanged; the relocatable ``.provider_env`` dir
    follows the env var."""
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))
    import loop

    assert loop._provider_config_root() == bff.REPO_ROOT
    assert loop._relocatable_provider_env_dir() == tmp_path
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)
    assert loop._relocatable_provider_env_dir() == bff.REPO_ROOT


# ---------------------------------------------------------------------------
# 4) boot restore — _load_provider_env() restores os.environ from the persisted file
# ---------------------------------------------------------------------------
def test_boot_restore_repopulates_os_environ_from_persisted_file(tmp_path, monkeypatch):
    """Writing to ``<tmp>/.provider_env`` then calling ``_load_provider_env()`` (the
    ``@app.on_event('startup')`` path) repopulates ``os.environ`` — the ``up``-restores-config proof.
    A post-``up`` BFF restores keys + bindings into os.environ → grading + chat come back."""
    _isolate_provider_env(monkeypatch)
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))

    (tmp_path / ".provider_env").write_text(
        "OPENAI_API_KEY=sk-boot-RESTORE-do-not-leak\n"
        "LITHRIM_LLM_PROVIDER=openai\n"
        "LITHRIM_LLM_PROVIDER_RISK=openai\n"
        "LITHRIM_CHAT_PROVIDER=openai\n"
    )
    # simulate the container restart: the keys are NOT yet in os.environ
    for k in ("OPENAI_API_KEY", "LITHRIM_LLM_PROVIDER", "LITHRIM_LLM_PROVIDER_RISK",
              "LITHRIM_CHAT_PROVIDER"):
        monkeypatch.delenv(k, raising=False)

    bff._load_provider_env()  # the startup boot path

    assert os.environ.get("OPENAI_API_KEY") == "sk-boot-RESTORE-do-not-leak"
    assert os.environ.get("LITHRIM_LLM_PROVIDER") == "openai"
    assert os.environ.get("LITHRIM_LLM_PROVIDER_RISK") == "openai"
    assert os.environ.get("LITHRIM_CHAT_PROVIDER") == "openai"


# ---------------------------------------------------------------------------
# 5) back-compat — unset → byte-identical to today; secret hygiene unchanged
# ---------------------------------------------------------------------------
def test_back_compat_unset_is_byte_identical_to_today(monkeypatch):
    monkeypatch.delenv("LITHRIM_PROVIDER_ENV_DIR", raising=False)
    assert bff._provider_env_path() == bff.REPO_ROOT / ".provider_env"
    assert bff._provider_status_path() == bff.REPO_ROOT / ".provider_status.json"
    assert bff._models_registry_path() == bff.REPO_ROOT / ".models_registry.json"


def test_relocated_file_is_still_write_only_no_key_in_a_response(tmp_path, monkeypatch):
    """Secret hygiene is unchanged by the relocation: the relocated ``.provider_env`` carries the key
    write-only and the key is NEVER in any response. Non-vacuous: the key IS on disk, NOT in the
    endpoint body."""
    _isolate_provider_env(monkeypatch)
    monkeypatch.setenv("LITHRIM_PROVIDER_ENV_DIR", str(tmp_path))

    from fastapi.testclient import TestClient

    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    ws = ws_mod.create_workspace("persist_hygiene", pack="_core", seed=False)
    ws_mod.set_active_workspace(ws.name)

    def _fake_probe(*, plane, provider, api_key, endpoint=None, model=None, role=None, api_version=None):
        return {"ok": True}

    monkeypatch.setattr(bff, "_probe_provider", _fake_probe)

    secret = "sk-persist-HYGIENE-do-not-leak"
    client = TestClient(bff.app)
    resp = client.post(
        "/v1/provider/config",
        json={"plane": "grading", "provider": "openai", "api_key": secret, "model": "gpt-4o"},
    )
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text  # NEVER in a response

    # the key IS on disk in the RELOCATED file (non-vacuity: the write happened, just not to REPO_ROOT)
    written = tmp_path / ".provider_env"
    assert written.is_file()
    assert f"OPENAI_API_KEY={secret}" in written.read_text()

    importlib.reload(ws_mod)
