"""CE-PACK-6b-CLEAN D1 / CE-PACK-6c — the semantic stages reroute to the AUTHORED council.

When no evaluator is injected, :func:`stages.run_semantic_transcript` AND
:func:`stages.run_semantic_source_message` build the authored evaluator
(:func:`stages._default_authored_evaluator`) — the single live prompt source (OQ-1) —
so neither the legacy ``ComplianceCouncil.build_prompt`` default council (transcript)
nor ``build_source_message_prompt`` (source_message, deleted in 6c) is reached on the
in-process grade. ``$0``: the council fan-out + retrieval are stubbed; this pins the
ROUTING only (no Azure, no network).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("openai")  # `stages` -> compliance_council imports openai at module load

from lithrim_bench.runtime.pipeline import stages
from lithrim_bench.runtime.pipeline.models import PipelineRequest


def _req(context_kind: str = "transcript") -> PipelineRequest:
    return PipelineRequest(
        artifact="ARTIFACT",
        artifact_type="clinical_note",
        context_kind=context_kind,
        context={"transcript": "T"},
        org_id="test",
    )


def _stub_payload():
    async def _p(_request):
        return ({}, None)

    return _p


def _capture_runner(captured: dict):
    def _fake(*, request, payload, context_kind, council_evaluate, retrieval):
        captured["context_kind"] = context_kind
        captured["council_evaluate"] = council_evaluate

        async def _runner():
            return ("stub", {})

        return _runner

    return _fake


def test_transcript_default_injects_authored_evaluator(monkeypatch):
    """No injected evaluator → the authored evaluator is built and passed down; the
    legacy default council (``_council_for_mode`` → ``build_prompt``) is never reached."""
    sentinel = object()
    captured: dict = {}
    monkeypatch.setattr(stages, "_default_authored_evaluator", lambda: sentinel)
    monkeypatch.setattr(stages, "_build_transcript_payload", _stub_payload())
    monkeypatch.setattr(stages, "_run_council_and_map", _capture_runner(captured))
    monkeypatch.setattr(
        stages,
        "_council_for_mode",
        lambda *a, **k: pytest.fail(
            "_council_for_mode (build_prompt path) must not be reached on the transcript default"
        ),
    )

    asyncio.run(stages.run_semantic_transcript(_req()))

    assert captured["council_evaluate"] is sentinel
    assert captured["context_kind"] == stages.CONTEXT_KIND_TRANSCRIPT


def test_transcript_injected_evaluator_skips_authored_default(monkeypatch):
    """An injected evaluator (the authored stage / a test stub) is used verbatim; the
    default authored evaluator is NOT built."""
    injected = object()
    captured: dict = {}
    monkeypatch.setattr(
        stages,
        "_default_authored_evaluator",
        lambda: pytest.fail("must not build the authored default when an evaluator is injected"),
    )
    monkeypatch.setattr(stages, "_build_transcript_payload", _stub_payload())
    monkeypatch.setattr(stages, "_run_council_and_map", _capture_runner(captured))

    asyncio.run(stages.run_semantic_transcript(_req(), council_evaluate=injected))

    assert captured["council_evaluate"] is injected


def test_source_message_reroutes_to_authored(monkeypatch):
    """CE-PACK-6c: the source_message path reroutes to the AUTHORED evaluator the same way
    transcript does — no injected evaluator → ``_default_authored_evaluator`` is built and
    passed down, so ``ComplianceCouncil.evaluate`` → ``build_source_message_prompt`` (now
    deleted) is never reached."""
    sentinel = object()
    captured: dict = {}
    monkeypatch.setattr(stages, "_default_authored_evaluator", lambda: sentinel)

    async def _stub_sm_payload(_request):
        return ({}, None)

    monkeypatch.setattr(stages, "_build_source_message_payload", _stub_sm_payload)
    monkeypatch.setattr(stages, "_run_council_and_map", _capture_runner(captured))

    asyncio.run(stages.run_semantic_source_message(_req("source_message")))

    assert captured["council_evaluate"] is sentinel
    assert captured["context_kind"] == stages.CONTEXT_KIND_SOURCE_MESSAGE
