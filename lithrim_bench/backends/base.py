"""BackendClient interface.

The harness is backend-agnostic: any client that returns BackendVerdict
in response to a case payload can be plugged in. Concrete clients:
MockBackend (tests + paper-spec instability demonstration without the
real backend running), LithrimHttpBackend (POST /v1/analyze).

per_judge is optional: a backend that exposes per-judge outputs (the
3-judge council scores) populates it for the three-layer
decomposition. A backend that doesn't (or a mock that emits only the
top-level verdict) leaves it None; downstream analysis then reports
layer-1 metrics only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class JudgeOutput:
    judge_name: str
    verdict: str
    flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BackendVerdict:
    compliance_verdict: str
    artifact_verdict: str
    flags: list[str]
    per_judge: dict[str, JudgeOutput] | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class BackendPin:
    """Identifying info recorded with every run for the eval-spec §1.6 pinned tuple."""

    backend: str
    backend_version: str
    judge_model: str | None = None
    judge_model_version: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class BackendClient(ABC):
    @property
    @abstractmethod
    def pin(self) -> BackendPin:
        """Identifier recorded in every run NDJSON row; refusing to mix incompatible pins is the
        eval spec's `--allow-cross-pin` policy enforced at analysis time."""

    @abstractmethod
    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        """Run the backend pipeline on one case row from the pack JSONL.

        Implementations MUST be re-callable on the same case to produce
        the distribution the determinism protocol measures.
        """
