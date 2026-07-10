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
# S-BS-134: pin the active pack so the council's taxonomy/owners/roster resolve to healthcare's
# v2 set when these tests run BY BARE PATH. The repo-root ``tests/conftest.py`` sets the same pin,
# but it is not an ancestor of this dir — so ``pytest lithrim_bench/runtime/council/tests/…`` ran
# under the neutral ``_core`` default and the consensus oracle's healthcare expectations failed
# (12/20). ``setdefault`` so the full-suite run + any explicit override still win.
# PACK-DIST-1: pin only when healthcare is discoverable (it is now an external pack); a bare CE
# checkout stays on the neutral _core default and these council oracle tests skip-when-absent.
try:
    from lithrim_bench.harness import pack as _pd_pack

    _pd_pack._pack_root("healthcare")
    os.environ.setdefault("LITHRIM_BENCH_PACK", "healthcare")
except FileNotFoundError:
    pass


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
