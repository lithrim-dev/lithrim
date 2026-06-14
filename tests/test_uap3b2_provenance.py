"""UAP-3b-2 — S-BS-72: the withstands ruling embedded in the run-PROVENANCE blob
(stream-2, ``GET /v1/runs/{id}/audit``), plus the re-pinned frozen-seam 0-delta and
the A5 by-construction guard.

The S-BS-72 integration test is dspy/openai-gated (the authored trio's seam), $0 via
injected per-role predictors (no Azure call) + an injected ``SqliteProvenanceStore``
(a tmp doc-shim DB). The frozen + guard + BFF-projection tests run on default deps /
the [bff] extra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.runtime.council.withstands import apply_withstands_gate

from ._seam_freeze import (
    assert_clinical_ontology_seam_frozen,
    assert_compliance_council_carveouts_only,
    assert_council_roles_relocated_only,
    assert_judges_dspy_consensus_seam_frozen,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seam(role: str, decision: str, codes: list[str]) -> dict:
    return {
        "model": role,
        "decision": decision,
        "confidence": 0.9,
        "findings": [
            {"taxonomy_code": c, "evidence_spans": [{"quote": "x", "turn_ids": []}]} for c in codes
        ],
        "errors": [],
    }


def _clean_case() -> dict:
    return {
        "transcript": "Agent verified identity first, then discussed the visit.",
        "artifacts": [{"content": "n"}],
    }


# ─────────────────────────── frozen + A5 guard (default deps) ───────────────────────


def test_frozen_seam_zero_delta():
    """A4 — the D2 provenance work + the D3 entity surface add ZERO lines to the frozen
    consensus seam + the per-judge seam + the metric + the committed seeds.

    BYOC-1: judges_dspy.py is no longer whole-file-pinned — ``build_judge_lm`` +
    ``build_trio`` are the authorized provider-seam change (driver A6). Its CONSENSUS seam
    is instead asserted byte-frozen by :func:`assert_judges_dspy_consensus_seam_frozen`."""
    # PACK-2: compliance_council.py is no longer whole-file-pinned — the live council
    # globs the role prompts itself, so relocating council_roles/ into the pack required
    # an AUTHORIZED path-only carve-out of its _ROLE_PROMPTS_DIR; and council_roles/ itself
    # relocated. Both are asserted by the carve-out guards below.
    # PACK-2c: judge_metric.py is no longer whole-file-pinned either — the lens un-freeze
    # (``LENS_BY_ROLE`` resolves from the active pack's ``lenses`` via ``pack_lenses()``;
    # judge_metric is NOT under any freeze guard) relocates the lens AUTHORITY into the
    # snapshot. The lens VALUES stay 0-delta, pinned by the EQUIVALENCE pin
    # (``tests/test_pack_layer2c.py`` A1 + ``test_trio_dspy.py``) — byte-identity is REPLACED
    # by value-equivalence, the same relaxation BYOC-1 applied to judges_dspy.py and PACK-2 to
    # compliance_council.py. The frozen-seam asserts below stay (the consensus seam, the council
    # carve-outs, the relocated role prompts, the seeds, the clinical ontology).
    assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)
    assert_compliance_council_carveouts_only(REPO_ROOT)
    assert_council_roles_relocated_only(REPO_ROOT)
    # PACK-DIST-1: ws0_default.json is now the neutral blank-slate default agent (0 clinical
    # strings; ontology_path → packs/_core); the clinical scribe-replay agent relocated to the
    # external healthcare pack repo, so the old healthcare-ontology_path seed pin is retired.
    # clinical_v1.json's consensus/owner seam stays frozen; only verification_contracts
    # may grow additively (GROUND-FLOOR-1's record_presence contract).
    assert_clinical_ontology_seam_frozen(REPO_ROOT)


def test_gate_cannot_relabel_true_case():
    """A5 (re-pinned) — a genuinely-correct in-lens finding is NEVER suppressed: risk
    raises WRONG_DOSAGE (its own Tier-1 lens code), it withstands, verdict stays
    reject. The S-BS-72/A6 work does not weaken the by-construction invariant."""
    ont = load_ontology()
    results = [
        _seam("risk_judge", "reject", ["WRONG_DOSAGE"]),
        _seam("policy_judge", "approve", []),
        _seam("faithfulness_judge", "approve", []),
    ]
    corrected, decisions = apply_withstands_gate(results, ontology=ont, case=_clean_case())
    assert [f["taxonomy_code"] for f in corrected[0]["findings"]] == ["WRONG_DOSAGE"]
    assert corrected[0]["decision"] == "reject"
    assert decisions[0].decision == "withstand"


# ─────────────────────────── BFF projection ([bff] extra) ───────────────────────────


def test_run_audit_report_projects_withstands():
    """The §2B stream-2 report surfaces the embedded ruling (a 1-line projection); a
    non-gated run (no key) degrades to an empty list, never a KeyError."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    if str(REPO_ROOT / "apps" / "bff") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "apps" / "bff"))
    import app as bff

    doc = {
        "verdict": "approve",
        "stage_results": {"semantic": {"judge_votes": []}},
        "withstands_decisions": [
            {
                "role": "risk_judge",
                "signals_weighed": {},
                "decision": "corrected",
                "what_failed": [],
            }
        ],
    }
    report = bff._run_audit_report(doc, "run-x")
    assert report["withstands"] == doc["withstands_decisions"]
    # a run with no ruling → empty list (back-compat).
    assert bff._run_audit_report({"stage_results": {}}, "run-y")["withstands"] == []
