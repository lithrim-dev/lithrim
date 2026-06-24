"""PHASE2-B — POST /v1/judges (the audited self-serve create-judge endpoint).

The STRUCTURAL TWIN of ``POST /v1/criterion`` (``test_criterion_endpoint.py``): resolve the active
WORKSPACE pack → ``splice_production_judge`` (roster + lens + owner-map) → seed the role prompt →
optional model bind → save the ``JudgeConfig`` → ONE author ``AuditRecord`` (``target.type='judge'``),
all atomic (the snapshot is rolled back on any later failure).

  * A — happy path (tier:core pack) → 200; the snapshot gains the role/lens/owner; a JudgeConfig is
        saved; ONE author AuditRecord; NO key in the response.
  * B — ``owned_codes ⊄ lens_codes`` → 422, snapshot UNCHANGED (atomic).
  * C — a code ∉ taxonomy → 422.
  * D — after create, the EXISTING ``PUT /v1/judges/{role}`` accepts the new role (404→200 flip).

Written RED-first: ``create_judge_endpoint`` does not exist yet. Runs $0/offline; needs the [bff]
extra. The active pack is a throwaway copy of ``packs/_core`` (no repo-source mutation).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness.audit import Actor  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "ws0_default"


def _make_pack(tmp_path: Path, name: str, tier: str = "core") -> str:
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "packs" / "_core", dst)
    m = json.loads((dst / "pack.json").read_text())
    m["pack_id"] = name
    m["tier"] = tier
    (dst / "pack.json").write_text(json.dumps(m, indent=2))
    return name


@pytest.fixture
def core_ws(tmp_path, monkeypatch):
    """Active workspace pinned to a throwaway tier:core pack; returns (pack_id, audit_records)."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.workspace import Workspace

    name = _make_pack(tmp_path, "corepack", tier="core")
    existing = os.environ.get("LITHRIM_BENCH_PACKS_DIR", "")
    monkeypatch.setenv(
        "LITHRIM_BENCH_PACKS_DIR", str(tmp_path) + (os.pathsep + existing if existing else "")
    )
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    pack_mod.assert_pack_judges_consistent.cache_clear()
    # the prompt-render dir is cached at judge_assignment import → the shipped _core; point it at the
    # throwaway pack so the role prompt the endpoint seeds (write_role_prompt) is what build_trio reads.
    import lithrim_bench.runtime.council.judge_assignment as _ja

    monkeypatch.setattr(_ja, "_ROLE_PROMPTS_DIR", tmp_path / "corepack" / "council_roles", raising=False)
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack=name))
    records: list = []
    # save_judge audits via the transactional upsert_with_audit, which calls
    # AuditLog.record(rec, conn=...) — accept the kwarg (the criterion twin calls record(rec) bare).
    monkeypatch.setattr(bff.AuditLog, "record", lambda self, rec, **kw: records.append(rec))
    yield name, records
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    pack_mod.assert_pack_judges_consistent.cache_clear()


def _req(**kw):
    return bff.CreateJudgeRequest(**kw)


def _call(tmp_path, body):
    """Call the endpoint fn directly with ALL params explicit (the FieldInfo-sentinel trap)."""
    return bff.create_judge_endpoint(
        body=body,
        rationale="the SME's why",
        db_path=tmp_path / "config.sqlite",
        default_actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _snapshot(pack: str) -> dict:
    from lithrim_bench.harness import pack as pack_mod

    return json.loads(pack_mod._pack_ref(pack, "flags_ref").read_text())


# ── A — happy path: snapshot spliced + role prompt seeded + JudgeConfig saved + ONE audit ──


def test_create_judge_splices_roster_lens_owner_and_saves_config(core_ws, tmp_path):
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.judges import load_judge

    pack, records = core_ws
    out = _call(
        tmp_path,
        _req(role="escalation_judge", lens_codes=["STYLE_VIOLATION"], owned_codes=["STYLE_VIOLATION"]),
    )
    assert out["role"] == "escalation_judge"
    assert out["lens_codes"] == ["STYLE_VIOLATION"]
    assert out["owned_codes"] == ["STYLE_VIOLATION"]
    assert "audit_id" in out

    # the snapshot gained the role on production_judges + lenses + tier1_owners
    snap = _snapshot(pack)
    assert "escalation_judge" in snap["production_judges"]
    assert snap["lenses"]["escalation_judge"] == ["STYLE_VIOLATION"]
    assert "escalation_judge" in snap["tier1_owners"]["STYLE_VIOLATION"]
    assert "escalation_judge" in pack_mod.pack_production_judges(pack)

    # the role prompt was seeded (the load_role_prompt FileNotFoundError wall)
    prompt_path = pack_mod._pack_ref(pack, "council_roles") / "escalation_judge.txt"
    assert prompt_path.exists()

    # a JudgeConfig was persisted with the lens as assigned_flags
    jc = load_judge("escalation_judge", db_path=tmp_path / "config.sqlite")
    assert jc is not None
    assert list(jc.assigned_flags) == ["STYLE_VIOLATION"]

    # ONE author AuditRecord for the judge
    judge_audits = [r for r in records if r.target.type == "judge" and r.action == "author"]
    assert len(judge_audits) == 1
    assert judge_audits[0].target.id == "escalation_judge"

    # NO key leaked anywhere in the response
    assert "key" not in json.dumps(out).lower() or "lens" in out  # no api_key field
    assert "api_key" not in out


# ── B — owned ⊄ lens → 422, snapshot UNCHANGED (atomic) ──


def test_inert_owner_422_snapshot_unchanged(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    before = _snapshot(pack)
    with pytest.raises(HTTPException) as ei:
        _call(
            tmp_path,
            _req(role="escalation_judge", lens_codes=["STYLE_VIOLATION"], owned_codes=["MISSING_CONTEXT"]),
        )
    assert ei.value.status_code == 422
    assert _snapshot(pack) == before  # no partial splice landed


# ── C — a code ∉ taxonomy → 422 ──


def test_unknown_code_422(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    before = _snapshot(pack)
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(role="escalation_judge", lens_codes=["NOT_IN_TAXONOMY"]))
    assert ei.value.status_code == 422
    assert _snapshot(pack) == before


# ── C2 — role collision (the role already runs) → 409 ──


def test_role_collision_409(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(role="risk_judge", lens_codes=["STYLE_VIOLATION"]))
    assert ei.value.status_code == 409


# ── C3 — empty lens → 422 ──


def test_empty_lens_422(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(role="escalation_judge", lens_codes=[]))
    assert ei.value.status_code == 422


# ── D — after create, the EXISTING PUT /v1/judges/{role} accepts the new role (404→200) ──


def test_put_judge_accepts_the_newly_created_role(core_ws, tmp_path):
    pack, _ = core_ws
    _call(
        tmp_path,
        _req(role="escalation_judge", lens_codes=["STYLE_VIOLATION"], owned_codes=["STYLE_VIOLATION"]),
    )
    # the new role's lens is now in the active pack snapshot, so the PUT gate
    # (_validate_judge_assignment via _active_lens_by_role) no longer 404s it
    out = bff.put_judge_endpoint(
        role="escalation_judge",
        judge={"assigned_flags": ["STYLE_VIOLATION"], "validator_refs": [], "model": ""},
        rationale="assign the lens",
        agent=None,
        db_path=tmp_path / "config.sqlite",
        default_actor=Actor(type="system", id="test"),
        x_actor=None,
    )
    assert out["status"] == "ok"
    assert out["role"] == "escalation_judge"


# ── F — the 4-judge authored grade votes through the UNCHANGED _apply_consensus ──
# (the consensus admission half lives in the runtime test file; here we prove the BFF-created
#  role reaches a clean 4-judge consensus via the authored stage with injected predictors.)


def test_created_role_votes_in_four_judge_consensus(core_ws, tmp_path, monkeypatch):
    # offline council construct (no real call — injected predictors); the sync openai client the
    # frozen __init__ builds reads the council settings singleton, so patch THAT (not just env).
    # $0: no completion is issued (every judge is a mocked predictor).
    from lithrim_bench.runtime.council import settings as council_settings
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator
    from lithrim_bench.runtime.council.judges_dspy import V2_ROLES

    monkeypatch.setattr(council_settings.settings, "OPENAI_API_KEY", "test-offline-key", raising=False)
    pack, _ = core_ws
    _call(
        tmp_path,
        _req(role="escalation_judge", lens_codes=["STYLE_VIOLATION"], owned_codes=["STYLE_VIOLATION"]),
    )

    def _pred(**_kw):
        return type("P", (), {"decision": "approve", "findings": [], "confidence": 0.9})()

    roster = [*V2_ROLES, "escalation_judge"]
    evaluator = build_authored_evaluator(
        ontology=None,
        assignments={"escalation_judge": ["STYLE_VIOLATION"]},
        predictors={r: _pred for r in roster},
        roles=roster,
        apply_gate=False,
    )
    out = evaluator({"call_context": {"transcript": "t"}, "artifacts": [{"content": "a"}]})
    assert out["consensus"]["decision"] in {"approve", "needs_review", "reject"}
    assert out["consensus"].get("reason") != "insufficient_valid_models"
    assert "escalation_judge" in {m["model"] for m in out["models"]}


# ── I — REGRESSION (P2-B critic Q6): rationale rides the QUERY param through REAL HTTP binding ──
# The _call tests above invoke the endpoint as a plain function with rationale= passed explicitly
# (the FieldInfo-sentinel trap), bypassing FastAPI's body/query binding — so they cannot catch the
# UI↔endpoint contract: the UI's createJudge sends rationale as a QUERY param (mirroring putJudge),
# the endpoint reads it via Query(). This drives a real TestClient request to PIN that the SME's
# audit "why" survives the round-trip (it was silently dropped when the UI sent it in the body).
def test_rationale_query_param_reaches_the_audit_why(core_ws, tmp_path):
    from fastapi.testclient import TestClient

    pack, records = core_ws
    db = tmp_path / "tc_config.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    try:
        client = TestClient(bff.app)
        resp = client.post(
            "/v1/judges?rationale=escalation+lane",  # query param, as the UI now sends it
            json={
                "role": "escalation_judge",
                "lens_codes": ["STYLE_VIOLATION"],
                "owned_codes": ["STYLE_VIOLATION"],
            },
        )
    finally:
        bff.app.dependency_overrides.pop(bff.get_config_db, None)

    assert resp.status_code == 200, resp.text
    judge_whys = [r.why for r in records if r.target.type == "judge"]
    assert {"rationale": "escalation lane"} in judge_whys, judge_whys  # NOT "" — the why survived
