"""Audio-DSP KPI agents — interface-complete, heavy bodies DEFERRED.

The three audio agents in the backend observation workflow are the heaviest, most
harness-irrelevant couplings in the recompose source:

- ``TranscriptionAgent`` — Whisper (``torch`` + ``whisper``, module-top in
  ``transcription_service.py:3-4``);
- ``AudioAnalysisAgent`` — ``numpy`` DSP over audio bytes;
- ``TechnicalMetricsAgent`` — ``librosa`` / ``pydub`` audio metrics.

The WS-6c-OBS slice (tier **A+**, user-elected) recomposes them as **in-process,
instantiation-hoisted agent classes implementing the interface**, but **gates the
real DSP bodies behind the optional ``lithrim[observation]`` extra** — the
faithful whisper/librosa port is a documented follow-up. This is sound because
the recomposed **text path never invokes the audio agents**: the transcript is
supplied in-memory (no Whisper), ``analyze_audio`` is skipped for text (mirroring
``observation_workflow.py:384-387``), and ``extract_technical_metrics`` is called
without audio bytes and degrades gracefully (matching the backend's
no-audio-success-false behavior). Invoking a real audio path on the default
install raises a clear, actionable ``ObservationExtraRequired``.
"""

from typing import Any


class ObservationExtraRequired(RuntimeError):
    """A deferred audio-DSP path needs the (unported) ``[observation]`` backend.

    Raised by the audio agents when invoked on a real-audio path. The text path
    never triggers it.
    """


_DEFER_MSG = (
    "{agent}.{method} needs the audio-DSP backend (whisper/torch/librosa), gated "
    "behind the optional `lithrim[observation]` extra; its faithful port is a "
    "documented WS-6c-OBS follow-up. The recomposed text path does not invoke it."
)


class TranscriptionAgent:
    """Ingest agent — audio bytes → transcript via Whisper (DEFERRED).

    Text inputs never reach this: the recomposed text path supplies the transcript
    in-memory (see ``pipeline.get_transcription_data``).
    """

    async def transcribe_from_bytes(self, audio_bytes: bytes, file_name: str) -> dict[str, Any]:
        raise ObservationExtraRequired(
            _DEFER_MSG.format(agent="TranscriptionAgent", method="transcribe_from_bytes")
        )


class AudioAnalysisAgent:
    """Audio DSP → ``CoreInteractionMetrics`` + turns/structure (DEFERRED).

    Skipped for text inputs (``observation_workflow.py:384-387``).
    """

    async def analyze_audio(
        self, audio_bytes: bytes, transcription_data: dict[str, Any], file_name: str
    ) -> dict[str, Any]:
        raise ObservationExtraRequired(
            _DEFER_MSG.format(agent="AudioAnalysisAgent", method="analyze_audio")
        )


class TechnicalMetricsAgent:
    """Technical call metrics via librosa (DEFERRED for real audio).

    On the text / no-audio path (``audio_bytes`` falsy) it returns a graceful
    success-false result so KPI aggregation proceeds without technical metrics —
    matching the backend agent's degrade-without-audio behavior. With real audio
    bytes the librosa body is deferred and this raises ``ObservationExtraRequired``.
    """

    async def extract_technical_metrics(
        self,
        audio_bytes: bytes | None,
        duration_ms: float | None = None,
        tool_errors: list[dict[str, Any]] | None = None,
        performance_metrics: dict[str, float] | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        if not audio_bytes:
            return {
                "success": False,
                "metrics": None,
                "error": "no audio bytes (text input); technical metrics require audio",
                "warnings": [
                    {
                        "code": "TECHNICAL_NO_AUDIO",
                        "message": "Technical metrics skipped — no audio bytes (text input).",
                        "component": "technical_metrics",
                    }
                ],
            }
        raise ObservationExtraRequired(
            _DEFER_MSG.format(agent="TechnicalMetricsAgent", method="extract_technical_metrics")
        )
