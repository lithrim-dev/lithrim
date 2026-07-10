"""Stage 0 (CE-INGEST-RESILIENT-1): the REUSE lookup is an OPTIMIZATION, never a requirement.

``_ingest_cases`` path (2) checks for a pinned ``ingest-{agent}`` transform via
``client.find_mapping_by_title`` (which lists the mapper's mappings). The docstring at the call
site promises "a client that can't list mappings simply can't reuse → falls through to generate",
but the bare ``_find(...)`` call did NOT honor it: a 500 from ``GET /mappings`` (e.g. a row with
non-JSON ``content`` poisoning the mapper's list) PROPAGATED and killed the whole ingest.

This is exactly the failure that bit the live MTS walkthrough (a polluted smoke mapping 500'd the
reuse-check). A fresh user's first ingest should NEVER fail because the mapper's list endpoint
hiccups — reuse is a $0 fast path, and its absence just means "pay the LM-gen cost once".

RED at parent: ``find_mapping_by_title`` raising → ``ingest_cases`` raises (the 500 propagates).
GREEN: the reuse attempt is trapped → falls through to LM-gen → cases land, pinned, ``reused`` False.

$0/offline: the LM/:3031 surface is mocked exactly like ``test_ingest_newsource.py``. Requires the
``[bff]`` extra (fastapi); pack-independent.
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

GH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "github_newsource_sample.json"


@pytest.fixture
def github_dump() -> str:
    return GH_FIXTURE.read_text()


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


def _github_records(dump: dict) -> list[dict]:
    issues = {i["number"]: i for i in dump["issues"]}
    out: list[dict] = []
    for cm in dump["comments"]:
        issue = issues.get(cm["issue_number"]) or {}
        out.append(
            {
                "case_id": f"gh-{cm['id']}",
                "issue_number": cm["issue_number"],
                "scene_title": issue.get("title"),
                "source": "github",
                "response": cm["body"],
            }
        )
    return out


def _to_envelope(records: list[dict]) -> list[dict]:
    from lithrim_bench.verification.jute_extractor import _to_envelope as _env

    return [_env(r) for r in records]


def test_reuse_lookup_500_falls_through_to_lm_gen(tmp_path, monkeypatch, github_dump):
    """A mapper whose ``find_mapping_by_title`` RAISES (the GET /mappings 500) must NOT fail the
    ingest — the reuse attempt is trapped and LM-gen runs. Cases land, freshly pinned, NOT reused.

    Drives the resilience bound: dropping the try/except around the reuse lookup turns this RED
    (the RuntimeError from ``find_mapping_by_title`` propagates out of ``ingest_cases``)."""
    bon_calls = {"n": 0}

    def fake_bon(make_gen, rules, sample, n=3):
        bon_calls["n"] += 1  # MUST be called — we fell through to generation
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        records = _github_records(json.loads(sample) if isinstance(sample, str) else sample)
        return {
            "accepted": True,
            "count": len(records),
            "expected_count": expected_count,
            "nulls": 0,
            "cases": _to_envelope(records),
        }

    class FakeJuteRaising:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def find_mapping_by_title(self, _title):
            # the live failure: GET /mappings 500s (a poisoned row) → the client raises
            raise RuntimeError("500 Server Error: list_mappings failed (JsonParseException)")

        def persist_or_update(self, *_a, **_k):
            return {"id": 777}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJuteRaising)
    monkeypatch.setattr(bff, "_build_authoring_lm", lambda: object())
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(
        json_dump=github_dump,
        extraction_rules="one case per `comments`",
        expected_count=6,
    )
    assert out["count"] == 6
    assert out["reused"] is False  # the reuse lookup failed → we generated
    assert out["mapping_id"] == 777  # freshly pinned, not the (unreachable) pinned id
    assert bon_calls["n"] == 1  # LM-gen ran — the fall-through happened
