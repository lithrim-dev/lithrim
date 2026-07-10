"""Persist a graded+grounded record: SSOT ``reports`` row + fs blob (transition mirror).

PERSIST-3a slice 2: the grade result is now a row in the one SSOT DB (``reports_store``,
``LITHRIM_DB_URL`` → Postgres else local SQLite), scoped by ``workspace_id`` and carrying the
record as linked JSON with ``verdict``/``run_id``/``scores`` projected out. The legacy
``out/<case_id>.json`` blob + the ``ws0.sqlite`` ``records`` doc-shim are kept as a transition
mirror (dual-write); ``load`` reads the SSOT first, the ``records`` row as fallback.

S-BS-4 (the ``records`` doc-shim): a single JSON text column, kept for back-compat during the
3a transition. Stdlib ``sqlite3`` for the legacy mirror; the SSOT row routes through the db layer.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "out" / "ws0"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    case_id    TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def persist(
    case_id: str,
    record: dict[str, Any],
    *,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    db_path: str | Path | None = None,
) -> dict[str, str]:
    """Write ``record`` to ``out_dir/<case_id>.json`` and a SQLite doc-shim row.

    Idempotent on ``case_id``: the fs blob is overwritten and the SQLite row is
    upserted, so a re-run produces the same store, not a growing one. Returns the
    two written paths for the caller to report.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(db_path) if db_path is not None else out_dir / "ws0.sqlite"

    blob_path = out_dir / f"{case_id}.json"
    blob_path.write_text(json.dumps(record, indent=2, sort_keys=True))

    # PERSIST-3a: the SSOT reports table is the source of truth (one DB selector); workspace_id
    # is derived from out_dir (``.../<name>/out`` → ``<name>``). Best-effort: a store hiccup never
    # fails a grade that already wrote its fs blob + the legacy records mirror below.
    from lithrim_bench.harness.db import workspace_id_of

    try:
        from lithrim_bench.harness import reports_store

        reports_store.save_report(
            case_id, record, db_path=db_path, workspace_id=workspace_id_of(out_dir)
        )
    except Exception:  # noqa: BLE001
        pass

    created_at = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(record, sort_keys=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        conn.execute(
            "INSERT INTO records (case_id, json, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(case_id) DO UPDATE SET json=excluded.json, created_at=excluded.created_at",
            (case_id, payload, created_at),
        )
        conn.commit()
    finally:
        conn.close()

    return {"blob": str(blob_path), "sqlite": str(db_path)}


def load(case_id: str, *, db_path: str | Path) -> dict[str, Any] | None:
    """Read a persisted record back. PERSIST-3a: the SSOT ``reports`` table first (one DB
    selector), the legacy ``ws0.sqlite`` ``records`` doc-shim as a transition fallback."""
    from lithrim_bench.harness.db import workspace_id_of

    try:
        from lithrim_bench.harness import reports_store

        rec = reports_store.load_report(
            case_id, db_path=db_path, workspace_id=workspace_id_of(Path(db_path).parent)
        )
        if rec is not None:
            return rec
    except Exception:  # noqa: BLE001 — a DB hiccup must not hide the legacy records mirror
        pass

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        row = conn.execute("SELECT json FROM records WHERE case_id = ?", (case_id,)).fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row else None
