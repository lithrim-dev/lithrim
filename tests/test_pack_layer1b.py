"""PACK-1b layer-1b — the council's taxonomy un-froze: the FROZEN ``compliance_council`` now
reads its 3 tier sets FROM the active pack's snapshot (``pack_tiers``), so the snapshot is the
single source of truth. This is the equivalence pin that REPLACES byte-identity for the
taxonomy: the consensus oracle (``test_consensus.py``) pins BEHAVIOR; this pins the source flip
is value-preserving (0-delta) AND genuinely reads from the pack (non-vacuous, both directions).

Core-env legs (no ``openai``): the ``pack_tiers`` accessor follows the named pack, the
snapshot⇄loader equivalence, and the relaxed freeze guard's non-vacuity (via its pure
predicate). ``[council]``-env legs (``openai``, debuglithrim): the genuine council⇄snapshot
equivalence (imports the council) + the AIRTIGHT subprocess proof that the council FOLLOWS the
active pack (``LITHRIM_BENCH_PACK=_tiers_fixture`` → sentinel codes, not the healthcare 19).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import pack
from lithrim_bench.taxonomy import load_taxonomy

from ._seam_freeze import (
    assert_compliance_council_carveouts_only,
    assert_council_carveouts_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"

# The acc4973 tier-set LITERALS, transcribed — the 0-delta target the carve-out must preserve.
_ACC4973_TIERS = {
    "TIER_1_NEVER_EVENTS": {
        "MISSED_ESCALATION", "WRONG_DOSAGE", "MISSING_ALLERGY", "FABRICATED_ALLERGY",
        "SEVERITY_ESCALATION", "PHI_DISCLOSURE_PRE_VERIFICATION", "FABRICATED_CONSENT",
        "VALUE_MISMATCH",
    },
    "TIER_2_HIGH_RISK": {
        "HALLUCINATED_DETAIL", "MEDICATION_NOT_IN_TRANSCRIPT", "FABRICATED_HISTORY",
        "WRONG_CODE", "WRONG_CATEGORY_CODE", "UPCODING_RISK", "PROTOCOL_STEP_SKIPPED",
    },
    "TIER_3_MEDIUM": {
        "DURATION_FABRICATION", "NEGATION_REVERSAL", "IMPLICIT_CONFIRMATION_OF_RECORD",
        "INCOMPLETE_DOCUMENTATION",
    },
}
_KNOWN_19 = set().union(*_ACC4973_TIERS.values())

_FIXTURE_PACK = "_tiers_fixture"
_FIXTURE_CODES = {"FIXTURE_SENTINEL_T1", "FIXTURE_SENTINEL_T2", "FIXTURE_SENTINEL_T3"}


# ───────────────────────── core-env: the accessor + the source flip ─────────────────────────


def test_pack_import_is_heavy_dep_free():
    """A1: importing the pack accessor pulls no ``openai`` — even where it is INSTALLED
    (debuglithrim), so the core OSS env stays dependency-light. A fresh interpreter so a prior
    test's council import can't pollute ``sys.modules``."""
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, lithrim_bench.harness.pack as p; "
            "assert 'openai' not in sys.modules, 'openai got imported by harness.pack'; "
            "print(len(p.pack_taxonomy_codes()))",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "19"


def test_pack_tiers_accessor_follows_the_named_pack():
    """A3(i) accessor leg: ``pack_tiers`` is pack-parametrized — the active ``healthcare`` pack
    yields the 19 real codes, the fixture pack yields its sentinels. (The council-binding leg
    is ``test_council_follows_active_pack_subprocess``.)"""
    hc = pack.pack_tiers("healthcare")
    assert {k: set(v) for k, v in hc.items()} == _ACC4973_TIERS
    fx = pack.pack_tiers(_FIXTURE_PACK)
    assert set(fx["TIER_1_NEVER_EVENTS"]) == {"FIXTURE_SENTINEL_T1"}
    assert set().union(*fx.values()) == _FIXTURE_CODES


def test_pack_tiers_default_is_the_active_pack():
    """``pack_tiers()`` with no arg resolves the active pack (``healthcare`` by default)."""
    assert pack.pack_tiers() == pack.pack_tiers("healthcare")
    assert set(pack.pack_taxonomy_codes()) == _KNOWN_19


def test_snapshot_equals_taxonomy_loader():
    """A2 (core side): the snapshot tiers == ``taxonomy.load_taxonomy()`` == 19 — no council
    import (this leg runs in the offline core env; the council leg is below)."""
    tax = load_taxonomy()
    assert tax.tier_1 == frozenset(_ACC4973_TIERS["TIER_1_NEVER_EVENTS"])
    assert tax.tier_2 == frozenset(_ACC4973_TIERS["TIER_2_HIGH_RISK"])
    assert tax.tier_3 == frozenset(_ACC4973_TIERS["TIER_3_MEDIUM"])
    assert set(tax.known_codes) == _KNOWN_19
    assert len(tax.known_codes) == 19


# ─────────────────── core-env: the relaxed freeze guard's non-vacuity (A3 ii) ───────────────────


def _council_base_lines() -> list[str]:
    """The acc4973 council baseline via the ONE resolution seam (S-REL-18) — public-mode
    SKIP when the baseline commit is unavailable (fresh-cut public history)."""
    import tests._seam_freeze as sf

    base = sf._resolve_baseline(REPO_ROOT, _COUNCIL_REL)
    if base is None:
        pytest.skip("public-mode: baseline commit unavailable; attested in the private history")
    return base.splitlines(keepends=True)


def _council_cur_text() -> str:
    return (REPO_ROOT / _COUNCIL_REL).read_text()


def test_freeze_guard_passes_on_the_real_tree():
    """The relaxed guard ACCEPTS the two authorized carve-outs (taxonomy + prompts-dir)."""
    assert_compliance_council_carveouts_only(REPO_ROOT)  # does not raise


def test_freeze_guard_fails_on_an_unauthorized_edit():
    """Upper bound: a benign edit OUTSIDE the carve-outs (a frozen ``__init__`` line) makes a
    changed hunk with no authorized marker → the guard FAILS (rejects edits elsewhere)."""
    base = _council_base_lines()
    tampered = _council_cur_text().replace(
        "self.models = list(models)", "self.models = list(models)  # tamper", 1
    )
    assert "# tamper" in tampered  # the substitution landed (else the test is vacuous)
    with pytest.raises(AssertionError, match="unauthorized changed hunk"):
        assert_council_carveouts_only(base, tampered)


def test_freeze_guard_fails_on_reverting_the_taxonomy_carveout():
    """Lower bound: removing the PACK-1b taxonomy carve-out call signature (``.pack_tiers()``)
    → the guard FAILS, so reverting the un-freeze cannot pass silently."""
    base = _council_base_lines()
    reverted = _council_cur_text().replace(".pack_tiers()", ".REVERTED()")
    with pytest.raises(AssertionError, match="missing an authorized carve-out"):
        assert_council_carveouts_only(base, reverted)


def test_freeze_guard_fails_on_reverting_the_prompts_carveout():
    """Lower bound: removing the PACK-2 prompts-dir carve-out call signature
    (``.pack_prompts_path()``) → the guard FAILS (the guard stays non-vacuous for PACK-2 too)."""
    base = _council_base_lines()
    reverted = _council_cur_text().replace(".pack_prompts_path()", ".REVERTED()")
    with pytest.raises(AssertionError, match="missing an authorized carve-out"):
        assert_council_carveouts_only(base, reverted)


# ───────────────────────── [council]-env: the council ⇄ snapshot pin ─────────────────────────


def _import_council():
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
    os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    from lithrim_bench.runtime.council import compliance_council as cc

    return cc


def test_council_taxonomy_equals_the_pack_snapshot():
    """A2: the IMPORTED council resolved its ``TIER_1/2/3`` + ``KNOWN_TAXONOMY_CODES`` FROM the
    active pack — they == the snapshot tiers == ``load_taxonomy()`` == the acc4973 literals == 19.
    This is the genuine council⇄snapshot equivalence the core-env legs cannot make (no council)."""
    cc = _import_council()
    assert set(cc.TIER_1_NEVER_EVENTS) == _ACC4973_TIERS["TIER_1_NEVER_EVENTS"]
    assert set(cc.TIER_2_HIGH_RISK) == _ACC4973_TIERS["TIER_2_HIGH_RISK"]
    assert set(cc.TIER_3_MEDIUM) == _ACC4973_TIERS["TIER_3_MEDIUM"]
    assert set(cc.KNOWN_TAXONOMY_CODES) == _KNOWN_19 == set(load_taxonomy().known_codes)
    assert len(cc.KNOWN_TAXONOMY_CODES) == 19
    # frozenset now (was a mutable ``set`` literal pre-1b; no reader mutates it — grep-verified).
    assert isinstance(cc.KNOWN_TAXONOMY_CODES, frozenset)


def test_dspy_taxonomy_prompt_is_byte_identical():
    """A2: ``default_taxonomy_context()`` renders the tiers via ``sorted(TIER_*)``, so the
    snapshot's (alphabetical) order is irrelevant and the judge PROMPT is byte-identical to the
    pre-1b literals — no live-judge drift."""
    _import_council()
    from lithrim_bench.runtime.council.judges_dspy import default_taxonomy_context

    ctx = default_taxonomy_context()
    assert f"{sorted(_ACC4973_TIERS['TIER_1_NEVER_EVENTS'])}" in ctx
    assert f"{sorted(_ACC4973_TIERS['TIER_2_HIGH_RISK'])}" in ctx
    assert f"{sorted(_ACC4973_TIERS['TIER_3_MEDIUM'])}" in ctx


def test_council_follows_active_pack_subprocess():
    """A3(i) the AIRTIGHT non-vacuity: a FRESH interpreter with
    ``LITHRIM_BENCH_PACK=_tiers_fixture`` imports the council, whose ``KNOWN_TAXONOMY_CODES``
    becomes the fixture's SENTINELS — proving the FROZEN council reads its taxonomy FROM the
    active pack, not a hardcode. A subprocess (not an in-process reload) because the council
    binds its tier sets once at module import."""
    pytest.importorskip("openai")
    env = dict(os.environ)
    env.update(
        LITHRIM_BENCH_PACK=_FIXTURE_PACK,
        OPENAI_API_KEY="test-offline-key",
        LITHRIM_LLM_PROVIDER="openai",
        COMPLIANCE_COUNCIL_VERSION="v2",
    )
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from lithrim_bench.runtime.council import compliance_council as c; "
            "print(json.dumps(sorted(c.KNOWN_TAXONOMY_CODES)))",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, f"council import under the fixture pack failed:\n{out.stderr}"
    codes = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert codes == _FIXTURE_CODES, f"council did NOT follow the fixture pack: {sorted(codes)}"
    assert codes.isdisjoint(_KNOWN_19)  # definitively NOT the healthcare hardcode
