"""Recomposed observation / KPI pipeline — the greenfield KPI half of WS-6c.

Recomposed from ``lithrim-backend@mvp-ready`` ``app/workflows/observation_workflow.py``
(the LangGraph ``StateGraph``) + ``app/agents/`` (the 7 instantiated agents) +
``app/models/call_kpi.py`` (the state contract). WS-6c-OBS, bench-salvage.

What this is
------------
The KPI half of the observation workflow — ``process_input_item →
get_transcription_data → analyze_audio → run_parallel_analyses → aggregate_kpis``
— recomposed as a **straight-line async pipeline** (``pipeline.py``). The
LangGraph ``StateGraph`` collapses to ``if``/``await`` control flow; the
``handle_error`` sink → ``try/except``; the **4-way ``asyncio.gather`` fan-out**
(intent / sentiment / safety / technical) is **preserved as concurrency**, not
flattened. No Celery, no Mongo, no LangGraph runtime.

The recompose boundary (the documented hand-off seam)
-----------------------------------------------------
The pipeline **STOPS at ``aggregate_kpis``**. The backend workflow's compliance
tail (``check_hipaa_compliance → evaluate_artifacts → save_compliance_results``)
delegates to ``ComplianceWorkflow().process()``
(``observation_workflow.py:686-687``) — the very compliance grade path that
**WS-6c-AGENTIC already recomposed in-process** as
``runtime/pipeline/orchestrator.py``. So the tail is a **hand-off seam**, not a
re-port: ``pipeline.py`` documents where it would hand the in-memory
``ObservationState`` to that orchestrator, but emits no ``ComplianceWorkflow`` /
council call (A3). This is the WS-6c-AGENTIC "verify-and-document, don't
rebuild-nodes" pattern applied at the OBS boundary.

Agent map (WS-6b Ratification Q4)
---------------------------------
7 agents recomposed in-process, instantiation **hoisted** (the backend
re-instantiated them per node call): ``transcription`` (ingest) + the 6 KPI
(``audio_analysis``, ``intent_quality``, ``sentiment``, ``safety``,
``technical_metrics``, ``kpi_aggregation``). The dead ``evaluation_agent`` is
**dropped** (zero refs upstream); the LiveKit real-time ``simulation_agent`` is
**parked** (out of the verification pipeline).

Dependency posture (A2 — default install unchanged)
---------------------------------------------------
Everything in this package imports cleanly on the default install
(pydantic + pandas). The heavy agent couplings are isolated:

- the **3 LLM agents** (``intent_quality`` / ``sentiment`` / ``safety``) call an
  OpenAI/Azure client via the vendored ``agents._llm`` shim, which **reuses the
  council's** ``llm_provider`` + ``phi_redaction`` and **lazy-imports** ``openai``
  (the ``[council]`` extra) only on a real call. Tests inject a stub LLM service
  — no ``openai`` touched.
- the **audio-DSP trio** (``transcription`` = whisper/torch, ``audio_analysis`` =
  numpy, ``technical_metrics`` = librosa) is interface-complete with an offline
  reference for the text path; the heavy bodies are gated behind a new
  ``[observation]`` extra (``audio.py``) and the full faithful port is a
  documented follow-up. On the text path the audio agents are not invoked.

See ``docs/specs/RECOMPOSITION_PLAN_ws6.md`` §4/§7 + the WS-6c-OBS driver.
"""

from .agents.base import ObservationAgents
from .models import CallKPI
from .pipeline import ObservationPipeline, run_observation_pipeline
from .state import ObservationState

__all__ = [
    "CallKPI",
    "ObservationState",
    "ObservationAgents",
    "ObservationPipeline",
    "run_observation_pipeline",
]
