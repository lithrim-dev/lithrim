"""Persist a graded+grounded record: fs blob + SQLite document-shim.

S-BS-4 is DECIDED = document shim: the SQLite table is a single JSON text column,
NOT relational tables, so the store swaps back to Mongo cleanly later (WS-1+). The
fs blob (``out/ws0/<case_id>.json``) is the human-readable mirror; the SQLite row
is the queryable index. Both are keyed by ``case_id`` and idempotent — re-running
the same case overwrites the same key rather than accumulating duplicates.

Stdlib ``sqlite3`` only — no new dependency.
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
    """Read a persisted record back out of the SQLite doc-shim (round-trip aid)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        row = conn.execute("SELECT json FROM records WHERE case_id = ?", (case_id,)).fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row else None
