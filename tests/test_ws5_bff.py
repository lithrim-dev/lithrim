"""WS-5-BFF acceptance: the shell BFF round-trip smoke (the shell's first test).

Hermetic + replay-only: no network, no live :8002. Drives the FastAPI BFF over the
vendored WS-0 fixtures (the tests/test_ws4a.py pattern) via a tmp config DB +
FastAPI dependency overrides, and asserts the response carries a well-formed
``composite`` + folded ``calibration_check`` (driver §5 A4). Requires the `[bff]`
extra (fastapi/httpx); skipped cleanly if absent so the default suite stays green.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"

# apps/bff on path so the test imports the BFF app the same way run_eval is imported.
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _fixture_agent(name: str = "ws5_bff_test") -> Agent:
    """A fixture-pointing agent (absolute paths → hermetic; the test_ws4a shape)."""
    return Agent(
        name=name,
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(
            case_id=CASE_ID,
            source=str(FIXTURES / f"case.{CASE_ID}.jsonl"),
            baseline=str(FIXTURES / f"baseline.{CASE_ID}.json"),
        ),
    )


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db_path)
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    # PUT writes go to a tmp working dir, never the committed seed (clobber-safety).
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    # UAP-1: the run-provenance read resolves against a tmp doc-shim DB (hermetic).
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_run_eval_replay_returns_composite_and_calibration_check(client):
    """A4 — the round trip: POST /v1/run-eval (replay) → well-formed composite + calibration_check."""
    res = client.post("/v1/run-eval", json={"agent": "ws5_bff_test", "live": False})
    assert res.status_code == 200
    body = res.json()

    assert body["grade_path"] == "replay"
    assert body["case_id"] == CASE_ID

    comp = body["composite"]
    # the real grounded outcome of the WS-0 baseline (not mock data.jsx TILES)
    assert comp["verdict"] == "reject"
    assert comp["stage_verdict"] == "BLOCK"
    assert comp["score"] == 1.0
    assert "FABRICATED_HISTORY" in comp["active_findings"]
    # the S-BS-7 exhibit: the confident MED FP is contract-suppressed
    assert any(a["flag"] == "MEDICATION_NOT_IN_TRANSCRIPT" for a in comp["grounded_adjustments"])

    cal = body["calibration_check"]
    assert cal["verdict_match_rate"] == 1.0
    assert cal["status"] == "PASS"
    assert cal["n_cases"] == 1
    assert cal["ece"] == 0.5  # degenerate N=1 diagnostic, NOT the WS-4b gate
    assert cal["caveat"] is not None and "small N" in cal["caveat"]


def test_corpus_is_listable(client):
    body = client.get("/v1/corpus").json()
    assert isinstance(body["rows"], list)  # graceful empty until a correction is written


def test_ontology_read(client):
    body = client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()
    assert body["domain"] == "clinical"
    assert len(body["flags"]) == 23
    assert "severity_map" in body


def test_unknown_agent_is_404(client):
    assert client.post("/v1/run-eval", json={"agent": "nope"}).status_code == 404


# ── D0: the judge-council view folded into /v1/run-eval ──────────────────────


def test_run_eval_carries_realized_council_votes(client):
    """D0 — the run response surfaces the REALIZED per-judge votes for the JudgeTab."""
    body = client.post("/v1/run-eval", json={"agent": "ws5_bff_test", "live": False}).json()
    council = body["council"]
    votes = council["votes"]
    # the WS-0 baseline cast 3 real votes (risk / policy / faithfulness)
    assert {v["judge_role"] for v in votes} == {"risk_judge", "policy_judge", "faithfulness_judge"}
    for v in votes:
        assert v["vote"] in {"PASS", "WARN", "FAIL", "BLOCK"}
        # confidence is float | null (WS-6a D-E) — the reader must tolerate either
        assert v["confidence"] is None or isinstance(v["confidence"], (int, float))
        assert "model" in v
    assert isinstance(council["configured"], list)


# ── D1: PUT /v1/ontology — clobber-safe + validated ──────────────────────────


def _seed_body() -> dict:
    import json

    return json.loads(ONTOLOGY_SEED.read_text())


def test_put_ontology_accepts_and_round_trips(client):
    """A3 — a valid PUT lands on the working copy; a subsequent GET reflects the edit."""
    ont = _seed_body()
    ont["severity_map"]["block_at_or_above"] = 0.75  # a benign, valid edit
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont)
    assert res.status_code == 200
    assert "working_copy" in res.json()

    got = client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()
    assert got["severity_map"]["block_at_or_above"] == 0.75  # the working copy is served


def test_put_ontology_rejects_malformed(client):
    """A3 — a structurally malformed ontology is rejected (422), nothing persists."""
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json={"not": "an ontology"})
    assert res.status_code == 422
    # GET still serves the committed seed (no working copy was written)
    assert (
        client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()["domain"] == "clinical"
    )


def test_put_ontology_rejects_snapshot_violation(client):
    """A3 — a gradeable flag outside the taxonomy snapshot is rejected loudly (S-BS-10/12)."""
    ont = _seed_body()
    ont["flags"].append(
        {
            "flag": "NOT_IN_SNAPSHOT_CODE",
            "category": "fidelity",
            "definition": "x",
            "when_to_use": "x",
            "when_NOT_to_use": "x",
            "owner_roles": [],
            "tier": "TIER_1",
            "gradeable": True,  # gradeable + not in the snapshot → must 422
        }
    )
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont)
    assert res.status_code == 422
    assert "NOT_IN_SNAPSHOT_CODE" in res.text


def test_put_ontology_never_clobbers_the_committed_seed(client):
    """A3 — the committed clinical_v1.json is byte-unchanged after a PUT (clobber-safety)."""
    before = ONTOLOGY_SEED.read_bytes()
    ont = _seed_body()
    ont["severity_map"]["warn_above"] = 0.123
    assert client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont).status_code == 200
    assert ONTOLOGY_SEED.read_bytes() == before  # the seed on disk did not move


# ── WS-7b: GET /v1/kb/{namespace}/search — additive KB-grounding proxy ────────


class _KbResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        return None


class _FakeKbHttp:
    """Fake :8002 KB client injected into the BFF so the endpoint test is hermetic
    (no live :8002). Records calls; returns a chosen results list for any KB GET."""

    def __init__(self, results):
        self._results = results
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params})
        return _KbResp(
            {
                "namespace": url.rstrip("/").split("/")[-2],
                "query": (params or {}).get("q"),
                "top_k": (params or {}).get("top_k"),
                "total_hits": len(self._results),
                "results": self._results,
                "duration_ms": 1,
            }
        )

    def close(self):
        pass


_TPO_CHUNK = (
    "Uses and disclosures to carry out treatment, payment, and health care "
    "operations; consent for such disclosures is not required."
)


@pytest.fixture
def kb_client(client):
    """The BFF client with the KB http_client overridden to a fake (no live :8002)."""
    fake = _FakeKbHttp([{"id": "hipaa:164-506", "score": 0.92, "text": _TPO_CHUNK, "metadata": {}}])
    bff.app.dependency_overrides[bff.get_kb_http_client] = lambda: fake
    client._fake_kb = fake  # expose for assertions
    yield client


def test_kb_search_endpoint_grounds_claim(kb_client):
    """A4 — the additive KB endpoint composes over KbRagTool and returns the grounding
    verdict + the determinism manifest, mocking :8002 (no live call)."""
    res = kb_client.get(
        "/v1/kb/hipaa/search",
        params={
            "q": "treatment payment operations consent not required",
            "match": "claim_in_chunk",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["namespace"] == "hipaa"
    assert body["conforms"] is True  # KB grounds the claim
    assert body["disposition"] == "CONFORMS"
    assert body["evidence"]["corroborated_ids"] == ["hipaa:164-506"]
    assert body["manifest"]["tool"] == "kb_rag"
    # composed over the confirmed :8002 wire, exactly once
    assert kb_client._fake_kb.calls[0]["url"] == "http://localhost:8002/v1/kb/hipaa/search"


def test_kb_search_endpoint_inconclusive_when_no_match():
    """A4 — KB silence -> conforms null (never a fabricated hit). Separate fake (empty)."""
    fake = _FakeKbHttp([])
    bff.app.dependency_overrides[bff.get_kb_http_client] = lambda: fake
    try:
        body = (
            TestClient(bff.app)
            .get("/v1/kb/hipaa/search", params={"q": "anything", "match": "claim_in_chunk"})
            .json()
        )
        assert body["conforms"] is None
        assert body["disposition"] == "INCONCLUSIVE"
    finally:
        bff.app.dependency_overrides.pop(bff.get_kb_http_client, None)


def test_kb_search_requires_query(kb_client):
    """A4 — q is required (422), matching the backend KB contract."""
    assert kb_client.get("/v1/kb/hipaa/search").status_code == 422


# ── UAP-1 R1: GET/PUT /v1/agent — assemble + persist to the config plane ──────


def test_agent_get_put_round_trips(client):
    """A1 — PUT then GET round-trips an assembled Agent through the config DB."""
    got = client.get("/v1/agent", params={"name": "ws5_bff_test"}).json()
    assert got["name"] == "ws5_bff_test"
    got["eval_profile"]["tools"] = ["presence_check", "kb_grounding"]
    res = client.put(
        "/v1/agent", params={"rationale": "add kb tool"}, headers={"X-Actor": "sme@acme"}, json=got
    )
    assert res.status_code == 200
    assert res.json()["actor"] == {"type": "user", "id": "sme@acme"}
    after = client.get("/v1/agent", params={"name": "ws5_bff_test"}).json()
    assert after["eval_profile"]["tools"] == ["presence_check", "kb_grounding"]


def test_agent_put_rejects_malformed(client):
    """A1 — a malformed agent body is rejected (422)."""
    assert client.put("/v1/agent", json={"name": "x"}).status_code == 422


def test_unknown_agent_get_is_404(client):
    assert client.get("/v1/agent", params={"name": "nope"}).status_code == 404


# ── UAP-1 R3: the draft→grade loop (the A2 headline) ─────────────────────────


def test_draft_ontology_grades_not_the_committed_seed(client):
    """A2 — a verdict-relevant PUT /v1/ontology draft, then POST /v1/run-eval, grades
    against the DRAFT (working copy), not the committed seed; clinical_v1.json is
    byte-unchanged. 'Edit the flag → see it grade.'"""
    seed_before = ONTOLOGY_SEED.read_bytes()
    # baseline: the committed seed blocks (reject)
    base = client.post("/v1/run-eval", json={"agent": "ws5_bff_test"}).json()
    assert base["composite"]["verdict"] == "reject"
    assert base["ontology_source"] == "committed"

    # draft: raise the block threshold above the active weight → BLOCK no longer fires
    draft = _seed_body()
    draft["severity_map"]["block_at_or_above"] = 99.0
    assert (
        client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=draft).status_code == 200
    )

    drafted = client.post("/v1/run-eval", json={"agent": "ws5_bff_test"}).json()
    assert drafted["ontology_source"] == "draft"
    assert drafted["composite"]["stage_verdict"] != "BLOCK"  # the draft graded
    assert drafted["composite"]["verdict"] != "reject"
    assert ONTOLOGY_SEED.read_bytes() == seed_before  # the committed seed never moved


def test_draft_re_edit_regrades_not_the_stale_cache(client, tmp_path):
    """S-BS-58 — editing the SAME draft and re-running reflects the new edit, not a
    cached stale ontology. The @lru_cache(path) bug made a long-running BFF reuse the
    first-loaded ontology on the 2nd+ edit of a draft (path unchanged), so iterative
    'edit → see it grade' silently no-op'd. A2 covered committed→draft; this covers
    draft→edit-same-draft (one path)."""
    import os

    # first draft: raise the threshold above the active weight → the case no longer blocks
    d1 = _seed_body()
    d1["severity_map"]["block_at_or_above"] = 99.0
    assert client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=d1).status_code == 200
    r1 = client.post("/v1/run-eval", json={"agent": "ws5_bff_test"}).json()
    assert r1["ontology_source"] == "draft"
    assert r1["composite"]["verdict"] != "reject"  # the high-threshold draft graded

    # re-edit the SAME draft back down so it blocks again; force a later mtime so the
    # cache bust is deterministic regardless of filesystem mtime resolution
    d2 = _seed_body()
    d2["severity_map"]["block_at_or_above"] = 0.5
    assert client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=d2).status_code == 200
    wc = tmp_path / "ont" / "ws5_bff_test.json"
    st = wc.stat()
    os.utime(wc, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    r2 = client.post("/v1/run-eval", json={"agent": "ws5_bff_test"}).json()
    assert r2["composite"]["verdict"] == "reject"  # the re-edit took effect, not stale-cached


# ── UAP-1 R0: the audit streams ──────────────────────────────────────────────


def test_config_writes_emit_appended_audit_records(client):
    """A3 — every config write emits an immutable, actor-attributed record; a second
    write APPENDS (no overwrite); GET /v1/audit lists them."""
    assert client.get("/v1/audit").json()["records"] == []

    ag = client.get("/v1/agent", params={"name": "ws5_bff_test"}).json()
    client.put(
        "/v1/agent", params={"rationale": "first edit"}, headers={"X-Actor": "sme@one"}, json=ag
    )
    ont = _seed_body()
    ont["severity_map"]["warn_above"] = 0.111
    client.put(
        "/v1/ontology",
        params={"agent": "ws5_bff_test", "rationale": "tweak"},
        headers={"X-Actor": "sme@two"},
        json=ont,
    )

    records = client.get("/v1/audit").json()["records"]
    assert len(records) == 2  # both writes recorded
    assert {r["target"]["type"] for r in records} == {"agent", "ontology"}
    assert records[0]["actor"] == {"type": "user", "id": "sme@one"}
    assert records[0]["why"]["rationale"] == "first edit"

    # a SECOND agent write appends a third row (append-only, never overwrite)
    client.put(
        "/v1/agent", params={"rationale": "second edit"}, headers={"X-Actor": "sme@one"}, json=ag
    )
    assert len(client.get("/v1/audit").json()["records"]) == 3
    assert len(client.get("/v1/audit", params={"target_type": "agent"}).json()["records"]) == 2


def test_product_write_with_no_actor_is_attributed_not_silent(client):
    """A3 — a write with no X-Actor is attributed to the honest dev-default (never
    silently un-attributed); the §2B 'no un-attributed write' invariant holds."""
    ag = client.get("/v1/agent", params={"name": "ws5_bff_test"}).json()
    client.put("/v1/agent", json=ag)  # no X-Actor
    rec = client.get("/v1/audit").json()["records"][-1]
    assert rec["actor"] == {"type": "system", "id": "dev-default"}


def _seed_provenance_blob(coll_db, run_id="run-abc"):
    from lithrim_bench.harness.collections import PIPELINE_RUNS

    blob = {
        "pipeline_run_id": run_id,
        "org_id": "local",
        "timestamp": "2026-06-04T00:00:00+00:00",
        "stages_executed": ["semantic"],
        "verdict": "reject",
        "gate_decision": "block",
        "verdict_flipped_by_stage": "none",
        "findings": [{"type": "semantic", "code": "FABRICATED_HISTORY", "detail": "x"}],
        "stage_results": {
            "semantic": {
                "status": "completed",
                "evidence": [{"span": "line 4"}],
                "judge_votes": [
                    {
                        "judge_role": "risk_judge",
                        "vote": "BLOCK",
                        "confidence": 0.99,
                        "model": "gpt-4.1",
                        "reason": "dose wrong",
                        "findings": [{"taxonomy_code": "WRONG_DOSAGE"}],
                    },
                ],
            }
        },
        "agent_id": "ws0_default",
    }
    PIPELINE_RUNS.insert(blob, db_path=coll_db)
    return run_id


def test_run_provenance_report_projects_the_blob(client, tmp_path):
    """A4 — GET /v1/runs/{id}/audit assembles a why/when/who/what report from a
    persisted SqliteProvenanceStore blob (per-judge votes + reasoning + verdict)."""
    run_id = _seed_provenance_blob(tmp_path / "coll.sqlite")
    rep = client.get(f"/v1/runs/{run_id}/audit")
    assert rep.status_code == 200
    body = rep.json()
    assert body["verdict"] == "reject"
    assert body["actor"] == {"type": "agent", "id": "ws0_default"}
    judges = body["judges"]
    assert judges[0]["judge_role"] == "risk_judge"
    assert judges[0]["vote"] == "BLOCK"
    assert judges[0]["reasoning"] == "dose wrong"
    assert judges[0]["evidence"] == [{"span": "line 4"}]
    assert judges[0]["findings"] == [{"taxonomy_code": "WRONG_DOSAGE"}]


def test_run_provenance_unpersisted_run_is_404_not_500(client):
    """A4 / N1 — an unknown / never-run id has no provenance blob, so it is a clean
    404 (never a 500). (UAP-3 S-BS-52: replay runs DO persist now; this id never ran.)"""
    res = client.get("/v1/runs/never-ran/audit")
    assert res.status_code == 404
    assert "not found" in res.text


# ── UAP-2 R2: /v1/judges — author a judge via ontology-assignment ─────────────

_AGENT = "ws5_bff_test"


def test_judges_list_returns_the_v2_trio(client):
    """A1 — GET /v1/judges lists each v2 role + its assignable lens + derived
    questions + the validator toolbox; unauthored roles are honest defaults."""
    body = client.get("/v1/judges", params={"agent": _AGENT}).json()
    roles = {j["role"] for j in body["judges"]}
    assert roles == {"risk_judge", "policy_judge", "faithfulness_judge"}
    assert "dosage_grounding" in body["validators"]
    risk = next(j for j in body["judges"] if j["role"] == "risk_judge")
    assert risk["authored"] is False and risk["assigned_flags"] == []
    assert "WRONG_DOSAGE" in {f["flag"] for f in risk["available_flags"]}


def test_judge_default_render_equals_base_prompt(client):
    """A4 — an unauthored judge renders role_key_questions byte-equal to its seed
    .txt base (no silent drift of safety-critical prose)."""
    j = client.get("/v1/judges/risk_judge", params={"agent": _AGENT}).json()
    assert j["rendered_prompt"] == j["base_prompt"]
    assert j["base_prompt"]  # non-empty


def test_judge_preview_diverges_with_an_assignment(client):
    """A8 — the demonstrable assignment→prompt link: assigning a flag renders the
    AUTHORED REFINEMENT into the exact prompt the bridge will send ($0, no model)."""
    j = client.get(
        "/v1/judges/risk_judge",
        params={"agent": _AGENT, "assigned_flags": "WRONG_DOSAGE,FABRICATED_ALLERGY"},
    ).json()
    assert j["rendered_prompt"] != j["base_prompt"]
    assert "AUTHORED REFINEMENT" in j["rendered_prompt"]
    assert "WRONG_DOSAGE" in j["rendered_prompt"]
    assert j["preview_flags"] == ["WRONG_DOSAGE", "FABRICATED_ALLERGY"]


def test_judge_put_round_trips_and_audits(client):
    """A1 + A3 — PUT assigns a lens + binds a model → GET reflects it + the saved
    assignment now renders into the prompt; the write emits an actor-attributed,
    immutable audit record (target.type='judge')."""
    res = client.put(
        "/v1/judges/risk_judge",
        params={"rationale": "assign dosage lens"},
        headers={"X-Actor": "sme@acme"},
        json={
            "model": "AZURE_OPENAI_DEPLOYMENT_COUNCIL",
            "assigned_flags": ["WRONG_DOSAGE"],
            "validator_refs": ["dosage_grounding"],
        },
    )
    assert res.status_code == 200, res.text

    j = client.get("/v1/judges/risk_judge", params={"agent": _AGENT}).json()
    assert j["authored"] is True
    assert j["assigned_flags"] == ["WRONG_DOSAGE"]
    assert j["model"] == "AZURE_OPENAI_DEPLOYMENT_COUNCIL"
    assert j["validator_refs"] == ["dosage_grounding"]
    assert "WRONG_DOSAGE" in j["rendered_prompt"]  # the saved assignment renders

    recs = client.get("/v1/audit", params={"target_type": "judge"}).json()["records"]
    assert len(recs) == 1
    assert recs[0]["actor"] == {"type": "user", "id": "sme@acme"}
    assert recs[0]["target"] == {"type": "judge", "id": "risk_judge"}
    assert recs[0]["why"]["rationale"] == "assign dosage lens"
    assert recs[0]["after"]["assigned_flags"] == ["WRONG_DOSAGE"]


def test_judge_put_422_on_owner_emit_violation(client):
    """A1 — owner↔emit (invariant #4): policy_judge cannot be assigned WRONG_DOSAGE
    (it neither owns nor emits it). 422, not a soft pass."""
    res = client.put("/v1/judges/policy_judge", json={"assigned_flags": ["WRONG_DOSAGE"]})
    assert res.status_code == 422
    assert "owner↔emit" in res.json()["detail"]


def test_judge_put_422_on_unknown_validator(client):
    """A1 — validators are execute-only references from the persisted toolbox; an
    unknown ref is rejected (a judge never authors/invents a validator)."""
    res = client.put(
        "/v1/judges/risk_judge",
        json={"assigned_flags": ["WRONG_DOSAGE"], "validator_refs": ["totally_made_up"]},
    )
    assert res.status_code == 422
    assert "validator" in res.json()["detail"]


def test_judge_unknown_role_is_404(client):
    """A retired/unknown role (e.g. the dormant behavior_judge) is a clean 404."""
    assert client.get("/v1/judges/behavior_judge", params={"agent": _AGENT}).status_code == 404
    assert client.put("/v1/judges/behavior_judge", json={"assigned_flags": []}).status_code == 404


def test_gate_authority_is_lens_not_stale_ontology_owner_roles(client):
    """The CITATION-DRIFT guard (Finding 1): the owner↔emit gate uses LENS_BY_ROLE
    (the v2 owned+emitted authority, owner-consistent vs _TIER1_OWNERS), NOT the
    ontology's owner_roles — which are stale v1 roles (behavior/source_message, NO
    faithfulness_judge). So faithfulness_judge CAN be assigned MISSING_ALLERGY /
    VALUE_MISMATCH (its v2 Tier-1 codes) even though the committed ontology's
    owner_roles for those codes never list it. Gating on the stale owner_roles would
    have wrongly 422'd this correct assignment."""
    res = client.put(
        "/v1/judges/faithfulness_judge",
        headers={"X-Actor": "sme@acme"},
        json={"assigned_flags": ["MISSING_ALLERGY", "VALUE_MISMATCH"]},
    )
    assert res.status_code == 200, res.text
    j = client.get("/v1/judges/faithfulness_judge", params={"agent": _AGENT}).json()
    assert set(j["assigned_flags"]) == {"MISSING_ALLERGY", "VALUE_MISMATCH"}
