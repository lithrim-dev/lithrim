"""Front door, Stage 1b (CE-INGEST-FRONTDOOR-1): the preview -> commit split over the existing
JUTE engine.

The chat path (``_ingest_cases`` with its defaults) generates + pins + upserts atomically. The
first-class front door wants a human in the loop: PREVIEW (decode + select/gen a template + apply
to the data, show the extracted cases, pin NOTHING, write NOTHING) -> the human validates the
field mapping -> COMMIT (pin the approved template + upsert the corpus, no LM gen).

These prove:
  * preview pins nothing + writes no corpus, and surfaces fmt/columns/sample_cases (CSV here);
  * commit with an approved template pins + upserts and SKIPS generation ($0, deterministic);
  * the existing chat ``ingest_cases`` defaults are byte-identical (pin + upsert still happen).

$0/offline: the LM/:3031 surface is mocked exactly like ``test_ingest_newsource.py``. Runs under
the council interpreter (dspy present) — the preview gen path imports dspy like the chat path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lithrim_bench.harness.audit import Actor

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_CSV = "case_id,note,dialogue\nc1,a note,a dialogue\nc2,another note,more dialogue\n"


def _real_ctx(tmp_path: Path):
    return bff._build_tool_context(
        req_agent="ws0_default",
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _csv_cases(sample) -> list[dict]:
    """The per-row extraction the template encodes: one case per `rows` entry."""
    rows = sample["rows"] if isinstance(sample, dict) else sample
    out = []
    for r in rows:
        out.append(
            {"case_id": r["case_id"], "response": r["note"], "context": r["dialogue"]}
        )
    return out


def _mock_engine(monkeypatch, *, calls):
    """Mock best_of_n_extractor + score_extraction + the client. score returns one case per CSV
    row; the client records pin calls; generation records gen calls."""

    def fake_bon(make_gen, rules, sample, n=3):
        calls["gen"] += 1
        return SimpleNamespace(accepted=True, jute_transform="<generated-template>")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        s = json.loads(sample) if isinstance(sample, str) else sample
        cases = _csv_cases(s)
        return {"accepted": True, "count": len(cases), "expected_count": expected_count,
                "nulls": 0, "cases": cases}

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def find_mapping_by_title(self, _t):
            return None  # nothing pinned yet → preview goes to gen

        def persist_or_update(self, *_a, **_k):
            calls["pin"] += 1
            return {"id": 555}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)
    monkeypatch.setattr(bff, "_build_authoring_lm", lambda: object())
    # each test sets its own get_active_workspace (it needs the test's tmp_path)


def test_preview_pins_nothing_and_writes_no_corpus(tmp_path, monkeypatch):
    calls = {"gen": 0, "pin": 0}
    _mock_engine(monkeypatch, calls=calls)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_preview(raw=_CSV, fmt="csv", filename="cases.csv")

    assert out["fmt"] == "csv"
    assert out["columns"] == ["case_id", "note", "dialogue"]
    assert out["count"] == 2
    assert [c["case_id"] for c in out["sample_cases"]] == ["c1", "c2"]
    assert out["template"] == "<generated-template>"
    assert calls["gen"] == 1  # preview DID generate the template
    assert calls["pin"] == 0  # ...but pinned NOTHING
    assert out.get("mapping_id") is None
    assert not (ws_out / "ingested_cases.jsonl").exists()  # wrote NO corpus


def test_commit_pins_and_upserts_without_generating(tmp_path, monkeypatch):
    calls = {"gen": 0, "pin": 0}
    _mock_engine(monkeypatch, calls=calls)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_commit(
        approved_template="<generated-template>", raw=_CSV, fmt="csv", filename="cases.csv"
    )

    assert out["count"] == 2
    assert out["mapping_id"] == 555  # pinned
    assert calls["pin"] == 1
    assert calls["gen"] == 0  # commit applies the APPROVED template — no LM gen
    corpus = ws_out / "ingested_cases.jsonl"
    assert corpus.exists()
    rows = [ln for ln in corpus.read_text().splitlines() if ln.strip()]
    assert len(rows) == 2


def test_chat_ingest_cases_defaults_still_pin_and_upsert(tmp_path, monkeypatch):
    """Regression: the chat tool path (json_dump, defaults) is byte-identical — still generates,
    pins, and writes the corpus. The preview/commit params are purely ADDITIVE."""
    calls = {"gen": 0, "pin": 0}
    _mock_engine(monkeypatch, calls=calls)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    dump = json.dumps({"rows": [
        {"case_id": "c1", "note": "n", "dialogue": "d"},
        {"case_id": "c2", "note": "n2", "dialogue": "d2"},
    ]})
    out = ctx.ingest_cases(json_dump=dump, extraction_rules="one case per `rows`", expected_count=2)

    assert out["count"] == 2
    assert calls["gen"] == 1 and calls["pin"] == 1
    assert (ws_out / "ingested_cases.jsonl").exists()


# ── the HTTP routes (POST /v1/cases/ingest/preview|commit) — route wiring, hermetic ───────────
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    seen: dict = {}

    class StubCtx:
        def ingest_preview(self, **kw):
            seen["preview"] = kw
            return {"fmt": "csv", "columns": ["a"], "count": 2, "template": "<t>",
                    "sample_cases": [{"case_id": "c1"}], "cases": [{"case_id": "c1"}]}

        def ingest_commit(self, **kw):
            seen["commit"] = kw
            return {"count": 2, "mapping_id": 9, "cases": []}

    monkeypatch.setattr(bff, "_build_tool_context", lambda *a, **k: StubCtx())
    monkeypatch.setattr(bff, "_resolve_chat_agent", lambda a, _db: a or "ws0_default")
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "c.db"
    c = TestClient(bff.app)
    c._seen = seen
    try:
        yield c
    finally:
        bff.app.dependency_overrides.clear()


def test_preview_endpoint_wires_fields_and_returns(client):
    res = client.post(
        "/v1/cases/ingest/preview",
        json={"raw": "a\n1\n", "fmt": "csv", "filename": "x.csv", "agent": "ws0_default"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["fmt"] == "csv" and body["count"] == 2 and body["template"] == "<t>"
    assert client._seen["preview"]["raw"] == "a\n1\n"
    assert client._seen["preview"]["fmt"] == "csv"


def test_commit_endpoint_wires_approved_template(client):
    res = client.post(
        "/v1/cases/ingest/commit",
        json={"approved_template": "<t>", "raw": "a\n1\n", "fmt": "csv"},
    )
    assert res.status_code == 200
    assert res.json()["mapping_id"] == 9
    assert client._seen["commit"]["approved_template"] == "<t>"


def test_preview_endpoint_bad_blob_is_422(client, monkeypatch):
    """A decode/convergence failure surfaces as a calm 422 with the reason, never a bare 500."""
    class BadCtx:
        def ingest_preview(self, **kw):
            raise ValueError("the uploaded data is empty")

    monkeypatch.setattr(bff, "_build_tool_context", lambda *a, **k: BadCtx())
    res = client.post("/v1/cases/ingest/preview", json={"raw": "   "})
    assert res.status_code == 422
    assert "empty" in res.json()["detail"]
