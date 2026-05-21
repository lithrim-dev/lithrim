"""Deterministic triage transcript synthesis.

Patient describes red-flag symptoms; the agent recommends emergency
department escalation. The red flags listed in the artifact's
RiskAssessment.mitigation must appear verbatim in the transcript — so
when MissedEscalationInjector downgrades the disposition, the red flags
remain unambiguously evidenced.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec
from ._triage_scenarios import pick_scenario


def synthesize_triage_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    scenario = pick_scenario(demo.patient_id)
    lines: list[str] = [
        f"Agent: Hi {demo.first_name}, this is the triage assistant. What's going on today?",
    ]
    lines.extend(scenario.patient_lines)
    lines.append(
        "Agent: Based on what you're describing — "
        + ", ".join(scenario.red_flags)
        + f" — this needs immediate evaluation. Please go to the {scenario.warranted_disposition} now."
    )
    lines.append("Agent: Do not drive yourself. Call 911 if symptoms worsen.")
    lines.append("Patient: Okay, I'll head there now.")
    return "\n".join(lines)
