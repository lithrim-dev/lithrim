"""CONSENSUS-PILLAR-INVARIANT-1 — every tiered code is pillar-classified.

The bug (live audit, run ``f5754825``): ``_apply_consensus`` correctly computes
``tier1_triggered`` (pack-resolved tier sets), then splits findings into
conversation/artifact pillars by membership in the HARDCODED healthcare pillar
sets (``ARTIFACT_CODES``/``CONVERSATION_CODES``/``DUAL_PILLAR_CODES``). A TIER-1
code that is in ``TIER_1_NEVER_EVENTS`` (pack-resolved → contains the neutral
``_core`` codes) but in NONE of the pillar sets is filtered out of both
``conv_tier1`` and ``art_tier1`` → ``_pillar_verdict([], …)`` → approve/PASS →
the one-strike reject is silently dropped → verdict defaults to PASS. Real
fabrications PASS on the CE/_core path.

The fix (CONSENSUS-PILLAR-INVARIANT-1): a module-level, pack-derived authorized
carve-out (the same pattern as the PACK-1b ``TIER_*`` carve-out) that defaults any
unclassified tiered code to dual-pillar, placed immediately after the pillar sets so
``_apply_consensus``'s BODY stays byte-frozen vs ``acc4973``.

These tests run bare-CE (no ``LITHRIM_BENCH_PACKS_DIR``) on the neutral ``_core`` pack,
whose TIER-1 codes (UNSUPPORTED_ASSERTION/SOURCE_CONTRADICTION/…) were exactly the
dropped codes — so the headline fix is exercised on the shipped default tier.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"
_SEAM_BASELINE = "acc4973"


def _import_council():
    """Import the council under the hermetic offline v2 config (no network)."""
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
    os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    from lithrim_bench.runtime.council import compliance_council as cc

    return cc


def _seam_results(code: str):
    """A synthesized seam-results list: one judge solo-rejects with a grounded span on
    ``code`` (a TIER-1 never-event for _core), the other two approve."""
    return [
        {
            "model": "risk_judge",
            "decision": "reject",
            "confidence": 0.99,
            "errors": [],
            "findings": [
                {
                    "taxonomy_code": code,
                    "evidence_spans": [{"quote": "unlimited storage", "turn_ids": []}],
                }
            ],
        },
        {"model": "policy_judge", "decision": "approve", "confidence": 0.9, "errors": [], "findings": []},
        {"model": "faithfulness_judge", "decision": "approve", "confidence": 0.9, "errors": [], "findings": []},
    ]


# ── T1 — THE FIX (headline, non-vacuous) ─────────────────────────────────────


def test_t1_unclassified_tier1_code_now_gates():
    """A TIER-1 _core code (UNSUPPORTED_ASSERTION) in none of the hardcoded pillar sets is
    now dual-pillar (the carve-out), so the solo grounded one-strike GATES → reject.

    risk_judge OWNS UNSUPPORTED_ASSERTION in the _core snapshot, so the single grounded fire
    is the never-event one-strike. Pre-fix the code was dropped from both pillars and the
    verdict defaulted to approve. The driver-named MUTATION (revert the
    ``DUAL_PILLAR_CODES = DUAL_PILLAR_CODES | _CONSENSUS_PILLAR_1_UNCLASSIFIED`` rebind) turns
    this RED (``decision == "approve"``, the bug)."""
    cc = _import_council()
    assert "UNSUPPORTED_ASSERTION" in cc.TIER_1_NEVER_EVENTS  # pack-resolved (_core)
    assert "UNSUPPORTED_ASSERTION" in cc.DUAL_PILLAR_CODES  # the carve-out rescued it
    r = cc.ComplianceCouncil(models=[])._apply_consensus(_seam_results("UNSUPPORTED_ASSERTION"))
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["UNSUPPORTED_ASSERTION"]
    assert r["artifact_verdict"] == "BLOCK"


# ── T2 — the invariant holds (zero unclassified tiered codes) ─────────────────


def test_t2_every_tiered_code_is_pillar_classified():
    """The realized invariant: for the active (_core) pack EVERY tiered code is in at least
    one pillar set — i.e. ZERO unclassified tiered codes remain after the carve-out."""
    cc = _import_council()
    tiered = set(cc.TIER_1_NEVER_EVENTS) | set(cc.TIER_2_HIGH_RISK) | set(cc.TIER_3_MEDIUM)
    classified = cc.ARTIFACT_CODES | cc.CONVERSATION_CODES | cc.DUAL_PILLAR_CODES
    unclassified = tiered - classified
    assert unclassified == set(), f"unclassified tiered codes remain: {sorted(unclassified)}"


def test_t2_core_tier1_codes_all_dual_pillar():
    """Stronger: every _core TIER-1 never-event (all 5) is now dual-pillar — none can be
    silently dropped on the CE path."""
    cc = _import_council()
    for code in cc.TIER_1_NEVER_EVENTS:
        assert code in cc.DUAL_PILLAR_CODES, f"{code} still not pillar-classified"


# ── T3 — anti-overreach / classified codes are unaffected ─────────────────────


def test_t3_already_classified_artifact_code_unchanged():
    """honest-Δ / anti-overreach: the carve-out adds ONLY previously-unclassified codes to
    DUAL_PILLAR_CODES. A healthcare-style ARTIFACT code (WRONG_DOSAGE, in ARTIFACT_CODES) is
    NOT moved into DUAL_PILLAR_CODES — its single-pillar classification is unchanged. The fix
    rescues dropped codes; it never reclassifies an already-pillared code."""
    cc = _import_council()
    assert "WRONG_DOSAGE" in cc.ARTIFACT_CODES  # an established artifact code
    assert "WRONG_DOSAGE" not in cc.DUAL_PILLAR_CODES  # NOT promoted to dual by the carve-out


def test_t3_carveout_is_exactly_the_unclassified_set():
    """The rescued set == exactly the previously-unclassified tiered codes (it adds nothing
    that was already pillared). Re-derives the unclassified set the same way the carve-out
    does and asserts DUAL_PILLAR_CODES is the original dual set ∪ that unclassified set."""
    cc = _import_council()
    tiered = set(cc.TIER_1_NEVER_EVENTS) | set(cc.TIER_2_HIGH_RISK) | set(cc.TIER_3_MEDIUM)
    unclassified = tiered - cc.ARTIFACT_CODES - cc.CONVERSATION_CODES
    # Every code the carve-out claims to have rescued is genuinely tiered-but-unpillared.
    assert unclassified <= cc.DUAL_PILLAR_CODES
    # And the carve-out did not pull a non-tiered, non-original code into dual.
    original_dual = {"MISSED_ESCALATION", "SEVERITY_ESCALATION"}
    expected_dual = original_dual | unclassified
    assert expected_dual == cc.DUAL_PILLAR_CODES


# ── T4 — the seam guard still passes (the amendment is valid + non-vacuous) ───


def _council_base_lines():
    return subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{_COUNCIL_REL}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines(keepends=True)


def _council_cur_text():
    return (REPO_ROOT / _COUNCIL_REL).read_text()


def test_t4_seam_guard_passes_with_the_pillar_carveout():
    """A5 upper bound: the real tree (the 4 pack carve-outs + the 6b/6c deletions + the NEW
    CONSENSUS-PILLAR-INVARIANT-1 module-level carve-out) is admitted by the guard — the new
    lines carry the ``_CONSENSUS_PILLAR_1`` marker now authorized in _COUNCIL_AUTHORIZED_MARKERS."""
    from tests._seam_freeze import assert_council_carveouts_only

    assert "_CONSENSUS_PILLAR_1" in _council_cur_text()  # the carve-out is present
    assert_council_carveouts_only(_council_base_lines(), _council_cur_text())  # does not raise


def test_t4_marker_is_load_bearing_non_vacuity(monkeypatch):
    """NON-VACUITY: with ``_CONSENSUS_PILLAR_1`` REMOVED from _COUNCIL_AUTHORIZED_MARKERS, the
    SAME assertion RAISES 'unauthorized' on the real tree — proving the new marker is what
    authorizes the carve-out (not some pre-existing marker). The driver-named MUTATION."""
    import tests._seam_freeze as sf

    pruned = tuple(m for m in sf._COUNCIL_AUTHORIZED_MARKERS if m != "_CONSENSUS_PILLAR_1")
    assert "_CONSENSUS_PILLAR_1" in sf._COUNCIL_AUTHORIZED_MARKERS  # it IS there now (else vacuous)
    monkeypatch.setattr(sf, "_COUNCIL_AUTHORIZED_MARKERS", pruned)
    with pytest.raises(AssertionError, match="unauthorized"):
        sf.assert_council_carveouts_only(_council_base_lines(), _council_cur_text())


def test_t4_apply_consensus_body_byte_identical_to_acc4973():
    """The carve-out is module-level ONLY: ``_apply_consensus``'s method body is byte-identical
    to ``acc4973``. Extracts the method source from both via AST and asserts equality."""
    import ast

    def _method_src(text: str) -> str:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ComplianceCouncil":
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == "_apply_consensus":
                        return ast.get_source_segment(text, sub)
        raise AssertionError("_apply_consensus not found")

    base = _method_src("".join(_council_base_lines()))
    cur = _method_src(_council_cur_text())
    assert cur == base, "_apply_consensus body drifted vs acc4973 (must be byte-frozen)"
