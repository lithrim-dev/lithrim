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
    confidence: float = 0.0
    # Per-judge rationale (council summary/rationale). Populated from
    # JudgeVote.reason; "" when the backend exposes no per-judge reasoning.
    # Needed to root-cause calibration misses (e.g. a false MEDICATION_NOT_IN_
    # TRANSCRIPT) offline without re-running the paid council.
    reason: str = ""


@dataclass(frozen=True)
class BackendVerdict:
    compliance_verdict: str
    artifact_verdict: str
    flags: list[str]
    per_judge: dict[str, JudgeOutput] | None = None
    structural_verdict: str | None = None
    structural_findings: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    # Rich Finding payloads alongside the flat-code surfaces above. Additive
    # so the BRS-0b §7 byte-identical invariance test (which keys off `flags`
    # and `structural_findings`) stays intact. Backends that don't expose
    # rich findings leave these empty; downstream analysis falls back to the
    # flat code lists.
    findings_rich: list[dict[str, Any]] = field(default_factory=list)
    structural_findings_rich: list[dict[str, Any]] = field(default_factory=list)


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
