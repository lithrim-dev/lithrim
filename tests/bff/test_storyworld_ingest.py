"""NARR-6c — ``POST /v1/connector/storyworld/ingest`` (deterministic direct-write).

The connector ingest no longer generates a JUTE transform via DSPy. ``_prepare_storyworld_
session`` already produces correct §4.1-shaped per-scene records deterministically (source/
finish_reason joined, §8.1 PII dropped+redacted); the endpoint now maps each record through
the FROZEN ``jute_extractor._to_envelope`` and writes directly. No LM, no ``:3031``, no
generation — $0, deterministic, instant. (NARR-6b's per-session ``ctx.ingest_cases`` +
``dspy.context`` are SUPERSEDED: the connector no longer drives the extractor.)

All $0/offline: only the ``StoryWorldAdminClient`` is mocked (it would otherwise hit the live
admin API). The extractor / ``:3031`` / LM are NOT mocked — they are no longer on the connector
path. ``_ingest_cases`` (the CHAT ingest path) stays byte-identical and is untouched here.

  * A3 — the real-shape redacted fixture → N enveloped cases with correct source/finish_reason
    per scene (the content_filtered scene → source:baseline, finish:content_filter); PII
    (child_name/age + the inline-PII string) absent/redacted; session_id present on every case.
  * A5 — a malformed / non-enhanced session yields 0 records and is skipped CLEANLY: count==0,
    audit fires (the batch summary), nothing written to ingested_cases.jsonl.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_synthetic_session.json"
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
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _install_fake_storyworld(monkeypatch, detail):
    """A StoryWorldAdminClient that lists ONE session and returns the given detail (or, if
    ``detail`` is None, lists ZERO sessions). The live admin API is the ONLY thing mocked."""

    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def list_sessions(self, limit=50, offset=0):
            if detail is None:
                return {"items": [], "total": 0}
            return {"items": [{"id": detail.get("id", "sess_real_001")}], "total": 1}

        def get_session(self, session_id):
            return detail

    monkeypatch.setattr("lithrim_bench.verification.StoryWorldAdminClient", FakeClient)


def test_ingest_llm_calls_projects_finish_model_and_redacts_pii(ws_env, monkeypatch):
    """A3 (CONN-2): the live-shape fixture → one case per ``llm_calls`` entry DETERMINISTICALLY
    (no LM / :3031 / generation). The graded artifact is the call's ``response_preview``; the
    ``finish_reason`` (incl. ``content_filter``) + ``model`` ride the envelope; ``purpose`` maps to
    ``source``. child_name/age (top-level PII) are structurally dropped + inline PII in a preview is
    redacted; session_id present on every case."""
    ws_mod, ws = ws_env
    detail = json.loads(_FIXTURE.read_text())
    _install_fake_storyworld(monkeypatch, detail)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3, body  # 3 llm_calls
    assert body["sessions"] == 1, body
    assert body["errors_trapped"] == 0, body

    corpus = ws.out_dir / "ingested_cases.jsonl"
    assert corpus.exists()
    rows = [json.loads(ln) for ln in corpus.read_text().splitlines() if ln.strip()]
    assert len(rows) == 3

    finishes = {}
    for r in rows:
        assert r.get("session_id") == "sess_real_001", f"session_id missing/wrong on {r}"
        # D1 gradeability: §4.1 envelope complete + unlabeled-by-construction
        assert r["artifacts"][0]["content"], "empty artifact content"  # the response
        assert r["expected_safety_flags"] == []
        assert r["injection_recipe"] is None
        # the call's model + purpose(-as-source) ride the envelope
        assert r.get("model") == "gpt-5", r
        assert r.get("source") == "enhancement", r
        # the prompt (the input that produced the response) rides the case context — the I/O pair
        ctx = json.loads(r["context"])
        assert ctx.get("prompt"), f"prompt not carried into context on {r['case_id']}"
        finishes[r.get("finish_reason")] = finishes.get(r.get("finish_reason"), 0) + 1

    # the content_filter signal survives the per-call projection (the gold safety signal)
    assert finishes.get("stop") == 2, finishes
    assert finishes.get("content_filter") == 1, finishes

    # the first call's prompt is carried (recognizable phrase) but its inline PII is redacted
    ctx0 = json.loads(rows[0]["context"])["prompt"]
    assert "ranger-arrival" in ctx0, ctx0

    blob = corpus.read_text()
    assert "Noor Al-Mansoori" not in blob, "child_name leaked into the corpus"
    assert '"age"' not in blob and "child_name" not in blob, "PII key leaked into the envelope"
    # the email appears in BOTH a prompt and a response_preview — redacted in both (prompt + artifact)
    assert _INLINE_PII not in blob, "inline PII (email) in prompt/response_preview was not redacted"


def test_ingest_non_enhanced_session_skips_clean(ws_env, monkeypatch):
    """A5 (reframed): a session with no enhanced_scenes yields 0 records and is skipped CLEANLY —
    count==0, the batch-summary audit still fires (one batch audit, no per-session audits), and
    nothing is written to ingested_cases.jsonl. There is no :3031 gate on the connector path."""
    ws_mod, ws = ws_env
    detail = {"id": "sess_empty", "story_id": "x", "metadata": {"llm_calls": []}}
    _install_fake_storyworld(monkeypatch, detail)

    audits = {"n": 0, "actions": []}

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, rec, *_a, **_k):
            audits["n"] += 1
            audits["actions"].append(getattr(rec, "action", None))

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)
    client = TestClient(bff.app)

    resp = client.post("/v1/connector/storyworld/ingest", json={"limit": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 0, body
    assert body["sessions"] == 0, body  # an empty-scene session contributes no records

    # exactly the ONE batch-summary audit (deterministic direct-write — no per-session ingest audits)
    assert audits["n"] == 1, audits
    assert audits["actions"] == ["ingest_batch"], audits

    corpus = ws.out_dir / "ingested_cases.jsonl"
    if corpus.exists():
        assert [ln for ln in corpus.read_text().splitlines() if ln.strip()] == []
