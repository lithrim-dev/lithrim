"""PERSIST-2b: config-object versioning (etlp `_history` shadow) + the `_history` read API.
A1–A5 (driver §5), written RED before the implementation.

A1 (agent/judge shadow + first-write-wins): a 2nd save of the same config id archives the
    prior into `{table}_history` (created_at PRESERVED) and the live row keeps first-write
    created_at; seed (un-audited) writes version too.
A2 (read API): list_versions → [current, …superseded] newest-first; version_at(k)
    reconstructs the object at version k; `current` == the live row.
A3 (ontology via the ledger): ledger_history projects the config_audit after-snapshots into
    the version timeline (the file-backed object has no table to shadow).
A4 (BFF endpoints): GET /v1/{agent,judges,ontology}/…/_history[/{version}] return the
    timelines; 404 on unknown id (debuglithrim + importorskip fastapi).
A5 (frozen / scope): 2a's PIPELINE_RUNS/DocShimCollection versioning + the four config
    collections untouched; the audit ledger change-stream behaviour unchanged; no new dep;
    save_agent without audit_log still works.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from pathlib import Path

import pytest

from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target
from lithrim_bench.harness.config import load_agent, save_agent
from lithrim_bench.harness.judges import JudgeConfig, load_judge, save_judge
from lithrim_bench.harness.versioning import (
    ledger_history,
    list_versions,
    version_at,
)
from tests._house_fixture import house_agent


def _agent(name: str, ref: str):
    """The neutral house agent, renamed + a varied field so v1≠v2 (frozen-dataclass safe —
    house_agent(name=) would hit the model_copy path, so we use dataclasses.replace)."""
    a = house_agent()
    ep = dataclasses.replace(a.eval_profile, ontology_ref=ref)
    return dataclasses.replace(a, name=name, eval_profile=ep)


def _live_created_at(db: Path, table: str, id_col: str, id_val: str):
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            f"SELECT created_at FROM {table} WHERE {id_col} = ?", (id_val,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _history_rows(db: Path, table: str) -> list[dict]:
    """The `{table}_history` archive rows; [] when the shadow does not exist yet (RED state —
    so the assertion fails cleanly, not with an OperationalError)."""
    conn = sqlite3.connect(db)
    try:
        try:
            rows = conn.execute(
                f"SELECT original_id, json, created_at, seq FROM {table}_history ORDER BY seq"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()
    return [{"original_id": r[0], "json": r[1], "created_at": r[2], "seq": r[3]} for r in rows]


# ── A1 (agent/judge shadow + first-write-wins) ────────────────────────────────


def test_config_upsert_versions_into_history(tmp_path):
    db = tmp_path / "config.sqlite"

    # seed/un-audited write (no audit_log) — versions too (storage property)
    save_agent(_agent("agX", "v-one"), db_path=db)
    created_1 = _live_created_at(db, "agents", "name", "agX")
    assert _history_rows(db, "agents") == []  # first write archives nothing

    save_agent(_agent("agX", "v-two"), db_path=db)  # edit → archive the prior
    assert load_agent("agX", db_path=db).eval_profile.ontology_ref == "v-two"  # head = latest
    assert _live_created_at(db, "agents", "name", "agX") == created_1  # first-write-wins

    hist = _history_rows(db, "agents")
    assert len(hist) == 1
    assert json.loads(hist[0]["json"])["eval_profile"]["ontology_ref"] == "v-one"  # the prior
    assert hist[0]["created_at"] == created_1  # PRESERVED, not re-stamped

    # judges version through the same chokepoint
    save_judge(
        JudgeConfig(role="risk_judge", model="azure", assigned_flags=("A",), validator_refs=()),
        db_path=db,
    )
    save_judge(
        JudgeConfig(
            role="risk_judge", model="byo-claude", assigned_flags=("A", "B"), validator_refs=()
        ),
        db_path=db,
    )
    jhist = _history_rows(db, "judges")
    assert len(jhist) == 1
    assert json.loads(jhist[0]["json"])["model"] == "azure"  # the prior version
    assert load_judge("risk_judge", db_path=db).model == "byo-claude"  # the head


# ── A2 (read API / addressability) ────────────────────────────────────────────


def test_list_versions_and_version_at(tmp_path):
    db = tmp_path / "config.sqlite"
    for m, flags in (("m1", ("A",)), ("m2", ("A", "B")), ("m3", ())):
        save_judge(
            JudgeConfig(role="risk_judge", model=m, assigned_flags=flags, validator_refs=()),
            db_path=db,
        )

    versions = list_versions(db, table="judges", id_col="role", id_val="risk_judge")
    assert [v["status"] for v in versions] == ["current", "superseded", "superseded"]
    assert [v["version"] for v in versions] == [3, 2, 1]  # newest-first
    assert [v["object"]["model"] for v in versions] == ["m3", "m2", "m1"]
    assert versions[0]["object"]["model"] == "m3"  # current == the live row

    assert version_at(db, table="judges", id_col="role", id_val="risk_judge", version=1)["model"] == "m1"
    assert version_at(db, table="judges", id_col="role", id_val="risk_judge", version=3)["model"] == "m3"
    assert version_at(db, table="judges", id_col="role", id_val="risk_judge", version=99) is None

    assert list_versions(db, table="judges", id_col="role", id_val="nope") == []


# ── A3 (ontology via the ledger) ──────────────────────────────────────────────


def test_ontology_history_from_the_ledger(tmp_path):
    db = tmp_path / "config.sqlite"
    log = AuditLog(db_path=db)
    log.record(
        AuditRecord(
            actor=Actor(type="user", id="sme"),
            action="edit",
            target=Target(type="ontology", id="agX"),
            before=None,
            after={"ontology_version": "o1"},
        )
    )
    log.record(
        AuditRecord(
            actor=Actor(type="user", id="sme"),
            action="edit",
            target=Target(type="ontology", id="agX"),
            before={"ontology_version": "o1"},
            after={"ontology_version": "o2"},
        )
    )

    hist = ledger_history(db, target_type="ontology", target_id="agX")
    assert [h["object"]["ontology_version"] for h in hist] == ["o2", "o1"]  # newest-first
    assert hist[0]["actor"]["id"] == "sme"
    assert hist[0]["action"] == "edit"
    assert ledger_history(db, target_type="ontology", target_id="nope") == []


# ── A4 (BFF endpoints) ────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    from fastapi.testclient import TestClient

    import apps.bff.app as bff

    db = tmp_path / "bench_config.sqlite"
    # two agent versions + two judge versions + two ontology ledger records
    save_agent(_agent("ws2b_house", "v-one"), db_path=db)
    save_agent(_agent("ws2b_house", "v-two"), db_path=db)
    save_judge(
        JudgeConfig(role="risk_judge", model="m1", assigned_flags=("A",), validator_refs=()),
        db_path=db,
    )
    save_judge(
        JudgeConfig(role="risk_judge", model="m2", assigned_flags=(), validator_refs=()),
        db_path=db,
    )
    log = AuditLog(db_path=db)
    for v in ("o1", "o2"):
        log.record(
            AuditRecord(
                actor=Actor(type="user", id="sme"),
                action="edit",
                target=Target(type="ontology", id="ws2b_house"),
                after={"ontology_version": v},
            )
        )
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_history_endpoints(client):
    ra = client.get("/v1/agent/_history", params={"name": "ws2b_house"})
    assert ra.status_code == 200
    av = ra.json()["versions"]
    assert av[0]["status"] == "current" and av[0]["object"]["eval_profile"]["ontology_ref"] == "v-two"
    assert len(av) == 2

    rj = client.get("/v1/judges/risk_judge/_history")
    assert rj.status_code == 200
    assert rj.json()["versions"][0]["object"]["model"] == "m2"

    ro = client.get("/v1/ontology/_history", params={"agent": "ws2b_house"})
    assert ro.status_code == 200
    assert [v["object"]["ontology_version"] for v in ro.json()["versions"]] == ["o2", "o1"]

    # point-lookup
    assert (
        client.get("/v1/judges/risk_judge/_history/1").json()["object"]["model"] == "m1"
    )
    # unknown id → 404
    assert client.get("/v1/agent/_history", params={"name": "nope"}).status_code == 404


# ── A5 (frozen / scope) ───────────────────────────────────────────────────────


def test_frozen_and_scope(tmp_path):
    # 2a's PIPELINE_RUNS stays versioned; the four config collections stay un-versioned
    from lithrim_bench.harness.collections import COLLECTIONS, PIPELINE_RUNS

    assert PIPELINE_RUNS.versioned is True
    for c in COLLECTIONS:
        assert c.versioned is False

    # save_agent without an audit_log still works (back-compat) and now versions
    db = tmp_path / "config.sqlite"
    save_agent(_agent("agZ", "r1"), db_path=db)
    save_agent(_agent("agZ", "r2"), db_path=db)
    assert load_agent("agZ", db_path=db).eval_profile.ontology_ref == "r2"
    assert len(_history_rows(db, "agents")) == 1

    # the audit ledger change-stream is unchanged (additive): a plain save (no audit_log)
    # writes NO audit record — versioning is independent of attribution
    log = AuditLog(db_path=db)
    assert log.query(target_type="agent", target_id="agZ") == []


def test_consensus_seam_is_zero_delta_vs_acc4973():
    from pathlib import Path as _P

    from tests._seam_freeze import assert_compliance_council_carveouts_only

    assert_compliance_council_carveouts_only(_P(__file__).resolve().parents[1])
