"""KPI Aggregation agent — combine all extracted metrics into the final score.

Ported verbatim from ``lithrim-backend@mvp-ready``
``app/agents/kpi_aggregation_agent/agent.py``. Mechanical adaptations only:
``app.models.call_kpi`` → ``..models`` (package-relative); the module-level
singleton and the ``__init__`` debug ``print`` are dropped (instantiation is
hoisted by ``ObservationAgents``). Pure — no LLM, no I/O, default-install clean.
"""

from typing import Any

from ..models import (
    AgentUnderstandingQuality,
    CoreInteractionMetrics,
    SafetyCompliance,
    SentimentMetrics,
    TechnicalCallStats,
)


class KPIAggregationAgent:
    """Agent for aggregating all KPI metrics into a final report."""

    def aggregate_kpis(
        self,
        core_metrics: CoreInteractionMetrics | None,
        quality_metrics: AgentUnderstandingQuality | None,
        sentiment_metrics: SentimentMetrics | None,
        safety_metrics: SafetyCompliance | None,
        technical_metrics: TechnicalCallStats | None,
    ) -> dict[str, Any]:
        """Aggregate all KPI metrics and calculate the overall score."""
        overall_score = self._calculate_overall_score(
            core_metrics,
            quality_metrics,
            sentiment_metrics,
            safety_metrics,
            technical_metrics,
        )

        return {
            "core_interaction_metrics": core_metrics,
            "agent_understanding_quality": quality_metrics,
            "sentiment_metrics": sentiment_metrics,
            "safety_compliance": safety_metrics,
            "technical_call_stats": technical_metrics,
            "overall_score": overall_score,
        }

    def _calculate_overall_score(
        self,
        core_metrics: CoreInteractionMetrics | None,
        quality_metrics: AgentUnderstandingQuality | None,
        sentiment_metrics: SentimentMetrics | None,
        safety_metrics: SafetyCompliance | None,
        technical_metrics: TechnicalCallStats | None,
    ) -> float:
        """Calculate overall KPI score (0-100).

        Weights: Core 20% · Quality 25% · Sentiment 15% · Safety 25% · Technical 15%.
        """
        scores = []

        # Core Interaction Metrics (20%)
        if core_metrics:
            core_score = 100.0
            if core_metrics.avg_turn_latency_ms:
                if core_metrics.avg_turn_latency_ms > 5000:  # > 5 seconds
                    core_score -= 20
                elif core_metrics.avg_turn_latency_ms > 3000:  # > 3 seconds
                    core_score -= 10
            core_score -= core_metrics.interruption_count * 5
            core_score -= core_metrics.repetition_count * 3
            core_score -= core_metrics.long_silence_gaps_count * 2
            scores.append(("core", max(0, min(100, core_score)), 0.20))

        # Quality & Understanding (25%)
        if quality_metrics:
            quality_score = 100.0
            if quality_metrics.intent_match:
                if not quality_metrics.intent_match.is_match:
                    quality_score -= 20
                quality_score -= (1 - quality_metrics.intent_match.confidence) * 10
            if quality_metrics.hallucination and quality_metrics.hallucination.has_hallucination:
                quality_score -= 30
            if (
                quality_metrics.workflow_deviation
                and quality_metrics.workflow_deviation.has_deviation
            ):
                quality_score -= 15
            if not quality_metrics.task_completion:
                quality_score -= 25
            else:
                quality_score -= (1 - quality_metrics.task_completion_confidence) * 10
            scores.append(("quality", max(0, min(100, quality_score)), 0.25))

        # Sentiment (15%)
        if sentiment_metrics:
            sentiment_score = 100.0
            if sentiment_metrics.user_sentiment_final == "negative":
                sentiment_score -= 30
            elif sentiment_metrics.user_sentiment_final == "neutral":
                sentiment_score -= 10
            sentiment_score -= (1 - sentiment_metrics.user_sentiment_confidence) * 5

            if sentiment_metrics.agent_sentiment_final == "negative":
                sentiment_score -= 10

            if "frustration" in sentiment_metrics.alerts:
                sentiment_score -= 15
            if "escalation_risk" in sentiment_metrics.alerts:
                sentiment_score -= 10

            scores.append(("sentiment", max(0, min(100, sentiment_score)), 0.15))

        # Safety (25% - increased weight due to compliance and risk)
        if safety_metrics:
            safety_score = 100.0

            if safety_metrics.overall_risk_score > 0:
                safety_score -= safety_metrics.overall_risk_score * 60
            else:
                if safety_metrics.pii_leakage and safety_metrics.pii_leakage.has_pii_leakage:
                    if safety_metrics.pii_leakage.severity == "high":
                        safety_score -= 50
                    elif safety_metrics.pii_leakage.severity == "medium":
                        safety_score -= 30
                    else:
                        safety_score -= 15
                    if safety_metrics.pii_leakage.confidence > 0.8:
                        safety_score -= 10

                if (
                    safety_metrics.unsafe_response
                    and safety_metrics.unsafe_response.has_unsafe_response
                ):
                    if safety_metrics.unsafe_response.severity == "high":
                        safety_score -= 50
                    elif safety_metrics.unsafe_response.severity == "medium":
                        safety_score -= 30
                    else:
                        safety_score -= 15
                    if safety_metrics.unsafe_response.confidence > 0.8:
                        safety_score -= 10

            if safety_metrics.compliance_violations:
                for violation in safety_metrics.compliance_violations:
                    if violation.has_violation:
                        if violation.severity == "high":
                            safety_score -= 40
                        elif violation.severity == "medium":
                            safety_score -= 25
                        else:
                            safety_score -= 15
                        if violation.confidence > 0.8:
                            safety_score -= 10

            if "high_risk_pii" in safety_metrics.alerts:
                safety_score -= 20
            if "high_risk_unsafe_content" in safety_metrics.alerts:
                safety_score -= 20
            if "high_risk_compliance" in safety_metrics.alerts:
                safety_score -= 30

            scores.append(("safety", max(0, min(100, safety_score)), 0.25))

        # Technical (15% - increased weight due to audio quality)
        if technical_metrics:
            technical_score = 100.0

            if technical_metrics.call_quality_score:
                mos_score = (technical_metrics.call_quality_score.overall_mos - 1) * 20
                technical_score = mos_score
            else:
                if technical_metrics.audio_quality:
                    audio_quality_score = technical_metrics.audio_quality.audio_quality_score * 100
                    technical_score = audio_quality_score

                    if technical_metrics.audio_quality.distortion_detected:
                        technical_score -= 15
                    if technical_metrics.audio_quality.snr_db is not None:
                        if technical_metrics.audio_quality.snr_db < 10:  # Poor SNR
                            technical_score -= 20
                        elif technical_metrics.audio_quality.snr_db < 20:  # Fair SNR
                            technical_score -= 10

            technical_score -= technical_metrics.tool_error_count * 5

            if (
                technical_metrics.performance_metrics
                and technical_metrics.performance_metrics.total_processing_time_ms
            ):
                total_time_sec = (
                    technical_metrics.performance_metrics.total_processing_time_ms / 1000
                )
                if total_time_sec > 60:  # > 1 minute
                    technical_score -= 10
                elif total_time_sec > 30:  # > 30 seconds
                    technical_score -= 5

            if not technical_metrics.call_availability:
                technical_score -= 15

            scores.append(("technical", max(0, min(100, technical_score)), 0.15))

        if not scores:
            return 0.0

        total_weight = sum(weight for _, _, weight in scores)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(score * weight for _, score, weight in scores)
        overall_score = weighted_sum / total_weight

        return round(overall_score, 2)
