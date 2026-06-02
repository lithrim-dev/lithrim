"""Offline acceptance tests for the recomposed observation / KPI pipeline.

Runs on the default install (pydantic + pytest) — no ``openai``/whisper/Celery/
Mongo/network. The 3 LLM agents are driven by an injected ``StubLLM``; the input
is a text case (the audio-DSP bodies are deferred behind ``[observation]``).

Maps to the WS-6c-OBS acceptance criteria:
  A1 — in-process KPI pipeline runs end-to-end, emits the aggregation;
  A2 — default import/run pulls no heavy deps; audio agents gated;
  A3 — the compliance tail is a seam, not a re-port (no ComplianceWorkflow/council);
  A4 — 7 agents hoisted, evaluation dropped, simulation parked, gather concurrent;
  A5 — ObservationState / CallKPI field contract preserved.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest

from lithrim_bench.runtime.observation import (
    CallKPI,
    ObservationAgents,
    ObservationPipeline,
    ObservationState,
)
from lithrim_bench.runtime.observation.agents import ObservationExtraRequired
from lithrim_bench.runtime.observation.agents.base import (
    IntentQualityLike,
    KpiAggregationLike,
    SafetyLike,
    SentimentLike,
    TranscriptionLike,
)
from lithrim_bench.runtime.observation.state import _KPI_FIELDS, _SEAM_FIELDS

from .conftest import StubLLM

_PKG_DIR = Path(__file__).resolve().parent.parent


def _run(coro):
    return asyncio.run(coro)


# ── A1: in-process KPI pipeline end-to-end ──────────────────────────────────
def test_pipeline_runs_text_case_end_to_end(text_case, stub_llm):
    agents = ObservationAgents.build(llm_service=stub_llm)
    state = _run(ObservationPipeline(agents).run(**text_case))

    assert state["status"] == "completed"
    ck = state["call_kpi"]
    assert isinstance(ck, CallKPI)
    assert ck.kpi_status == "completed"
    # the aggregation was produced
    assert isinstance(state["overall_score"], float)
    assert state["aggregated_kpis"]["overall_score"] == state["overall_score"]
    # the LLM-backed KPI metrics landed on the CallKPI
    assert ck.agent_understanding_quality.task_completion is True
    assert ck.sentiment_metrics.user_sentiment_final == "positive"
    assert ck.safety_compliance.overall_risk_score == 0.0
    # text path → no audio → technical metrics gracefully absent
    assert ck.technical_call_stats is None


def test_pipeline_fails_cleanly_without_input(stub_llm):
    agents = ObservationAgents.build(llm_service=stub_llm)
    state = _run(
        ObservationPipeline(agents).run(
            session_id="s", agent_id="a", file_path="x.txt", item_id="i"
        )
    )
    assert state["status"] == "failed"
    assert "no transcript" in state["error_message"]


# ── A4: agent map (7 hoisted, drop/park) + the gather fan-out ───────────────
def test_seven_agents_hoisted_and_reused(stub_llm):
    agents = ObservationAgents.build(llm_service=stub_llm)
    roles = (
        "transcription",
        "audio_analysis",
        "intent_quality",
        "sentiment",
        "safety",
        "technical_metrics",
        "kpi_aggregation",
    )
    assert all(getattr(agents, r) is not None for r in roles)
    # structural Protocol conformance (the agent interface / map)
    assert isinstance(agents.transcription, TranscriptionLike)
    assert isinstance(agents.intent_quality, IntentQualityLike)
    assert isinstance(agents.sentiment, SentimentLike)
    assert isinstance(agents.safety, SafetyLike)
    assert isinstance(agents.kpi_aggregation, KpiAggregationLike)
    # hoist: the pipeline reuses the SAME instances (no per-call re-instantiation)
    pipe = ObservationPipeline(agents)
    assert pipe.agents.intent_quality is agents.intent_quality


def test_evaluation_dropped_and_simulation_parked():
    import lithrim_bench.runtime.observation.agents as agents_pkg

    names = dir(agents_pkg)
    assert not any("Evaluation" in n for n in names), "evaluation_agent must be dropped"
    assert not any("Simulation" in n for n in names), "simulation_agent must be parked"
    # not importable as a submodule either
    for mod in ("evaluation", "simulation"):
        with pytest.raises(ModuleNotFoundError):
            __import__(f"lithrim_bench.runtime.observation.agents.{mod}")


def test_gather_fanout_runs_concurrently(text_case):
    """Prove run_parallel_analyses really fans out (not sequential sugar).

    A peak-concurrency probe over invoke_llm: if the LLM agents ran sequentially
    the peak would be 1; the 4-way gather overlaps them, so peak >= 2.
    """

    class ConcurrencyProbeLLM(StubLLM):
        def __init__(self):
            super().__init__()
            self._lock = threading.Lock()
            self._active = 0
            self.peak = 0

        def invoke_llm(self, prompt: str) -> str:
            with self._lock:
                self._active += 1
                self.peak = max(self.peak, self._active)
            try:
                time.sleep(0.05)  # hold the slot so concurrent calls overlap
                return super().invoke_llm(prompt)
            finally:
                with self._lock:
                    self._active -= 1

    probe = ConcurrencyProbeLLM()
    agents = ObservationAgents.build(llm_service=probe)
    state = _run(ObservationPipeline(agents).run(**text_case))
    assert state["status"] == "completed"
    assert probe.peak >= 2, f"expected concurrent LLM calls, peak was {probe.peak}"


# ── A5: ObservationState / CallKPI field contract ───────────────────────────
def test_observation_state_field_contract():
    # the recomposed ObservationState preserves the KPI-half field set …
    assert set(ObservationState.__annotations__) == _KPI_FIELDS
    # … and excludes the compliance/artifact tail (the hand-off seam)
    assert _KPI_FIELDS.isdisjoint(_SEAM_FIELDS)
    assert set(ObservationState.__annotations__).isdisjoint(_SEAM_FIELDS)


def test_call_kpi_field_contract():
    # Pinned from lithrim-backend@mvp-ready app/models/call_kpi.py:549 (CallKPI),
    # minus nothing — the Mongo `_id` alias became the plain `id` field.
    expected = {
        "id",
        "agent_id",
        "organization_id",
        "session_id",
        "item_id",
        "file_path",
        "core_interaction_metrics",
        "agent_understanding_quality",
        "sentiment_metrics",
        "safety_compliance",
        "technical_call_stats",
        "normalized_transcript_stream",
        "overall_score",
        "kpi_status",
        "error_message",
        "compliance_report_id",
        "hipaa_compliance_status",
        "created_at",
        "updated_at",
    }
    assert set(CallKPI.model_fields) == expected


# ── A3: the compliance tail is a documented seam, not a re-port ─────────────
def test_no_compliance_tail_imported_or_called():
    # A3: the compliance tail is a documented SEAM (prose comments may NAME
    # ComplianceWorkflow), but the package must never IMPORT or CALL the compliance
    # grade path. Flag only real import statements / instantiations — not the
    # documented-seam prose in docstrings/comments.
    # An actual call requires an import binding the name first (these are not
    # builtins), so an import-statement scan is sufficient and precise — it does
    # not false-flag the KPI model names (SafetyCompliance / ComplianceViolation)
    # or the documented-seam prose. The runtime check below is the behavioral back-stop.
    offenders = []
    for path in _PKG_DIR.rglob("*.py"):
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line.startswith(("import ", "from ")):
                continue
            if any(
                tok in line
                for tok in (
                    "compliance_council",
                    "compliance_workflow",
                    "ComplianceWorkflow",
                    "ComplianceCouncil",
                    "pipeline.orchestrator",
                    "runtime.council",
                    "runtime.pipeline",
                )
            ):
                offenders.append(f"{path.name}: {line}")
    assert not offenders, offenders


def test_importing_observation_does_not_load_compliance_modules():
    # A3 (runtime): importing the package must not pull the recomposed compliance
    # grade path (council / orchestrator) — they are a hand-off seam, not a dep.
    import importlib

    importlib.import_module("lithrim_bench.runtime.observation")
    assert "lithrim_bench.runtime.council.compliance_council" not in sys.modules
    assert "lithrim_bench.runtime.pipeline.orchestrator" not in sys.modules


def test_returned_state_has_no_compliance_seam_values(text_case, stub_llm):
    agents = ObservationAgents.build(llm_service=stub_llm)
    state = _run(ObservationPipeline(agents).run(**text_case))
    # the pipeline stops at aggregate_kpis — it sets none of the seam fields
    for seam_field in _SEAM_FIELDS:
        assert state.get(seam_field) is None


# ── A2: default install isolation + audio agents gated ──────────────────────
def test_default_run_pulls_no_heavy_deps(text_case, stub_llm):
    agents = ObservationAgents.build(llm_service=stub_llm)
    _run(ObservationPipeline(agents).run(**text_case))
    for mod in ("openai", "whisper", "torch", "librosa", "boto3", "pydantic_settings"):
        assert mod not in sys.modules, f"{mod} must not be pulled into the default run"


def test_audio_agents_are_extra_gated():
    agents = ObservationAgents.build()
    # real-audio paths raise the actionable extra error …
    with pytest.raises(ObservationExtraRequired):
        _run(agents.transcription.transcribe_from_bytes(b"x", "f.wav"))
    with pytest.raises(ObservationExtraRequired):
        _run(agents.audio_analysis.analyze_audio(b"x", {"transcription": "t"}, "f.wav"))
    with pytest.raises(ObservationExtraRequired):
        _run(agents.technical_metrics.extract_technical_metrics(b"x"))
    # … but the no-audio (text) path degrades gracefully
    result = _run(agents.technical_metrics.extract_technical_metrics(None))
    assert result["success"] is False
    assert result["warnings"][0]["code"] == "TECHNICAL_NO_AUDIO"


def test_audio_file_without_bytes_fails():
    agents = ObservationAgents.build(llm_service=StubLLM())
    state = _run(
        ObservationPipeline(agents).run(
            session_id="s", agent_id="a", file_path="call.wav", item_id="i"
        )
    )
    assert state["status"] == "failed"
    assert "audio_bytes" in state["error_message"]
