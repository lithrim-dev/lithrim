"""GROUND-FLOOR-SOURCE-1 — the core-generic ``source_grounding`` suppress executor.

The answer⊆source faithfulness floor: the S-BS-7 token-presence mechanism generalized.
It disproves a ``SOURCE_CONTRADICTION`` / ``UNSUPPORTED_ASSERTION`` finding iff EVERY
salient (stemmed) claim the ANSWER makes is present in the SOURCE — so a verbatim-faithful
answer can never be falsely BLOCKED — while a real fabrication (claims absent from the
source) is NEVER cleared (the anti-masking guarantee, A2).

Bare-CE, offline, pure-stdlib: no network, no LM, no pack. The two case shapes are the
REAL ones from the live diagnosis (run_002_faithful / a fabricating twin).
"""

from __future__ import annotations

from lithrim_bench.harness import grounding
from lithrim_bench.harness.grounding import SourceGrounding, ground, suppress_executors
from lithrim_bench.harness.ontology import VerificationContractDecl, from_dict

_TRANSCRIPT = (
    "You are a support assistant. Answer ONLY with facts from the source. "
    "How much storage does the Pro plan include? "
    "Pro plan: 100 GB storage; email support; $20/month."
)
_FAITHFUL_ANSWER = "The Pro plan includes 100 GB of storage with email support, at $20/month."
_FABRICATING_ANSWER = (
    "Yes! The Pro plan comes with unlimited storage, free forever, "
    "plus a lifetime money-back guarantee."
)


def _case(answer: str) -> dict:
    return {
        "transcript": _TRANSCRIPT,
        "artifacts": [{"content": answer}],
    }


def _decl(flag_code: str, params: dict | None = None) -> VerificationContractDecl:
    return VerificationContractDecl(
        flag_code=flag_code,
        question="Is every claim in the answer present in the source?",
        contract_type="source_grounding",
        params=params or {},
        version="source_grounding/1",
    )


# ─────────────────────────── A1 — suppress the faithful false positive ───────────────────────────


def test_a1_faithful_answer_suppresses_source_contradiction():
    """A1: every salient token in the verbatim-faithful answer is present in the source
    (``includes``/``storage`` matched via the light stemmer) → SOURCE_CONTRADICTION disproved."""
    sg = SourceGrounding(_decl("SOURCE_CONTRADICTION"))
    v = sg.check({"code": "SOURCE_CONTRADICTION"}, _case(_FAITHFUL_ANSWER))
    assert v.disproved is True
    assert "present in the source" in v.reason


def test_a1_faithful_answer_suppresses_unsupported_assertion():
    """A1: the same faithful answer clears UNSUPPORTED_ASSERTION (answer asserts nothing absent)."""
    sg = SourceGrounding(_decl("UNSUPPORTED_ASSERTION"))
    v = sg.check({"code": "UNSUPPORTED_ASSERTION"}, _case(_FAITHFUL_ANSWER))
    assert v.disproved is True


# ─────────────── A2 — THE ANTI-MASKING GUARANTEE (load-bearing, non-vacuous) ───────────────


def test_a2_fabricating_answer_is_never_suppressed():
    """A2 (load-bearing): the fabricating answer asserts content absent from the source
    (unlimited / lifetime / guarantee) → disproved is False, and the reason NAMES the
    ungrounded fabricated tokens. A floor that masks a real fabrication is a BLOCKING failure.

    NON-VACUITY: weaken the executor's disproved rule from ALL-tokens-present to
    ANY-token-present (the driver-named mutation) and THIS test goes red — the fabricating
    answer shares grounded tokens like ``storage``/``plan`` with the source, so an ANY rule
    would falsely suppress it.
    """
    sg = SourceGrounding(_decl("SOURCE_CONTRADICTION"))
    v = sg.check({"code": "SOURCE_CONTRADICTION"}, _case(_FABRICATING_ANSWER))
    assert v.disproved is False
    # The verdict NAMES the ungrounded fabrications: the reason carries a sample, the evidence
    # the full set. The distinctive fabricated claims must be surfaced for the SME / audit.
    surfaced = f"{v.reason} {v.evidence}".lower()
    assert "unlimited" in surfaced
    assert "lifetime" in surfaced
    assert "guarantee" in surfaced
    # the reason states the finding stands (never clear by silence)
    assert "the finding stands" in v.reason


# ─────────────── A3 — ground() integration, the GOVERNED FLIP, both directions ───────────────


def _ont():
    """A synthetic _core-shaped ontology that attaches source_grounding to BOTH TIER-1 flags."""
    return from_dict(
        {
            "ontology_version": "source_grounding_test/1",
            "domain": "generic",
            "flags": [
                {
                    "flag": "SOURCE_CONTRADICTION",
                    "category": "faithfulness",
                    "definition": "contradicts the source",
                    "when_to_use": "x",
                    "when_NOT_to_use": "y",
                    "owner_roles": ["faithfulness_judge"],
                    "tier": "TIER_1",
                    "gradeable": True,
                },
                {
                    "flag": "UNSUPPORTED_ASSERTION",
                    "category": "accuracy",
                    "definition": "asserts beyond the source",
                    "when_to_use": "x",
                    "when_NOT_to_use": "y",
                    "owner_roles": ["risk_judge"],
                    "tier": "TIER_1",
                    "gradeable": True,
                },
                {
                    "flag": "MISSING_CONTEXT",
                    "category": "completeness",
                    "definition": "omits required context",
                    "when_to_use": "x",
                    "when_NOT_to_use": "y",
                    "owner_roles": [],
                    "tier": "TIER_2",
                    "gradeable": True,
                },
            ],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "SOURCE_CONTRADICTION",
                    "question": "?",
                    "contract_type": "source_grounding",
                    "params": {},
                    "version": "source_grounding/1",
                },
                {
                    "flag_code": "UNSUPPORTED_ASSERTION",
                    "question": "?",
                    "contract_type": "source_grounding",
                    "params": {},
                    "version": "source_grounding/1",
                },
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
                "block_at_or_above": 0.5,
                "warn_above": 0.0,
            },
        }
    )


def _result():
    return {
        "verdict": "BLOCK",
        "findings": [
            {"code": "SOURCE_CONTRADICTION", "severity": "HIGH", "detail": "contradicts source"},
            {"code": "UNSUPPORTED_ASSERTION", "severity": "HIGH", "detail": "asserts beyond"},
            {"code": "MISSING_CONTEXT", "severity": "MEDIUM", "detail": "omits a caveat"},
        ],
        "semantic": {
            "evidence": [
                {"violation_code": "SOURCE_CONTRADICTION", "spans": []},
                {"violation_code": "UNSUPPORTED_ASSERTION", "spans": []},
                {"violation_code": "MISSING_CONTEXT", "spans": []},
            ]
        },
    }


def test_a3_governed_flip_faithful_case_suppresses_both_tier1_keeps_missing_context():
    """A3: ground() over the FAITHFUL case suppresses BOTH TIER-1 flags but leaves the
    MEDIUM MISSING_CONTEXT active (the floor does NOT touch the omission flag — honest scope).
    The residual rescore on the lone MEDIUM is BLOCK (0.5 >= block_at_or_above=0.5)."""
    g = ground(_result(), _case(_FAITHFUL_ANSWER), ontology=_ont())
    suppressed = {s["finding"]["code"] for s in g.suppressed}
    active = {f["code"] for f in g.active}
    assert suppressed == {"SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION"}
    assert active == {"MISSING_CONTEXT"}
    # The honest residual: a lone MEDIUM still BLOCKs at the 0.5 threshold (documented, not a bug).
    assert g.verdict == "BLOCK"


def test_a3_governed_flip_fabricating_case_suppresses_nothing():
    """A3 (the anti-masking guarantee at the ground() level): the FABRICATING case suppresses
    NOTHING — all three findings stay active, verdict stays BLOCK."""
    g = ground(_result(), _case(_FABRICATING_ANSWER), ontology=_ont())
    assert g.suppressed == []
    assert {f["code"] for f in g.active} == {
        "SOURCE_CONTRADICTION",
        "UNSUPPORTED_ASSERTION",
        "MISSING_CONTEXT",
    }
    assert g.verdict == "BLOCK"


# ─────────────────────────── A4 — defaults / robustness ───────────────────────────


def test_a4_constructs_with_empty_params():
    """A4: no param is required — SourceGrounding({}) constructs (safe defaults everywhere)."""
    sg = SourceGrounding(_decl("SOURCE_CONTRADICTION", params={}))
    assert sg.flag_code == "SOURCE_CONTRADICTION"


def test_a4_missing_artifact_or_source_never_clears_by_silence():
    """A4: a missing artifact OR a missing source → disproved=False (never raise, never clear)."""
    sg = SourceGrounding(_decl("SOURCE_CONTRADICTION"))
    # missing artifact (no answer to ground) -> nothing salient grounded -> stands
    v_no_artifact = sg.check({"code": "SOURCE_CONTRADICTION"}, {"transcript": _TRANSCRIPT})
    assert v_no_artifact.disproved is False
    # an answer but no source -> nothing can be grounded -> stands
    v_no_source = sg.check(
        {"code": "SOURCE_CONTRADICTION"}, {"artifacts": [{"content": _FAITHFUL_ANSWER}]}
    )
    assert v_no_source.disproved is False
    # entirely empty case -> stands
    assert sg.check({"code": "SOURCE_CONTRADICTION"}, {}).disproved is False


def test_a4_noise_tokens_override_honored():
    """A4: noise_tokens drop a would-be-ungrounded token from the salient set, so an otherwise
    faithful answer with one extra noise word still suppresses."""
    case = _case("The Pro plan includes 100 GB of storage with email support, at $20/month okayyy.")
    # "okayyy" is not in the source -> without the override it keeps the finding open
    assert (
        SourceGrounding(_decl("SOURCE_CONTRADICTION"))
        .check({"code": "SOURCE_CONTRADICTION"}, case)
        .disproved
        is False
    )
    # declaring it noise removes it from salience -> suppresses
    assert (
        SourceGrounding(_decl("SOURCE_CONTRADICTION", params={"noise_tokens": ["okayyy"]}))
        .check({"code": "SOURCE_CONTRADICTION"}, case)
        .disproved
        is True
    )


def test_a4_source_path_override_honored():
    """A4: source_path resolves a dotted path; here a non-default field carries the source."""
    case = {
        "artifacts": [{"content": _FAITHFUL_ANSWER}],
        "ctx": {"material": _TRANSCRIPT},
    }
    sg = SourceGrounding(_decl("SOURCE_CONTRADICTION", params={"source_path": "ctx.material"}))
    assert sg.check({"code": "SOURCE_CONTRADICTION"}, case).disproved is True


def test_a4_token_min_len_override_honored():
    """A4: token_min_len changes which short alpha tokens count as salient. With the default
    (4) a 2-char answer word ("hi") is below the floor → not salient → an otherwise-faithful
    answer suppresses; lowering the floor to 2 makes "hi" salient and — absent from the source
    — keeps the finding open. So the override is honored AND the conservative posture holds."""
    src = "Greetings. The plan exists."
    answer = "Hi the plan exists."  # "hi" is the only token below the default len-4 floor
    case = {"transcript": src, "artifacts": [{"content": answer}]}
    # default floor (4): "hi" not salient, "plan"/"exists"(→"exist") ground -> suppress
    assert (
        SourceGrounding(_decl("SOURCE_CONTRADICTION"))
        .check({"code": "SOURCE_CONTRADICTION"}, case)
        .disproved
        is True
    )
    # floor lowered to 2: "hi" now salient + absent from source -> finding STANDS (override honored)
    assert (
        SourceGrounding(_decl("SOURCE_CONTRADICTION", params={"token_min_len": 2}))
        .check({"code": "SOURCE_CONTRADICTION"}, case)
        .disproved
        is False
    )


# ─────────────────────────── A5 — registry + plugin enumeration ───────────────────────────


def test_a5_registered_in_suppress_executors():
    """A5: source_grounding is in the core suppress registry."""
    assert "source_grounding" in suppress_executors()
    assert suppress_executors()["source_grounding"] is SourceGrounding


def test_a5_enumerated_as_core_in_process_suppress_plugin():
    """A5: contract_plugins() declares it kind:contract tier:core transport:in_process
    implements:grounding.suppress."""
    plugins = {p.id: p for p in grounding.contract_plugins()}
    assert "source_grounding" in plugins
    p = plugins["source_grounding"]
    assert (p.kind, p.tier, p.transport, p.implements) == (
        "contract",
        "core",
        "in_process",
        "grounding.suppress",
    )
