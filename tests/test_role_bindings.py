"""ROLE-BINDINGS-DB — the per-role model-binding config-plane store.

The NON-SECRET half of a provider binding ({provider, model, endpoint, api_version} per council
role) is a first-class config-plane entity in the DB (PG via LITHRIM_DB_URL, else SQLite) — NOT a
loose ``.provider_env`` file. The API KEY is DELIBERATELY excluded — it stays in the secret store.

  * roundtrip: save → load returns the binding.
  * upsert: a second save on the same role OVERWRITES (one row), not a second insert.
  * secret hygiene: an ``api_key`` in the binding dict is dropped — never persisted, never in the
    raw db bytes (the whole point of the split).
  * portability: the upsert SQL is ``ON CONFLICT … EXCLUDED`` (works on Postgres AND SQLite),
    never ``INSERT OR REPLACE`` (SQLite-only — the trap this store must not fall into).
  * delete: removes a row; idempotent no-op (False) on a missing role.
"""

from __future__ import annotations

import inspect

from lithrim_bench.harness import role_bindings as rb


def test_save_load_roundtrip(tmp_path):
    db = tmp_path / "provider_config.sqlite"
    rb.save_binding(
        "risk_judge",
        {"provider": "azure", "model": "gpt-4.1", "endpoint": "https://x", "api_version": "2024-08"},
        db_path=db,
    )
    out = rb.load_bindings(db_path=db)
    assert out["risk_judge"]["provider"] == "azure"
    assert out["risk_judge"]["model"] == "gpt-4.1"
    assert out["risk_judge"]["endpoint"] == "https://x"


def test_upsert_overwrites_single_row(tmp_path):
    db = tmp_path / "provider_config.sqlite"
    rb.save_binding("policy_judge", {"provider": "azure", "model": "Mistral-Large-3"}, db_path=db)
    rb.save_binding("policy_judge", {"provider": "azure", "model": "gpt-4.1"}, db_path=db)
    out = rb.load_bindings(db_path=db)
    assert out["policy_judge"]["model"] == "gpt-4.1"  # the second write wins
    assert list(out.keys()) == ["policy_judge"]  # ONE row, not two (upsert, not insert)


def test_api_key_never_persisted(tmp_path):
    db = tmp_path / "provider_config.sqlite"
    rb.save_binding(
        "risk_judge",
        {"provider": "azure", "model": "gpt-4.1", "api_key": "sk-MUST-NOT-PERSIST-deadbeef"},
        db_path=db,
    )
    out = rb.load_bindings(db_path=db)
    assert "api_key" not in out["risk_judge"]
    # NON-VACUOUS: the secret is nowhere in the on-disk db bytes
    assert b"sk-MUST-NOT-PERSIST-deadbeef" not in db.read_bytes()


def test_upsert_sql_is_postgres_portable():
    src = inspect.getsource(rb.save_binding)
    assert "ON CONFLICT" in src, "must use the portable ON CONFLICT … EXCLUDED upsert"
    assert "INSERT OR REPLACE" not in src, "INSERT OR REPLACE is SQLite-only — breaks Postgres"


def test_delete_binding(tmp_path):
    db = tmp_path / "provider_config.sqlite"
    rb.save_binding("risk_judge", {"provider": "azure", "model": "gpt-4.1"}, db_path=db)
    assert rb.delete_binding("risk_judge", db_path=db) is True
    assert rb.delete_binding("risk_judge", db_path=db) is False  # idempotent
    assert rb.load_bindings(db_path=db) == {}


def test_load_empty_is_empty_dict(tmp_path):
    db = tmp_path / "provider_config.sqlite"
    assert rb.load_bindings(db_path=db) == {}  # provisions the table; no rows
