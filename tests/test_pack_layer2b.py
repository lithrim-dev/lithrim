"""PACK-2b layer-2b — the council's Tier-1 OWNER-MAP un-froze: the FROZEN ``compliance_council``
now reads ``_TIER1_OWNERS`` FROM the active pack's snapshot (``pack_tier1_owners``), the direct
analogue of the layer-1b taxonomy flip. This is the equivalence pin that REPLACES byte-identity
for the owner-map: the consensus oracle (``test_consensus.py``) + the lens⊆owners invariant
(``test_trio_dspy.py``) pin BEHAVIOR; this pins the source flip is value-preserving (0-delta) AND
genuinely reads from the pack (non-vacuous, both directions).

Core-env legs (no ``openai``): the ``pack_tier1_owners`` accessor follows the named pack, the
snapshot⇄acc4973-literal equivalence, the ``council_roster`` value is 0-delta under the flip, and
the relaxed freeze guard's owner-map non-vacuity + the S-BS-124 per-line hardening (via the pure
predicate). ``[council]``-env legs (``openai``, debuglithrim): the genuine council⇄snapshot owner
equivalence (imports the council) + the AIRTIGHT subprocess proof that the council's
``_TIER1_OWNERS`` FOLLOWS the active pack (``LITHRIM_BENCH_PACK=_tiers_fixture`` → the sentinel
owner-map, not the real 8).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import pack

from ._seam_freeze import (
    assert_compliance_council_carveouts_only,
    assert_council_carveouts_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"

# The acc4973 _TIER1_OWNERS LITERAL, transcribed — the 0-delta target the carve-out must preserve.
_ACC4973_OWNERS = {
    "WRONG_DOSAGE": {"behavior_judge", "source_message_judge", "risk_judge"},
    "MISSING_ALLERGY": {"behavior_judge", "source_message_judge", "faithfulness_judge"},
    "FABRICATED_ALLERGY": {"risk_judge", "behavior_judge", "source_message_judge"},
    "FABRICATED_CONSENT": {"behavior_judge", "source_message_judge", "policy_judge"},
    "MISSED_ESCALATION": {"behavior_judge", "risk_judge"},
    "SEVERITY_ESCALATION": {"behavior_judge", "risk_judge"},
    "PHI_DISCLOSURE_PRE_VERIFICATION": {"policy_judge"},
    "VALUE_MISMATCH": {"behavior_judge", "faithfulness_judge"},
}
# council_roster() = CouncilModel names ∪ owner roles; source_message_judge is owner-only.
_ROSTER_5 = {
    "risk_judge",
    "policy_judge",
    "faithfulness_judge",
    "behavior_judge",
    "source_message_judge",
}

_FIXTURE_PACK = "_tiers_fixture"
_FIXTURE_OWNERS = {"FIXTURE_SENTINEL_T1": {"FIXTURE_SENTINEL_OWNER"}}


# ───────────────────────── core-env: the accessor + the source flip ─────────────────────────


def _as_sets(owner_map: dict) -> dict:
    return {code: set(owners) for code, owners in owner_map.items()}


def test_pack_tier1_owners_accessor_follows_the_named_pack():
    """A3(i) accessor leg: ``pack_tier1_owners`` is pack-parametrized — the active ``healthcare``
    pack yields the real 8-entry owner-map, the fixture pack yields its sentinel. (The
    council-binding leg is ``test_council_follows_active_pack_owners_subprocess``.)"""
    assert _as_sets(pack.pack_tier1_owners("healthcare")) == _ACC4973_OWNERS
    assert _as_sets(pack.pack_tier1_owners(_FIXTURE_PACK)) == _FIXTURE_OWNERS


def test_pack_tier1_owners_default_is_the_active_pack():
    """``pack_tier1_owners()`` with no arg resolves the active pack (``healthcare`` by default)."""
    assert pack.pack_tier1_owners() == pack.pack_tier1_owners("healthcare")


def test_snapshot_owners_equal_the_acc4973_literal():
    """A2 (core side): the snapshot ``tier1_owners`` == the acc4973 ``_TIER1_OWNERS`` literal
    (8 entries, sets equal) — the value the carve-out must preserve, pinned WITHOUT a council
    import (this leg runs offline; the council leg is below)."""
    owners = _as_sets(pack.pack_tier1_owners("healthcare"))
    assert owners == _ACC4973_OWNERS
    assert len(owners) == 8


def test_council_roster_unchanged_by_the_owner_reposition():
    """A2/D-D: ``council_roster()`` re-points its owner leg to the snapshot (D3a) but the VALUE is
    0-delta — still the 5 roles (the CouncilModel names ∪ the owner roles, incl. the owner-only
    ``source_message_judge``). Proves the re-point did not drop or add a role."""
    assert set(pack.council_roster()) == _ROSTER_5
    assert len(pack.council_roster()) == 5


def test_council_roster_is_pack_independent_under_a_fixture_pack():
    """Regression guard (the council's roster is its VALIDATION IDENTITY, not active-pack DATA):
    ``council_roster()`` stays CANONICAL (the 5 real roles incl. the owner-only
    ``source_message_judge``) even under ``LITHRIM_BENCH_PACK=_tiers_fixture`` — it reads
    ``DEFAULT_PACK``'s owner-map, NOT the active pack's sentinel. If it followed the active pack the
    fixture's reused healthcare ``council_roles`` would fail the judges gate at council import (the
    bug this pins). A subprocess because the accessor is ``lru_cache``d; openai-free (AST + snapshot,
    no council import)."""
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = _FIXTURE_PACK
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from lithrim_bench.harness import pack; "
            "print(json.dumps(sorted(pack.council_roster())))",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    roster = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert roster == _ROSTER_5, (
        f"council_roster() followed the fixture pack (must stay canonical): {sorted(roster)}"
    )
    assert "source_message_judge" in roster


# ─────────────────── core-env: the relaxed freeze guard's owner-map non-vacuity (A3 ii) ──────────────────


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


def test_freeze_guard_passes_on_the_real_tree_with_three_carveouts():
    """The relaxed guard ACCEPTS the THREE authorized carve-outs (prompts-dir + tiers + owners)
    on the real tree — including the PACK-2b per-line hardening (all carve-out code lines carry a
    marker; the relocated provenance comments are exempt)."""
    assert_compliance_council_carveouts_only(REPO_ROOT)  # does not raise


def test_freeze_guard_fails_on_reverting_the_owners_carveout():
    """Lower bound (A3 ii): removing the PACK-2b owner-map carve-out call signature
    (``.pack_tier1_owners()``) → the guard FAILS, so reverting the owner-map un-freeze cannot pass
    silently."""
    base = _council_base_lines()
    reverted = _council_cur_text().replace(".pack_tier1_owners()", ".REVERTED()")
    with pytest.raises(AssertionError, match="missing an authorized carve-out"):
        assert_council_carveouts_only(base, reverted)


def test_freeze_guard_fails_on_a_smuggled_code_line_in_an_authorized_hunk():
    """S-BS-124 hardening: a marker-less CODE line smuggled INSIDE the (marker-bearing) owner-map
    carve-out hunk passes the hunk-level check but FAILS the per-line check — closing the residual
    where the old guard let an extra line ride along."""
    base = _council_base_lines()
    anchor = "_TIER1_OWNERS: Dict[str, set] = dict("
    cur = _council_cur_text()
    assert anchor in cur  # the substitution will land (else the test is vacuous)
    smuggled = cur.replace(anchor, "SMUGGLED_BACKDOOR = True\n" + anchor, 1)
    with pytest.raises(AssertionError, match="unauthorized code line inside an authorized"):
        assert_council_carveouts_only(base, smuggled)


# ───────────────────────── [council]-env: the council ⇄ snapshot owner pin ─────────────────────────


def _import_council():
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
    os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    from lithrim_bench.runtime.council import compliance_council as cc

    return cc


def test_council_owners_equal_the_pack_snapshot():
    """A2: the IMPORTED council resolved its ``_TIER1_OWNERS`` FROM the active pack — it == the
    snapshot ``tier1_owners`` == the acc4973 literal (8 entries, sets equal). This is the genuine
    council⇄snapshot owner equivalence the core-env legs cannot make (no council)."""
    cc = _import_council()
    resolved = _as_sets(cc._TIER1_OWNERS)
    assert resolved == _ACC4973_OWNERS
    assert resolved == _as_sets(pack.pack_tier1_owners("healthcare"))
    assert len(cc._TIER1_OWNERS) == 8


def test_council_consensus_membership_is_frozenset_value_stable():
    """A2: the carve-out makes the owner sets ``frozenset`` (was mutable ``set`` literals pre-2b);
    the only reader is the ``_apply_consensus`` one-strike MEMBERSHIP test (``code in owners``),
    which is identical on a frozenset — no reader mutates ``_TIER1_OWNERS`` (grep-verified)."""
    cc = _import_council()
    for owners in cc._TIER1_OWNERS.values():
        assert isinstance(owners, frozenset)
    # membership (the :2077 semantics) is value-stable
    assert "risk_judge" in cc._TIER1_OWNERS["FABRICATED_ALLERGY"]
    assert "policy_judge" not in cc._TIER1_OWNERS["WRONG_DOSAGE"]


def test_council_follows_active_pack_owners_subprocess():
    """A3(i) the AIRTIGHT non-vacuity: a FRESH interpreter with
    ``LITHRIM_BENCH_PACK=_tiers_fixture`` imports the council, whose ``_TIER1_OWNERS`` becomes the
    fixture's SENTINEL owner-map — proving the FROZEN council reads its owner-map FROM the active
    pack, not a hardcode. A subprocess (not an in-process reload) because the council binds
    ``_TIER1_OWNERS`` once at module import."""
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
            "print(json.dumps({k: sorted(v) for k, v in c._TIER1_OWNERS.items()}))",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, f"council import under the fixture pack failed:\n{out.stderr}"
    owners = {
        code: set(roles) for code, roles in json.loads(out.stdout.strip().splitlines()[-1]).items()
    }
    assert owners == _FIXTURE_OWNERS, f"council did NOT follow the fixture pack: {owners}"
    # definitively NOT the healthcare owner-map (disjoint codes AND disjoint roles)
    assert set(owners).isdisjoint(_ACC4973_OWNERS)
    real_roles = set().union(*_ACC4973_OWNERS.values())
    assert set().union(*owners.values()).isdisjoint(real_roles)
