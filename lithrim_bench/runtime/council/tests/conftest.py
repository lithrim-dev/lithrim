"""Shared fixtures for the council consensus oracle.

The offline oracle drives ``ComplianceCouncil._apply_consensus`` directly with
synthesized per-judge result dicts — NO network, NO LLM. Construction of the
``ComplianceCouncil`` builds an OpenAI client *object* (no network call); the
env defaults below keep that hermetic and pin the v2 path.
"""
from __future__ import annotations

import os

import pytest

# Set BEFORE the council's settings singleton is constructed (first import).
# setdefault so the live-smoke run can still override via real env / .env.
os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")  # no Azure validation offline
os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")


@pytest.fixture(scope="module")
def council():
    from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil

    return ComplianceCouncil()


@pytest.fixture
def judge():
    """Build one per-judge result dict in the shape ``_apply_consensus`` consumes.

    ``{model, decision, confidence, errors, findings:[{taxonomy_code, evidence_spans}]}``
    — the §6 hybrid per-judge boundary. ``evidence=False`` emits a finding with
    no spans (the stripped-evidence path); ``errors`` non-empty marks the judge
    invalid (excluded from consensus).
    """

    def _make(model, decision, *, code=None, evidence=True, confidence=0.9, errors=None):
        findings = []
        if code:
            spans = [{"quote": f"q::{code}", "turn_ids": [1]}] if evidence else []
            findings = [{"taxonomy_code": code, "evidence_spans": spans}]
        return {
            "model": model,
            "decision": decision,
            "confidence": confidence,
            "errors": errors or [],
            "findings": findings,
        }

    return _make
