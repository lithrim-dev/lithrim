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


def _connect(db_path: str | Path) -> sqlite3.Connection:
    """The one sqlite connect chokepoint. sqlite creates a missing DB *file* but not a
    missing parent *directory* — ``DEFAULT_COLLECTIONS_DB`` lives under the gitignored
    ``out/``, so a fresh clone crashed with ``unable to open database file`` on first use
    (REL-5d, S-REL-23). Ensure the parent exists, then connect."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


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
    # PERSIST-2a: when True, a write that REPLACES an existing row (same id) first archives
    # the prior row into a ``{name}_history`` shadow with its first-write ``created_at``
    # PRESERVED (the S-BS-68 last-write-wins fix), keeping the live row's original
    # ``created_at`` too. Default False → the four M1 config/report collections are
    # byte-identical (their versioning is PERSIST-2b). Only ``PIPELINE_RUNS`` opts in.
    versioned: bool = False

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

    def _history_schema(self) -> str:
        """The append-only ``_history`` shadow for a versioned collection (etlp-mapper's
        ``mappings_history``): every superseded version, version-addressable by
        ``(original_id, seq/txnid)``. PERSIST-2a."""
        return (
            f"CREATE TABLE IF NOT EXISTS {self.name}_history (\n"
            "    hist_id     INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    original_id TEXT NOT NULL,\n"
            "    txnid       TEXT NOT NULL,\n"
            "    seq         INTEGER NOT NULL,\n"
            "    fk          TEXT,\n"
            "    json        TEXT NOT NULL,\n"
            "    created_at  TEXT NOT NULL,\n"
            "    archived_at TEXT NOT NULL\n"
            ");\n"
            f"CREATE INDEX IF NOT EXISTS idx_{self.name}_history_orig "
            f"ON {self.name}_history(original_id)"
        )

    def insert(self, doc: dict[str, Any], *, db_path: str | Path = DEFAULT_COLLECTIONS_DB) -> str:
        """Upsert a document (idempotent on its id_field). Returns the db path.

        On a ``versioned`` collection, a write that REPLACES an existing row first copies
        the prior row into ``{name}_history`` (with its first-write ``created_at`` PRESERVED)
        and keeps the live row's original ``created_at`` — first-write-wins, the S-BS-68 fix
        scoped to this tier. The snapshot-then-write runs in ONE transaction, so it is
        portable (no SQLite trigger) and runs identically on PG later."""
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        doc_id = str(doc[self.id_field])
        fk_val = doc.get(self.fk)
        fk_val = str(fk_val) if fk_val is not None else None
        payload = json.dumps(doc, sort_keys=True)
        created_at = datetime.now(timezone.utc).isoformat()
        conn = _connect(db_path)
        try:
            conn.executescript(self._schema())
            if self.versioned:
                conn.executescript(self._history_schema())
                prior = conn.execute(
                    f"SELECT fk, json, created_at FROM {self.name} WHERE id = ?", (doc_id,)
                ).fetchone()
                if prior is not None:
                    prior_fk, prior_json, prior_created = prior
                    seq = (
                        conn.execute(
                            f"SELECT COUNT(*) FROM {self.name}_history WHERE original_id = ?",
                            (doc_id,),
                        ).fetchone()[0]
                        + 1
                    )
                    conn.execute(
                        f"INSERT INTO {self.name}_history "
                        "(original_id, txnid, seq, fk, json, created_at, archived_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (doc_id, f"{created_at}#{seq}", seq, prior_fk, prior_json,
                         prior_created, created_at),
                    )
                    created_at = prior_created  # first-write-wins on the live row
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

    def find_by_json(
        self,
        fields: dict[str, str],
        *,
        db_path: str | Path = DEFAULT_COLLECTIONS_DB,
        newest_first: bool = True,
    ) -> list[dict]:
        """All docs matching every ``json_extract`` field equality, newest-first by
        insertion order (``rowid``). Backs the versioned read seam (``latest_for`` /
        ``list_versions``) WITHOUT promoting a field to an indexed column — S-BS-4
        doc-shim-minimal. ``fields`` keys are internal (e.g. ``agent_id``/``case_id``),
        never user input."""
        if not fields:
            return []
        order = "DESC" if newest_first else "ASC"
        where = " AND ".join(f"json_extract(json, '$.{k}') = ?" for k in fields)
        conn = _connect(db_path)
        try:
            conn.executescript(self._schema())
            rows = conn.execute(
                f"SELECT json FROM {self.name} WHERE {where} ORDER BY rowid {order}",
                tuple(fields.values()),
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]

    def history(
        self, original_id: str, *, db_path: str | Path = DEFAULT_COLLECTIONS_DB
    ) -> list[dict]:
        """The archived prior versions of ``original_id`` from ``{name}_history``,
        newest-first (the most-recently superseded version first). PERSIST-2a / RUNTRAIL-2:
        the READ-BACK accessor for the versioned-replace archive — archival is UNCHANGED
        (the ``versioned=True`` write path), this only reads what it already wrote. Returns
        ``[]`` on a non-versioned collection or when nothing has been superseded. Decode
        shape mirrors ``find_by_json`` (the stored doc dicts)."""
        if not self.versioned:
            return []
        conn = _connect(db_path)
        try:
            conn.executescript(self._schema())
            conn.executescript(self._history_schema())
            rows = conn.execute(
                f"SELECT json FROM {self.name}_history WHERE original_id = ? "
                "ORDER BY seq DESC",
                (original_id,),
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]

    def get(self, doc_id: str, *, db_path: str | Path = DEFAULT_COLLECTIONS_DB) -> dict | None:
        conn = _connect(db_path)
        try:
            conn.executescript(self._schema())
            row = conn.execute(f"SELECT json FROM {self.name} WHERE id = ?", (doc_id,)).fetchone()
        finally:
            conn.close()
        return json.loads(row[0]) if row else None

    def find_by_fk(
        self, fk_val: str, *, db_path: str | Path = DEFAULT_COLLECTIONS_DB
    ) -> list[dict]:
        conn = _connect(db_path)
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
        conn = _connect(db_path)
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
PIPELINE_RUNS = DocShimCollection(
    "pipeline_runs", id_field="pipeline_run_id", fk="org_id", versioned=True
)
