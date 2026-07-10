"""S-BS-NARR2-2 — the bound ``_ingest_cases`` mis-join → no-pin ORDERING, automated.

NARR-2 verified the no-pin error path by code-read + a HANDLER-layer stub (the bound op
raised, the handler surfaced it). The seam this closes: nothing drove the REAL bound
closure (``apps/bff/app.py`` ``_build_tool_context._ingest_cases``) to assert that on a
mis-join / short-or-null apply NOTHING is pinned or audited — ``client.persist_or_update``
and ``AuditLog.record`` are each called ZERO times, because the structural output-invariant
gates BEFORE the pin / corpus-upsert / audit block.

Trust-model note (SPEC_NARRATIVE_EVAL A4): the extractor is INGESTION-only — it builds +
pins a ``jute_transform`` via ``EtlpJuteClient`` directly and NEVER enters the grade-time
floor. These tests mock the verification surface so they run $0/offline (no :3031, no LM):
the two failure paths (extractor non-convergence; apply-time invariant fail) assert the
no-pin/no-audit ordering, and a success companion proves the SAME spies fire once each — so
the zero-counts are real, not dead spies (non-vacuous in both directions).

Requires the ``[bff]`` extra (fastapi) — ``import app`` is the BFF surface; skipped cleanly
on a bare core so the default suite stays green. Pack-independent (no healthcare reads).
"""

from __future__ import annotations

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

_SAMPLE = '{"resource": {"id": "x"}}'


def _real_ctx(tmp_path: Path):
    """A ToolContext carrying the REAL bound ``_ingest_cases`` closure over tmp paths."""
    return bff._build_tool_context(
        req_agent="ws0_default",
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _patch_audit(monkeypatch, calls):
    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            calls["audit"] += 1

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)


def _patch_client(monkeypatch, calls, *, pin_id=999):
    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            calls["persist"] += 1
            return {"id": pin_id}

    # the closure resolves these off the package at call time (``from lithrim_bench.verification
    # import ...``), so patching the package attribute is what the bound fn actually sees.
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeClient)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")


def _patch_extractor(monkeypatch, calls, *, accepted, score):
    def fake_bon(make_gen, rules, sample, n=3):  # never calls make_gen → no :3031 / no LM
        calls["bon"] += 1
        return SimpleNamespace(accepted=accepted, jute_transform="t" if accepted else "")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        calls["score"] += 1
        return score

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)


def _inject_authoring_lm(monkeypatch):
    """INGEST-LM-1: stub ``_build_authoring_lm`` so the ingest generation path has an LM without
    a configured provider (unconfigured in bare CE → an actionable RuntimeError BEFORE the
    extractor runs). The extractor (``best_of_n_extractor``) is mocked, so the stub is never
    invoked; patching the helper (not the global ``dspy.settings.lm``) keeps downstream dspy
    state untouched."""
    monkeypatch.setattr(bff, "_build_authoring_lm", lambda: object())


def test_real_ingest_pins_nothing_on_null_apply(tmp_path, monkeypatch):
    """The seam: the extractor converges but the apply-time invariant FAILS (short/null
    apply) → ``RuntimeError`` 'nothing pinned'; the gate ran (``score_extraction`` called)
    yet ``persist_or_update`` + ``AuditLog.record`` are each called ZERO times."""
    calls = {"persist": 0, "audit": 0, "score": 0, "bon": 0}
    _patch_audit(monkeypatch, calls)
    _inject_authoring_lm(monkeypatch)
    _patch_client(monkeypatch, calls)
    _patch_extractor(
        monkeypatch,
        calls,
        accepted=True,
        score={"accepted": False, "count": 3, "nulls": 2, "cases": []},
    )
    ctx = _real_ctx(tmp_path)

    with pytest.raises(RuntimeError, match="nothing pinned"):
        ctx.ingest_cases(_SAMPLE)

    assert calls["score"] == 1  # non-vacuous: the apply-gate actually ran
    assert calls["persist"] == 0  # NOTHING pinned
    assert calls["audit"] == 0  # NOTHING audited


def test_real_ingest_pins_nothing_when_extractor_does_not_converge(tmp_path, monkeypatch):
    """The other no-pin path: the extractor never converges (``accepted=False``) →
    ``RuntimeError`` 'nothing pinned' BEFORE the apply-gate, so ``score_extraction`` is
    never reached and nothing is pinned/audited (the ordering: convergence short-circuits
    first)."""
    calls = {"persist": 0, "audit": 0, "score": 0, "bon": 0}
    _patch_audit(monkeypatch, calls)
    _inject_authoring_lm(monkeypatch)
    _patch_client(monkeypatch, calls)
    _patch_extractor(
        monkeypatch,
        calls,
        accepted=False,
        score={"accepted": True, "count": 1, "nulls": 0, "cases": [{"case_id": "z"}]},
    )
    ctx = _real_ctx(tmp_path)

    with pytest.raises(RuntimeError, match="nothing pinned"):
        ctx.ingest_cases(_SAMPLE)

    assert calls["bon"] == 1  # the extractor ran
    assert calls["score"] == 0  # short-circuited BEFORE the apply-gate
    assert calls["persist"] == 0
    assert calls["audit"] == 0


def test_real_ingest_spies_fire_once_on_success(tmp_path, monkeypatch):
    """Non-vacuity companion: on a clean converge+apply the SAME spies fire EXACTLY once
    each (one pin, one audit) and the corpus JSONL is written — proving the zero-counts
    above are real, not dead spies."""
    calls = {"persist": 0, "audit": 0, "score": 0, "bon": 0}
    cases = [{"case_id": "a", "response": "x"}, {"case_id": "b", "response": "y"}]
    _patch_audit(monkeypatch, calls)
    _inject_authoring_lm(monkeypatch)
    _patch_client(monkeypatch, calls, pin_id=555)
    _patch_extractor(
        monkeypatch,
        calls,
        accepted=True,
        score={"accepted": True, "count": 2, "nulls": 0, "cases": cases},
    )
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(_SAMPLE)

    assert out["count"] == 2 and out["mapping_id"] == 555
    assert calls["persist"] == 1  # pinned exactly once
    assert calls["audit"] == 1  # audited exactly once
    corpus = ws_out / "ingested_cases.jsonl"
    assert corpus.exists()
    assert len([ln for ln in corpus.read_text().splitlines() if ln.strip()]) == 2
