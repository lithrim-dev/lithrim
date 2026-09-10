"""UI-JOURNEY-1 acceptance (B0): the six verbs of the loop, each reachable over HTTP from the
shell, all scoped to one workspace, on the $0 replay path (a stubbed judge; no key, no
network). The definition of done for the branch: an uninvolved person on a fresh compose stack
with the dataset files and their own key reproduces the pilot table without a terminal. These
tests pin the service half of that: import through an importer manifest, a background grade
job that survives a restart and can be listed, the two-vocabulary scorecard, the export, the
spend line, and a workspace resources read. They fail with 404 until each route exists."""

from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402
from tests.bff.test_corpus_grade_loop import _envelope, _stub_record, _write_corpus  # noqa: E402
from tests.examples.test_ragtruth_adapter import _corpus, _train_rows  # noqa: E402

AGENT = "journey_agent"
WS = "journey_ws"
JUDGE = json.loads((REPO_ROOT / "examples/ragtruth/judge.ragtruth_detector.json").read_text())


def _jsonl(rows) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


def _raw_files() -> dict[str, str]:
    """The two upstream files as text, from the adapter test's synthetic corpus: six test
    sources per task (clean + labeled response each) plus two train rows per task."""
    responses, sources = _corpus()
    # the adapter fixture's stray train row shares a source with the test split; the loop's
    # splits must be source-disjoint (the route refuses otherwise), so keep only true test rows
    responses = [r for r in responses if r.get("split") == "test"]
    responses += _train_rows(sources, per_task=2)
    # RAGTruth keeps a QA source as a {question, passages} object (the paper prompt reads both)
    for sid, s in sources.items():
        if s["task_type"] == "QA":
            s["source_info"] = {"question": f"question {sid}?", "passages": f"passages for {sid}"}
    return {"response.jsonl": _jsonl(responses), "source_info.jsonl": _jsonl(sources.values())}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    fake_ws = types.SimpleNamespace(
        out_dir=out,
        pack=bff.workspace.DEFAULT_PACK,
        packs_dir=None,
        name=WS,
        collections_db=tmp_path / "coll.sqlite",
        config_db=db_path,
        dir=tmp_path,
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)
    # the judge the journey configures is pack STATE: point the authoring writers at a temporary
    # overlay so the tracked _core pack is never written (PACK-OVERLAY-1)
    monkeypatch.setenv("LITHRIM_BENCH_PACK_OVERLAY_DIR", str(tmp_path / "overlay"))

    seq = {"n": 0}

    def _judged_run(agent, **kw):
        """A perfect judge over the case's own labels, persisted as the run blob the audit and
        scorecard reads project (the real pipeline writes this itself). Every call is its own
        run (unique id), as in the pipeline."""
        rec = _stub_record(agent, **kw)
        cid = agent.dataset.case_id
        seq["n"] += 1
        rid = f"run-{cid}-{seq['n']}"
        rec["result"]["provenance"]["pipeline_run_id"] = rid
        case = next((c for c in bff._read_ingested_corpus(fake_ws) if c.get("case_id") == cid), {})
        flags = list(case.get("expected_safety_flags") or [])
        spans = [
            {"quote": lab.get("text")}
            for lab in ((case.get("ragtruth") or {}).get("labels") or [])
            if lab.get("text")
        ]
        verdict = "BLOCK" if flags else "PASS"
        rec["composite"]["verdict"] = "reject" if flags else "approve"
        rec["composite"]["stage_verdict"] = verdict
        doc = {
            "pipeline_run_id": rid,
            "case_id": cid,
            "agent_id": agent.name,
            "timestamp": "2026-09-10T00:00:00+00:00",
            "verdict": verdict,
            "grade_path": "in_process",
            "stage_results": {
                "semantic": {
                    "judge_votes": [
                        {
                            "judge_role": "ragtruth_detector",
                            "vote": verdict,
                            "model": "azure/gpt-4.1",
                            "served_model": "gpt-4.1-2025-04-14",
                            "findings": flags,
                            "errors": [],
                            "usage": {
                                "prompt_tokens": 1000,
                                "completion_tokens": 50,
                                "total_tokens": 1050,
                            },
                        }
                    ],
                    "evidence": [
                        {
                            "judge": "ragtruth_detector",
                            "violation_code": flags[0] if flags else None,
                            "spans": spans,
                        }
                    ]
                    if spans
                    else [],
                }
            },
            "grounded": {"verdict": verdict, "suppressed": [], "enforced": []},
            "cost_tokens": {"prompt": 1000, "completion": 50, "total": 1050},
        }
        bff.run_coro(bff.provenance_store_for(fake_ws.collections_db).save_blob(doc))
        return rec

    monkeypatch.setattr(bff.run_eval, "run", _judged_run)
    monkeypatch.setattr(
        bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)}
    )
    monkeypatch.setattr(bff, "_JOBS", {})
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), out
    finally:
        bff.app.dependency_overrides.clear()


def _import(cli, per_task=2) -> dict:
    res = cli.post(
        "/v1/cases/import",
        json={
            "agent": AGENT,
            "importer": "ragtruth",
            "files": _raw_files(),
            "per_task": per_task,
            "splits": ["test", "calibration"],
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _split_corpus(out, n_test=3, n_calib=2) -> None:
    """A corpus already carrying split tags (what the importer writes), so the grade tests do
    not depend on the import route."""
    rows = []
    for i in range(n_test):
        rows.append(
            {
                **_envelope(f"t{i}_bad", context=f"Doctor: t{i}"),
                "split": "test",
                "importer": "ragtruth_vocabulary",
            }
        )
    for i in range(n_calib):
        rows.append(
            {
                **_envelope(f"c{i}_ok", context=f"Doctor: c{i}"),
                "split": "calibration",
                "importer": "ragtruth_vocabulary",
            }
        )
    _write_corpus(out, rows)


def _wait_done(cli, job_id, timeout=10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = cli.get(f"/v1/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


# --------------------------------------------------------------------------- load (B4)
def test_importers_are_listed_with_their_dataset_and_adapter(client):
    cli, _out = client
    res = cli.get("/v1/importers")
    assert res.status_code == 200, res.text
    by_id = {i["id"]: i for i in res.json()["importers"]}
    imp = by_id["ragtruth_vocabulary"]
    assert imp["dataset"] == "ragtruth" and imp["adapter"] is True
    assert imp["files"] == ["response.jsonl", "source_info.jsonl"]


def test_import_applies_the_importer_and_tags_every_case_with_its_split(client):
    cli, _out = client
    body = _import(cli)
    assert body["importer"] == "ragtruth_vocabulary" and body["dataset"] == "ragtruth"
    assert body["imported"]["test"] >= 3 and body["imported"]["calibration"] >= 1
    cases = cli.get(f"/v1/cases?agent={AGENT}&limit=500").json()["cases"]
    splits = {c["split"] for c in cases}
    assert splits == {"test", "calibration"}
    assert all(c["importer"] == "ragtruth_vocabulary" for c in cases)
    labeled = [c for c in cases if c["split"] == "test" and c.get("expected_safety_flags")]
    assert labeled, "labels are kept on the native path (never mapped away)"


def test_import_refuses_an_unknown_importer_and_a_missing_file(client):
    cli, _out = client
    res = cli.post(
        "/v1/cases/import",
        json={"agent": AGENT, "importer": "nope", "files": _raw_files(), "per_task": 1},
    )
    assert res.status_code == 404 and "nope" in res.json()["detail"]
    files = _raw_files()
    files.pop("source_info.jsonl")
    res = cli.post(
        "/v1/cases/import",
        json={"agent": AGENT, "importer": "ragtruth", "files": files, "per_task": 1},
    )
    assert res.status_code == 422 and "source_info.jsonl" in res.json()["detail"]


# --------------------------------------------------------------------------- grade (B2, B7)
def test_jobs_are_listed_per_agent_with_their_round(client):
    cli, out = client
    _split_corpus(out)
    res = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "before",
            "split": "test",
        },
    )
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    _wait_done(cli, job_id)
    listed = cli.get(f"/v1/jobs?agent={AGENT}").json()["jobs"]
    mine = {j["job_id"]: j for j in listed}[job_id]
    assert mine["status"] == "done" and mine["round"] == "before" and mine["total"] == 3
    assert mine["split"] == "test" and "rows" not in mine
    calib = cli.post(
        "/v1/cases/grade",
        json={"agent": AGENT, "in_process": True, "background": True, "split": "calibration"},
    )
    assert calib.status_code == 202 and calib.json()["total"] == 2
    _wait_done(cli, calib.json()["job_id"])
    none = cli.post("/v1/cases/grade", json={"agent": AGENT, "background": True, "split": "x"})
    assert none.status_code == 400 and "split" in none.json()["detail"]
    assert cli.get("/v1/jobs?agent=someone_else").json()["jobs"] == []


def test_a_job_orphaned_by_a_restart_reads_as_interrupted_and_resumes(client):
    cli, out = client
    _split_corpus(out)
    job_id = "job-orphan"
    (out / "jobs").mkdir(exist_ok=True)
    (out / "jobs" / f"{job_id}.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "agent": AGENT,
                "status": "running",
                "error": None,
                "targets": ["ragtruth_2", "ragtruth_4"],
                "total": 2,
                "done": 1,
                "rows": [
                    {
                        "case_id": "ragtruth_2",
                        "verdict": "reject",
                        "findings": [],
                        "votes": [],
                        "run_id": "run-ragtruth_2",
                    },
                ],
                "request": {"live": False, "in_process": True, "strict": False},
                "round": "before",
            }
        )
    )
    # the process that owned the thread is gone (fresh _JOBS): the record must not read
    # as running forever, and resume must be allowed instead of a 409
    got = cli.get(f"/v1/jobs/{job_id}").json()
    assert got["status"] == "interrupted"
    res = cli.post("/v1/cases/grade", json={"agent": AGENT, "resume": job_id, "background": True})
    assert res.status_code == 202, res.text
    job = _wait_done(cli, job_id)
    assert job["status"] == "done" and job["done"] == 2 and job["round"] == "before"


# --------------------------------------------------------------------------- scorecard (B5)
def test_scorecard_for_a_job_speaks_both_vocabularies(client):
    cli, _out = client
    _import(cli)
    cli.post("/v1/judges?rationale=test", json=JUDGE)
    job_id = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "before",
            "split": "test",
        },
    ).json()["job_id"]
    _wait_done(cli, job_id)
    res = cli.get(f"/v1/jobs/{job_id}/scorecard?vocabulary=ragtruth")
    assert res.status_code == 200, res.text
    card = res.json()
    tasks = {r["task"] for r in card["per_task"]}
    assert {"QA", "Summary", "Data2txt", "OVERALL"} <= tasks
    overall = next(r for r in card["per_task"] if r["task"] == "OVERALL")
    assert {"n", "P", "R", "F1", "span_P", "span_R", "span_F1", "refused"} <= set(overall)
    codes = {r["code"]: r for r in card["per_code"]}
    assert "Evident Conflict" in codes["SOURCE_CONTRADICTION"]["dataset_terms"]
    assert card["vocabulary"]["dataset"] == "ragtruth"
    assert "annotated span" in card["vocabulary"]["verdict_rule"]["ragtruth"]
    assert "Tier-1" in card["vocabulary"]["verdict_rule"]["lithrim"]
    assert card["round"] == "before" and "rendered" in card


def test_scorecard_without_an_importer_vocabulary_still_scores_in_our_terms(client):
    cli, _out = client
    _import(cli)
    job_id = cli.post(
        "/v1/cases/grade",
        json={"agent": AGENT, "in_process": True, "background": True, "split": "test"},
    ).json()["job_id"]
    _wait_done(cli, job_id)
    card = cli.get(f"/v1/jobs/{job_id}/scorecard").json()
    assert card["vocabulary"]["dataset"] == "ragtruth", "the cases name their importer"
    assert any(r["task"] == "OVERALL" for r in card["per_task"])


# --------------------------------------------------------------------------- export (B8)
def test_export_writes_the_corpus_under_the_workspace_and_serves_it(client):
    cli, out = client
    _import(cli)
    job_id = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "before",
            "split": "test",
        },
    ).json()["job_id"]
    _wait_done(cli, job_id)
    res = cli.post("/v1/export", json={"agent": AGENT, "job_id": job_id, "format": "generic"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rows"] >= 3 and body["split"] == "test" and body["format"] == "generic"
    assert set(body["tiers"]) <= {"judge-only", "floor-proved", "expert-confirmed"}
    assert body["vocabulary"] == "ragtruth_vocabulary"
    path = out / "exports" / body["name"]
    assert path.exists() and path.with_suffix(".manifest.json").exists()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == body["rows"] and all("label_basis" in r for r in rows)
    listed = cli.get(f"/v1/exports?agent={AGENT}").json()["exports"]
    assert any(e["name"] == body["name"] for e in listed)
    served = cli.get(f"/v1/exports/{body['name']}")
    assert served.status_code == 200 and served.text.count("\n") == body["rows"]


def test_export_refuses_a_training_format_off_the_calibration_split(client):
    cli, _out = client
    _import(cli)
    job_id = cli.post(
        "/v1/cases/grade",
        json={"agent": AGENT, "in_process": True, "background": True, "split": "test"},
    ).json()["job_id"]
    _wait_done(cli, job_id)
    res = cli.post("/v1/export", json={"agent": AGENT, "job_id": job_id, "format": "paper"})
    assert res.status_code == 422 and "calibration" in res.json()["detail"]


# --------------------------------------------------------------------------- spend (B9)
def test_spend_prices_the_agents_runs_at_list_price(client):
    cli, _out = client
    _import(cli)
    job_id = cli.post(
        "/v1/cases/grade",
        json={"agent": AGENT, "in_process": True, "background": True, "split": "test"},
    ).json()["job_id"]
    _wait_done(cli, job_id)
    res = cli.get(f"/v1/spend?agent={AGENT}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert {
        "usd_list_price",
        "prompt_tokens",
        "completion_tokens",
        "runs",
        "runs_priced",
        "runs_unpriced_model",
        "runs_without_cost_record",
    } <= set(body)
    assert body["runs"] >= 3
    assert cli.get("/v1/spend?agent=nobody").json()["runs"] == 0


# --------------------------------------------------------------------------- workspace (B3)
def test_workspace_resources_name_everything_the_loop_left_behind(client):
    cli, out = client
    _split_corpus(out)
    job_id = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "before",
            "split": "test",
        },
    ).json()["job_id"]
    _wait_done(cli, job_id)
    (out / "compiled_demos_dspy3b_ragtruth_detector.json").write_text("[]")
    (out / "compiled_demos_dspy3b_ragtruth_detector.score.json").write_text(
        json.dumps({"graded": 0.67, "source": "x"})
    )
    res = cli.get(f"/v1/workspaces/{WS}/resources?agent={AGENT}")
    assert res.status_code == 200, res.text
    r = res.json()
    assert r["name"] == WS and r["pack"] == "_core"
    assert r["cases"]["by_split"]["test"] >= 3 and r["cases"]["importer"] == "ragtruth_vocabulary"
    assert any(j["job_id"] == job_id and j["round"] == "before" for j in r["jobs"])
    assert r["pinned_demos"]["ragtruth_detector"]["graded"] == 0.67
    assert {"runs", "corrections", "exports", "bindings", "arm_manifest"} <= set(r)
    assert cli.get("/v1/workspaces/not_here/resources").status_code == 404


# --------------------------------------------------------------------------- the whole chain
def test_the_loop_from_import_to_export_over_one_workspace(client):
    cli, out = client
    body = _import(cli)
    cli.post("/v1/judges?rationale=journey", json=JUDGE)
    before = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "before",
            "split": "test",
        },
    ).json()["job_id"]
    assert _wait_done(cli, before)["status"] == "done"
    after = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "after",
            "split": "test",
        },
    ).json()["job_id"]
    assert _wait_done(cli, after)["status"] == "done"
    rounds = {j["round"] for j in cli.get(f"/v1/jobs?agent={AGENT}").json()["jobs"]}
    assert rounds == {"before", "after"}
    (out / "compiled_demos_dspy3b_ragtruth_detector.json").write_text("[1, 2, 3, 4]")
    card = cli.get(f"/v1/jobs/{after}/scorecard?vocabulary=ragtruth&compare=before").json()
    assert card["round"] == "after"
    assert card["compare"]["job_id"] == before and card["compare"]["round"] == "before"
    assert {r["task"] for r in card["compare"]["per_task"]} == {r["task"] for r in card["per_task"]}
    assert card["pinned_demos"]["ragtruth_detector"]["demos"] == 4
    lone = cli.get(f"/v1/jobs/{before}/scorecard?compare=before").json()
    assert lone["compare"] is None, "a round never compares with itself"
    by_id = cli.get(f"/v1/jobs/{after}/scorecard?compare={before}").json()
    assert by_id["compare"]["job_id"] == before
    exp = cli.post("/v1/export", json={"agent": AGENT, "job_id": after}).json()
    assert exp["rows"] == body["imported"]["test"]
    spend = cli.get(f"/v1/spend?agent={AGENT}").json()
    assert spend["runs"] == 2 * body["imported"]["test"]
    res = cli.get(f"/v1/workspaces/{WS}/resources?agent={AGENT}").json()
    assert len(res["jobs"]) == 2 and len(res["exports"]) == 1


# --------------------------------------------------------------------------- FT-FROM-SHELL-1
def test_a_calibration_round_exports_the_chat_training_file_with_the_importers_prompt(client):
    """The training export needs graded calibration rows (a round=calibration job) and the
    chat format's prompt module comes from the importer manifest, so the shell sends none."""
    cli, out = client
    body = _import(cli)
    job_id = cli.post(
        "/v1/cases/grade",
        json={
            "agent": AGENT,
            "in_process": True,
            "background": True,
            "round": "calibration",
            "split": "calibration",
        },
    ).json()["job_id"]
    job = _wait_done(cli, job_id)
    assert job["status"] == "done" and job["total"] == body["imported"]["calibration"]
    res = cli.post(
        "/v1/export", json={"agent": AGENT, "job_id": job_id, "format": "chat", "filter": "all"}
    )
    assert res.status_code == 200, res.text
    exp = res.json()
    assert (
        exp["split"] == "calibration" and exp["format"] == "chat" and exp["round"] == "calibration"
    )
    rows = [json.loads(line) for line in (out / "exports" / exp["name"]).read_text().splitlines()]
    assert len(rows) == exp["rows"] > 0
    assert all([m["role"] for m in r["messages"]] == ["user", "assistant"] for r in rows)
    assert all("hallucination list" in r["messages"][1]["content"] for r in rows)
    imp = next(
        i for i in cli.get("/v1/importers").json()["importers"] if i["dataset"] == "ragtruth"
    )
    assert imp["training_formats"] == ["generic", "paper", "chat"]
