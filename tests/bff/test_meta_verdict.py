"""META-VERDICT-1 acceptance: a physician records an INDEPENDENT clinician verdict +
judge meta-audit (dissent + named fallacy) against a run.

This is Clinical Scribe Review's Layer-3 reason to exist — the surface that was missing (grep
``meta_verdict|human_verdict|agrees_with`` over apps/bff + apps/shell/src was empty). A
clinician can read the council's votes but could not record their own pass/fail, **dissent**
on the record, or name the judge's fallacy. Without it there is no cohort matrix and no
85.7%-blindness stat.

Contract (SPEC_CLINICAL_SCRIBE_SELF_SERVE §4 P0):
  * POST /v1/meta-verdict {run_id, human_verdict, agrees_with_council, judge_fallacy_code?,
    rationale} writes ONE immutable AuditRecord (action=meta_verdict, target=verdict/run_id)
    via the SAME audited-write idiom as PUT /v1/ontology — no harness/engine file touched.
  * GET /v1/audit?target_type=verdict&target_id={run_id} returns it; a 2nd POST APPENDS
    (immutability: history is never rewritten).
  * judge_fallacy_code is a CLOSED enum (nullable); human_verdict is {pass, fail};
    out-of-enum -> 422.
  * the record_meta_verdict SDK-MCP tool is $0 (no PAID_KEY) and routes through the bound
    closure (the conversational path), surfacing a structured error, never a paid run.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ── HTTP endpoint (the canonical write + read) ───────────────────────────────────


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "cfg.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_meta_verdict_writes_audit_and_appends(client):
    run_id = "run-abc"
    r = client.post(
        "/v1/meta-verdict",
        json={
            "run_id": run_id,
            "human_verdict": "fail",
            "agrees_with_council": False,
            "judge_fallacy_code": "Reference Bias",
            "rationale": "the reference note omitted the dissent",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok" and body["run_id"] == run_id
    assert body["human_verdict"] == "fail" and body["agrees_with_council"] is False
    assert body["judge_fallacy_code"] == "Reference Bias"

    recs = client.get(
        "/v1/audit", params={"target_type": "verdict", "target_id": run_id}
    ).json()["records"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["action"] == "meta_verdict"
    assert rec["target"] == {"type": "verdict", "id": run_id}
    assert rec["after"]["human_verdict"] == "fail"
    assert rec["after"]["agrees_with_council"] is False
    assert rec["after"]["judge_fallacy_code"] == "Reference Bias"
    assert rec["why"]["rationale"].startswith("the reference note")
    assert rec["run_id"] == run_id

    # a SECOND submission APPENDS — immutability is enforced by construction
    client.post(
        "/v1/meta-verdict",
        json={
            "run_id": run_id,
            "human_verdict": "fail",
            "agrees_with_council": True,
            "rationale": "second pass after re-reading",
        },
    )
    recs2 = client.get(
        "/v1/audit", params={"target_type": "verdict", "target_id": run_id}
    ).json()["records"]
    assert len(recs2) == 2


def test_meta_verdict_null_fallacy_when_agreeing(client):
    """Agreeing with the council carries NO fallacy — nullable enum, the common path."""
    r = client.post(
        "/v1/meta-verdict",
        json={"run_id": "run-agree", "human_verdict": "pass", "agrees_with_council": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["judge_fallacy_code"] is None


def test_meta_verdict_out_of_enum_422(client):
    bad_fallacy = client.post(
        "/v1/meta-verdict",
        json={
            "run_id": "r",
            "human_verdict": "fail",
            "agrees_with_council": False,
            "judge_fallacy_code": "Vibes",
        },
    )
    assert bad_fallacy.status_code == 422, bad_fallacy.text
    bad_verdict = client.post(
        "/v1/meta-verdict",
        json={"run_id": "r", "human_verdict": "maybe", "agrees_with_council": False},
    )
    assert bad_verdict.status_code == 422, bad_verdict.text


# ── the conversational tool (record_meta_verdict) ────────────────────────────────


def _stub_ctx(record_meta_verdict=None):
    def _noop(*_a, **_k):
        return {"status": "ok", "actor": {"id": "sme"}}

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
        create_flag=_noop,
        delete_flag=_noop,
        put_grounding_contract=_noop,
        kb_context=_noop,
        ingest_cases=_noop,
        list_cases=_noop,
        record_meta_verdict=record_meta_verdict or _noop,
    )


def test_record_meta_verdict_tool_routes_through_closure_and_stays_conversational():
    """A3 / CONV-FIRST (SPEC_CONVERSATIONAL_FIRST §2): the handler calls the bound
    ctx.record_meta_verdict with the normalized args and confirms IN THE CONVERSATION — it must
    NOT open the pane (the reversed anti-pattern). The clinician-verdict form lives inline on the
    verdict card; the human opens the full report only on an explicit drill-down. $0, no paid run."""
    seen: dict = {}

    def fake(run_id, human_verdict, agrees_with_council, judge_fallacy_code, rationale):
        seen.update(
            run_id=run_id,
            human_verdict=human_verdict,
            agrees=agrees_with_council,
            fallacy=judge_fallacy_code,
            rationale=rationale,
        )
        return {"status": "ok"}

    ctx = _stub_ctx(record_meta_verdict=fake)
    out = asyncio.run(
        agent_tools.record_meta_verdict_handler(
            ctx,
            {
                "run_id": "run-xyz",
                "human_verdict": "fail",
                "agrees_with_council": False,
                "judge_fallacy_code": "Reference Bias",
                "rationale": "ref note omitted the dissent",
            },
        )
    )
    assert "is_error" not in out
    assert seen["run_id"] == "run-xyz" and seen["human_verdict"] == "fail"
    assert seen["agrees"] is False and seen["fallacy"] == "Reference Bias"
    # CONV-FIRST: NO pane-focus directive — recording is complete in the conversation.
    assert not [p for p in ctx.parts if p.get("type") == "tool-open_artifact"], ctx.parts


def test_record_meta_verdict_tool_surfaces_error_and_pins_nothing():
    """A3 negative: a closure failure (e.g. a 422) surfaces a STRUCTURED error and emits
    nothing — same surface add_grounding_contract uses; never a crash, never a paid run."""

    def boom(**_k):
        raise RuntimeError("invalid judge_fallacy_code 'Vibes'; nothing recorded")

    ctx = _stub_ctx(record_meta_verdict=boom)
    out = asyncio.run(
        agent_tools.record_meta_verdict_handler(
            ctx, {"run_id": "r", "human_verdict": "fail", "agrees_with_council": False}
        )
    )
    assert out.get("is_error") is True
    assert "nothing recorded" in out["content"][0]["text"].lower()
    assert ctx.parts == []
