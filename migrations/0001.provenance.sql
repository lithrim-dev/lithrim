-- PERSIST-2c: the managed-tier provenance schema (Postgres).
-- Mirrors PostgresProvenanceStore._SCHEMA — the versioned blob (live + _history) with
-- first-write-wins created_at + a monotonic ins_seq (the SQLite rowid analogue). yoyo
-- applies this for the managed tier; the SQLite core self-provisions inline.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id         TEXT PRIMARY KEY,
    org_id     TEXT,
    agent_id   TEXT,
    case_id    TEXT,
    doc        JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ins_seq    BIGSERIAL
);
CREATE TABLE IF NOT EXISTS pipeline_runs_history (
    hist_id     BIGSERIAL PRIMARY KEY,
    original_id TEXT NOT NULL,
    txnid       TEXT,
    seq         INT,
    doc         JSONB NOT NULL,
    created_at  TIMESTAMPTZ,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_lineage ON pipeline_runs (agent_id, case_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_history_orig ON pipeline_runs_history (original_id);
