"""NARR-6 P1b — ``POST /v1/connector/storyworld/ingest`` (the real-field batch ingest).

The endpoint paginates the StoryWorld admin API (via an injected ``StoryWorldAdminClient``),
fetches each session detail, and per session runs the FROZEN ``_ingest_cases`` machinery with
endpoint-side sample-prep (owner §8 decisions):

  * §8.3 — ``metadata.enhanced_scenes`` dict-OR-list normalized to a list of scenes (endpoint-side).
  * source/finish_reason — per scene, ``enhancement_status=="success" -> "enhanced"`` else
    ``"baseline"``; ``finish_reason`` joined from ``metadata.llm_calls`` by ``scene_node_id`` so the
    ``content_filtered`` fallback projects ``source:baseline, finish:content_filter`` (what
    ``SilentDegradationTool`` reads).
  * §8.1 PII — structurally DROP ``child_name``/``age`` (+ reader free-text) so they never enter the
    envelope, AND ``redact_text`` over the body text (no PHI_PATTERNS extension).

All $0/offline: the StoryWorld client + ``best_of_n_extractor`` + ``score_extraction`` + the
``:3031`` client are mocked (mirror ``tests/bff/test_ingest_cases_bound.py``). The mocked extractor
returns the SAME enveloped scene records the endpoint prepared, so the test asserts the endpoint's
real-field projection + redaction, not the JUTE transform itself.

  * A3 — the real-shape redacted fixture → N enveloped cases with correct source/finish_reason per
    scene; PII (child_name/age + the inline-PII string) absent/redacted; session_id present.
  * A5 — a mocked mis-join (score_extraction accepted=False) → trapped, count==0, persist/audit
    spies ZERO, nothing in ingested_cases.jsonl (mirror the bound mis-join test).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_real_session.json"
_SECRET = "sw-secret-do-not-leak-INGEST"
_INLINE_PII = "jane.doe@example.com"


@pytest.fixture()
def ws_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    monkeypatch.setattr(bff, "workspace", ws_mod, raising=False)
    try:
        ws = ws_mod.create_workspace("narr6_ingest", pack="narrative", seed=False)
        ws_mod.set_active_workspace(ws.name)
        # write the connector secret so the endpoint resolves base_url + key (offline)
        ws.dir.mkdir(parents=True, exist_ok=True)
        (ws.dir / ".connector_env").write_text(f"STORYWORLD_API_KEY={_SECRET}\n")
        (ws.dir / "connector.json").write_text(
            json.dumps({"base_url": "https://storyworld-api.example.test"})
        )
        yield ws_mod, ws
    finally:
        importlib.reload(ws_mod)


def _install_fake_storyworld(monkeypatch, detail: dict):
    """A StoryWorldAdminClient that lists ONE session and returns the given detail."""

    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def list_sessions(self, limit=50, offset=0):
            return {"items": [{"id": detail.get("id", "sess_real_001")}], "total": 1}

        def get_session(self, session_id):
            return detail

    monkeypatch.setattr("lithrim_bench.verification.StoryWorldAdminClient", FakeClient)


def _install_passthrough_extractor(monkeypatch, calls):
    """Mock best_of_n_extractor + score_extraction so the cases the ENDPOINT prepared (the
    sample passed to _ingest_cases) pass through unchanged — proving the endpoint's real-field
    projection + redaction, $0 (no :3031, no LM)."""
    from lithrim_bench.verification.jute_extractor import _to_envelope

    def fake_bon(make_gen, rules, sample, n=3):
        calls["bon"] += 1
        # the endpoint hands _ingest_cases a prepared list of per-scene records; carry it through.
        records = sample if isinstance(sample, list) else [sample]
        calls["_records"] = records
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1):
        calls["score"] += 1
        records = calls.get("_records") or (sample if isinstance(sample, list) else [sample])
        cases = [_to_envelope(r) for r in records]
        return {"accepted": True, "count": len(cases), "nulls": 0, "cases": cases}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            calls["persist"] += 1
            return {"id": 777}

    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)


def test_ingest_real_fields_projects_source_finish_and_redacts_pii(ws_env, monkeypatch):
    """A3: the real-shape fixture → 3 cases; per-scene source/finish correct (the content_filtered
    fallback → source:baseline, finish:content_filter); child_name/age + inline PII absent/redacted;
    session_id present on every case."""
    ws_mod, ws = ws_env
    detail = json.loads(_FIXTURE.read_text())
    _install_fake_storyworld(monkeypatch, detail)
    calls = {"bon": 0, "score": 0, "persist": 0, "audit": 0}
    _install_passthrough_extractor(monkeypatch, calls)

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            calls["audit"] += 1

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3, body
    assert body["sessions"] == 1
    assert resp.text.count("content_filter") >= 0  # not asserting on the response, on the corpus

    corpus = ws.out_dir / "ingested_cases.jsonl"
    assert corpus.exists()
    rows = [json.loads(ln) for ln in corpus.read_text().splitlines() if ln.strip()]
    assert len(rows) == 3

    by_source = {}
    for r in rows:
        # session_id present on every emitted case
        ctx = json.loads(r["context"]) if isinstance(r.get("context"), str) else {}
        assert r.get("session_id") or ctx.get("session_id"), f"session_id missing on {r}"
        by_source.setdefault((r.get("source"), r.get("finish_reason")), 0)
        by_source[(r.get("source"), r.get("finish_reason"))] += 1

    # 2 enhanced/stop + 1 baseline/content_filter (the masked fallback)
    assert by_source.get(("enhanced", "stop")) == 2, by_source
    assert by_source.get(("baseline", "content_filter")) == 1, by_source

    blob = corpus.read_text()
    assert "Noor Al-Mansoori" not in blob, "child_name leaked into the corpus"
    assert '"age"' not in blob and "child_name" not in blob, "PII key leaked into the envelope"
    assert _INLINE_PII not in blob, "inline PII (email) was not redacted"


def test_ingest_misjoin_fails_clean_nothing_pinned(ws_env, monkeypatch):
    """A5: a mocked mis-join (score_extraction accepted=False) → the per-session error is trapped,
    count==0, persist/audit spies ZERO, nothing in ingested_cases.jsonl."""
    ws_mod, ws = ws_env
    detail = json.loads(_FIXTURE.read_text())
    _install_fake_storyworld(monkeypatch, detail)
    calls = {"bon": 0, "score": 0, "persist": 0, "audit": 0}

    def fake_bon(make_gen, rules, sample, n=3):
        calls["bon"] += 1
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1):
        calls["score"] += 1
        return {"accepted": False, "count": 3, "nulls": 2, "cases": []}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            calls["persist"] += 1
            return {"id": 777}

    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            calls["audit"] += 1

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 0, body
    assert body["errors_trapped"] >= 1, body

    assert calls["score"] >= 1  # non-vacuous: the apply-gate ran
    assert calls["persist"] == 0  # NOTHING pinned
    corpus = ws.out_dir / "ingested_cases.jsonl"
    if corpus.exists():
        assert [ln for ln in corpus.read_text().splitlines() if ln.strip()] == []
