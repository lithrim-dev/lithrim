"""Deterministic triage transcript synthesis.

v2 (2026-05-21): the agent's turn now explicitly grounds the risk
level, the outcome name, and the recommended disposition that appear
in the FHIR RiskAssessment artifact. v1 said "this needs immediate
evaluation, go to ED" without naming the high-risk-of-X outcome the
artifact carries; the live council flagged 4/4 clean triage cases as
needs_review because the artifact's prediction.outcome wasn't
textually grounded.

v3 (2026-05-21): mirrors the numeric probability anchor emitted by
triage_artifact.py v3 (prediction.probabilityDecimal = 0.85). The
structural validator change is the load-bearing fix for the
clean-recall=0/4 finding; this transcript update keeps the council's
grounding tight against the new artifact shape.

When MissedEscalationInjector downgrades the disposition, the
red-flags + agent's high-risk statement remain in the transcript —
the absent escalation becomes unambiguously evidenced by negative
audit trail.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec
from ._triage_scenarios import pick_scenario
from .triage_artifact import HIGH_RISK_PROBABILITY


def synthesize_triage_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    scenario = pick_scenario(demo.patient_id)
    probability_pct = int(round(HIGH_RISK_PROBABILITY * 100))
    lines: list[str] = [
        f"Agent: Hi {demo.first_name}, this is the triage assistant. What's going on today?",
    ]
    lines.extend(scenario.patient_lines)
    lines.append(
        "Agent: Based on what you're describing — "
        + ", ".join(scenario.red_flags)
        + f" — this presentation indicates {scenario.warranted_risk} risk of {scenario.risk_outcome}."
    )
    lines.append(
        f"Agent: My probability estimate for {scenario.risk_outcome} is roughly {probability_pct}% — "
        "well above the threshold for emergency evaluation."
    )
    lines.append(
        f"Agent: My disposition is to refer you to the {scenario.warranted_disposition} immediately. "
        f"Do not attempt self-care; this requires emergency evaluation."
    )
    lines.append("Agent: Do not drive yourself. Call 911 if symptoms worsen.")
    lines.append("Patient: Okay, I'll head there now.")
    return "\n".join(lines)
