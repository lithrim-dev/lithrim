"""MockBackend: deterministic with configurable noise.

Purpose: stand in for the real backend in tests and in the paper's
illustrative determinism demonstration without an LLM. Calibrated to
reproduce the two failure modes the determinism protocol measures:

- decision-layer drift: the verdict itself flips between runs (rare in
  practice; the eval spec's hba1c case showed it was bistability at
  the code-attribution layer, not the decision layer)
- code-attribution drift: the verdict stays put, but the attached
  flags vary across runs (the canonical failure pattern)

Three params control the noise:

- `decision_flip_rate`: per-run probability that the verdict drifts to
  the next-softer category (reject -> needs_review -> approve)
- `flag_attachment_rate`: per-run probability that an expected flag is
  attached (0.0 = the backend always drops the flag; 1.0 = perfect
  attribution)
- `noise_seed`: per-case PRNG seed. The same (seed, case_id) tuple
  always produces the same N-run distribution.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput

_SOFTER = {"reject": "needs_review", "needs_review": "approve", "approve": "approve"}
_ARTIFACT_FOR = {"reject": "BLOCK", "needs_review": "WARN", "approve": "PASS"}


def _seed_for(noise_seed: int, case_id: str, run_index: int) -> int:
    h = hashlib.sha1(f"{noise_seed}|{case_id}|{run_index}".encode()).hexdigest()
    return int(h[:8], 16)


class MockBackend(BackendClient):
    def __init__(
        self,
        *,
        decision_flip_rate: float = 0.0,
        flag_attachment_rate: float = 1.0,
        structural_drift_rate: float = 0.0,
        noise_seed: int = 0,
        judges: tuple[str, ...] = ("policy_judge", "risk_judge", "behavior_judge"),
    ):
        self.decision_flip_rate = decision_flip_rate
        self.flag_attachment_rate = flag_attachment_rate
        self.structural_drift_rate = structural_drift_rate
        self.noise_seed = noise_seed
        self.judges = judges
        self._call_index: dict[str, int] = {}

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="MockBackend",
            backend_version="0.1.0",
            judge_model="mock",
            judge_model_version="deterministic-with-noise",
            extra={
                "decision_flip_rate": self.decision_flip_rate,
                "flag_attachment_rate": self.flag_attachment_rate,
                "structural_drift_rate": self.structural_drift_rate,
                "noise_seed": self.noise_seed,
            },
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        case_id = case["case_id"]
        run_index = self._call_index.get(case_id, 0)
        self._call_index[case_id] = run_index + 1
        rng = random.Random(_seed_for(self.noise_seed, case_id, run_index))

        expected_verdict = case.get("expected_compliance_verdict", "approve")
        if isinstance(expected_verdict, list):
            expected_verdict = expected_verdict[0]
        verdict = expected_verdict
        if verdict != "approve" and rng.random() < self.decision_flip_rate:
            verdict = _SOFTER[verdict]

        expected_flags: list[str] = case.get("expected_safety_flags") or []
        flags = [f for f in expected_flags if rng.random() < self.flag_attachment_rate]

        per_judge: dict[str, JudgeOutput] = {}
        for j in self.judges:
            j_rng = random.Random(_seed_for(self.noise_seed, case_id + j, run_index))
            j_verdict = verdict
            if j_verdict != "approve" and j_rng.random() < self.decision_flip_rate:
                j_verdict = _SOFTER[j_verdict]
            j_flags = [f for f in expected_flags if j_rng.random() < self.flag_attachment_rate]
            per_judge[j] = JudgeOutput(judge_name=j, verdict=j_verdict, flags=j_flags)

        expected_structural = case.get("expected_structural_verdict")
        structural_verdict: str | None = None
        structural_findings: list[str] = []
        if expected_structural is not None:
            s_rng = random.Random(_seed_for(self.noise_seed, case_id + "::struct", run_index))
            if s_rng.random() < self.structural_drift_rate:
                structural_verdict = "PASS" if expected_structural == "BLOCK" else "BLOCK"
            else:
                structural_verdict = expected_structural
            if structural_verdict == "BLOCK":
                structural_findings = [
                    f for f in (case.get("expected_safety_flags") or [])
                    if f.startswith("STRUCTURAL_")
                ]

        return BackendVerdict(
            compliance_verdict=verdict,
            artifact_verdict=_ARTIFACT_FOR.get(verdict, "PASS"),
            flags=flags,
            per_judge=per_judge,
            structural_verdict=structural_verdict,
            structural_findings=structural_findings,
            raw={"mock": True, "run_index": run_index},
        )
