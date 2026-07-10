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

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"


def _run_bare_core_probe(code: str) -> dict:
    """Run ``code`` in a subprocess pinned to the module docstring's bare-CE contract: the
    neutral ``_core`` pack (``LITHRIM_BENCH_PACK``/``LITHRIM_BENCH_PACKS_DIR`` REMOVED from the
    env copy) + the same offline vars :func:`_import_council` sets. The t1/t2-core tests are
    _core-contract tests — importing the council in-process freezes its module constants to
    whatever pack the ambient suite env resolves, so they must probe hermetically. The
    subprocess imports the REAL tree, so the driver-named mutations still turn them RED."""
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    env = dict(os.environ)
    env.pop("LITHRIM_BENCH_PACK", None)
    env.pop("LITHRIM_BENCH_PACKS_DIR", None)
    env.setdefault("OPENAI_API_KEY", "test-offline-key")
    env.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    env.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )
    assert proc.returncode == 0, f"bare-core probe failed:\n{proc.stdout}\n{proc.stderr}"
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def _import_council():
    """Import the council under the hermetic offline v2 config (no network)."""
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
    os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    from lithrim_bench.runtime.council import compliance_council as cc

    return cc


# ── T1 — THE FIX (headline, non-vacuous) ─────────────────────────────────────
# The synthesized seam-results (one judge solo-rejects with a grounded span on a TIER-1
# _core never-event, the other two approve) live INSIDE the probe script — the whole
# assertion body must run in the bare-core subprocess.


_T1_PROBE = r"""
import json

from lithrim_bench.runtime.council import compliance_council as cc

code = "UNSUPPORTED_ASSERTION"
seam_results = [
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
r = cc.ComplianceCouncil(models=[])._apply_consensus(seam_results)
print("__JSON__" + json.dumps({
    "in_tier1": code in cc.TIER_1_NEVER_EVENTS,
    "in_dual": code in cc.DUAL_PILLAR_CODES,
    "decision": r["decision"],
    "tier1_triggered": [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]],
    "artifact_verdict": r["artifact_verdict"],
}))
"""


def test_t1_unclassified_tier1_code_now_gates():
    """A TIER-1 _core code (UNSUPPORTED_ASSERTION) in none of the hardcoded pillar sets is
    now dual-pillar (the carve-out), so the solo grounded one-strike GATES → reject.

    risk_judge OWNS UNSUPPORTED_ASSERTION in the _core snapshot, so the single grounded fire
    is the never-event one-strike. Pre-fix the code was dropped from both pillars and the
    verdict defaulted to approve. The driver-named MUTATION (revert the
    ``DUAL_PILLAR_CODES = DUAL_PILLAR_CODES | _CONSENSUS_PILLAR_1_UNCLASSIFIED`` rebind) turns
    this RED (``decision == "approve"``, the bug). Runs as a bare-core subprocess probe —
    _core-contract + import-order-coupled, per the module docstring."""
    out = _run_bare_core_probe(_T1_PROBE)
    assert out["in_tier1"] is True  # pack-resolved (_core)
    assert out["in_dual"] is True  # the carve-out rescued it
    assert out["decision"] == "reject"
    assert out["tier1_triggered"] == ["UNSUPPORTED_ASSERTION"]
    assert out["artifact_verdict"] == "BLOCK"


# ── T2 — the invariant holds (zero unclassified tiered codes) ─────────────────


def test_t2_every_tiered_code_is_pillar_classified():
    """The realized invariant: for the active (_core) pack EVERY tiered code is in at least
    one pillar set — i.e. ZERO unclassified tiered codes remain after the carve-out."""
    cc = _import_council()
    tiered = set(cc.TIER_1_NEVER_EVENTS) | set(cc.TIER_2_HIGH_RISK) | set(cc.TIER_3_MEDIUM)
    classified = cc.ARTIFACT_CODES | cc.CONVERSATION_CODES | cc.DUAL_PILLAR_CODES
    unclassified = tiered - classified
    assert unclassified == set(), f"unclassified tiered codes remain: {sorted(unclassified)}"


_T2_CORE_PROBE = r"""
import json

from lithrim_bench.runtime.council import compliance_council as cc

print("__JSON__" + json.dumps({
    "tier1": sorted(cc.TIER_1_NEVER_EVENTS),
    "not_dual": sorted(set(cc.TIER_1_NEVER_EVENTS) - cc.DUAL_PILLAR_CODES),
}))
"""


def test_t2_core_tier1_codes_all_dual_pillar():
    """Stronger: every _core TIER-1 never-event (all 5) is now dual-pillar — none can be
    silently dropped on the CE path. Runs as a bare-core subprocess probe — _core-contract +
    import-order-coupled, per the module docstring."""
    out = _run_bare_core_probe(_T2_CORE_PROBE)
    assert out["tier1"], "the _core snapshot must declare TIER-1 never-events (non-vacuous)"
    assert out["not_dual"] == [], f"still not pillar-classified: {out['not_dual']}"


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
    """The acc4973 council baseline via the ONE resolution seam (S-REL-18) — public-mode
    SKIP when the baseline commit is unavailable (fresh-cut public history)."""
    import tests._seam_freeze as sf

    base = sf._resolve_baseline(REPO_ROOT, _COUNCIL_REL)
    if base is None:
        pytest.skip("public-mode: baseline commit unavailable; attested in the private history")
    return base.splitlines(keepends=True)


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
    to ``acc4973``. Extracts the method source from both via AST and asserts equality. Public
    mode (S-REL-18): the same section is hash-pinned (``_FROZEN_SECTION_SHA256``), so the
    attestation stays live without the private history."""
    import ast

    import tests._seam_freeze as sf

    cur_text = _council_cur_text()
    base_text = sf._resolve_baseline(REPO_ROOT, _COUNCIL_REL)
    if base_text is None:
        sf._assert_sections_match_hash_pins(
            "compliance_council.py", sf._council_frozen_sections(cur_text)
        )
        return

    def _method_src(text: str) -> str:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ComplianceCouncil":
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == "_apply_consensus":
                        return ast.get_source_segment(text, sub)
        raise AssertionError("_apply_consensus not found")

    assert _method_src(cur_text) == _method_src(base_text), (
        "_apply_consensus body drifted vs acc4973 (must be byte-frozen)"
    )
