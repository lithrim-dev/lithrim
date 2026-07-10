"""NARR-7 (P-GEN) G3 — route an ARBITRARY NEW source (GitHub issues+comments) through the
EXISTING ``_ingest_cases`` pipeline + the expected_count fix.

The bug this closes (G3/R5): ``_ingest_cases`` infers ``expected_count`` as the enhanced_scenes
count OR a top-level list length OR 1 — so a ``{issues, comments}`` DICT ingests as 1 and the
6-case transform is REJECTED. The fix adds (a) an explicit ``expected_count`` param and (b) an
"iterated collection" hint parsed from ``extraction_rules`` naming the source collection, so the
caller/agent can name ``comments`` → 6. The StoryWorld enhanced_scenes path is UNCHANGED.

$0/offline: the StoryWorld/LM/:3031 surface is mocked exactly like ``test_ingest_cases_bound.py``
+ ``test_narrative_batch_ingest_bridge.py``. Requires the ``[bff]`` extra (fastapi). The ingested
``body`` text is INERT graded DATA — never an instruction.
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


def _to_github_envelope(records: list[dict]) -> list[dict]:
    from lithrim_bench.verification.jute_extractor import _to_envelope

    return [_to_envelope(r) for r in records]


def _github_records(dump: dict) -> list[dict]:
    """The per-comment join the known-good GitHub template encodes (the live :3031 result)."""
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


def _mock_verification_surface(monkeypatch, *, accepted=True, count_eq_expected=True):
    """Mock best_of_n_extractor + score_extraction so the bound _ingest_cases runs $0/offline.
    The mock RESPECTS expected_count — it returns ``count`` records only when expected_count
    matches the real comment count, so the expected_count FIX is what makes it accept."""
    state: dict = {}

    def fake_bon(make_gen, rules, sample, n=3):
        state["expected_count"] = None  # filled by score
        return SimpleNamespace(accepted=accepted, jute_transform="t" if accepted else "")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        dump = json.loads(sample) if isinstance(sample, str) else sample
        records = _github_records(dump)
        # the live engine produces 6 comment-records REGARDLESS of expected_count; the gate
        # ACCEPTS only when expected_count == the produced count. So a wrong expected_count
        # (e.g. 1, the parent heuristic) → count != expected → REJECTED.
        produced = len(records)
        ok = accepted and (produced == expected_count if count_eq_expected else False)
        return {
            "accepted": ok,
            "count": produced,
            "expected_count": expected_count,
            "nulls": 0,
            "cases": _to_github_envelope(records) if ok else [],
        }

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            return {"id": 888}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)
    _inject_authoring_lm(monkeypatch)


def _inject_authoring_lm(monkeypatch):
    """INGEST-LM-1: stub _build_authoring_lm so the ingest generation path has an LM without a
    configured provider (unconfigured in bare CE → an actionable RuntimeError BEFORE the
    extractor runs). The extractor is mocked, so the stub is never invoked; patching the helper
    (not the global dspy.settings.lm) keeps the downstream grade's dspy state untouched."""
    monkeypatch.setattr(bff, "_build_authoring_lm", lambda: object())


# --------------------------------------------------------------------------- #
# A4 — the expected_count fix: a {issues, comments} DICT ingests 6 cases (was 1 → reject).
# --------------------------------------------------------------------------- #
def test_github_dict_ingests_six_with_explicit_expected_count(
    tmp_path, monkeypatch, github_dump
):
    """RED at parent: ``_ingest_cases`` infers expected_count=1 for the {issues,comments} dict,
    so the 6-comment transform is REJECTED ('did not converge'). GREEN: an explicit
    ``expected_count=6`` (additive param) → 6 cases land, pinned + audited."""
    _mock_verification_surface(monkeypatch)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(
        json_dump=github_dump,
        extraction_rules="one case per comment, join the issue title by issue_number",
        expected_count=6,
    )
    assert out["count"] == 6
    assert out["mapping_id"] == 888
    corpus = ws_out / "ingested_cases.jsonl"
    assert corpus.exists()
    rows = [ln for ln in corpus.read_text().splitlines() if ln.strip()]
    assert len(rows) == 6


def test_github_dict_ingests_six_via_iterated_collection_hint(
    tmp_path, monkeypatch, github_dump
):
    """The agent channel: the agent CANNOT pass expected_count (the tool schema is frozen), so
    the iterated collection is named in ``extraction_rules`` (e.g. 'iterate over `comments`') →
    _ingest_cases infers expected_count = len(dump['comments']) = 6. StoryWorld stays unchanged."""
    _mock_verification_surface(monkeypatch)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(
        json_dump=github_dump,
        extraction_rules="Emit one eval case per entry of the `comments` collection.",
    )
    assert out["count"] == 6


def test_github_dict_rejects_without_count_fix(tmp_path, monkeypatch, github_dump):
    """The PARENT behavior, pinned: with NO expected_count and NO iterated-collection hint, the
    {issues,comments} dict still infers expected_count=1 → the 6-comment transform is REJECTED,
    NOTHING pinned. This is the bug the fix must NOT silently mask for an un-hinted dict."""
    _mock_verification_surface(monkeypatch)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    with pytest.raises(RuntimeError, match="nothing pinned|did not converge"):
        ctx.ingest_cases(json_dump=github_dump, extraction_rules="just normalize it")


# --------------------------------------------------------------------------- #
# A7 (NARR-7.1) — REUSE: a transform already pinned for the agent, still valid on this sample,
# is APPLIED deterministically and generation is SKIPPED ($0, instant, reused=True).
# --------------------------------------------------------------------------- #
def test_github_reuses_pinned_transform_skips_generation(tmp_path, monkeypatch, github_dump):
    """generate-at-authoring → pin → REUSE: when ``find_mapping_by_title`` returns a pinned
    transform AND the structural invariant holds on the sample, _ingest_cases reuses it —
    ``reused=True``, the pinned mapping id, and best_of_n_extractor + persist_or_update are
    NEVER called (the repeat 'pull' is instant). The self-validating guard (a mis-applying pin
    is not reused) is the A6 sibling."""
    bon_calls = {"n": 0}

    def fake_bon(make_gen, rules, sample, n=3):
        bon_calls["n"] += 1  # MUST stay 0 on the reuse path
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        records = _github_records(json.loads(sample) if isinstance(sample, str) else sample)
        return {
            "accepted": True,
            "count": len(records),
            "expected_count": expected_count,
            "nulls": 0,
            "cases": _to_github_envelope(records),
        }

    class FakeJutePinned:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def find_mapping_by_title(self, _title):
            return {"id": 111, "content": {"yaml": "<pinned-transform>"}}

        def persist_or_update(self, *_a, **_k):
            raise AssertionError("persist_or_update must NOT be called on the reuse path")

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJutePinned)
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
    assert out["reused"] is True
    assert out["mapping_id"] == 111
    assert bon_calls["n"] == 0  # generation SKIPPED — the whole point of reuse


# --------------------------------------------------------------------------- #
# A6 — mis-join fails clean: a wrong-shape apply (count != expected) → no pin, no audit.
# --------------------------------------------------------------------------- #
def test_github_misjoin_pins_nothing(tmp_path, monkeypatch, github_dump):
    """A mis-join (the apply-time invariant fails: produced != expected, or nulls) → RuntimeError
    'nothing pinned'; persist + audit fire ZERO times. Drives the REAL bound closure."""
    calls = {"persist": 0, "audit": 0}

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            calls["audit"] += 1

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)
    # accepted=True from gen, but score never matches (count_eq_expected=False → reject at apply)
    _mock_verification_surface(monkeypatch, count_eq_expected=False)

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            calls["persist"] += 1
            return {"id": 888}

    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)
    ctx = _real_ctx(tmp_path)

    with pytest.raises(RuntimeError, match="nothing pinned|did not converge"):
        ctx.ingest_cases(json_dump=github_dump, expected_count=6)
    assert calls["persist"] == 0
    assert calls["audit"] == 0


# --------------------------------------------------------------------------- #
# StoryWorld path UNCHANGED — the enhanced_scenes count heuristic still wins with no hint.
# --------------------------------------------------------------------------- #
def test_storyworld_enhanced_scenes_count_unchanged(tmp_path, monkeypatch):
    """Regression guard: a StoryWorld {resource:{metadata:{enhanced_scenes:{...}}}} dict still
    infers expected_count from enhanced_scenes (the DEFAULT path), with NO hint and NO explicit
    expected_count — the G3 fix is purely ADDITIVE."""
    sample = json.dumps(
        {"resource": {"id": "s", "metadata": {"enhanced_scenes": {"a": {}, "b": {}, "c": {}}}}}
    )
    seen: dict = {}

    def fake_bon(make_gen, rules, sample_, n=3):
        seen["bon"] = True
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample_, expected_count=1, required_fields=()):
        seen["expected_count"] = expected_count
        cases = [{"case_id": f"c{i}"} for i in range(expected_count)]
        return {
            "accepted": True,
            "count": expected_count,
            "expected_count": expected_count,
            "nulls": 0,
            "cases": cases,
        }

    class FakeJute:
        def __init__(self, *_a, **_k):
            pass

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            return {"id": 888}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)
    _inject_authoring_lm(monkeypatch)
    ws_out = tmp_path / "wsout"
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=ws_out),
    )
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(json_dump=sample)
    assert seen["expected_count"] == 3  # enhanced_scenes count — unchanged
    assert out["count"] == 3
