"""WS-6c-DSPy-2 A1/A2/A4: the full DSPy judge trio (risk + policy + faithfulness).

Generalizes the DSPy-1 single-judge proof to the whole v2 trio assembled by
``build_trio``:

A1 — each of the three roles emits the EXACT §6 seam via ``Judge.forward``,
including the ``policy_judge`` (Mistral, no logprobs) ``confidence=None`` round-trip
that is NEVER coerced, and ``errors:[…]`` on a simulated judge failure.

A4 — the 3-judge trio through the UNCHANGED ``_apply_consensus`` reproduces the
WS-6c oracle for the post-S-BS-31 v2 owners: ``faithfulness_judge`` solo-rejects
``MISSING_ALLERGY`` / ``VALUE_MISMATCH`` (Tier-1 one-strike), ``policy_judge``
solo-rejects ``FABRICATED_CONSENT`` / ``PHI_DISCLOSURE_PRE_VERIFICATION``, and an
off-domain solo Tier-1 raise downgrades.

A2 — ``POLICY_JUDGE_LENS`` / ``FAITHFULNESS_JUDGE_LENS`` score via ``score_judge``
(incl. an out-of-lens corroboration raise counted as FP — the lower-bound
semantics), and the lens↔snapshot↔owner guard holds: every lens code is in the
taxonomy snapshot and every Tier-1 lens code is owner-resident in ``_TIER1_OWNERS``.

No network: judges are built with injected per-role predictors; confidence is read
from a synthesized response payload, exactly as the live path reads logprobs. The
predictor path imports neither ``dspy`` nor a live LM — only the ``[council]`` extra.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

# judges_dspy imports compliance_council (the [council] extra: openai + tenacity);
# the injected-predictor path needs no dspy. Skip cleanly on the offline core.
pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.runtime.council.compliance_council import (  # noqa: E402
    _TIER1_OWNERS,
    KNOWN_TAXONOMY_CODES,
    TIER_1_NEVER_EVENTS,
    ComplianceCouncil,
)
from lithrim_bench.runtime.council.judge_metric import (  # noqa: E402
    FAITHFULNESS_JUDGE_LENS,
    LENS_BY_ROLE,
    POLICY_JUDGE_LENS,
    RISK_JUDGE_LENS,
    score_judge,
)
from lithrim_bench.runtime.council.judges_dspy import (  # noqa: E402
    V2_ROLES,
    build_trio,
    evaluate_dspy,
    load_role_prompt,
)


def _raw_for_conf(conf):
    """A synthesized chat-completion carrying (or lacking) the verdict-token logprob
    — the shape ``extract_verdict_confidence`` reads. ``None`` => no logprobs (Mistral)."""
    if conf is None:
        return {"choices": [{"logprobs": None}]}
    lp = math.log(conf) if 0 < conf <= 1 else 0.0
    return {"choices": [{"logprobs": {"content": [{"token": "reject", "logprob": lp}]}}]}


def _predictor(decision, *, code=None, evidence=True, confidence=0.9, fail=False):
    """A per-role predictor for ``build_trio(predictors=…)`` — yields a decision /
    finding routed through ``Judge.forward`` so the seam is built by the production
    path. ``fail=True`` raises (simulating a transport/parse failure → errors:[…])."""
    findings = []
    if code:
        spans = [{"quote": f"q::{code}", "turn_ids": [1]}] if evidence else []
        findings = [{"taxonomy_code": code, "evidence_spans": spans}]
    raw = _raw_for_conf(confidence)

    def _predict(**_kw):
        if fail:
            raise RuntimeError("simulated judge failure: upstream 500")
        return SimpleNamespace(decision=decision, findings=findings, reason="", _raw_response=raw)

    return _predict


def _trio(specs):
    """Build the v2 trio with one injected predictor per role. ``specs`` maps each
    role to (decision, kwargs)."""
    predictors = {role: _predictor(dec, **kw) for role, (dec, kw) in specs.items()}
    return build_trio(predictors=predictors)


def _run(specs, council):
    judges = _trio(specs)
    return evaluate_dspy(judges, transcript="t", artifact="a", council=council)


# ── A1: the trio emits the seam for all three roles ─────────────────────────


def test_build_trio_yields_three_role_prompt_bound_judges():
    trio = _trio({r: ("approve", {}) for r in V2_ROLES})
    assert [j.role for j in trio] == list(V2_ROLES)
    # each judge carries its council_roles/<role>.txt text (not the default empty)
    for j in trio:
        assert j.role_prompt and "JUDGE" in j.role_prompt.upper()


def test_all_three_roles_emit_the_exact_seam():
    trio = _trio(
        {
            "risk_judge": ("reject", {"code": "WRONG_DOSAGE", "confidence": 0.92}),
            "policy_judge": ("reject", {"code": "FABRICATED_CONSENT", "confidence": None}),
            "faithfulness_judge": ("reject", {"code": "VALUE_MISMATCH", "confidence": 0.8}),
        }
    )
    for j in trio:
        seam = j.forward(transcript="t", artifact="a")
        assert set(seam) == {"model", "decision", "confidence", "findings", "errors"}
        assert seam["model"] == j.role
        assert seam["decision"] in {"approve", "needs_review", "reject"}
        assert seam["errors"] == []


def test_policy_judge_none_confidence_round_trips_uncoerced():
    """The new None-path relative to DSPy-1's risk_judge: Mistral policy_judge has
    no logprobs => confidence is None, NEVER coerced to 0.0/1.0."""
    trio = _trio(
        {
            "risk_judge": ("approve", {"confidence": 0.9}),
            "policy_judge": ("approve", {"confidence": None}),
            "faithfulness_judge": ("approve", {"confidence": 0.9}),
        }
    )
    seams = {j.role: j.forward(transcript="t", artifact="a") for j in trio}
    assert seams["policy_judge"]["confidence"] is None
    assert seams["risk_judge"]["confidence"] == 0.9


def test_errors_populated_on_simulated_failure_and_judge_excluded(council):
    """A predictor exception becomes errors:[…]; the errored judge is excluded so two
    clean approves still drive the verdict (not <2-valid needs_review)."""
    specs = {
        "risk_judge": ("reject", {"code": "WRONG_DOSAGE", "fail": True}),
        "policy_judge": ("approve", {}),
        "faithfulness_judge": ("approve", {}),
    }
    trio = _trio(specs)
    failed = trio[0].forward(transcript="t", artifact="a")
    assert failed["errors"] and "simulated judge failure" in failed["errors"][0]

    r = evaluate_dspy(trio, transcript="t", artifact="a", council=council)
    assert r["decision"] == "approve"
    assert r["reason"] != "insufficient_valid_models"


# ── A4: the trio + ported _apply_consensus reproduces the v2-owner oracle ────


def test_faithfulness_owns_missing_allergy_one_strike(council):
    r = _run(
        {
            "risk_judge": ("approve", {}),
            "policy_judge": ("approve", {}),
            "faithfulness_judge": ("reject", {"code": "MISSING_ALLERGY"}),
        },
        council,
    )
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["MISSING_ALLERGY"]


def test_faithfulness_owns_value_mismatch_one_strike(council):
    r = _run(
        {
            "risk_judge": ("approve", {}),
            "policy_judge": ("approve", {}),
            "faithfulness_judge": ("reject", {"code": "VALUE_MISMATCH"}),
        },
        council,
    )
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["VALUE_MISMATCH"]


def test_policy_owns_fabricated_consent_one_strike(council):
    r = _run(
        {
            "risk_judge": ("approve", {}),
            "policy_judge": ("reject", {"code": "FABRICATED_CONSENT"}),
            "faithfulness_judge": ("approve", {}),
        },
        council,
    )
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == [
        "FABRICATED_CONSENT"
    ]


def test_policy_owns_phi_disclosure_one_strike(council):
    r = _run(
        {
            "risk_judge": ("approve", {}),
            "policy_judge": ("reject", {"code": "PHI_DISCLOSURE_PRE_VERIFICATION"}),
            "faithfulness_judge": ("approve", {}),
        },
        council,
    )
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == [
        "PHI_DISCLOSURE_PRE_VERIFICATION"
    ]


def test_faithfulness_off_domain_tier1_single_judge_downgrades(council):
    """faithfulness solo-raising WRONG_DOSAGE (risk's Tier-1 code) is off-domain →
    downgrades to needs_review, not a one-strike reject."""
    r = _run(
        {
            "risk_judge": ("approve", {}),
            "policy_judge": ("approve", {}),
            "faithfulness_judge": ("needs_review", {"code": "WRONG_DOSAGE"}),
        },
        council,
    )
    assert r["decision"] == "needs_review"
    assert r["evidence_summary"]["tier1_triggered"] == []
    flagged = r["evidence_summary"]["tier2_flagged"]
    assert [f["violation"] for f in flagged] == ["WRONG_DOSAGE"]
    assert flagged[0]["reason"] == "tier1_off_domain_single_judge"


def test_trio_clean_negative_all_approve(council):
    r = _run({r_: ("approve", {}) for r_ in V2_ROLES}, council)
    assert r["decision"] == "approve"


# ── A2: the two new lenses score, incl. the out-of-lens corroboration FP ─────

_POLICY_CASES = [
    {"case_id": "consent_viol", "expected_safety_flags": ["FABRICATED_CONSENT"]},
    {"case_id": "phi_viol", "expected_safety_flags": ["PHI_DISCLOSURE_PRE_VERIFICATION"]},
    {"case_id": "clean", "expected_safety_flags": []},
]

_FAITH_CASES = [
    {"case_id": "value_mismatch", "expected_safety_flags": ["VALUE_MISMATCH"]},
    {"case_id": "missing_allergy", "expected_safety_flags": ["MISSING_ALLERGY"]},
    # FABRICATED_ALLERGY is risk's Tier-1 code, NOT in the faithfulness lens — a
    # faithfulness raise on it is out-of-lens corroboration (the FP lower-bound).
    {"case_id": "fab_allergy", "expected_safety_flags": ["FABRICATED_ALLERGY"]},
    {"case_id": "clean", "expected_safety_flags": []},
]


def _finding(code):
    return {"taxonomy_code": code, "evidence_spans": [{"quote": f"q::{code}", "turn_ids": [1]}]}


def test_policy_lens_perfect_judge_accepted():
    def policy(case):
        flags = set(case["expected_safety_flags"])
        return {"findings": [_finding(c) for c in flags & POLICY_JUDGE_LENS]}

    s = score_judge(policy, _POLICY_CASES, lens_codes=POLICY_JUDGE_LENS)
    assert s["accepted"] is True
    assert (s["tp"], s["fp"], s["fn"]) == (2, 0, 0)


def test_faithfulness_lens_in_scope_perfect_but_corroboration_is_out_of_lens_fp():
    """A faithfulness judge that raises every expected code — INCLUDING the
    out-of-lens FABRICATED_ALLERGY corroboration the prompt invites — is NOT
    accepted: the corroborating raise scores as an FP (the documented lower bound)."""

    def faithfulness(case):
        return {"findings": [_finding(c) for c in case["expected_safety_flags"]]}

    s = score_judge(faithfulness, _FAITH_CASES, lens_codes=FAITHFULNESS_JUDGE_LENS)
    assert s["accepted"] is False
    assert s["fp"] == 1  # the FABRICATED_ALLERGY raise — out-of-lens overreach
    assert s["fn"] == 0  # both in-lens labels (VALUE_MISMATCH, MISSING_ALLERGY) caught


def test_faithfulness_lens_owner_consistent_judge_accepted():
    """Staying silent on the out-of-lens FABRICATED_ALLERGY (leaving it to risk) is
    the owner-consistent behavior → accepted on its lens."""

    def faithfulness(case):
        flags = set(case["expected_safety_flags"])
        return {"findings": [_finding(c) for c in flags & FAITHFULNESS_JUDGE_LENS]}

    s = score_judge(faithfulness, _FAITH_CASES, lens_codes=FAITHFULNESS_JUDGE_LENS)
    assert s["accepted"] is True
    assert (s["tp"], s["fp"], s["fn"]) == (2, 0, 0)


# ── A2 guard: lens ↔ snapshot ↔ owner ───────────────────────────────────────


def test_lens_by_role_covers_the_v2_trio():
    # PACK-2c: LENS_BY_ROLE resolves FROM the active pack's snapshot ``lenses`` (the
    # source-of-truth flip), so the pin is VALUE-equality against ``pack_lenses()``,
    # not literal-identity against the module constants. The per-role constants are
    # now derived references (``RISK_JUDGE_LENS = LENS_BY_ROLE["risk_judge"]``), so
    # ``is`` would still hold incidentally — but ``==`` against the resolved pack map
    # asserts the right invariant after the flip.
    from lithrim_bench.harness.pack import pack_lenses

    assert set(LENS_BY_ROLE) == set(V2_ROLES)
    assert pack_lenses() == LENS_BY_ROLE
    assert LENS_BY_ROLE["risk_judge"] == RISK_JUDGE_LENS
    assert LENS_BY_ROLE["policy_judge"] == POLICY_JUDGE_LENS
    assert LENS_BY_ROLE["faithfulness_judge"] == FAITHFULNESS_JUDGE_LENS


def test_every_lens_code_is_in_the_taxonomy_snapshot():
    """S-BS-12: a lens code outside KNOWN_TAXONOMY_CODES is a hard error, never a
    silent score."""
    for role, lens in LENS_BY_ROLE.items():
        off_snapshot = set(lens) - KNOWN_TAXONOMY_CODES
        assert not off_snapshot, f"{role} lens has off-snapshot codes: {sorted(off_snapshot)}"


def test_every_tier1_lens_code_is_owner_resident():
    """Owner-consistency (lens (A)): for every Tier-1 code in a role's lens, the role
    must be an owner in _TIER1_OWNERS — else the lens would claim a one-strike code
    the role can never solo-fire."""
    for role, lens in LENS_BY_ROLE.items():
        for code in lens:
            if code in TIER_1_NEVER_EVENTS:
                owners = _TIER1_OWNERS.get(code, set())
                assert role in owners, (
                    f"{role} lens includes Tier-1 {code} but is not an owner {sorted(owners)}"
                )


def test_faithfulness_lens_excludes_the_unowned_tier1_codes():
    """The S-BS-12 surfacing made explicit: the four Tier-1 codes faithfulness_judge.txt
    invites but does NOT own are deliberately absent from the lens."""
    unowned = {"WRONG_DOSAGE", "FABRICATED_ALLERGY", "MISSED_ESCALATION", "SEVERITY_ESCALATION"}
    assert not (unowned & FAITHFULNESS_JUDGE_LENS)


# ── S-BS-44 GATE: the two A/B arms get byte-identical role prompts ───────────


def test_build_trio_role_prompts_byte_match_the_prompt_council():
    """S-BS-44: the DSPy arm (build_trio) and the prompt-council arm
    (_load_role_prompts) must load the SAME role-prompt text byte-for-byte, or the
    live A/B is not the like-for-like comparison it claims to be. The fix is the
    matching ``.strip()`` in load_role_prompt (judges_dspy) ↔ _load_role_prompts
    (compliance_council:527). Built with injected predictors so no live LM / network.
    """
    prompt_council = ComplianceCouncil._load_role_prompts()
    trio = build_trio(predictors={role: (lambda **_: None) for role in V2_ROLES})
    by_role = {j.role: j.role_prompt for j in trio}

    assert set(by_role) == set(V2_ROLES)
    for role in V2_ROLES:
        assert by_role[role] == prompt_council[role], (
            f"{role}: build_trio role_prompt diverges from the prompt-council's "
            f"_load_role_prompts (S-BS-44 regression — check the .strip() parity)"
        )
        # belt-and-suspenders: the helper itself matches, and is whitespace-stripped
        assert load_role_prompt(role) == prompt_council[role]
        assert by_role[role] == by_role[role].strip()
