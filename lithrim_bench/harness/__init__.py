"""WS-0 walking-skeleton harness.

A domain-agnostic, tool-grounded eval/calibration harness composed *over* the
live verification stack (``:8002 /v1/pipeline/evaluate``), not vendored from it
(vendoring = WS-6). This package is the spine: ingest -> grade -> persist ->
harness-side grounding -> composite + calibration report.

WS-0 proves the vertical on exactly one case. The grading seam was proven live
2026-05-30 (baseline captured); the persist/grounding/correction/report code is
built and tested entirely offline against that baseline, so the cycle costs $0
in new paid calls. See ``.devloop/prompts/bench-salvage_phaseWS-0_*``.

WS-3 adds the structural-floor direction to grounding (``ground(..., http_client=)``
flips PASS→BLOCK on a bench-accepted structural contract the council missed); the
floor correction record is ``correction.build_floor_correction``.
"""

from .correction import build_correction, build_floor_correction, emit
from .grade import build_request_body, grade_live, grade_replay
from .grounding import GroundedResult, PresenceCheck, Verdict, VerificationContract, ground
from .ontology import Ontology, VerificationContractDecl, load_ontology
from .report import calibration, composite

__all__ = [
    "ground",
    "GroundedResult",
    "VerificationContract",
    "PresenceCheck",
    "Verdict",
    "Ontology",
    "VerificationContractDecl",
    "load_ontology",
    "grade_live",
    "grade_replay",
    "build_request_body",
    "build_correction",
    "build_floor_correction",
    "emit",
    "composite",
    "calibration",
]
