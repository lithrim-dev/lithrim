"""NARR-6 A4 — a batch-ingested StoryWorld case is gradeable through the D1 bridge.

The loop NARR-6 productizes: a real-field batch ingest writes enveloped cases to
``ws.out_dir/ingested_cases.jsonl``, and those cases resolve via ``load_case(case_id)`` (the
S-BS-NARR2-1 / NARR-5 D1 workspace-corpus fallback) and grade end-to-end via ``grade_inprocess``
with an INJECTED predictor stage ($0, no Azure). This is the NARR-5 ``test_narrative_corpus_bridge``
pattern, but the corpus is written by driving the ACTUAL ``POST /v1/connector/storyworld/ingest``
endpoint (offline, mocked extractor + StoryWorld client) — so the assertion is that the ingest
endpoint's output reaches the grade path, not just a hand-written envelope.

$0/offline: the StoryWorld client + ``:3031`` + the extractor + the predictors are all mocked.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")
pytest.importorskip("dspy")
pytest.importorskip("openai")

from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_synthetic_session.json"
PACK = "narrative"


@pytest.fixture()
def ws_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    try:
        ws = ws_mod.create_workspace("narr6_bridge", pack=PACK, seed=False)
        ws_mod.set_active_workspace(ws.name)
        ws.dir.mkdir(parents=True, exist_ok=True)
        (ws.dir / ".connector_env").write_text("STORYWORLD_API_KEY=k\n")
        (ws.dir / "connector.json").write_text(
            json.dumps({"base_url": "https://storyworld-api.example.test"})
        )
        yield ws_mod, ws
    finally:
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _mock_ingest_surface(monkeypatch):
    from lithrim_bench.verification.jute_extractor import _to_envelope

    detail = json.loads(_FIXTURE.read_text())

    class FakeStoryWorld:
        def __init__(self, *_a, **_k):
            pass

        def list_sessions(self, limit=50, offset=0):
            return {"items": [{"id": detail["id"]}], "total": 1}

        def get_session(self, session_id):
            return detail

    monkeypatch.setattr("lithrim_bench.verification.StoryWorldAdminClient", FakeStoryWorld)

    state: dict = {}

    def fake_bon(make_gen, rules, sample, n=3):
        state["records"] = sample if isinstance(sample, list) else [sample]
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        records = state.get("records") or (sample if isinstance(sample, list) else [sample])
        return {
            "accepted": True,
            "count": len(records),
            "nulls": 0,
            "cases": [_to_envelope(r) for r in records],
        }

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            return {"id": 777}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)


def _approve(*, role_key_questions="", **_kw):
    return {"decision": "approve", "findings": []}


def test_batch_ingested_case_resolves_and_grades_via_load_case(ws_env, monkeypatch):
    """RED at parent: the ingest endpoint 404s, so no batch case lands. GREEN: the endpoint
    writes the corpus, ``load_case`` resolves a batch case, and ``grade_inprocess`` grades it."""
    ws_mod, ws = ws_env
    _mock_ingest_surface(monkeypatch)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 3

    corpus = ws.out_dir / "ingested_cases.jsonl"
    rows = [json.loads(ln) for ln in corpus.read_text().splitlines() if ln.strip()]
    assert rows, "the ingest endpoint wrote no corpus rows"
    case_id = rows[0]["case_id"]
    assert case_id

    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.ontology import load_ontology
    from lithrim_bench.harness.pack import pack_ontology_path
    from lithrim_bench.harness.report import composite
    from lithrim_bench.picklist import load_case
    from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
    from lithrim_bench.runtime.council.judges_dspy import V2_ROLES

    case = load_case(case_id)
    assert case is not None, "the batch-ingested case did not resolve via load_case (the D1 bridge)"
    assert case["case_id"] == case_id

    ont = load_ontology(pack_ontology_path())
    stage = build_authored_semantic_stage(
        ontology=ont, assignments={}, predictors={r: _approve for r in V2_ROLES}
    )
    rc = grade_inprocess(case, semantic_stage=stage)
    comp = composite(ground(rc, case, ontology=ont))
    assert comp["verdict"] in {"approve", "needs_review", "reject"}
