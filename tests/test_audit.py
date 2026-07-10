"""UAP-1 R0/R3 acceptance — the audit substrate + the draft→grade override.

Hermetic + offline ($0): exercises harness/audit.py (the AuditRecord shape +
the append-only/immutable AuditLog) and scripts/run_eval.run(ontology_path=…)
(the working-copy override + the no-override back-compat). No network, no Azure.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.audit import (
    Actor,
    AuditLog,
    AuditRecord,
    Target,
    make_actor,
    now_iso,
)
from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent
from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# scripts/ on path so run_eval imports the same way the BFF does.
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import run_eval  # noqa: E402

# ── AuditRecord shape (§2B) ───────────────────────────────────────────────────


def test_audit_record_carries_the_2b_shape():
    rec = AuditRecord(
        actor=Actor(type="user", id="sme@acme"),
        action="edit",
        target=Target(type="agent", id="ws0_default"),
        why={"rationale": "tighten the floor"},
        before={"x": 1},
        after={"x": 2},
    )
    d = rec.model_dump()
    assert d["actor"] == {"type": "user", "id": "sme@acme"}
    assert d["target"] == {"type": "agent", "id": "ws0_default"}
    assert d["action"] == "edit"
    # N2: before/after are the canonical diff; why is NOT a duplicate of it.
    assert d["before"] == {"x": 1} and d["after"] == {"x": 2}
    assert d["why"] == {"rationale": "tighten the floor"}
    assert "before" not in d["why"] and "after" not in d["why"]
    assert d["ts"] and d["run_id"] is None and d["case_id"] is None


def test_make_actor_defaults_to_system_seed_not_a_fake_sme():
    assert make_actor(None).model_dump() == {"type": "system", "id": "seed"}
    assert make_actor("sme@x").model_dump() == {"type": "user", "id": "sme@x"}


def test_now_iso_is_utc():
    assert now_iso().endswith("+00:00")


# ── AuditLog: append-only + immutable + deterministic ─────────────────────────


def _rec(action="edit", target_id="a1", actor="sme@acme", rationale="r"):
    return AuditRecord(
        actor=make_actor(actor),
        action=action,
        target=Target(type="agent", id=target_id),
        why={"rationale": rationale},
        before=None,
        after={"v": 1},
    )


def test_audit_log_appends_never_overwrites(tmp_path):
    log = AuditLog(db_path=tmp_path / "cfg.sqlite")
    log.record(_rec(action="author", rationale="first"))
    log.record(_rec(action="edit", rationale="second"))
    rows = log.query(target_id="a1")
    # a second write to the same target APPENDS (2 rows), oldest-first.
    assert [r["action"] for r in rows] == ["author", "edit"]
    assert [r["why"]["rationale"] for r in rows] == ["first", "second"]


def test_audit_log_has_no_update_or_delete_path():
    # Immutability is enforced by absence — the table is INSERT-only.
    assert not hasattr(AuditLog, "update")
    assert not hasattr(AuditLog, "delete")
    assert not hasattr(AuditLog, "remove")


def test_audit_log_query_filters_are_anded(tmp_path):
    log = AuditLog(db_path=tmp_path / "cfg.sqlite")
    log.record(_rec(target_id="a1", actor="sme@one"))
    log.record(_rec(target_id="a2", actor="sme@two"))
    log.record(
        AuditRecord(
            actor=make_actor("sme@one"),
            action="edit",
            target=Target(type="ontology", id="a1"),
            why={},
        )
    )
    assert len(log.query(actor="sme@one")) == 2
    assert len(log.query(target_type="agent")) == 2
    assert len(log.query(target_type="agent", target_id="a1")) == 1
    assert len(log.query(target_type="ontology")) == 1


def test_audit_log_table_is_insert_only_by_schema(tmp_path):
    # The raw SQL surface carries no UPDATE/DELETE — only the INSERT in record().
    db = tmp_path / "cfg.sqlite"
    AuditLog(db_path=db).record(_rec())
    conn = sqlite3.connect(db)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(config_audit)").fetchall()]
    finally:
        conn.close()
    assert {
        "seq",
        "ts",
        "actor_type",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "json",
    } <= set(cols)


def test_save_agent_emits_audit_in_one_transaction(tmp_path):
    db = tmp_path / "cfg.sqlite"
    log = AuditLog(db_path=db)

    def agent(ont="packs/healthcare/ontology.json"):
        return Agent(
            name="a1",
            eval_profile=EvalProfile(
                judges=("risk_judge",),
                council_config={},
                ontology_ref="clinical_v1",
                ontology_path=ont,
                tools=(),
                kb_bindings={},
                severity_map_ref="clinical_v1",
            ),
            dataset=Dataset(case_id="c1", source="s", baseline="b"),
        )

    save_agent(agent(), db_path=db, actor="sme@acme", audit_log=log, rationale="first")
    save_agent(
        agent(ont="data/ontology/other.json"),
        db_path=db,
        actor=make_actor("sme@acme"),
        audit_log=log,
        rationale="repoint",
    )
    rows = log.query(target_id="a1")
    assert [r["action"] for r in rows] == ["author", "edit"]
    # the edit carries the canonical before→after diff.
    assert rows[1]["before"]["eval_profile"]["ontology_path"] == "packs/healthcare/ontology.json"
    assert rows[1]["after"]["eval_profile"]["ontology_path"] == "data/ontology/other.json"


def test_save_agent_without_audit_log_records_nothing(tmp_path):
    # A5 back-compat: the low-level seed path (no audit_log) writes no audit row.
    db = tmp_path / "cfg.sqlite"
    save_agent(
        Agent(
            name="seed1",
            eval_profile=EvalProfile(
                judges=(),
                council_config={},
                ontology_ref="r",
                ontology_path="p",
                tools=(),
                kb_bindings={},
                severity_map_ref="s",
            ),
            dataset=Dataset(case_id="c", source="s", baseline="b"),
        ),
        db_path=db,
    )
    # No config_audit table writes happened (the table may not even exist).
    conn = sqlite3.connect(db)
    try:
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config_audit'"
        ).fetchone()
        n = conn.execute("SELECT count(*) FROM config_audit").fetchone()[0] if existing else 0
    finally:
        conn.close()
    assert n == 0


# ── R3: run_eval.run(ontology_path=…) — the draft override ─────────────────────


def _agent(name="t") -> Agent:
    # The neutral _core house fixture (S-BS-137): test_run_no_override grades it on _core in a
    # bare CE checkout. The draft-override funcs below (RELOCATED) read the clinical seed bytes
    # directly and skip when the clinical content is absent — the house agent does not affect them.
    return house_agent(name=name)


def test_run_no_override_grades_the_committed_seed(tmp_path):
    rec = run_eval.run(_agent(), out_dir=tmp_path / "a")
    assert rec["composite"]["verdict"] == "reject"
    assert rec["composite"]["stage_verdict"] == "BLOCK"


# PACK-DIST-2 D5: the draft-override funcs that read the committed clinical ontology seed bytes
# directly (test_run_ontology_path_override_grades_the_draft +
# test_run_override_and_no_override_diverge_only_by_the_draft) relocated to the pack repo
# (tests/test_audit_relocated.py); the generic AuditRecord/AuditLog funcs + the neutral _core
# house-agent run func stay here.


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
