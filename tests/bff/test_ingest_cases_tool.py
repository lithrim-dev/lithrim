"""NARR-2 acceptance: the ingest_cases SDK-MCP tool (the 17th) — drop JSON → generate →
live-gate → PIN → audited corpus upsert, with deny-default + A-SAFE held.

The trust posture (mirrors add_grounding_contract): the handler calls the bound
ctx.ingest_cases(...) and SURFACES a structured error (invariant failed / :3031 down /
nothing pinned) exactly as add_grounding_contract_handler surfaces 404/422 — never
bypassed, never a paid run; on accept it emits a `corpus` focus part and returns the case
count. On the error path NOTHING is pinned/persisted/upserted (A3 negative).

Layers (by import weight, mirroring test_flag_crud.py):
  - STRUCTURAL / A-SAFE (plain core — agent package is SDK-free + fastapi-free): the 17-tool
    bound; ingest_cases carries NO paid knob; the S-BS-90 deny hook covers it (byte-frozen).
  - HANDLER (plain core, stub ctx): accept pins-once + corpus-focus part (A3); an invariant
    failure surfaces a structured error and pins NOTHING (A3 negative).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# the agent package is import-safe on the default core (SDK lazy; no fastapi at module level),
# so the STRUCTURAL + HANDLER layers run in BOTH suites (not only under [bff]).
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _deny_non_lithrim  # noqa: E402

# ── STRUCTURAL / A-SAFE (plain core — SDK-free) ──────────────────────────────────


def test_registry_adds_exactly_ingest_cases_and_deny_hook_frozen():
    """A5: _TOOL_SPECS grew by exactly one (16 → 17) and contains ingest_cases; NO tool
    carries a paid knob (the S-BS-81 guarantee generalized, non-vacuous over the full set);
    the A-SAFE deny hook passes ingest_cases (allowed) yet still DENIES a built-in (byte-
    frozen — the 17th tool is bounded for free)."""
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert len(names) == 24 and len(set(names)) == 24, names  # +PHASE2-WIRE create_judge +TOOL-AUTHOR-1 author_tool
    assert "ingest_cases" in names
    assert "record_meta_verdict" in names

    for _h, n, _d, schema in agent_tools._TOOL_SPECS:  # NON-VACUOUS: includes the new tool
        assert [k for k in agent_tools.PAID_KEYS if k in schema] == [], (n, schema)

    by_name = {n: schema for _h, n, _d, schema in agent_tools._TOOL_SPECS}
    assert "json" in by_name["ingest_cases"]  # the JSON dump to ingest
    assert "ingest_cases" in agent_tools.ToolContext.__dataclass_fields__

    def decision(out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    allow = asyncio.run(
        _deny_non_lithrim({"tool_name": "mcp__lithrim__ingest_cases"}, "t", {"signal": None})
    )
    assert decision(allow) is None  # no decision == allowed
    deny = asyncio.run(_deny_non_lithrim({"tool_name": "Bash"}, "t", {"signal": None}))
    assert decision(deny) == "deny"


# ── HANDLER (plain core, stub ctx) ───────────────────────────────────────────────


def _stub_ctx(*, ingest_cases=None):
    def _noop(*_a, **_k):
        return {"actor": {"id": "sme"}}

    return agent_tools.ToolContext(
        author_judge=_noop,
        get_judge=_noop,
        run_eval_replay=_noop,
        get_agent=_noop,
        author_flag=_noop,
        review_runs=_noop,
        run_eval_pack=_noop,
        assemble_agent=_noop,
        delete_judge=_noop,
        create_flag=_noop,
        delete_flag=_noop,
        put_grounding_contract=_noop,
        kb_context=_noop,
        ingest_cases=ingest_cases or _noop,
        list_cases=_noop,
        record_meta_verdict=_noop,
    )


def test_ingest_presents_then_pins_on_accept():
    """A3: on accept the handler calls the bound ctx.ingest_cases (which generates → live-
    gates → PINs → upserts the corpus + writes one AuditRecord), emits a `corpus` focus
    part, and returns the case count. The handler holds NO pin/persist logic of its own —
    that is the bound op's, exercised end-to-end in the [bff] layer."""
    seen: dict = {}

    def fake(json_dump, extraction_rules, agent):
        seen["json"] = json_dump
        seen["rules"] = extraction_rules
        seen["agent"] = agent
        return {
            "cases": [{"case_id": "x-1"}, {"case_id": "x-2"}],
            "mapping_id": 555,
            "count": 2,
        }

    ctx = _stub_ctx(ingest_cases=fake)
    out = asyncio.run(
        agent_tools.ingest_cases_handler(
            ctx, {"json": '{"resource": {"id": "x"}}', "extraction_rules": "per-scene"}
        )
    )
    assert "is_error" not in out
    assert "2" in out["content"][0]["text"]  # the case count
    assert seen["json"] == '{"resource": {"id": "x"}}'
    assert seen["rules"] == "per-scene"
    # a corpus focus part was emitted (the gen-UI directive opening the corpus tab)
    parts = [p for p in ctx.parts if p.get("output", {}).get("tab") == "corpus"]
    assert parts, ctx.parts


def test_ingest_pins_nothing_on_invariant_fail():
    """A3 negative: an invariant failure / :3031-down path surfaces a STRUCTURED error and
    pins NOTHING — no corpus part is emitted, the run is not a paid one, the error text
    states nothing was persisted (the same surface add_grounding_contract uses)."""

    def boom(json_dump, extraction_rules, agent):
        raise RuntimeError(
            "extraction invariant failed: 3 of 5 records null on required keys; nothing pinned"
        )

    ctx = _stub_ctx(ingest_cases=boom)
    out = asyncio.run(agent_tools.ingest_cases_handler(ctx, {"json": "{}"}))
    assert out.get("is_error") is True
    assert "nothing pinned" in out["content"][0]["text"].lower()
    # NOTHING was emitted on the error path (no corpus focus, no run)
    assert ctx.parts == []


def test_ingest_requires_json():
    """A malformed call with no JSON is refused with a structured error, never a crash and
    never a pin."""
    ctx = _stub_ctx()
    out = asyncio.run(agent_tools.ingest_cases_handler(ctx, {}))
    assert out.get("is_error") is True
    assert ctx.parts == []


# ── CE-INGEST-FASTFAIL (Build D): the BYO-data ingest grind is bounded ────────────
#
# The DSPy/JUTE extractor can grind ~2 min (up to 6 LLM attempts, no timeout) before
# failing. These tests pin a BOUNDED timeout (default 30s, LITHRIM_INGEST_TIMEOUT) at
# the `best_of_n_extractor` call: on timeout it raises into the existing RuntimeError
# path (nothing pinned, no audit row — A3) and the user surface names the timeout + a
# remediation hint. A fast/valid ingest still succeeds (the timeout doesn't break the
# happy path). The timeout is a worker thread + bounded join (NOT signal.alarm — that
# is main-thread-only and breaks under the BFF/uvicorn worker).

import importlib  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402


def _build_ingest(monkeypatch, tmp_path, *, extractor, score_accepts: bool):
    """Bind `_ingest_cases` from `app.py` against a tmp-isolated workspace + a stubbed
    EtlpJuteClient + a stubbed `best_of_n_extractor`. Hermetic: no network, no LM, no
    :3031. Returns (ingest_callable, workspace, db_path)."""
    app = importlib.import_module("app")
    from lithrim_bench import verification as _verif
    from lithrim_bench.harness import workspace as _ws
    from lithrim_bench.harness.audit import make_actor

    # isolate the workspace so the corpus jsonl + audit table are tmp-scoped
    monkeypatch.setattr(_ws, "WORKSPACES_DIR", tmp_path / "workspaces")
    ws = _ws.Workspace(name="ingest_ff")
    monkeypatch.setattr(_ws, "get_active_workspace", lambda: ws)

    # stub the :3031 client — find_mapping returns nothing (force generate), test_template
    # echoes a valid 1-record envelope so score_extraction accepts on the happy path.
    class _StubClient:
        def __init__(self, base_url="http://localhost:3031", **_k):
            self.base_url = base_url

        def find_mapping_by_title(self, _title):
            return None

        def get_dsl_spec(self):
            return {}

        def test_template(self, _template, _sample):
            return [{"case_id": "c-1", "response": "r", "context": "ctx"}]

        def persist_or_update(self, _title, _template):
            return {"id": 42}

    monkeypatch.setattr(_verif, "EtlpJuteClient", _StubClient)
    monkeypatch.setattr(app, "EtlpJuteClient", _StubClient, raising=False)

    monkeypatch.setattr(_verif, "best_of_n_extractor", extractor)

    if not score_accepts:
        # the happy-path stub above accepts; for the timeout tests the extractor never
        # returns, so score_extraction is unreached — leave it.
        pass

    db_path = tmp_path / "config.sqlite"
    actor = make_actor("tester")

    def _call(json_dump: str):
        ctx = app._build_tool_context(
            req_agent="ws0_default",
            db_path=db_path,
            out_dir=ws.out_dir,
            workdir=tmp_path / "ontology",
            collections_db=ws.collections_db,
            actor=actor,
            x_actor=None,
        )
        return ctx.ingest_cases(json_dump=json_dump)

    return _call, ws, db_path


def _configure_dummy_lm(monkeypatch):
    """Configure a dummy DSPy LM so `_ingest_cases` skips the BYO-Claude `claude` CLI
    lookup (gen_lm is not None) — keeps the test offline. The extractor is stubbed, so
    the LM is never actually called."""
    import dspy

    class _DummyLM(dspy.BaseLM):
        def __init__(self):
            super().__init__(model="dummy")

        def forward(self, *a, **k):  # never reached (extractor is stubbed)
            raise RuntimeError("no LM call in a hermetic ingest test")

    monkeypatch.setattr(dspy.settings, "lm", _DummyLM(), raising=False)


def test_ingest_fastfails_on_extractor_timeout(monkeypatch, tmp_path):
    """A: when the extractor grinds past LITHRIM_INGEST_TIMEOUT, ingest raises a BOUNDED
    TimeoutError within ~the timeout — NOT the full sleep (the ~2-min hang). TimeoutError
    is an Exception (caught by the handler's existing nothing-pinned except) AND lets the
    handler discriminate the timeout from a converge failure for a tailored remediation."""
    monkeypatch.setenv("LITHRIM_INGEST_TIMEOUT", "1")
    _configure_dummy_lm(monkeypatch)

    def slow_extractor(make_gen, rules, sample, *, n=2):
        time.sleep(30)  # far past the 1s bound — must be cut off
        raise AssertionError("should have timed out before returning")

    call, _ws, _db = _build_ingest(
        monkeypatch, tmp_path, extractor=slow_extractor, score_accepts=False
    )

    t0 = time.monotonic()
    with pytest.raises(TimeoutError) as exc:
        call('{"a": 1}')
    elapsed = time.monotonic() - t0

    assert elapsed < 10, f"ingest hung {elapsed:.1f}s — not bounded by the 1s timeout"
    msg = str(exc.value).lower()
    assert "timed out" in msg or "timeout" in msg, msg


def test_ingest_timeout_pins_nothing_no_audit(monkeypatch, tmp_path):
    """B (A3): on the timeout NOTHING is pinned — the corpus jsonl is absent and the
    audit ledger has NO ingest row."""
    monkeypatch.setenv("LITHRIM_INGEST_TIMEOUT", "1")
    _configure_dummy_lm(monkeypatch)

    def slow_extractor(make_gen, rules, sample, *, n=2):
        time.sleep(30)

    call, ws, db_path = _build_ingest(
        monkeypatch, tmp_path, extractor=slow_extractor, score_accepts=False
    )

    with pytest.raises(TimeoutError):
        call('{"a": 1}')

    assert not (ws.out_dir / "ingested_cases.jsonl").exists(), "corpus pinned on timeout"

    from lithrim_bench.harness.audit import AuditLog

    rows = AuditLog(db_path=db_path).query(target_type="corpus")
    assert rows == [], f"an audit row was written on timeout: {rows}"


def test_ingest_timeout_message_has_remediation(monkeypatch, tmp_path):
    """C: the user-facing error (via the handler) names the timeout AND a remediation
    hint, so the human knows what to do — not a raw 2-min stall."""
    monkeypatch.setenv("LITHRIM_INGEST_TIMEOUT", "1")
    _configure_dummy_lm(monkeypatch)

    def slow_extractor(make_gen, rules, sample, *, n=2):
        time.sleep(30)

    call, _ws, _db = _build_ingest(
        monkeypatch, tmp_path, extractor=slow_extractor, score_accepts=False
    )

    ctx = _stub_ctx(ingest_cases=lambda json_dump, extraction_rules, agent: call(json_dump))
    out = asyncio.run(agent_tools.ingest_cases_handler(ctx, {"json": '{"a": 1}'}))
    assert out.get("is_error") is True
    text = out["content"][0]["text"].lower()
    assert "timed out" in text or "timeout" in text, text
    # a remediation hint — simplify rules / reduce JSON / name the join key
    assert any(h in text for h in ("simplify", "reduce", "join key", "converge")), text
    assert _ws.out_dir.joinpath("ingested_cases.jsonl").exists() is False


def test_ingest_fast_path_still_succeeds(monkeypatch, tmp_path):
    """D (regression): a FAST extractor that returns inside the bound still succeeds —
    the timeout wrapper does not break the happy path. The case is pinned + the count
    returned."""
    monkeypatch.setenv("LITHRIM_INGEST_TIMEOUT", "30")
    _configure_dummy_lm(monkeypatch)

    class _Pred:
        jute_transform = "yaml: ok"
        accepted = True

    def fast_extractor(make_gen, rules, sample, *, n=2):
        return _Pred()

    call, ws, _db = _build_ingest(
        monkeypatch, tmp_path, extractor=fast_extractor, score_accepts=True
    )

    res = call('{"a": 1}')
    assert res["count"] == 1, res
    assert res["mapping_id"] == 42, res
    assert (ws.out_dir / "ingested_cases.jsonl").exists()
