"""TunedMockBackend: simulates the strong-baseline LLM-as-judge from
Lail & Markham (arXiv 2604.13717, RewardBench 2). Critically, blind
to structural defects by contract — that's the paper claim being
simulated, not a limitation of the mock.

Why this exists:

The paper's main argument is "structural validation is orthogonal to
*any* improvement in the semantic judge, including a tuned ensemble
baseline." Until the tuned baseline exists in the harness, that claim
is rhetorical. With it, the contrast is a single CLI invocation:

  worst-of(TunedMockBackend, structural_validator)
        vs
  TunedMockBackend alone

Simulation contract:

- K ensemble members independently decide; aggregate via majority vote.
  At K=3 with per-member accuracy p=0.85, majority-vote accuracy is
  P(2 of 3 correct) ≈ 0.94 — the published ceiling.
- Flag attachment per member is independent. Composed flags are the
  union of flags from members that voted reject.
- Semantic correctness comes from criteria-injection: each member is
  told what categories to look for. Modeled here as a high
  per-member catch rate on semantic flags only.
- **structural_verdict is always None**. Criteria-injection improves
  semantic reasoning; it does not turn a meaning-validator into a
  spec-validator. This is the categorical-blindness invariant.

Determinism: same (noise_seed, case_id, member_index) -> same draws.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput

_ARTIFACT_FOR = {"reject": "BLOCK", "needs_review": "WARN", "approve": "PASS"}


def _seed(noise_seed: int, case_id: str, member: int) -> int:
    h = hashlib.sha1(f"{noise_seed}|{case_id}|{member}".encode()).hexdigest()
    return int(h[:8], 16)


class TunedMockBackend(BackendClient):
    def __init__(
        self,
        *,
        ensemble_size: int = 3,
        per_member_semantic_accuracy: float = 0.85,
        per_member_flag_attachment_rate: float = 0.80,
        false_positive_rate: float = 0.02,
        noise_seed: int = 0,
    ):
        if ensemble_size < 1:
            raise ValueError("ensemble_size must be >= 1")
        self.ensemble_size = ensemble_size
        self.per_member_semantic_accuracy = per_member_semantic_accuracy
        self.per_member_flag_attachment_rate = per_member_flag_attachment_rate
        self.false_positive_rate = false_positive_rate
        self.noise_seed = noise_seed
        self._call_index: dict[str, int] = {}

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="TunedMockBackend",
            backend_version="0.1.0",
            judge_model="mock-tuned",
            judge_model_version="criteria-injection-plus-ensembling",
            extra={
                "ensemble_size": self.ensemble_size,
                "per_member_semantic_accuracy": self.per_member_semantic_accuracy,
                "per_member_flag_attachment_rate": self.per_member_flag_attachment_rate,
                "false_positive_rate": self.false_positive_rate,
                "noise_seed": self.noise_seed,
                "lit_anchor": "Lail+Markham arXiv 2604.13717 RewardBench 2",
                "structural_blind_by_contract": True,
            },
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        case_id = case["case_id"]
        run_index = self._call_index.get(case_id, 0)
        self._call_index[case_id] = run_index + 1

        expected_flags = case.get("expected_safety_flags") or []
        semantic_flags = [f for f in expected_flags if not f.startswith("STRUCTURAL_")]

        member_decisions: list[str] = []
        member_flag_sets: list[list[str]] = []

        for k in range(self.ensemble_size):
            rng = random.Random(_seed(self.noise_seed, f"{case_id}::{run_index}", k))
            if not semantic_flags:
                if rng.random() < self.false_positive_rate:
                    member_decisions.append("needs_review")
                    member_flag_sets.append([])
                else:
                    member_decisions.append("approve")
                    member_flag_sets.append([])
                continue
            if rng.random() < self.per_member_semantic_accuracy:
                attached = [
                    f for f in semantic_flags
                    if rng.random() < self.per_member_flag_attachment_rate
                ]
                member_decisions.append("reject")
                member_flag_sets.append(attached)
            else:
                member_decisions.append("approve")
                member_flag_sets.append([])

        verdict_counts = Counter(member_decisions)
        modal_verdict = verdict_counts.most_common(1)[0][0]

        reject_flag_sets = [
            set(flags) for d, flags in zip(member_decisions, member_flag_sets, strict=False) if d == "reject"
        ]
        composed_flags = sorted(set().union(*reject_flag_sets)) if reject_flag_sets else []

        per_judge: dict[str, JudgeOutput] = {}
        for i, (d, flags) in enumerate(zip(member_decisions, member_flag_sets, strict=False)):
            name = f"tuned_member_{i}"
            per_judge[name] = JudgeOutput(judge_name=name, verdict=d, flags=list(flags))

        return BackendVerdict(
            compliance_verdict=modal_verdict,
            artifact_verdict=_ARTIFACT_FOR.get(modal_verdict, "PASS"),
            flags=composed_flags,
            per_judge=per_judge,
            structural_verdict=None,
            structural_findings=[],
            raw={
                "tuned_mock": True,
                "run_index": run_index,
                "member_decisions": member_decisions,
            },
        )
