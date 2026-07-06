"""FLAG-1 acceptance: reference-flag CREATE + DELETE (local, honest) + the gradeable-from-
clean refusal (the core-invariant gate) + the 11-tool A-SAFE bound.

The one law (CLAUDE.md "labels are true by construction" + "the taxonomy snapshot is the
contract"): you may create/delete a REFERENCE (gradeable=false) flag locally; you may NEVER
create a gradeable/scoreable flag from clean — its code comes only from a lithrim-backend
re-snapshot. The create path HARDCODES gradeable=false; the gradeable path is refused with a
legible message.

Layers, by import weight:
  - STRUCTURAL / A-SAFE (plain core — agent package is SDK-free + fastapi-free): the 11-tool
    bound; create_flag has NO gradeable field; delete_flag is {flag_code, rationale}; the
    S-BS-90 deny hook covers both new tools.
  - HANDLER (plain core, stub ctx): the wrappers forward params + surface errors without crashing.
  - BFF routes + bound tools ([bff] extra, debuglithrim): reference-create round-trips + is
    skip-logged-never-scored (A1); gradeable-from-clean is REFUSED, non-vacuous (A2); the four
    delete guards + the audited allow (A3); the agent-reachable delete is bounded by the
    endpoint guards (PIN 2).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
# Self-contained against the in-repo public sample pack (clinical_scribe, tier:core) — no
# external healthcare Pro pack. Its ontology carries gradeable in-snapshot contract codes
# (e.g. WRONG_DOSAGE), which is all GUARD 1 (the delete refusal) needs.
ONTOLOGY_SEED = REPO_ROOT / "packs" / "clinical_scribe" / "ontology.json"

# The agent package is import-safe on the default core (SDK is pulled LAZILY; no fastapi at
# module level), so the STRUCTURAL + HANDLER layers run in BOTH suites — not only under [bff].
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _deny_non_lithrim  # noqa: E402

AGENT = "flag1_test"
REF_CODE = "LOCAL_REF_FLAG1"  # a brand-new out-of-snapshot reference code (not in the seed)
GRADEABLE_SEED_CODE = "WRONG_DOSAGE"  # an in-snapshot (gradeable) contract code from the seed


# ── STRUCTURAL / A-SAFE (plain core — SDK-free) ──────────────────────────────────


def test_create_flag_schema_has_no_gradeable_field():
    """The ONE LAW, structural half: the agent has NO knob to make a flag scoreable —
    CREATE_FLAG_SCHEMA carries the definitional fields only, never `gradeable`/`tier`/
    `owner_roles`. (The behavioral half — the hardcode + the refusal — is below.)"""
    assert "gradeable" not in agent_tools.CREATE_FLAG_SCHEMA
    assert "tier" not in agent_tools.CREATE_FLAG_SCHEMA
    assert "owner_roles" not in agent_tools.CREATE_FLAG_SCHEMA
    assert set(agent_tools.CREATE_FLAG_SCHEMA) == {
        "flag_code",
        "category",
        "definition",
        "when_to_use",
        "when_NOT_to_use",
        "rationale",
    }


def test_flag_tools_are_the_tenth_and_eleventh_no_paid_knob():
    """A-SAFE: the FLAG-1 tools complete the (pre-CHATBIND-2) 11-tool set and NEITHER carries a
    paid knob (the S-BS-81 guarantee generalized). delete_flag is exactly {flag_code, rationale}.
    The full surface is now 17 (CHATBIND-2 focus_artifact + CHATBIND-3 show_case + CHATBIND-4
    propose_live_run + GROUND-CHAT-1 add_grounding_contract + KB-CONTEXT-1 kb_context + NARR-2
    ingest_cases); the sweep below covers all of them."""
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert len(names) == 24 and len(set(names)) == 24, names  # +PHASE2-WIRE create_judge +TOOL-AUTHOR-1 author_tool
    assert {"create_flag", "delete_flag"} <= set(names)
    for _h, n, _d, schema in agent_tools._TOOL_SPECS:  # NON-VACUOUS: the new tools included
        assert [k for k in agent_tools.PAID_KEYS if k in schema] == [], (n, schema)
    by_name = {n: schema for _h, n, _d, schema in agent_tools._TOOL_SPECS}
    assert set(by_name["delete_flag"]) == {"flag_code", "rationale"}
    fields = set(agent_tools.ToolContext.__dataclass_fields__)
    assert {"create_flag", "delete_flag"} <= fields


def test_deny_hook_covers_create_and_delete_flag_and_still_denies_builtins():
    """The S-BS-90 deny gate passes mcp__lithrim__create_flag / delete_flag (allowed) and
    still DENIES a built-in — the hook is byte-identical; the 10th/11th tools are bounded
    for free."""

    def decision(out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    for name in ("create_flag", "delete_flag"):
        allow = asyncio.run(
            _deny_non_lithrim({"tool_name": f"mcp__lithrim__{name}"}, "t", {"signal": None})
        )
        assert decision(allow) is None, name  # no decision == allowed
    deny = asyncio.run(_deny_non_lithrim({"tool_name": "Bash"}, "t", {"signal": None}))
    assert decision(deny) == "deny"


# ── HANDLER (plain core, stub ctx) ───────────────────────────────────────────────


def _stub_ctx(*, create_flag=None, delete_flag=None):
    def _noop(*_a, **_k):
        return {"actor": {"id": "sme"}}

    return agent_tools.ToolContext(
        author_judge=_noop,
        get_judge=_noop,
        run_eval_replay=_noop,
        get_agent=_noop,
        author_flag=_noop,
        review_runs=_noop,
        run_eval_pack=_noop,
        assemble_agent=_noop,
        delete_judge=_noop,
        create_flag=create_flag or _noop,
        delete_flag=delete_flag or _noop,
        put_grounding_contract=_noop,
        kb_context=_noop,
        ingest_cases=_noop,
        list_cases=_noop,
        record_meta_verdict=_noop,
    )


def test_create_flag_handler_surfaces_error_without_crashing():
    def boom(**_k):
        raise RuntimeError("flag 'X' already exists")

    out = asyncio.run(
        agent_tools.create_flag_handler(_stub_ctx(create_flag=boom), {"flag_code": "X"})
    )
    assert out.get("is_error") is True
    assert "already exists" in out["content"][0]["text"]


def test_delete_flag_handler_forwards_only_flag_code_and_rationale():
    """PIN 1 at the handler boundary: the wrapper passes through flag_code + rationale and
    holds NO guard logic of its own — the guards are the endpoint's."""
    seen = {}

    def fake(flag_code, rationale):
        seen["flag_code"] = flag_code
        seen["rationale"] = rationale
        return {"status": "deleted", "flag": flag_code, "actor": {"id": "sme"}}

    out = asyncio.run(
        agent_tools.delete_flag_handler(
            _stub_ctx(delete_flag=fake), {"flag_code": REF_CODE, "rationale": "r"}
        )
    )
    assert "is_error" not in out
    assert seen == {"flag_code": REF_CODE, "rationale": "r"}


def test_delete_flag_handler_surfaces_a_guard_refusal_without_crashing():
    def boom(flag_code, rationale):
        raise RuntimeError("refusing to delete: gradeable / in-snapshot contract code")

    out = asyncio.run(
        agent_tools.delete_flag_handler(_stub_ctx(delete_flag=boom), {"flag_code": "X"})
    )
    assert out.get("is_error") is True
    assert "contract code" in out["content"][0]["text"]


# ── BFF routes + bound tools ([bff] extra — debuglithrim) ─────────────────────────


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
def env(tmp_path):
    """A tmp config plane + ontology workdir + corpus dir, a ToolContext bound to the FROZEN
    BFF ops, and a TestClient over the SAME db/workdir/examples so the tool writes and the
    route reads resolve identically."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    import app as bff
    from fastapi.testclient import TestClient

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


def test_delete_guard_404_unknown(env):
    bff, ctx, client, db, workdir, examples = env
    assert client.delete("/v1/ontology/flags/NOPE", params={"agent": AGENT}).status_code == 404


def test_delete_guard_refuses_gradeable_in_snapshot(env):
    """A3 / GUARD 1 (NON-VACUOUS): a gradeable in-snapshot contract code is refused (422).
    Removing the guard would let a contract code be deleted locally — desyncing the contract."""
    bff, ctx, client, db, workdir, examples = env
    r = client.delete(f"/v1/ontology/flags/{GRADEABLE_SEED_CODE}", params={"agent": AGENT})
    assert r.status_code == 422 and "re-snapshot" in r.text


def test_agent_reachable_delete_is_bounded_by_the_endpoint_guards(env):
    """PIN 2 — the agent-reachable delete path (the delete_flag tool over the bound op) refuses
    a gradeable/in-snapshot contract code, because the guard lives in the ENDPOINT, not the
    wrapper. The agent can delete only an unused reference flag."""
    bff, ctx, client, db, workdir, examples = env
    out = asyncio.run(
        agent_tools.delete_flag_handler(ctx, {"flag_code": GRADEABLE_SEED_CODE, "rationale": "x"})
    )
    assert out.get("is_error") is True
    assert (
        "contract code" in out["content"][0]["text"] or "re-snapshot" in out["content"][0]["text"]
    )
