"""WorstOfBackend: compose semantic + structural under the worst-of rule.

The paper's headline claim is about *this composition*. WorstOfBackend
makes it a single BackendClient: harness, analysis, and CLI treat it
identically to any other backend.

Rule (mirrors lithrim-backend/app/services/artifact_evaluator.py:37-45):

  artifact_verdict   = worst-of(semantic.artifact, structural.artifact)
                       using {PASS=0, WARN=1, BLOCK=2}
  compliance_verdict = worst-of(semantic.compliance, lift(structural.artifact))
                       using {approve=0, needs_review=1, reject=2}
                       where lift maps BLOCK->reject, WARN->needs_review,
                       PASS->approve.
  flags              = sorted set union of semantic.flags + structural.structural_findings
  per_judge          = passed through from semantic (structural has none)
  structural_verdict = structural.structural_verdict (passed through)

The structural backend is expected to set compliance_verdict='approve'
and flags=[] by convention (the structural validator does not make
semantic judgments); WorstOfBackend tolerates non-conforming
structural backends by composing on artifact_verdict alone if
structural.compliance_verdict is not 'approve'.
"""
from __future__ import annotations

from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict

_COMPLIANCE_RANK = {"approve": 0, "needs_review": 1, "reject": 2}
_ARTIFACT_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}
_LIFT_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


def _worst(a: str, b: str, rank: dict[str, int]) -> str:
    return a if rank.get(a, 0) >= rank.get(b, 0) else b


class WorstOfBackend(BackendClient):
    def __init__(self, semantic: BackendClient, structural: BackendClient):
        self.semantic = semantic
        self.structural = structural

    @property
    def pin(self) -> BackendPin:
        s_pin = self.semantic.pin
        x_pin = self.structural.pin
        return BackendPin(
            backend="WorstOfBackend",
            backend_version="0.1.0",
            judge_model=s_pin.judge_model,
            judge_model_version=s_pin.judge_model_version,
            extra={
                "semantic": {
                    "backend": s_pin.backend,
                    "backend_version": s_pin.backend_version,
                    "extra": s_pin.extra,
                },
                "structural": {
                    "backend": x_pin.backend,
                    "backend_version": x_pin.backend_version,
                    "extra": x_pin.extra,
                },
            },
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        sem = self.semantic.evaluate(case)
        struct = self.structural.evaluate(case)

        composed_artifact = _worst(
            sem.artifact_verdict, struct.artifact_verdict, _ARTIFACT_RANK
        )
        structural_lifted_compliance = _LIFT_TO_COMPLIANCE.get(
            struct.artifact_verdict, "approve"
        )
        composed_compliance = _worst(
            sem.compliance_verdict, structural_lifted_compliance, _COMPLIANCE_RANK
        )

        merged_flags = sorted(set(sem.flags) | set(struct.structural_findings))

        return BackendVerdict(
            compliance_verdict=composed_compliance,
            artifact_verdict=composed_artifact,
            flags=merged_flags,
            per_judge=sem.per_judge,
            structural_verdict=struct.structural_verdict,
            structural_findings=list(struct.structural_findings),
            raw={"semantic": sem.raw, "structural": struct.raw},
        )
