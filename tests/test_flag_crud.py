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
import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import grounding
from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent
from lithrim_bench.harness.judges import JudgeConfig, save_judge
from lithrim_bench.harness.ontology import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_SEED = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"

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
    """A-SAFE: the FLAG-1 tools complete the 11-tool set and NEITHER carries a paid knob
    (the S-BS-81 guarantee generalized). delete_flag is exactly {flag_code, rationale}."""
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert len(names) == 11 and len(set(names)) == 11, names
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


def _create_ref(ctx, code=REF_CODE, **over):
    args = {
        "flag_code": code,
        "category": "fidelity",
        "definition": "a locally-authored reference flag",
        "when_to_use": "demo",
        "when_NOT_to_use": "never score it",
        "rationale": "FLAG-1 test",
        **over,
    }
    return asyncio.run(agent_tools.create_flag_handler(ctx, args))


def _seed_body() -> dict:
    return json.loads(ONTOLOGY_SEED.read_text())


def test_reference_create_round_trips_and_is_audited(env):
    """A1 — a brand-new gradeable=false flag is created via the audited path, appears in the
    working copy as a reference flag, and the create is in the §2B audit stream."""
    bff, ctx, client, db, workdir, examples = env
    out = _create_ref(ctx)
    assert not out.get("is_error"), out
    assert any(p["type"] == "tool-flag_editor" for p in ctx.parts)  # existing card, no new type

    ont = client.get("/v1/ontology", params={"agent": AGENT}).json()
    match = next((f for f in ont["flags"] if f["flag"] == REF_CODE), None)
    assert match is not None
    assert match["gradeable"] is False and match["tier"] is None and match["owner_roles"] == []

    loaded = load_ontology(workdir / f"{AGENT}.json")
    assert loaded.is_reference(REF_CODE) is True and loaded.is_gradeable(REF_CODE) is False

    recs = client.get("/v1/audit", params={"target_type": "ontology"}).json()["records"]
    afters = [r for r in recs if (r.get("after") or {})]
    assert any(REF_CODE in [f["flag"] for f in (r["after"].get("flags") or [])] for r in afters)


def test_reference_create_is_skip_logged_never_scored(env):
    """A1 — a HIGH finding coded with the new reference flag is skip-logged and removed from
    the scored set (it would BLOCK if it were gradeable). The non-gradeable guarantee."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    ont = load_ontology(workdir / f"{AGENT}.json")

    result = {"findings": [{"code": REF_CODE, "severity": "HIGH"}], "verdict": "BLOCK"}
    grounded = grounding.ground(result, {"transcript": ""}, ontology=ont)
    assert [f["code"] for f in grounded.skipped_non_gradeable] == [REF_CODE]
    assert grounded.active == []  # never scored
    assert grounded.verdict == "PASS"  # the HIGH would have BLOCKed if scored


def test_create_hardcodes_gradeable_false_nonvacuous(env):
    """A-SAFE (the hardcode, NON-VACUOUS): create persists gradeable=False. This is the
    guard for the _create_flag hardcode — flipping it to True would make the create a
    gradeable-out-of-snapshot flag, which _validate_ontology REFUSES (422), so this very
    'create succeeds + gradeable False' assertion would start FAILING."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    ont = client.get("/v1/ontology", params={"agent": AGENT}).json()
    match = next(f for f in ont["flags"] if f["flag"] == REF_CODE)
    assert match["gradeable"] is False


def test_create_existing_flag_409(env):
    """create != edit: a second create of the same code is a 409 (edit it via author_flag)."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    again = _create_ref(ctx)
    assert again.get("is_error") is True
    assert "already exists" in again["content"][0]["text"]


def test_gradeable_from_clean_is_refused_nonvacuous(env):
    """A2 — THE load-bearing honest gate. Flipping a created reference flag to gradeable=true
    (an out-of-snapshot code) is REFUSED (422) with the re-snapshot message. NON-VACUOUS: an
    in-snapshot gradeable code is accepted (200), so the refusal targets only unblessed codes."""
    bff, ctx, client, db, workdir, examples = env

    # the refusal: a new out-of-snapshot code marked gradeable -> 422 + the cross-repo message
    body = _seed_body()
    body["flags"].append(
        {
            "flag": REF_CODE,
            "category": "fidelity",
            "definition": "x",
            "when_to_use": "x",
            "when_NOT_to_use": "x",
            "owner_roles": [],
            "tier": "TIER_1",
            "gradeable": True,  # gradeable + out-of-snapshot -> must 422
        }
    )
    r = client.put("/v1/ontology", params={"agent": AGENT}, json=body)
    assert r.status_code == 422
    assert "re-snapshot" in r.text and REF_CODE in r.text  # names the path + the offender

    # NON-VACUOUS: the committed seed (its gradeable codes ARE in-snapshot) is accepted
    ok = client.put("/v1/ontology", params={"agent": AGENT}, json=_seed_body())
    assert ok.status_code == 200


def test_author_flag_flip_to_gradeable_is_refused_via_the_tool(env):
    """A2 (via the conversational surface): author_flag flipping the reference code to
    gradeable=true surfaces the snapshot refusal — the agent cannot re-grade from clean."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    out = asyncio.run(
        agent_tools.author_flag_handler(
            ctx, {"flag_code": REF_CODE, "gradeable": True, "rationale": "try to score it"}
        )
    )
    assert out.get("is_error") is True
    assert "re-snapshot" in out["content"][0]["text"]


def test_delete_guard_404_unknown(env):
    bff, ctx, client, db, workdir, examples = env
    assert client.delete("/v1/ontology/flags/NOPE", params={"agent": AGENT}).status_code == 404


def test_delete_guard_refuses_gradeable_in_snapshot(env):
    """A3 / GUARD 1 (NON-VACUOUS): a gradeable in-snapshot contract code is refused (422).
    Removing the guard would let a contract code be deleted locally — desyncing the contract."""
    bff, ctx, client, db, workdir, examples = env
    r = client.delete(f"/v1/ontology/flags/{GRADEABLE_SEED_CODE}", params={"agent": AGENT})
    assert r.status_code == 422 and "re-snapshot" in r.text


def test_delete_guard_refuses_judge_assigned(env):
    """A3 / GUARD 2 (NON-VACUOUS): a reference flag a persisted (global) judge assigns is
    refused (422) — an orphan guard. Removing it would orphan the judge's lens."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    save_judge(JudgeConfig("risk_judge", "", (REF_CODE,), ()), db_path=db)
    r = client.delete(f"/v1/ontology/flags/{REF_CODE}", params={"agent": AGENT})
    assert r.status_code == 422 and "assign it" in r.text and "risk_judge" in r.text


def test_delete_guard_refuses_case_emitted(env):
    """A3 / GUARD 3 (NON-VACUOUS): a reference flag a committed case emits is refused (422) —
    a corpus orphan that would break the golden lint. Removing it would orphan the case."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    (examples / "case.jsonl").write_text(
        json.dumps({"case_id": "CASE_X", "expected_safety_flags": [REF_CODE]}) + "\n"
    )
    r = client.delete(f"/v1/ontology/flags/{REF_CODE}", params={"agent": AGENT})
    assert r.status_code == 422 and "CASE_X" in r.text


def test_delete_allows_unused_reference_and_audits(env):
    """A3 — an UNUSED reference flag deletes (200) with an action=delete / target=flag audit
    record (before=<the flag>, after=None); the flag is gone from the working copy."""
    bff, ctx, client, db, workdir, examples = env
    assert not _create_ref(ctx).get("is_error")
    r = client.delete(
        f"/v1/ontology/flags/{REF_CODE}",
        params={"agent": AGENT, "rationale": "cleanup"},
        headers={"X-Actor": "sme"},
    )
    assert r.status_code == 200 and r.json()["status"] == "deleted"

    ont = client.get("/v1/ontology", params={"agent": AGENT}).json()
    assert REF_CODE not in [f["flag"] for f in ont["flags"]]

    recs = client.get("/v1/audit", params={"target_type": "flag"}).json()["records"]
    dels = [r for r in recs if r["action"] == "delete" and r["target"]["id"] == REF_CODE]
    assert len(dels) == 1
    assert dels[0]["before"] is not None and dels[0]["after"] is None
    assert dels[0]["actor"]["id"] == "sme"


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
