"""EVAL-FLOW A1 acceptance: the grounding-contract WRITE is honest, audited, idempotent
and 404s on an unknown flag.

The rail must tick Ground truth on the SAME store the grade consumes — the ontology's
``verification_contracts`` (CLAUDE.md "labels are true by construction" + the EVAL-FLOW §0
diagnose-before-edit evidence). The conversational write path is ``add_grounding_contract``
(tools.py) → the bound ``ctx.put_grounding_contract`` (the BFF ``_put_grounding_contract``)
→ the FROZEN audited ``put_ontology_endpoint``. This pins:

  A1.1 — a contract for a KNOWN flag lands in the active agent's ontology
         ``verification_contracts`` (the draft the grade reads).
  A1.2 — re-saving by ``flag_code`` is IDEMPOTENT (replace-in-place, never append a dup).
  A1.3 — the write is AUDITED (an action=edit / target=ontology AuditRecord fires).
  A1.4 — an UNKNOWN flag is REFUSED (404), nothing persisted (the structural gate holds).

Mirrors ``tests/test_flag_crud.py``'s ``env`` fixture (the [bff] extra, debuglithrim): a tmp
config plane + ontology workdir, a ToolContext bound to the FROZEN BFF ops, and a TestClient
over the SAME db/workdir so the tool writes and the route reads resolve identically. The
agent-reachable path (the ``add_grounding_contract`` tool over the bound op) is bounded by the
endpoint guards, exactly as FLAG-1's delete path is.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
# The in-repo seed path is the historical (PACK-DIST-1-relocated) anchor; the BFF self-heals it
# to the active pack's ontology (S-BS-128), so the fixture stays byte-identical to FLAG-1's.
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
from agent import tools as agent_tools  # noqa: E402

AGENT = "evalflow_test"
KNOWN_FLAG = "WRONG_DOSAGE"  # an in-ontology flag from the healthcare seed
UNKNOWN_FLAG = "NOPE_NOT_A_FLAG"


def _fixture_agent() -> Agent:
    return Agent(
        name=AGENT,
        eval_profile=EvalProfile(
            judges=("risk_judge",),
            council_config={},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=(),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(case_id="c", source="s", baseline="b"),
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    import app as bff
    from fastapi.testclient import TestClient

    # S-BS-154/FAUTH-2a: the audited PUT's snapshot gate + the contract-type gate resolve the
    # ACTIVE WORKSPACE's pack. The product binds this clinical agent to a workspace pinned to
    # its pack; construct that binding hermetically (the ws5_bff client pattern) — the suite's
    # canonical pack under pack-on runs (these funcs are NEEDS_PACK, skipped bare).
    from lithrim_bench.harness import workspace as _workspace
    from lithrim_bench.harness.pack import active_pack

    monkeypatch.setattr(
        _workspace,
        "get_active_workspace",
        lambda: _workspace.Workspace(name="default", pack=active_pack()),
    )

    db = tmp_path / "bench_config.sqlite"
    workdir = tmp_path / "ont"
    examples = tmp_path / "examples"
    examples.mkdir()
    save_agent(_fixture_agent(), db_path=db)
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=workdir,
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: workdir
    bff.app.dependency_overrides[bff.get_examples_dir] = lambda: examples
    try:
        yield bff, ctx, TestClient(bff.app), db, workdir, examples
    finally:
        bff.app.dependency_overrides.clear()


def _draft_contracts(workdir: Path):
    draft = workdir / f"{AGENT}.json"
    assert draft.exists(), "the audited PUT should have written a working-copy draft"
    return json.loads(draft.read_text()).get("verification_contracts") or []


def test_grounding_contract_persists_audited_and_404s(env):
    """A1: KNOWN-flag contract persists to verification_contracts (A1.1), re-save by
    flag_code is idempotent (A1.2), the write is audited (A1.3), an unknown flag 404s (A1.4)."""
    bff, ctx, client, db, workdir, examples = env

    # A1.1 — a KNOWN-flag contract lands in the agent's ontology verification_contracts.
    # params are the REAL presence_check schema (med_source + dosage_regex) — GRADE-GUARD-1
    # (08fbaeb) dry-constructs the contract at author time and 422s the old inert shape.
    res = ctx.put_grounding_contract(
        flag_code=KNOWN_FLAG,
        contract_type="presence_check",
        params={"med_source": "response.claims", "dosage_regex": r"\b\d+\b"},
        question="Is the flagged dosage actually present?",
        version=f"{KNOWN_FLAG}/v1",
        agent=AGENT,
    )
    assert res.get("replaced") is False  # first write is a new append, not a replace
    contracts = _draft_contracts(workdir)
    mine = [c for c in contracts if c.get("flag_code") == KNOWN_FLAG]
    assert len(mine) == 1, contracts
    assert mine[0]["contract_type"] == "presence_check"
    assert mine[0]["question"] == "Is the flagged dosage actually present?"
    n_after_first = len(contracts)

    # A1.2 — re-saving by the SAME flag_code REPLACES in place (idempotent, never appends a dup).
    # source_grounding: a REGISTERED core type (the FAUTH-2 gate refuses an unregistered one),
    # all params optional — a genuinely different type from A1.1 so the replace is visible.
    res2 = ctx.put_grounding_contract(
        flag_code=KNOWN_FLAG,
        contract_type="source_grounding",
        params={"source_path": "transcript"},
        question="updated question",
        version=f"{KNOWN_FLAG}/v2",
        agent=AGENT,
    )
    assert res2.get("replaced") is True
    contracts2 = _draft_contracts(workdir)
    mine2 = [c for c in contracts2 if c.get("flag_code") == KNOWN_FLAG]
    assert len(mine2) == 1, "re-save by flag_code must replace, not append"
    assert mine2[0]["contract_type"] == "source_grounding"  # the new value won
    assert len(contracts2) == n_after_first  # no growth on a replace

    # A1.3 — the write is AUDITED (an action=edit / target_type=ontology record fires).
    audit = client.get("/v1/audit", params={"target_type": "ontology"})
    assert audit.status_code == 200
    records = audit.json().get("records") or audit.json().get("audit") or []
    assert records, audit.json()
    assert any(
        (r.get("action") in ("edit", "update", "put")) for r in records
    ), [r.get("action") for r in records]

    # A1.4 — an UNKNOWN flag is REFUSED (404), nothing about it persisted.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        ctx.put_grounding_contract(
            flag_code=UNKNOWN_FLAG,
            contract_type="presence_check",
            params={},
            question="q",
            version="x/v1",
            agent=AGENT,
        )
    assert exc.value.status_code == 404
    assert all(
        c.get("flag_code") != UNKNOWN_FLAG for c in _draft_contracts(workdir)
    ), "a refused write must not leave a contract behind"


def test_grounding_contract_route_reuses_the_bound_op(env):
    """A1 / W1b: the ContractBuilder card's route (POST /v1/grounding-contract) lands the
    contract in verification_contracts (the SAME store the rail reads) by REUSING the bound
    op — no new write logic. A known flag persists + is audited; an unknown flag 404s."""
    bff, ctx, client, db, workdir, examples = env

    ok = client.post(
        "/v1/grounding-contract",
        json={
            "flag_code": KNOWN_FLAG,
            "contract_type": "presence_check",
            # the REAL presence_check params schema (GRADE-GUARD-1 422s the old inert shape)
            "params": {"med_source": "response.claims", "dosage_regex": r"\b\d+\b"},
            "question": "present?",
            "version": f"{KNOWN_FLAG}/v1",
            "agent": AGENT,
        },
    )
    assert ok.status_code == 200, ok.text
    assert any(c.get("flag_code") == KNOWN_FLAG for c in _draft_contracts(workdir))

    # an unknown flag 404s through the SAME endpoint guard (NON-VACUOUS).
    bad = client.post(
        "/v1/grounding-contract",
        json={"flag_code": UNKNOWN_FLAG, "contract_type": "presence_check", "agent": AGENT},
    )
    assert bad.status_code == 404
    assert all(c.get("flag_code") != UNKNOWN_FLAG for c in _draft_contracts(workdir))


def test_add_grounding_contract_tool_is_bounded_by_the_endpoint_guards(env):
    """A1 (agent-reachable, NON-VACUOUS): the add_grounding_contract tool over the bound op
    surfaces the 404 for an unknown flag without crashing — the guard lives in the endpoint."""
    bff, ctx, client, db, workdir, examples = env
    out = asyncio.run(
        agent_tools.add_grounding_contract_handler(
            ctx, {"flag_code": UNKNOWN_FLAG, "contract_type": "presence_check"}
        )
    )
    assert out.get("is_error") is True
    assert UNKNOWN_FLAG in out["content"][0]["text"]

    # and the happy path round-trips through the tool, landing the contract (well-formed
    # presence_check params — GRADE-GUARD-1 422s the param-less inert default).
    ok = asyncio.run(
        agent_tools.add_grounding_contract_handler(
            ctx,
            {
                "flag_code": KNOWN_FLAG,
                "contract_type": "presence_check",
                "params": {"med_source": "response.claims", "dosage_regex": r"\b\d+\b"},
            },
        )
    )
    assert "is_error" not in ok
    assert any(c.get("flag_code") == KNOWN_FLAG for c in _draft_contracts(workdir))
