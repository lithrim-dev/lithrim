"""PERSIST-CONV — durable conversation persistence (the chat thread survives a refresh).

The conversational shell's chat thread lived ONLY in CenterPane React state, keyed by a
remount sessionKey, so a browser refresh wiped it. This adds a backend conversation store
mirroring the agents table: a plain (un-audited) per-(workspace, agent) thread blob, with a
GET/PUT pair on the BFF. Auditing every turn would bloat the §2B log — the conversation is
high-frequency UX state, not an audited config change (the config WRITES inside it are
already audited on their own routes).

Acceptance (driver §TESTS FIRST):
  * A1 — GET on an agent with no stored thread → ``{"thread": []}`` (clean default, no 404).
  * A2 — PUT a thread then GET returns it byte-equivalent (the round-trip survives).
  * A3 — workspace isolation: a thread saved under one config DB is absent under another.
  * A4 — save_conversation/load_conversation unit round-trip (the store primitive itself).
  * A5 — DELETE clears the thread (the "clear conversation" affordance): next GET → ``[]``.
  * A6 — DELETE on an agent with no stored thread is an idempotent no-op (200, ``removed=False``).
  * A7 — delete_conversation unit: True iff a row was removed; idempotent; workspace-isolated.

Requires the ``[bff]`` extra (fastapi); skipped cleanly if absent so the default suite stays
green. Hermetic — a tmp config DB via the get_config_db dependency override (the tests/bff/
TestClient pattern); no network, no live :8002, pack-independent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import (
    delete_conversation,
    load_conversation,
    save_conversation,
)

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

# A representative thread: the {role, text, parts} message shape the shell persists.
_THREAD = [
    {"role": "user", "text": "my domain is radiology"},
    {"role": "assistant", "text": "Authoring the risk judge.", "parts": []},
    {"role": "user", "text": "what did we just do?"},
]


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "bench_config.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_get_conversation_no_stored_thread_is_empty(client):
    """A1: GET on an agent with no stored thread returns an empty thread (not a 404)."""
    resp = client.get("/v1/conversation", params={"agent": "ws0_default"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent"] == "ws0_default"
    assert body["thread"] == []


def test_put_then_get_conversation_round_trips(client):
    """A2: a PUT thread is returned byte-equivalent by the next GET (the refresh survives)."""
    put = client.put("/v1/conversation", json={"agent": "ws0_default", "thread": _THREAD})
    assert put.status_code == 200, put.text
    assert put.json() == {"ok": True, "agent": "ws0_default", "n": len(_THREAD)}

    got = client.get("/v1/conversation", params={"agent": "ws0_default"})
    assert got.status_code == 200, got.text
    assert got.json()["thread"] == _THREAD


def test_conversation_is_workspace_isolated(tmp_path):
    """A3: a thread saved under one config DB is ABSENT under another (the tenancy boundary —
    non-vacuous vs the round-trip above)."""
    db_a = tmp_path / "a" / "bench_config.sqlite"
    db_b = tmp_path / "b" / "bench_config.sqlite"
    db_a.parent.mkdir(parents=True)
    db_b.parent.mkdir(parents=True)

    save_conversation("ws0_default", _THREAD, db_path=db_a)

    assert load_conversation("ws0_default", db_path=db_a) == _THREAD
    assert load_conversation("ws0_default", db_path=db_b) == []


def test_save_load_conversation_unit_round_trip(tmp_path):
    """A4: the store primitive itself round-trips (and an absent agent is an empty list, not a
    KeyError — the conversation default is benign, unlike load_agent)."""
    db_path = tmp_path / "bench_config.sqlite"
    assert load_conversation("never_saved", db_path=db_path) == []

    save_conversation("ws0_default", _THREAD, db_path=db_path)
    assert load_conversation("ws0_default", db_path=db_path) == _THREAD

    # idempotent overwrite — the latest thread wins (per-turn upsert, no history shadow)
    shorter = _THREAD[:1]
    save_conversation("ws0_default", shorter, db_path=db_path)
    assert load_conversation("ws0_default", db_path=db_path) == shorter


def test_delete_then_get_conversation_is_empty(client):
    """A5: a DELETE clears the stored thread — the next GET returns the empty default (the
    'clear conversation' affordance round-trips through the store)."""
    client.put("/v1/conversation", json={"agent": "ws0_default", "thread": _THREAD})
    assert client.get("/v1/conversation", params={"agent": "ws0_default"}).json()["thread"] == _THREAD

    deleted = client.delete("/v1/conversation", params={"agent": "ws0_default"})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True, "agent": "ws0_default", "removed": True}

    after = client.get("/v1/conversation", params={"agent": "ws0_default"})
    assert after.status_code == 200, after.text
    assert after.json()["thread"] == []


def test_delete_absent_conversation_is_idempotent(client):
    """A6: clearing an agent with no stored thread is an idempotent no-op (200, removed=False) —
    a brand-new chat's clear affordance never 404s."""
    resp = client.delete("/v1/conversation", params={"agent": "never_saved"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "agent": "never_saved", "removed": False}


def test_delete_conversation_unit_present_then_absent(tmp_path):
    """A7: the delete primitive itself — True iff a row was removed; idempotent on a second call;
    workspace-isolated (clearing one config DB leaves another's thread intact)."""
    db_a = tmp_path / "a" / "bench_config.sqlite"
    db_b = tmp_path / "b" / "bench_config.sqlite"
    db_a.parent.mkdir(parents=True)
    db_b.parent.mkdir(parents=True)

    save_conversation("ws0_default", _THREAD, db_path=db_a)
    save_conversation("ws0_default", _THREAD, db_path=db_b)

    assert delete_conversation("ws0_default", db_path=db_a) is True
    assert load_conversation("ws0_default", db_path=db_a) == []
    # idempotent — a second clear removes nothing
    assert delete_conversation("ws0_default", db_path=db_a) is False
    # workspace isolation — db_b's thread is untouched by clearing db_a
    assert load_conversation("ws0_default", db_path=db_b) == _THREAD
