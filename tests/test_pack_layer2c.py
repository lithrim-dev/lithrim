"""PACK-2c layer-2c — the council's ROSTER IDENTITY + the LENS authority un-froze: the FROZEN
``compliance_council`` now builds its v2 roster by iterating the active pack's ``production_judges``
(``pack_production_judges``), and ``judge_metric.LENS_BY_ROLE`` resolves from the pack's ``lenses``
(``pack_lenses``). This is the strangler-fig ENDGAME: after 2c the core council carries only the
domain-agnostic MECHANISM; ALL domain specifics (taxonomy, owners, roster identity, lens authority)
live in the pack.

The identity↔deployment SPLIT: the pack carries WHICH judges run; the CORE keeps HOW each runs
(``_ROLE_DEPLOYMENT`` — provider / Azure model id / capability flags; infra ∉ a domain pack). A pack
judge with no core deployment fails CLEAN at construction (A8).

Core-env legs (no ``openai``): the accessors follow the named pack; healthcare lens/roster
equivalence to the ``acc4973`` values (0-delta); ``council_roster()`` stays CANONICAL and
subset-validates a 2nd judge-bearing pack (S-BS-125 (a)); the freeze guard accepts the 4th carve-out
and is non-vacuous (revert FAILS; a smuggled marker-less line in the roster hunk FAILS).
``[council]``-env legs (``openai``, debuglithrim): the IMPORTED council's roster == ``acc4973``
identity+order (A2); the AIRTIGHT subprocess DECOUPLE proof — ``LITHRIM_BENCH_PACK=story_audit`` →
the council assembles story_audit's 2-judge roster AND ``LENS_BY_ROLE`` == story_audit's lenses with
ZERO core edits (A3); and the deployment-boundary fail-clean (A8).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import pack
from lithrim_bench.runtime.council.judge_metric import (
    FAITHFULNESS_JUDGE_LENS,
    LENS_BY_ROLE,
    POLICY_JUDGE_LENS,
    RISK_JUDGE_LENS,
)

from ._seam_freeze import (
    assert_compliance_council_carveouts_only,
    assert_council_carveouts_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"

# The acc4973 lens VALUES, transcribed from judge_metric.py:54-106 — the 0-delta target the
# pack-resolution must preserve (A1).
_ACC4973_LENSES = {
    "risk_judge": {
        "MISSED_ESCALATION",
        "SEVERITY_ESCALATION",
        "WRONG_DOSAGE",
        "MEDICATION_NOT_IN_TRANSCRIPT",
        "FABRICATED_ALLERGY",
    },
    "policy_judge": {"FABRICATED_CONSENT", "PHI_DISCLOSURE_PRE_VERIFICATION"},
    "faithfulness_judge": {
        "VALUE_MISMATCH",
        "MISSING_ALLERGY",
        "HALLUCINATED_DETAIL",
        "FABRICATED_HISTORY",
        "MEDICATION_NOT_IN_TRANSCRIPT",
        "UPCODING_RISK",
        "WRONG_CODE",
        "PROTOCOL_STEP_SKIPPED",
        "INCOMPLETE_DOCUMENTATION",
        "DURATION_FABRICATION",
        "NEGATION_REVERSAL",
    },
}

# The acc4973 v2 roster IDENTITY+ORDER — (name, provider, supports_logprobs,
# supports_response_format_json, prompt_role). NOT the model strings: those are env-resolved
# (council_model / AZURE_OPENAI_DEPLOYMENT_*) and are deliberately excluded from the 0-delta pin.
_ACC4973_ROSTER = [
    ("risk_judge", "openai", True, True, "risk_judge"),
    ("policy_judge", "mistral", False, True, "policy_judge"),
    ("faithfulness_judge", "meta", True, True, "faithfulness_judge"),
]

# council_roster() = CouncilModel names ∪ owner roles; source_message_judge is owner-only.
_ROSTER_5 = {
    "risk_judge",
    "policy_judge",
    "faithfulness_judge",
    "behavior_judge",
    "source_message_judge",
}

_STORY_PACK = "story_audit"
_STORY_ROSTER = ["risk_judge", "policy_judge"]
_STORY_LENSES = {
    "risk_judge": {"FABRICATED_QUOTE", "UNVERIFIED_CLAIM"},
    "policy_judge": {"FABRICATED_SOURCE", "MISLEADING_FRAMING"},
}
_NONDEPLOY_PACK = "_nondeployable_fixture"


def _as_sets(lens_map: dict) -> dict:
    return {role: set(codes) for role, codes in lens_map.items()}


# ───────────────────── core-env: the lens accessor + the source flip (A1) ─────────────────────


def test_pack_lenses_accessor_follows_the_named_pack():
    """A1 accessor leg: ``pack_lenses`` is pack-parametrized — the active ``healthcare`` pack yields
    the real lens map, ``story_audit`` yields its DIFFERENT story-domain lenses."""
    assert _as_sets(pack.pack_lenses("healthcare")) == _ACC4973_LENSES
    assert _as_sets(pack.pack_lenses(_STORY_PACK)) == _STORY_LENSES


def test_pack_lenses_default_is_the_active_pack():
    assert pack.pack_lenses() == pack.pack_lenses("healthcare")


def test_lens_by_role_equals_the_acc4973_values_under_healthcare():
    """A1: under the active healthcare pack, the resolved ``LENS_BY_ROLE`` (+ the derived constants)
    == the acc4973 lens values (per-role frozenset equality) — the source flip is 0-delta."""
    assert _as_sets(LENS_BY_ROLE) == _ACC4973_LENSES
    assert set(RISK_JUDGE_LENS) == _ACC4973_LENSES["risk_judge"]
    assert set(POLICY_JUDGE_LENS) == _ACC4973_LENSES["policy_judge"]
    assert set(FAITHFULNESS_JUDGE_LENS) == _ACC4973_LENSES["faithfulness_judge"]


def test_pack_production_judges_accessor_follows_the_named_pack():
    """A2/A3 accessor leg: ``pack_production_judges`` is pack-parametrized + ORDER-preserving — the
    healthcare trio vs story_audit's 2-judge subset (the roster identity source-of-truth)."""
    assert pack.pack_production_judges("healthcare") == [
        "risk_judge",
        "policy_judge",
        "faithfulness_judge",
    ]
    assert pack.pack_production_judges(_STORY_PACK) == _STORY_ROSTER


# ───────────────── core-env: council_roster canonical + subset-validates 2nd pack (S-BS-125 a) ─────────────────


def test_council_roster_is_canonical_and_subset_validates_story_audit():
    """S-BS-125 (a): ``council_roster()`` stays CANONICAL (the core capability universe — the 5
    deployable/prompt-able/owner roles), NOT the active pack's identity. A 2nd judge-bearing pack
    (story_audit) declares a strict SUBSET of the roster, so it validates correctly under the
    canonical roster — re-pointing it to the active pack would be WRONG (the active snapshot does not
    define the core's full capability set). The CouncilModel deployment literals are byte-preserved,
    so the AST name-collect is untouched (value 0-delta = 5)."""
    assert set(pack.council_roster()) == _ROSTER_5
    assert len(pack.council_roster()) == 5
    # story_audit's declared judges are a strict subset of the canonical roster → the judges gate
    # accepts them (no PackConsistencyError) even though they are NOT healthcare's production trio.
    assert set(_STORY_ROSTER) < pack.council_roster()
    pack.assert_judges_known(
        _STORY_ROSTER,
        prompt_stems=_ROSTER_5,  # a 5-stem roster (the pure-function check; not read off disk)
        pack=_STORY_PACK,
    )


def test_council_roster_stays_canonical_under_story_audit_subprocess():
    """S-BS-125 (a), airtight: even with ``LITHRIM_BENCH_PACK=story_audit`` active, ``council_roster()``
    stays the canonical 5 (it reads DEFAULT_PACK's identity, not the active pack). A subprocess
    because the accessor is ``lru_cache``d; openai-free (AST + snapshot, no council import)."""
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = _STORY_PACK
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
        f"council_roster() followed story_audit (must stay canonical): {sorted(roster)}"
    )


# ───────────────────── core-env: the freeze guard's 4th carve-out + non-vacuity (A5) ─────────────────────


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


def test_freeze_guard_passes_on_the_real_tree_with_four_carveouts():
    """A5: the guard ACCEPTS the FOUR authorized carve-outs (prompts-dir + tiers + owners + roster)
    on the real tree, including the S-BS-124 per-line hardening."""
    assert_compliance_council_carveouts_only(REPO_ROOT)  # does not raise


def test_freeze_guard_fails_on_reverting_the_roster_carveout():
    """A5 lower bound: removing the PACK-2c roster carve-out call signature
    (``.pack_production_judges()``) → the guard FAILS, so reverting the roster un-freeze cannot pass
    silently."""
    base = _council_base_lines()
    reverted = _council_cur_text().replace(".pack_production_judges()", ".REVERTED()")
    with pytest.raises(AssertionError, match="missing an authorized carve-out"):
        assert_council_carveouts_only(base, reverted)


def test_freeze_guard_fails_on_a_smuggled_line_in_the_roster_hunk():
    """A5 upper bound (the user's explicit addendum): a marker-less CODE line smuggled INSIDE the
    (marker-bearing) roster carve-out hunk FAILS — proving the new hunk is held to the same S-BS-124
    per-line bar as the 1b/2b carve-outs (no extra line can ride along)."""
    base = _council_base_lines()
    anchor = "_pack_judges = __import__("
    cur = _council_cur_text()
    assert anchor in cur  # the substitution will land (else the test is vacuous)
    smuggled = cur.replace(
        anchor, "                SMUGGLED_BACKDOOR = True\n                " + anchor, 1
    )
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(base, smuggled)


# ───────────────── [council]-env: the imported council's roster (A2) + the DECOUPLE proof (A3) + A8 ─────────────────


def _council_env(pack_id: str | None = None) -> dict:
    env = dict(os.environ)
    env.update(
        OPENAI_API_KEY="test-offline-key",
        LITHRIM_LLM_PROVIDER="openai",
        COMPLIANCE_COUNCIL_VERSION="v2",
    )
    if pack_id is not None:
        env["LITHRIM_BENCH_PACK"] = pack_id
    return env


def test_imported_council_roster_is_acc4973_identity_and_order():
    """A2: the IMPORTED council assembles its v2 roster FROM the healthcare pack's
    ``production_judges`` — the resolved (name, provider, supports_logprobs,
    supports_response_format_json, prompt_role) tuples == the acc4973 roster, IN ORDER. The
    env-resolved model strings are intentionally excluded (deployment binding stays core)."""
    pytest.importorskip("openai")
    pytest.importorskip("tenacity")
    os.environ.setdefault("OPENAI_API_KEY", "test-offline-key")
    os.environ.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    os.environ.setdefault("COMPLIANCE_COUNCIL_VERSION", "v2")
    from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil

    roster = [
        (m.name, m.provider, m.supports_logprobs, m.supports_response_format_json, m.prompt_role)
        for m in ComplianceCouncil().models
    ]
    assert roster == _ACC4973_ROSTER


def test_council_follows_story_audit_roster_and_lens_subprocess():
    """A3 — the A-DECOUPLE gate: a FRESH interpreter with ``LITHRIM_BENCH_PACK=story_audit`` imports
    the council, which assembles a roster of EXACTLY story_audit's 2-judge subset AND whose
    ``LENS_BY_ROLE`` == story_audit's (DIFFERENT) lenses — with ZERO core edits. A subprocess because
    both the roster and LENS_BY_ROLE bind once at module/instance build time."""
    pytest.importorskip("openai")
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; "
            "from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil; "
            "from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE; "
            "c = ComplianceCouncil(); "
            "print(json.dumps({"
            "'roster': [m.name for m in c.models], "
            "'lenses': {k: sorted(v) for k, v in LENS_BY_ROLE.items()}}))",
        ],
        cwd=REPO_ROOT,
        env=_council_env(_STORY_PACK),
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, f"council import under story_audit failed:\n{out.stderr}"
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["roster"] == _STORY_ROSTER, f"roster did NOT follow story_audit: {got['roster']}"
    assert _as_sets(got["lenses"]) == _STORY_LENSES, (
        f"LENS_BY_ROLE did NOT follow story_audit: {got['lenses']}"
    )
    # definitively NOT the healthcare roster/lenses (the decouple is real, not a coincidence)
    assert got["roster"] != ["risk_judge", "policy_judge", "faithfulness_judge"]
    assert "faithfulness_judge" not in got["lenses"]


def test_council_fails_clean_on_a_nondeployable_pack_judge_subprocess():
    """A8 (the user's explicit addendum): the deployment boundary. ``_nondeployable_fixture`` declares
    ``production_judges = [risk_judge, behavior_judge]`` — behavior_judge is a CANONICAL-roster role
    (it passes the judges gate) that is NOT in the core ``_ROLE_DEPLOYMENT`` trio. The council
    fails CLEAN at construction: a ``KeyError`` naming the non-deployable judge, not a silent
    mis-roster. Packs SUBSET known deployable identities; a brand-new deployable judge needs core
    deployment support."""
    pytest.importorskip("openai")
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil; "
            "ComplianceCouncil()",
        ],
        cwd=REPO_ROOT,
        env=_council_env(_NONDEPLOY_PACK),
        capture_output=True,
        text=True,
    )
    assert out.returncode != 0, "council construction must FAIL on a non-deployable pack judge"
    assert "behavior_judge" in out.stderr, (
        f"the fail-clean error must name the non-deployable judge:\n{out.stderr}"
    )
    assert "KeyError" in out.stderr, (
        f"expected a fail-clean KeyError at construction:\n{out.stderr}"
    )
