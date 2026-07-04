"""CHAT-CASE-RESOLVE-1: the chat-NAMED case is the grade target, deterministically.

The bug (CONFIRMED live — deployed-BFF probe): with the CHAT-CASE-TARGET-1 plumbing deployed
(the cost-confirm directive carries ``ctx.active_case``, the shell syncs+grades it), the residual
is at the MODEL layer. gpt-4.1 non-deterministically FAILS to extract the named case from the
message — it calls ``run_eval`` WITHOUT ``case_id``, so ``ctx.active_case`` stays the stale request
``active_case`` and the WRONG case gets graded. Verbatim, asking
"run a live eval on run_001_fabricates" with ``active_case:"run_002_faithful"``::

    directive_output: { case_id: "run_002_faithful" }   ← the WRONG case

The fix: resolve the case the human NAMED in the message to a known ingested ``case_id``
DETERMINISTICALLY in the BFF, BEFORE the agent runs, and use it as ``ctx.active_case``. Because
``run_eval_handler`` only overrides ``ctx.active_case`` when an explicit ``case_id`` is passed and
``propose_live_run_handler`` emits ``propose_live_run_part(ctx.active_case)``, setting
``ctx.active_case`` up front makes EVERY agent path carry the named case — regardless of the model's
tool-calling. The CHAT-CASE-TARGET-1 plumbing does the rest.

A-SAFE (NON-NEGOTIABLE): ``_resolve_named_case`` performs only the $0 ingested-case read + a
SELECTOR resolution. NO spend, NO new tool, NO schema change, NO paid knob. ``confirmPaidRun``
still requires the human's confirm; the agent gains no spend path.

Hermetic — NO real Claude, NO Azure. The resolver runs against a stubbed corpus; the integration
test mocks ``run_chat`` (no SDK) to capture the ctx ``chat_endpoint`` hands it. Requires the [bff]
extra (the FastAPI TestClient runs in ``debuglithrim``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

import app as bff  # noqa: E402

_CORPUS = [{"case_id": "run_001_fabricates"}, {"case_id": "run_002_faithful"}]


# ── T1 — the resolver (unit, non-vacuous) ─────────────────────────────────────


def test_resolve_named_case_picks_the_named_case(monkeypatch):
    """A message naming a known ingested case resolves to that case_id — the SELECTOR the
    chat_endpoint pins as ctx.active_case before the agent runs."""
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    assert (
        bff._resolve_named_case("run a live eval on run_001_fabricates")
        == "run_001_fabricates"
    )
    assert (
        bff._resolve_named_case("now grade run_002_faithful please")
        == "run_002_faithful"
    )


def test_resolve_named_case_returns_none_when_no_known_case_is_named(monkeypatch):
    """A message that names NO known case → None (so chat_endpoint falls back to the client's
    active_case — byte-identical to today)."""
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    assert bff._resolve_named_case("what judges do I have?") is None
    assert bff._resolve_named_case("") is None
    assert bff._resolve_named_case(None) is None


def test_resolve_named_case_never_raises_on_a_read_failure(monkeypatch):
    """A resolution failure must NEVER break the chat: a corpus read that raises → None."""

    def _boom():
        raise RuntimeError("DB hiccup")

    monkeypatch.setattr(bff, "_read_ingested_corpus", _boom)
    assert bff._resolve_named_case("run a live eval on run_001_fabricates") is None


def test_resolve_named_case_longest_match_wins(monkeypatch):
    """Longest-match disambiguation: a generic ``run_001`` known-case must NOT shadow the more
    specific ``run_001_fabricates`` when the message names the latter."""
    monkeypatch.setattr(
        bff,
        "_read_ingested_corpus",
        lambda: [{"case_id": "run_001"}, {"case_id": "run_001_fabricates"}],
    )
    assert (
        bff._resolve_named_case("run a live eval on run_001_fabricates")
        == "run_001_fabricates"
    )


def test_resolve_named_case_ignores_rows_without_a_case_id(monkeypatch):
    """Conservative: rows missing case_id are skipped (no crash, no spurious match)."""
    monkeypatch.setattr(
        bff,
        "_read_ingested_corpus",
        lambda: [{"foo": "bar"}, {"case_id": "run_002_faithful"}],
    )
    assert bff._resolve_named_case("grade run_002_faithful") == "run_002_faithful"
    assert bff._resolve_named_case("nothing here") is None


# ── T2 — THE HEADLINE (integration, non-vacuous) ──────────────────────────────


def _override_deps(tmp_path):
    """Pin every chat_endpoint dep to tmp paths so the route is hermetic (no active-workspace
    on-disk reads). The behavior under test (the named-case override) is independent of these."""
    from app import (
        get_actor,
        get_collections_db,
        get_config_db,
        get_ontology_workdir,
        get_out_dir,
    )

    bff.app.dependency_overrides[get_config_db] = lambda: tmp_path / "cfg.sqlite"
    bff.app.dependency_overrides[get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[get_collections_db] = lambda: tmp_path / "coll.sqlite"
    bff.app.dependency_overrides[get_actor] = lambda: bff.Actor(
        type="system", id="test-sme"
    )


def _capture_ctx_chat(monkeypatch):
    """Mock run_chat (no SDK / no Claude) to record the ctx chat_endpoint hands it, then yield
    one harmless done event so the SSE stream closes cleanly."""
    captured: dict = {}

    async def _fake_run_chat(message, ctx, *, history=None):
        captured["ctx"] = ctx
        yield {"type": "done"}

    import agent

    monkeypatch.setattr(agent, "run_chat", _fake_run_chat, raising=True)
    # also stub agent resolution so the route never touches a real config DB
    monkeypatch.setattr(bff, "_resolve_chat_agent", lambda req_agent, db_path: req_agent)
    return captured


def test_chat_named_case_overrides_the_stale_client_active_case(tmp_path, monkeypatch):
    """THE HEADLINE: POST /v1/chat with message naming run_001_fabricates but a stale client
    active_case=run_002_faithful → chat_endpoint resolves the named case and hands the agent a
    ctx whose active_case == run_001_fabricates (the named case overrode the stale selection).

    MUTATION (the driver names it): revert the resolution in chat_endpoint (pass
    ``active_case=req.active_case``) → captured ctx.active_case stays "run_002_faithful" → RED."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    captured = _capture_ctx_chat(monkeypatch)
    _override_deps(tmp_path)
    try:
        client = TestClient(bff.app)
        with client.stream(
            "POST",
            "/v1/chat",
            json={
                "message": "run a live eval on run_001_fabricates",
                "agent": "ws0_default",
                "active_case": "run_002_faithful",
            },
        ) as resp:
            assert resp.status_code == 200
            for _ in resp.iter_lines():
                pass
    finally:
        bff.app.dependency_overrides.clear()

    assert "ctx" in captured, "run_chat was not invoked"
    assert captured["ctx"].active_case == "run_001_fabricates"


# ── T3 — fallback / back-compat ───────────────────────────────────────────────


def test_chat_no_named_case_falls_back_to_the_client_active_case(tmp_path, monkeypatch):
    """No named case in the message → the client's active_case is used (unchanged behavior)."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    captured = _capture_ctx_chat(monkeypatch)
    _override_deps(tmp_path)
    try:
        client = TestClient(bff.app)
        with client.stream(
            "POST",
            "/v1/chat",
            json={
                "message": "what judges do I have?",
                "agent": "ws0_default",
                "active_case": "run_002_faithful",
            },
        ) as resp:
            assert resp.status_code == 200
            for _ in resp.iter_lines():
                pass
    finally:
        bff.app.dependency_overrides.clear()

    assert captured["ctx"].active_case == "run_002_faithful"


def test_chat_no_named_case_and_null_active_case_is_none(tmp_path, monkeypatch):
    """No named case AND no client active_case → ctx.active_case is None (byte-identical to today)."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: list(_CORPUS))
    captured = _capture_ctx_chat(monkeypatch)
    _override_deps(tmp_path)
    try:
        client = TestClient(bff.app)
        with client.stream(
            "POST",
            "/v1/chat",
            json={
                "message": "what judges do I have?",
                "agent": "ws0_default",
                "active_case": None,
            },
        ) as resp:
            assert resp.status_code == 200
            for _ in resp.iter_lines():
                pass
    finally:
        bff.app.dependency_overrides.clear()

    assert captured["ctx"].active_case is None


# ── A-SAFE pin (non-vacuous): the resolver is a $0 read + selector, no paid surface ──


def test_resolve_named_case_does_only_the_ingested_read_no_paid_op(monkeypatch):
    """A-SAFE: _resolve_named_case calls ONLY _read_ingested_corpus (the $0 ingested-case read) —
    it never reaches a paid op. A spy on the corpus read is the only thing it touches."""
    calls: list[str] = []

    def _spy():
        calls.append("read")
        return list(_CORPUS)

    monkeypatch.setattr(bff, "_read_ingested_corpus", _spy)
    bff._resolve_named_case("run a live eval on run_001_fabricates")
    assert calls == ["read"]  # exactly the one $0 read, nothing else


def test_chat_schema_and_tool_specs_are_unchanged_by_the_resolver():
    """A-SAFE: the resolver widened NO schema. ChatRequest stays {message, agent, history,
    active_case}; the chat carries no new paid knob; the agent tool-set is unchanged at 22."""
    from agent import tools as agent_tools
    from agent.tools import PAID_KEYS

    fields = set(bff.ChatRequest.model_fields)
    assert fields == {"message", "agent", "history", "active_case"}
    assert not any(k in fields for k in PAID_KEYS)
    assert len(agent_tools._TOOL_SPECS) == 24
