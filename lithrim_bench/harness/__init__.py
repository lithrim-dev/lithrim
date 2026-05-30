"""WS-0 walking-skeleton harness.

A domain-agnostic, tool-grounded eval/calibration harness composed *over* the
live verification stack (``:8002 /v1/pipeline/evaluate``), not vendored from it
(vendoring = WS-6). This package is the spine: ingest -> grade -> persist ->
harness-side grounding -> composite + calibration report.

WS-0 proves the vertical on exactly one case. The grading seam was proven live
2026-05-30 (baseline captured); the persist/grounding/correction/report code is
built and tested entirely offline against that baseline, so the cycle costs $0
in new paid calls. See ``.devloop/prompts/bench-salvage_phaseWS-0_*``.
"""
