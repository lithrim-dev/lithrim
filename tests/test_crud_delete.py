"""CRUD-1 acceptance: judge + agent DELETE (guarded, audited) + the 9-tool A-SAFE bound.

Three layers, by import weight:
  - HARNESS (plain core — runs under plain python3 AND debuglithrim): delete_judge REVERTS
    to default + writes an action="delete" audit row; the no-op writes NO row (the §2B
    trail is change-only); delete_agent audited; list_agents sorted.
  - A-SAFE (plain core — the agent package is SDK-free + fastapi-free): the tool set is 9,
    all no-paid-knob, delete_judge present (revert-only); NON-VACUOUS — the agent-reachable
    surface has NO agent-delete; the S-BS-90 deny hook covers the 9th tool for free.
  - BFF routes (the [bff] extra, debuglithrim): DELETE /v1/judges/{role} + DELETE /v1/agent
    + GET /v1/agents — the guards (422), the 404s, the idempotent revert, the audit trail.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.audit import AuditLog
from lithrim_bench.harness.config import (
    Agent,
    Dataset,
    EvalProfile,
    delete_agent,
    list_agents,
    save_agent,
)
from lithrim_bench.harness.judges import (
    JudgeConfig,
    delete_judge,
    load_judge,
    save_judge,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"

# The agent package is import-safe on the default core (it pulls claude_agent_sdk LAZILY
# and imports no fastapi at module level), so the A-SAFE structural bound runs in BOTH
# suites — not only under the [bff] extra.
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _deny_non_lithrim  # noqa: E402


def _agent(name: str, judges: tuple[str, ...] = ()) -> Agent:
    return Agent(
        name=name,
        eval_profile=EvalProfile(
            judges=judges,
            council_config={},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=(),
            kb_bindings={},
            severity_map_ref="",
        ),
        dataset=Dataset(case_id="c", source="s", baseline="b"),
    )


def _deletes(log: AuditLog) -> list[dict]:
    return [r for r in log.query() if r["action"] == "delete"]


# ── HARNESS (plain core — both envs) ─────────────────────────────────────────────


def test_delete_judge_reverts_to_default_and_audits(tmp_path):
    db = tmp_path / "c.sqlite"
    log = AuditLog(db_path=db)
    save_judge(
        JudgeConfig("risk_judge", "", ("FABRICATED_ALLERGY",), ()),
        db_path=db,
        audit_log=log,
        actor="sme",
    )
    assert load_judge("risk_judge", db_path=db) is not None
    assert (
        delete_judge("risk_judge", db_path=db, audit_log=log, actor="sme", rationale="revert")
        is True
    )
    assert load_judge("risk_judge", db_path=db) is None  # reverted to default (row gone)
    deletes = _deletes(log)
    assert len(deletes) == 1
    rec = deletes[0]
    assert rec["target"] == {"type": "judge", "id": "risk_judge"}
    assert rec["before"] is not None and rec["after"] is None  # the §2B before→after diff
    assert rec["why"] == {"rationale": "revert"} and rec["actor"]["id"] == "sme"


def test_delete_judge_noop_on_unauthored_role_writes_no_audit(tmp_path):
    db = tmp_path / "c.sqlite"
    log = AuditLog(db_path=db)
    assert delete_judge("policy_judge", db_path=db, audit_log=log, actor="sme") is False
    assert _deletes(log) == []  # the trail is change-only — no record for a non-event


def test_delete_agent_audited_and_list_agents_sorted(tmp_path):
    db = tmp_path / "c.sqlite"
    log = AuditLog(db_path=db)
    for name in ("a2", "a1"):
        save_agent(_agent(name), db_path=db)
    assert list_agents(db_path=db) == ["a1", "a2"]  # sorted
    assert delete_agent("a1", db_path=db, audit_log=log, actor="sme", rationale="rm") is True
    assert list_agents(db_path=db) == ["a2"]
    assert delete_agent("ghost", db_path=db, audit_log=log) is False  # absent -> no-op
    deletes = _deletes(log)
    assert len(deletes) == 1  # only the real removal is audited
    assert deletes[0]["target"] == {"type": "agent", "id": "a1"}
    assert deletes[0]["before"] is not None and deletes[0]["after"] is None


# ── A-SAFE: the 9-tool bound incl. delete_judge (plain core — SDK-free) ───────────


def test_asafe_delete_judge_is_the_ninth_tool_no_paid_knob():
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    # CRUD-1 added delete_judge (9th); FLAG-1 added create_flag (10th) + delete_flag (11th);
    # CHATBIND-2 added focus_artifact (12th); CHATBIND-3 show_case (13th); CHATBIND-4 propose_live_run (14th);
    # GROUND-CHAT-1 added add_grounding_contract (15th); KB-CONTEXT-1 added kb_context (16th);
    # NARR-2 added ingest_cases (17th); NARR-CHAT-LOOP added list_cases (18th);
    # then META-VERDICT-1 record_meta_verdict, FAUTH-1 author_contract, TOOL-AUTHOR-1 author_tool,
    # NARR-5-CRIT-b author_criterion, PHASE2-WIRE create_judge — 24 total (delete_judge stays 9th;
    # every later addition sits after it, so the ninth-tool position is unchanged).
    assert len(names) == 24 and len(set(names)) == 24, names
    assert {"delete_judge", "create_flag", "delete_flag"} <= set(names)
    # NON-VACUOUS: every one of the 17 schemas is no-paid-knob, the new tools included.
    for _h, n, _d, schema in agent_tools._TOOL_SPECS:
        assert [k for k in agent_tools.PAID_KEYS if k in schema] == [], (n, schema)
    # delete_judge's schema is exactly {role, rationale} — no agent target, no paid field.
    by_name = {n: schema for _h, n, _d, schema in agent_tools._TOOL_SPECS}
    assert set(by_name["delete_judge"]) == {"role", "rationale"}


def test_asafe_agent_delete_is_not_agent_reachable():
    """Non-vacuity (D-B): the ToolContext exposes delete_judge (revert, reversible) but NO
    delete_agent — removing a whole eval profile is HUMAN-ONLY (mirrors flag-create)."""
    fields = set(agent_tools.ToolContext.__dataclass_fields__)
    assert "delete_judge" in fields
    assert "delete_agent" not in fields


def test_asafe_deny_hook_covers_delete_judge_and_still_denies_builtins():
    """The S-BS-90 deny gate passes mcp__lithrim__delete_judge (allowed) and still DENIES a
    built-in — the hook is byte-identical; the 9th tool is bounded for free."""

    def decision(out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    allow = asyncio.run(
        _deny_non_lithrim({"tool_name": "mcp__lithrim__delete_judge"}, "t", {"signal": None})
    )
    deny = asyncio.run(_deny_non_lithrim({"tool_name": "Bash"}, "t", {"signal": None}))
    assert decision(allow) is None  # no decision == allowed under the existing allowlist
    assert decision(deny) == "deny"


def _stub_ctx(delete_judge_fn):
    def _noop(*_a, **_k):
        return {}

    return agent_tools.ToolContext(
        author_judge=_noop,
        get_judge=_noop,
        run_eval_replay=_noop,
        get_agent=_noop,
        author_flag=_noop,
        review_runs=_noop,
        run_eval_pack=_noop,
        assemble_agent=_noop,
        delete_judge=delete_judge_fn,
        create_flag=_noop,
        delete_flag=_noop,
        put_grounding_contract=_noop,
        kb_context=_noop,
        ingest_cases=_noop,
        list_cases=_noop,
        record_meta_verdict=_noop,
    )


def test_delete_judge_handler_reverts_and_emits_the_judge_card():
    seen = {}

    def fake(role, rationale):
        seen["role"] = role
        seen["rationale"] = rationale
        return {"status": "reverted", "role": role, "removed": True, "actor": {"id": "sme"}}

    ctx = _stub_ctx(fake)
    out = asyncio.run(
        agent_tools.delete_judge_handler(ctx, {"role": "risk_judge", "rationale": "r"})
    )
    assert "is_error" not in out
    assert seen == {"role": "risk_judge", "rationale": "r"}
    assert any(
        p.get("type") == "tool-judge_editor" for p in ctx.parts
    )  # existing card, no new type


def test_delete_judge_handler_surfaces_an_error_without_crashing():
    def boom(role, rationale):
        raise RuntimeError("unknown judge role 'x'")

    ctx = _stub_ctx(boom)
    out = asyncio.run(agent_tools.delete_judge_handler(ctx, {"role": "x"}))
    assert out.get("is_error") is True
    assert "unknown judge role" in out["content"][0]["text"]


# ── BFF routes (the [bff] extra — debuglithrim) ──────────────────────────────────


def _client_for(db: Path):
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    import app as bff
    from fastapi.testclient import TestClient

    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    return bff, TestClient(bff.app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    bff, c = _client_for(tmp_path / "bench_config.sqlite")
    # Self-contained against the in-repo _core fixture pack: pin the active workspace to the
    # neutral _core pack so the judge-lens offer/gate (_active_lens_by_role) resolves against
    # packs/_core/ instead of whatever workspace happens to be active on the machine (which may
    # be a healthcare/clinical workspace on disk). risk_judge is a _core production-judge role,
    # so the DELETE/PUT mechanism is unchanged. Mirrors tests/test_bff_units.py::client.
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    yield c
    bff.app.dependency_overrides.clear()


def _route_deletes(client):
    recs = client.get("/v1/audit").json()["records"]
    return [(r["target"]["type"], r["target"]["id"]) for r in recs if r["action"] == "delete"]


def test_delete_agent_refuses_the_last_agent_in_isolation(tmp_path):
    """The last-agent guard, exercised independently of the ws0_default seed-default guard:
    a config DB with a SINGLE non-default agent still refuses (422 'last remaining')."""
    db = tmp_path / "solo.sqlite"
    save_agent(_agent("solo"), db_path=db)  # one NON-default agent, no seed -> no re-seed
    bff, c = _client_for(db)
    try:
        r = c.delete("/v1/agent", params={"name": "solo"})
        assert r.status_code == 422 and "last remaining" in r.json()["detail"]
    finally:
        bff.app.dependency_overrides.clear()


def test_delete_judge_route_reverts_idempotent_and_404(client):
    client.put(
        "/v1/judges/risk_judge", json={"assigned_flags": [], "validator_refs": [], "model": ""}
    )
    r = client.delete(
        "/v1/judges/risk_judge", params={"rationale": "revert"}, headers={"X-Actor": "sme"}
    )
    assert r.status_code == 200 and r.json()["removed"] is True
    # idempotent: already default -> still 200, removed=false (no second audit row)
    r = client.delete("/v1/judges/risk_judge")
    assert r.status_code == 200 and r.json()["removed"] is False
    # unknown role -> 404
    assert client.delete("/v1/judges/nope_judge").status_code == 404
    deletes = _route_deletes(client)
    assert deletes.count(("judge", "risk_judge")) == 1  # only the real revert is audited
