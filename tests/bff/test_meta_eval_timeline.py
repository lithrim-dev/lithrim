"""REL-OPS-1 / O3 — the longitudinal meta-eval READ surface.

``GET /v1/meta-eval/timeline`` joins the immutable run-history blobs (RUNTRAIL SoT) to
their agreement outcomes over the time axis, scoped to one agent: per run — when it ran,
its ``grade_signature`` (so a config change is detectable as a series break), the recorded
model/roster identity, verdict-vs-gold agreement where the case carries gold, and the
clinician meta-verdict (META-VERDICT-1 AuditRecords) where one exists. "The evaluator's
own accuracy, dated" (SPEC_RELIABILITY_PROGRAM O3).

Honesty contract: an absent join is an explicit ``null`` — never a fabricated value.
Pure READ: no new write path, no engine edit, no consensus touch. $0 / offline.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent
from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "o3_timeline_agent"
_OTHER_AGENT = "o3_other_agent"
_IDLE_AGENT = "o3_idle_agent"  # exists in config, has zero runs

_SIG_A = "sig-aaaa"
_SIG_B = "sig-bbbb"

# the ingested corpus the gold join derives from (the SAME _corpus_golds_labeled
# derivation the RUN-ALL-1 cohort scorecard reads): c1 is labeled, c2 is unlabeled.
_CORPUS = [
    {"case_id": "c1", "expected_safety_flags": ["F_ALPHA"]},
    {"case_id": "c2", "expected_safety_flags": []},  # HONEST-1 placeholder — NOT gold
]


def _blob(run_id, ts, agent, case_id, verdict, codes, sig, models=None):
    """A minimal persisted-PipelineProvenance-shaped run blob (the fields the
    run_eval persist/enrich helpers stamp: agent_id/case_id/grade_signature ride as
    extra doc fields, findings carry taxonomy ``code``s, judge_votes carry ``model``)."""
    return {
        "pipeline_run_id": run_id,
        "org_id": "test",
        "timestamp": ts,
        "request_hash": "h",
        "stages_executed": ["semantic"],
        "stage_results": {
            "semantic": {
                "status": "completed",
                "findings": [],
                "evidence": [],
                "judge_votes": [
                    {"judge_role": role, "vote": "approve", "model": model}
                    for role, model in (models or {}).items()
                ],
            }
        },
        "council_config": {},
        "verdict": verdict,
        "gate_decision": "block" if verdict == "BLOCK" else "pass",
        "findings": [{"severity": "high", "code": c} for c in codes],
        "agent_id": agent,
        "case_id": case_id,
        "grade_signature": sig,
    }


def _seed_runs(coll_db: Path) -> None:
    store = SqliteProvenanceStore(db_path=coll_db)

    async def _save_all():
        # inserted OUT of time order on purpose — the timeline must sort by ts,
        # not echo insertion order.
        await store.save_blob(
            _blob(
                "run-3",
                "2026-07-03T00:00:00+00:00",
                _AGENT,
                "c1",
                "PASS",
                [],
                _SIG_B,
                models={"risk_judge": "gpt-x"},
            )
        )
        await store.save_blob(
            _blob(
                "run-1",
                "2026-07-01T00:00:00+00:00",
                _AGENT,
                "c1",
                "BLOCK",
                ["F_ALPHA"],
                _SIG_A,
                models={"risk_judge": "gpt-x", "policy_judge": "claude-y"},
            )
        )
        await store.save_blob(
            _blob(
                "run-2",
                "2026-07-02T00:00:00+00:00",
                _AGENT,
                "c2",
                "PASS",
                [],
                _SIG_A,
            )
        )
        # another agent's run — must NEVER appear in _AGENT's timeline
        await store.save_blob(
            _blob(
                "run-other",
                "2026-07-01T12:00:00+00:00",
                _OTHER_AGENT,
                "c1",
                "BLOCK",
                ["F_ALPHA"],
                _SIG_A,
            )
        )

    asyncio.run(_save_all())


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=_AGENT), db_path=db_path)
    save_agent(house_agent(name=_IDLE_AGENT), db_path=db_path)
    coll_db = tmp_path / "coll.sqlite"
    _seed_runs(coll_db)
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: coll_db
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def _timeline(client, agent=_AGENT):
    r = client.get("/v1/meta-eval/timeline", params={"agent": agent})
    assert r.status_code == 200, r.text
    return r.json()


# ── ordering + agent scoping ──────────────────────────────────────────────────────


def test_timeline_oldest_to_newest_scoped_to_agent(client):
    body = _timeline(client)
    assert body["agent"] == _AGENT
    ids = [row["run_id"] for row in body["timeline"]]
    assert ids == ["run-1", "run-2", "run-3"]  # oldest → newest, run-other excluded
    assert body["n_runs"] == 3
    ts = [row["ts"] for row in body["timeline"]]
    assert ts == sorted(ts)


def test_unknown_agent_is_404(client):
    r = client.get("/v1/meta-eval/timeline", params={"agent": "no_such_agent"})
    assert r.status_code == 404, r.text


def test_known_agent_with_no_runs_is_empty(client):
    body = _timeline(client, agent=_IDLE_AGENT)
    assert body["timeline"] == [] and body["n_runs"] == 0


# ── the gold (verdict-vs-gold) join — honest presence AND absence ─────────────────


def test_gold_join_where_case_carries_gold(client):
    rows = {row["run_id"]: row for row in _timeline(client)["timeline"]}
    g1 = rows["run-1"]["gold"]
    assert g1 is not None
    assert g1["expected"] == ["F_ALPHA"]
    assert g1["caught"] == ["F_ALPHA"] and g1["missed"] == [] and g1["spurious"] == []
    assert g1["verdict_match"] is True  # gold present + BLOCK
    # the SAME case, later run under a changed config: the judge missed the gold flag
    g3 = rows["run-3"]["gold"]
    assert g3["caught"] == [] and g3["missed"] == ["F_ALPHA"]
    assert g3["verdict_match"] is False  # gold present + PASS = disagreement, dated


def test_gold_join_absent_is_explicit_null_never_fabricated(client):
    rows = {row["run_id"]: row for row in _timeline(client)["timeline"]}
    # c2 carries only the HONEST-1 `expected_safety_flags: []` placeholder — no gold
    assert rows["run-2"]["gold"] is None


# ── the clinician meta-verdict join (META-VERDICT-1 AuditRecords) ─────────────────


def test_meta_verdict_join_where_record_exists(client):
    # a clinician dissents on run-1, twice (the record APPENDS; latest wins the summary)
    client.post(
        "/v1/meta-verdict",
        json={
            "run_id": "run-1",
            "human_verdict": "fail",
            "agrees_with_council": False,
            "judge_fallacy_code": "Reference Bias",
            "rationale": "first read",
        },
    )
    client.post(
        "/v1/meta-verdict",
        json={
            "run_id": "run-1",
            "human_verdict": "fail",
            "agrees_with_council": True,
            "rationale": "second read — the council was right after all",
        },
    )
    rows = {row["run_id"]: row for row in _timeline(client)["timeline"]}
    mv = rows["run-1"]["meta_verdict"]
    assert mv is not None
    assert mv["n_records"] == 2
    assert mv["human_verdict"] == "fail"
    assert mv["agrees_with_council"] is True  # the LATEST record
    assert mv["judge_fallacy_code"] is None


def test_meta_verdict_absent_is_explicit_null(client):
    rows = {row["run_id"]: row for row in _timeline(client)["timeline"]}
    assert rows["run-2"]["meta_verdict"] is None
    assert rows["run-3"]["meta_verdict"] is None


# ── grade_signature grouping: a signature change is a visible series break ────────


def test_signature_per_run_and_segments_mark_the_series_break(client):
    body = _timeline(client)
    sigs = [row["grade_signature"] for row in body["timeline"]]
    assert sigs == [_SIG_A, _SIG_A, _SIG_B]
    segs = body["signature_segments"]
    assert [s["grade_signature"] for s in segs] == [_SIG_A, _SIG_B]
    assert [s["n_runs"] for s in segs] == [2, 1]
    assert segs[0]["start_ts"] == "2026-07-01T00:00:00+00:00"
    assert segs[0]["end_ts"] == "2026-07-02T00:00:00+00:00"
    assert segs[1]["start_ts"] == segs[1]["end_ts"] == "2026-07-03T00:00:00+00:00"


# ── model/roster identity as recorded ─────────────────────────────────────────────


def test_models_projected_from_recorded_judge_votes(client):
    rows = {row["run_id"]: row for row in _timeline(client)["timeline"]}
    assert {"judge_role": "risk_judge", "model": "gpt-x"} in rows["run-1"]["models"]
    assert {"judge_role": "policy_judge", "model": "claude-y"} in rows["run-1"]["models"]
    assert rows["run-2"]["models"] == []  # no votes recorded → honest empty, not fabricated


# ── the CLI presenter (scripts/meta_eval_timeline.py) — the same join, one code path ──


def _cli_module():
    import importlib.util

    path = REPO_ROOT / "scripts" / "meta_eval_timeline.py"
    spec = importlib.util.spec_from_file_location("meta_eval_timeline_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """The CLI reads the SAME stores directly (no HTTP): a tmp config DB + tmp run
    history + the monkeypatched corpus — mirrors the endpoint fixture without the app."""
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=_AGENT), db_path=db_path)
    coll_db = tmp_path / "coll.sqlite"
    _seed_runs(coll_db)
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    return db_path, coll_db


def test_cli_json_emits_the_same_join(cli_env, capsys):
    db_path, coll_db = cli_env
    mod = _cli_module()
    rc = mod.main(
        ["--agent", _AGENT, "--config-db", str(db_path),
         "--collections-db", str(coll_db), "--json"]
    )
    assert rc == 0
    body = __import__("json").loads(capsys.readouterr().out)
    assert [r["run_id"] for r in body["timeline"]] == ["run-1", "run-2", "run-3"]
    assert [s["grade_signature"] for s in body["signature_segments"]] == [_SIG_A, _SIG_B]
    assert body["timeline"][1]["gold"] is None  # honest absence survives the CLI path


def test_cli_table_marks_the_series_break_and_dissent(cli_env, capsys):
    db_path, coll_db = cli_env
    # one clinician dissent on run-1 so the table exercises the meta column
    from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target

    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=Actor(type="user", id="dr-test"),
            action="meta_verdict",
            target=Target(type="verdict", id="run-1"),
            why={"rationale": "r"},
            after={"human_verdict": "fail", "agrees_with_council": False,
                   "judge_fallacy_code": "Reference Bias"},
            run_id="run-1",
        )
    )
    mod = _cli_module()
    rc = mod.main(
        ["--agent", _AGENT, "--config-db", str(db_path), "--collections-db", str(coll_db)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("series break") == 1  # exactly the sig-a → sig-b transition
    assert "DISSENT" in out  # run-1's clinician dissent is visible
    lines = [ln for ln in out.splitlines() if ln.startswith("2026-")]
    assert len(lines) == 3
    assert lines[1].split()[-1] == "-"  # run-2: no meta-verdict → an honest dash


def test_cli_unknown_agent_exits_nonzero(cli_env, capsys):
    db_path, coll_db = cli_env
    mod = _cli_module()
    rc = mod.main(
        ["--agent", "no_such_agent", "--config-db", str(db_path),
         "--collections-db", str(coll_db)]
    )
    assert rc == 1
    assert "no_such_agent" in capsys.readouterr().err
