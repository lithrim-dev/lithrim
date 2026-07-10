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

from tests._house_fixture import house_agent, pack_ws0_dir_or_none  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
# the ws0 fixture lives with the pack (PACK-DIST-2 C2). Only the NEEDS_PACK replay func reads
# it server-side (skipped in bare CE); the agent below just needs path strings, so resolve
# non-skipping (a None-fallback string the non-reading client funcs never touch).
FIXTURES = pack_ws0_dir_or_none() or (REPO_ROOT / "tests" / "fixtures" / "ws0")

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
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db_path)
    # S-BS-154: the BFF lens/snapshot authorities key off the ACTIVE WORKSPACE pack, not the
    # boot env. The product binds a clinical agent to a workspace pinned to its pack; construct
    # that binding hermetically (the house_client pattern) — the suite's canonical pack under
    # pack-on runs, the neutral _core default bare (where the clinical funcs skip, NEEDS_PACK).
    from lithrim_bench.harness.pack import active_pack

    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=active_pack()),
    )
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


@pytest.fixture
def house_client(tmp_path, monkeypatch):
    """The BFF client over the NEUTRAL _core house fixture (S-BS-137) — used by the
    domain-agnostic plumbing funcs (run-id/votes round-trip) so they run on _core in a
    bare CE checkout. The clinical funcs keep the clinical ``client`` (NEEDS_PACK/RELOCATED)."""
    db_path = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name="ws5_bff_house"), db_path=db_path)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
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


def test_case_labeled_helper():
    """HONEST-1 (H-D6): /v1/case must distinguish a DECLARED label (clean-negative ``[]``
    or a verdict) from an UNLABELED BYO case (absent), so the CaseTab never mislabels
    unknown-truth as a clean negative. ``_case_labeled`` is the pure presence test."""
    assert bff._case_labeled({"expected_safety_flags": []}) is True  # declared clean-negative
    assert bff._case_labeled({"expected_safety_flags": ["FABRICATED_HISTORY"]}) is True
    assert bff._case_labeled({"expected_compliance_verdict": "approve"}) is True
    assert bff._case_labeled({}) is False  # BYO unlabeled — no planted label
    assert bff._case_labeled({"expected_safety_flags": None, "expected_compliance_verdict": None}) is False


def test_get_case_reports_labeled_flag(client):
    """A by-construction corpus case is reported as labeled=True (the field is emitted)."""
    res = client.get("/v1/case?agent=ws5_bff_test")
    assert res.status_code == 200
    assert res.json()["labeled"] is True


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


def test_run_eval_carries_realized_council_votes(house_client):
    """D0 — the run response surfaces the REALIZED per-judge votes for the JudgeTab.
    Domain-agnostic plumbing: runs on the neutral _core house fixture (3 votes, v2 roles)."""
    body = house_client.post("/v1/run-eval", json={"agent": "ws5_bff_house", "live": False}).json()
    council = body["council"]
    votes = council["votes"]
    # the house baseline cast 3 real votes (risk / policy / faithfulness)
    assert {v["judge_role"] for v in votes} == {"risk_judge", "policy_judge", "faithfulness_judge"}
    for v in votes:
        assert v["vote"] in {"PASS", "WARN", "FAIL", "BLOCK"}
        # confidence is float | null (WS-6a D-E) — the reader must tolerate either
        assert v["confidence"] is None or isinstance(v["confidence"], (int, float))
        assert "model" in v
    assert isinstance(council["configured"], list)


def test_judges_lists_roster_when_default_agent_absent(house_client):
    """JUDGES-EMPTY-WS: GET /v1/judges must NOT 404 in a workspace that lacks the default
    agent (an empty/just-created workspace). It falls back to the active pack's ontology
    to render the role questions and still returns the saved roster — consistent with
    /v1/meta's judge count, which counts saved judges independent of any agent. The
    house_client db has 'ws5_bff_house' but NOT 'ws0_default' (the default agent param)."""
    res = house_client.get("/v1/judges")  # no ?agent → defaults to the absent ws0_default
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body["roles"]) == {"risk_judge", "policy_judge", "faithfulness_judge"}
    assert len(body["judges"]) == len(body["roles"])
    assert "validators" in body


def test_judges_still_resolves_an_existing_agent(house_client):
    """Regression: the agent-bound path is unchanged — an explicit existing agent resolves 200
    (the empty-workspace fallback must not change behavior when the agent IS present)."""
    res = house_client.get("/v1/judges", params={"agent": "ws5_bff_house"})
    assert res.status_code == 200, res.text
    assert set(res.json()["roles"]) == {"risk_judge", "policy_judge", "faithfulness_judge"}


# ── D1: PUT /v1/ontology — clobber-safe + validated ──────────────────────────


def _seed_body() -> dict:
    import json

    return json.loads(ONTOLOGY_SEED.read_text())


# PACK-DIST-2 D5: the funcs that read the committed clinical ontology seed bytes directly
# (test_put_ontology_accepts_and_round_trips + _rejects_snapshot_violation +
# _never_clobbers_the_committed_seed + the draft→grade loop + the audit-record write +
# the judge PUT round-trip/422/lens-gate funcs) relocated to the pack repo
# (tests/test_ws5_bff_relocated.py). The generic plumbing funcs (the house_client votes round-trip,
# the KB-proxy funcs, the agent/judge CRUD funcs that never read the seed) + the NEEDS_PACK funcs
# (test_run_eval_replay_…, test_ontology_read, test_put_ontology_rejects_malformed,
# test_judges_list_returns_the_v2_trio) stay here.


def test_put_ontology_rejects_malformed(client):
    """A3 — a structurally malformed ontology is rejected (422), nothing persists."""
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json={"not": "an ontology"})
    assert res.status_code == 422
    # GET still serves the committed seed (no working copy was written)
    assert (
        client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()["domain"] == "clinical"
    )


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


# PACK-DIST-2 D5: the draft→grade loop funcs (test_draft_ontology_grades_not_the_committed_seed +
# test_draft_re_edit_regrades_not_the_stale_cache) + the audit-record write
# (test_config_writes_emit_appended_audit_records) read/grade the committed clinical seed bytes
# directly → relocated to the pack repo (tests/test_ws5_bff_relocated.py).


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


# PACK-DIST-2 D5: test_judge_put_round_trips_and_audits relocated to the pack repo
# (tests/test_ws5_bff_relocated.py) — its assignment renders the clinical lens (WRONG_DOSAGE) into
# the prompt over the committed clinical seed.


def test_judge_put_422_on_owner_emit_violation(client):
    """A1 — owner↔emit (invariant #4): policy_judge cannot be assigned WRONG_DOSAGE
    (it neither owns nor emits it). 422, not a soft pass."""
    res = client.put("/v1/judges/policy_judge", json={"assigned_flags": ["WRONG_DOSAGE"]})
    assert res.status_code == 422
    assert "owner↔emit" in res.json()["detail"]


# PACK-DIST-2 D5: test_judge_put_422_on_unknown_validator relocated to the pack repo
# (tests/test_ws5_bff_relocated.py) — it assigns the clinical WRONG_DOSAGE lens.


def test_judge_unknown_role_is_404(client):
    """A retired/unknown role (e.g. the dormant behavior_judge) is a clean 404."""
    assert client.get("/v1/judges/behavior_judge", params={"agent": _AGENT}).status_code == 404
    assert client.put("/v1/judges/behavior_judge", json={"assigned_flags": []}).status_code == 404


# PACK-DIST-2 D5: test_gate_authority_is_lens_not_stale_ontology_owner_roles relocated to the pack
# repo (tests/test_ws5_bff_relocated.py) — it assigns clinical Tier-1 codes (MISSING_ALLERGY /
# VALUE_MISMATCH) over the committed clinical seed.
