"""REPRO-1 / R1a — NATIVE eval-case corpus import: rows that already ARE eval cases
(the product's own corpus schema: ``case_id`` + ``artifacts[0].content`` + a transcript/context)
import VERBATIM — no JUTE template, no LM, no :3031 mapper.

The gap this closes: a by-construction corpus JSONL (the judge-vs-floor research corpus shape)
fell through to the paid, slow LM-gen path, which silently DROPPED every field the experiment
needs (the structured record the floor grounds against, the injection provenance). Importing the
product's OWN schema is not a transform problem — a verbatim pass-through preserves everything by
construction, at $0, with the mapper down.

$0/offline. Requires the [bff] extra.
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

_DOC = json.dumps(
    {"resourceType": "DocumentReference", "content": [{"attachment": {"data": "THE DRAFT NOTE"}}]}
)
_ROW_DEFECT = {
    "case_id": "cv_001_bait",
    "transcript": "Doctor: what brings you in?\n\nPatient: my memory.",
    "artifacts": [{"type": "fhir_document_reference", "content": _DOC}],
    "patient_profile": {"conditions": ["Dementia", "Hypertensive disorder"]},
    "expected_compliance_verdict": "reject",
    "expected_safety_flags": ["FABRICATED_HISTORY"],
    "injection_recipes": [{"defect_type": "history_fabrication"}],
    "pinned": {"generator_version": "bench/0.1.0"},
}
_ROW_CLEAN = {
    "case_id": "cv_002_clean",
    "transcript": "Doctor: hello.\n\nPatient: hi.",
    "artifacts": [{"type": "fhir_document_reference", "content": _DOC}],
    "patient_profile": {"conditions": ["Asthma"]},
    "expected_compliance_verdict": "approve",
    "expected_safety_flags": [],
}
_ROWS = [_ROW_DEFECT, _ROW_CLEAN]


class _NeverConstructed:
    """The mapper client must NEVER be constructed on the native path."""

    def __init__(self, *_a, **_k):
        raise AssertionError("native corpus import must not touch the JUTE mapper")


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


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", _NeverConstructed)
    from lithrim_bench.harness import workspace as ws_mod

    ws = SimpleNamespace(
        name="native_test", pack="_core",
        out_dir=tmp_path / "ws" / "out",
        collections_db=tmp_path / "ws" / "collections.sqlite",
        config_db=tmp_path / "ws" / "config.sqlite",
        ontology_dir=tmp_path / "ws" / "ontology",
        dir=tmp_path / "ws",
    )
    monkeypatch.setattr(ws_mod, "get_active_workspace", lambda *a, **k: ws)
    return _real_ctx(tmp_path), ws


# ── the matcher ────────────────────────────────────────────────────────────────


def test_native_matcher_matches_a_bare_list_and_the_rows_wrapper():
    assert bff._native_eval_rows(_ROWS) == _ROWS
    assert bff._native_eval_rows({"rows": _ROWS}) == _ROWS  # the JSONL front-door decode shape


@pytest.mark.parametrize(
    "sample",
    [
        pytest.param([{**_ROW_CLEAN, "case_id": ""}], id="falsy-case-id"),
        pytest.param([{k: v for k, v in _ROW_CLEAN.items() if k != "case_id"}], id="no-case-id"),
        pytest.param([{k: v for k, v in _ROW_CLEAN.items() if k != "artifacts"}], id="no-artifacts"),
        pytest.param([{**_ROW_CLEAN, "artifacts": []}], id="empty-artifacts"),
        pytest.param([{**_ROW_CLEAN, "artifacts": [{"type": "x", "content": ""}]}], id="empty-content"),
        pytest.param(
            [{k: v for k, v in _ROW_CLEAN.items() if k != "transcript"}], id="no-source"
        ),
        pytest.param([_ROW_CLEAN, 42], id="non-dict-entry"),
        pytest.param([], id="empty-list"),
        pytest.param("not rows", id="non-collection"),
        # the OTHER known shapes must stay on their own paths (curated templates):
        pytest.param(
            {"runs": [{"id": "r1", "messages": [{"content": "a"}], "final": {"content": "b"}}]},
            id="agent-trace-shape",
        ),
        pytest.param(
            {"rows": [{"id": "r1", "note": "n", "transcript": "t"}]}, id="flat-notes-shape"
        ),
    ],
)
def test_native_matcher_is_conservative(sample):
    assert bff._native_eval_rows(sample) is None


# ── verbatim import, mapper never touched ─────────────────────────────────────


def test_native_import_is_verbatim_and_mapper_free(env):
    ctx, ws = env
    res = ctx.ingest_cases(json_dump=json.dumps(_ROWS), agent="ws0_default")
    assert res["count"] == 2
    assert res["native"] is True
    assert res["labeled"] == 2  # both rows carry labels ([] IS a label)
    by_id = {c["case_id"]: c for c in res["cases"]}
    got = by_id["cv_001_bait"]
    # VERBATIM: the record, the nested artifact, the labels, and the provenance all survive.
    assert got["patient_profile"] == {"conditions": ["Dementia", "Hypertensive disorder"]}
    assert got["artifacts"] == _ROW_DEFECT["artifacts"]
    assert got["expected_safety_flags"] == ["FABRICATED_HISTORY"]
    assert got["injection_recipes"] == [{"defect_type": "history_fabrication"}]
    assert got["pinned"] == {"generator_version": "bench/0.1.0"}
    # the corpus landed
    corpus = ws.out_dir / "ingested_cases.jsonl"
    rows = [json.loads(x) for x in corpus.read_text().splitlines() if x.strip()]
    assert {r["case_id"] for r in rows} == {"cv_001_bait", "cv_002_clean"}
    assert next(r for r in rows if r["case_id"] == "cv_001_bait")["patient_profile"][
        "conditions"
    ] == ["Dementia", "Hypertensive disorder"]


def test_native_import_from_a_jsonl_chat_dump(env):
    """The chat path receives a raw STRING; a JSONL corpus (one case per line) must parse via the
    front-door decode fallback and then import natively."""
    ctx, _ws = env
    jsonl = "\n".join(json.dumps(r) for r in _ROWS)
    res = ctx.ingest_cases(json_dump=jsonl, agent="ws0_default")
    assert res["count"] == 2 and res["native"] is True


def test_native_import_writes_one_honest_audit_row(env, tmp_path):
    ctx, _ws = env
    ctx.ingest_cases(json_dump=json.dumps(_ROWS), agent="ws0_default")
    from lithrim_bench.harness.audit import AuditLog

    recs = AuditLog(db_path=tmp_path / "config.sqlite").query(target_type="corpus")
    assert len(recs) == 1
    why = json.dumps(recs[0].get("why") or {}).lower()
    assert "native" in why and "verbatim" in why and "2 cases" in why


def test_native_preview_returns_cases_without_writing(env):
    ctx, ws = env
    res = ctx.ingest_preview(raw="\n".join(json.dumps(r) for r in _ROWS), fmt="jsonl")
    assert res["preview"] is True and res["native"] is True and res["count"] == 2
    assert res["template"] is None  # nothing to approve — the rows already ARE cases
    assert not (ws.out_dir / "ingested_cases.jsonl").exists()  # preview writes nothing


def test_frontdoor_commit_accepts_a_templateless_native_approval(env):
    """The card approves with the preview's template — null for a native corpus. The commit
    endpoint must accept the absent template (the native path needs none), not 422."""
    from fastapi.testclient import TestClient

    ctx, ws = env
    client = TestClient(bff.app)
    resp = client.post(
        "/v1/cases/ingest/commit",
        json={"raw": "\n".join(json.dumps(r) for r in _ROWS), "fmt": "jsonl",
              "agent": "ws0_default", "approved_template": None},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 2 and body["native"] is True
    assert (ws.out_dir / "ingested_cases.jsonl").exists()
