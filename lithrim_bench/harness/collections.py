"""Four slim-path doc-shim collections — S-BS-4 (DECIDED = document shim).

WHY DOC-SHIM, NOT RELATIONAL (the rationale A3 requires recorded):
These four collections mirror the Mongo collections the in-process M1 runtime uses
(``conversation_item``, ``conversation_session``, ``call_kpi``,
``compliance_report``). The harness needs a local, dependency-free store for them
now, but the WS-6 compartmentalize-local milestone may swap the store back to Mongo
(or forward to a managed document DB). A *document shim* — one ``json TEXT`` column
per row plus a few indexed key columns extracted from that JSON — keeps the swap
clean: the row IS the document, so a later store change is a write-path change, not
a schema migration. Normalizing these into relational tables now would (a) freeze a
schema we don't yet need to query relationally, and (b) make the Mongo swap-back a
data-modelling exercise instead of a connector change. The indexed keys exist only
so the slim path can look a row up by its natural id / foreign key without scanning
the JSON. This mirrors the WS-0 ``persist.py`` doc-shim exactly (single JSON column,
idempotent upsert on the primary key) — same decision, four more collections.

Stdlib ``sqlite3`` only — no new dependency.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLLECTIONS_DB = REPO_ROOT / "out" / "config" / "bench_collections.sqlite"


@dataclass(frozen=True)
class DocShimCollection:
    """A single doc-shim table: a JSON document + one indexed foreign key.

    ``name`` is the table/collection name; ``fk`` is the JSON field promoted to an
    indexed column so callers can fetch a document set by its natural foreign key
    (e.g. all conversation_items for a session_id) without scanning JSON. ``id_field``
    is the JSON field used as the primary key.
    """

    name: str
    id_field: str
    fk: str

    def _schema(self) -> str:
        return (
            f"CREATE TABLE IF NOT EXISTS {self.name} (\n"
            "    id         TEXT PRIMARY KEY,\n"
            "    fk         TEXT,\n"
            "    json       TEXT NOT NULL,\n"
            "    created_at TEXT NOT NULL\n"
            ");\n"
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_fk ON {self.name}(fk)"
        )

    def insert(self, doc: dict[str, Any], *, db_path: str | Path = DEFAULT_COLLECTIONS_DB) -> str:
        """Upsert a document (idempotent on its id_field). Returns the db path."""
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        doc_id = str(doc[self.id_field])
        fk_val = doc.get(self.fk)
        fk_val = str(fk_val) if fk_val is not None else None
        payload = json.dumps(doc, sort_keys=True)
        created_at = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(self._schema())
            conn.execute(
                f"INSERT INTO {self.name} (id, fk, json, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET fk=excluded.fk, json=excluded.json, "
                "created_at=excluded.created_at",
                (doc_id, fk_val, payload, created_at),
            )
            conn.commit()
        finally:
            conn.close()
        return str(db_path)

    def get(self, doc_id: str, *, db_path: str | Path = DEFAULT_COLLECTIONS_DB) -> dict | None:
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(self._schema())
            row = conn.execute(f"SELECT json FROM {self.name} WHERE id = ?", (doc_id,)).fetchone()
        finally:
            conn.close()
        return json.loads(row[0]) if row else None

    def find_by_fk(
        self, fk_val: str, *, db_path: str | Path = DEFAULT_COLLECTIONS_DB
    ) -> list[dict]:
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(self._schema())
            rows = conn.execute(
                f"SELECT json FROM {self.name} WHERE fk = ? ORDER BY id", (fk_val,)
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]

    def list_all(
        self,
        *,
        db_path: str | Path = DEFAULT_COLLECTIONS_DB,
        limit: int | None = None,
        newest_first: bool = True,
    ) -> list[dict]:
        """All documents in the collection, ``created_at``-ordered (newest-first by
        default). Returns ``[]`` when the table is empty / absent. Backs the UAP-3
        ``GET /v1/runs`` run-history list off ``PIPELINE_RUNS`` without leaking the
        doc-shim's SQL into the BFF."""
        order = "DESC" if newest_first else "ASC"
        sql = f"SELECT json FROM {self.name} ORDER BY created_at {order}, id {order}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(self._schema())
            rows = conn.execute(sql).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]


CONVERSATION_ITEM = DocShimCollection("conversation_item", id_field="item_id", fk="session_id")
CONVERSATION_SESSION = DocShimCollection(
    "conversation_session", id_field="session_id", fk="call_id"
)
CALL_KPI = DocShimCollection("call_kpi", id_field="kpi_id", fk="session_id")
COMPLIANCE_REPORT = DocShimCollection("compliance_report", id_field="report_id", fk="case_id")

COLLECTIONS: tuple[DocShimCollection, ...] = (
    CONVERSATION_ITEM,
    CONVERSATION_SESSION,
    CALL_KPI,
    COMPLIANCE_REPORT,
)

# WS-6d: the in-process pipeline's provenance sink. Mirrors the backend's
# ``pipeline_runs`` collection (``app/services/pipeline/provenance.py``
# COLLECTION_NAME) — one audit doc per run, keyed on ``pipeline_run_id`` with
# ``org_id`` as the indexed fk. ``SqliteProvenanceStore`` persists through this.
# Kept OUT of the ``COLLECTIONS`` tuple above on purpose: that tuple is the four
# M1 conversation/report collections (its membership is pinned by
# ``tests/test_ws1.py``); ``pipeline_runs`` is the run-keyed provenance store the
# store looks up directly, not one of that mirrored set.
PIPELINE_RUNS = DocShimCollection("pipeline_runs", id_field="pipeline_run_id", fk="org_id")
