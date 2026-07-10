"""UAP-3b — THE MOAT: the per-judge, pre-consensus withstands-gate.

The headline (A2): a confidently-wrong judge finding, contradicted by a deterministic
signal, is CORRECTED by the gate PRE-consensus, and the composite verdict CHANGES — a
flip the existing POST-consensus ``ground()`` does NOT produce (the double-assertion
that makes the flip gate-attributable, defeating the "theater" critique). The exhibit
is the §2A ontology-rule rejection: on a genuine **clean-negative** case (expected
``approve``), ``risk_judge`` confidently raises ``PHI_DISCLOSURE_PRE_VERIFICATION`` — a
Tier-1 code OUTSIDE its lens, sole-owned by ``policy_judge`` who stays silent. Without
the gate that off-domain FP flows through (downgraded to a lone MEDIUM, which blocks)
→ composite ``reject``. With the gate the ontology-rule signal rejects it pre-consensus
→ composite ``approve`` = the by-construction truth RESTORED (never a relabel; A5).

The pure gate/audit/guard tests run on default deps; the full-pipeline exhibit +
consensus-coherence tests are dspy/openai-gated (debuglithrim), $0 via injected
per-role predictors (no Azure call).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target
from lithrim_bench.harness.correction import (
    WITHSTANDS_SCHEMA_VERSION,
    build_withstands_correction,
)
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.runtime.council.signals import build_judge_signals
from lithrim_bench.runtime.council.withstands import apply_withstands_gate

from ._seam_freeze import (
    assert_clinical_ontology_seam_frozen,
    assert_compliance_council_carveouts_only,
    assert_council_roles_relocated_only,
    assert_judges_dspy_consensus_seam_frozen,
)

_REPO = Path(__file__).resolve().parents[1]

# the exhibit FP: a Tier-1 code OUTSIDE risk_judge's lens, sole-owned by policy_judge.
_FP_CODE = "PHI_DISCLOSURE_PRE_VERIFICATION"
_FP_ROLE = "risk_judge"
# PACK-DIST-2 D5: the clean-negative corpus (_CLEAN_CASE_ID/_CLEAN_CASE_SRC = examples/proof_case.jsonl)
# moved to the pack with the MOAT exhibit (tests/test_uap3b_withstands_relocated.py); the funcs that
# remain here build their cases inline, so the gone-path constants are no longer referenced.


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
    return {"transcript": "Agent verified identity first, then discussed the visit.", "artifacts": [{"content": "n"}]}


# ─────────────────────────── pure gate / signal / audit (default deps) ──────────────


def test_signals_bus_assembles_ontology_and_validator_signals():
    """D1: build_judge_signals returns tagged ontology-rule signals (with the
    lens/owner authority + tier/severity) and a validator-output signal for a raised
    code that carries a suppress contract."""
    ont = load_ontology()
    # MEDICATION_NOT_IN_TRANSCRIPT is faithfulness-lensed AND has a presence_check
    # contract; the med IS in the transcript so the validator disproves the raise.
    case = {"transcript": "Patient on zidovudine 300 MG Oral Tablet.",
            "patient_profile": {"active_medications": ["zidovudine 300 MG Oral Tablet"]},
            "artifacts": [{"content": "n"}]}
    sig = build_judge_signals(
        _seam("faithfulness_judge", "reject", ["MEDICATION_NOT_IN_TRANSCRIPT"]),
        "faithfulness_judge",
        ontology=ont,
        case=case,
    )
    raised_rule = next(r for r in sig.ontology_rules if r.code == "MEDICATION_NOT_IN_TRANSCRIPT")
    assert raised_rule.raised and raised_rule.in_lens
    assert "faithfulness_judge" in raised_rule.owner_roles
    assert raised_rule.tier == "TIER_2"
    val = next(v for v in sig.validator_outputs if v.code == "MEDICATION_NOT_IN_TRANSCRIPT")
    assert val.disproved is True and val.contract_type == "presence_check"
    assert "MEDICATION_NOT_IN_TRANSCRIPT" in sig.disproved_codes()


def test_out_of_lens_fp_rejected_pre_consensus():
    """D2: the ontology-rule mode — risk's out-of-lens PHI FP (policy silent) is
    rejected and the judge's verdict down-ranked to approve."""
    ont = load_ontology()
    results = [
        _seam(_FP_ROLE, "reject", [_FP_CODE]),
        _seam("policy_judge", "approve", []),
        _seam("faithfulness_judge", "approve", []),
    ]
    corrected, decisions = apply_withstands_gate(results, ontology=ont, case=_clean_case())
    assert corrected[0]["findings"] == []  # the FP is stripped
    assert corrected[0]["decision"] == "approve"  # verdict down-ranked (no grounds left)
    d = decisions[0]
    assert d.decision == "corrected"
    assert d.what_failed[0]["mode"] == "ontology_rule_out_of_lens"
    assert d.what_failed[0]["code"] == _FP_CODE
    # the silent judges withstand, untouched.
    assert all(x.decision == "withstand" for x in decisions[1:])


def test_validator_disproved_finding_suppressed():
    """D2: the validator mode — a MED-FP raised by an OWNING (in-lens) judge that the
    presence-check disproves is suppressed (distinct from the lens mode)."""
    ont = load_ontology()
    case = {"transcript": "Patient on zidovudine 300 MG Oral Tablet.",
            "patient_profile": {"active_medications": ["zidovudine 300 MG Oral Tablet"]},
            "artifacts": [{"content": "n"}]}
    results = [
        _seam("faithfulness_judge", "reject", ["MEDICATION_NOT_IN_TRANSCRIPT"]),
        _seam("risk_judge", "approve", []),
        _seam("policy_judge", "approve", []),
    ]
    corrected, decisions = apply_withstands_gate(results, ontology=ont, case=case)
    assert corrected[0]["findings"] == []
    assert decisions[0].what_failed[0]["mode"] == "validator_disproved"


def test_by_construction_guard_in_lens_true_finding_withstands():
    """A5: a genuinely-correct in-lens finding is NEVER suppressed — risk raises
    WRONG_DOSAGE (its own Tier-1 lens code), which withstands, verdict stays reject."""
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


def test_by_construction_guard_corroborated_owner_not_dropped():
    """A5: an out-of-lens raise CORROBORATED by the owning judge is kept — the gate
    never drops a corroborated true finding (else it could relabel a true case)."""
    ont = load_ontology()
    results = [
        # faithfulness raises PHI (out of its lens) BUT policy (the owner) co-raises it.
        _seam("faithfulness_judge", "reject", [_FP_CODE]),
        _seam("policy_judge", "reject", [_FP_CODE]),
        _seam("risk_judge", "approve", []),
    ]
    corrected, _ = apply_withstands_gate(results, ontology=ont, case=_clean_case())
    assert [f["taxonomy_code"] for f in corrected[0]["findings"]] == [_FP_CODE]  # kept
    assert [f["taxonomy_code"] for f in corrected[1]["findings"]] == [_FP_CODE]  # owner kept


def test_withstands_decision_audited(tmp_path):
    """A4: a corrected decision records an immutable AuditRecord (action flip, the §2B
    {signals_weighed, decision, what_failed} ruling, run/case ids) AND a
    build_withstands_correction RLVR record."""
    ont = load_ontology()
    results = [
        _seam(_FP_ROLE, "reject", [_FP_CODE]),
        _seam("policy_judge", "approve", []),
        _seam("faithfulness_judge", "approve", []),
    ]
    _, decisions = apply_withstands_gate(results, ontology=ont, case=_clean_case())
    corrected_dec = next(d for d in decisions if d.decision == "corrected")

    db = tmp_path / "audit.sqlite"
    log = AuditLog(db_path=db)
    log.record(
        AuditRecord(
            actor=Actor(type="critique", id="withstands_gate"),
            action="flip",
            target=Target(type="verdict", id="case-1"),
            why=corrected_dec.to_audit_why(),
            run_id="run-1",
            case_id="case-1",
        )
    )
    rows = log.query(target_type="verdict")
    assert len(rows) == 1
    rec = rows[0]
    assert rec["action"] == "flip"
    assert rec["actor"]["type"] == "critique"
    assert rec["run_id"] == "run-1"
    assert set(rec["why"]) == {"signals_weighed", "decision", "what_failed"}
    assert set(rec["why"]["signals_weighed"]) == {"ontology_rules", "validator_outputs"}
    assert rec["why"]["what_failed"][0]["mode"] == "ontology_rule_out_of_lens"

    # the RLVR correction record pairs the corrected judge's rollout with what_failed.
    wrec = build_withstands_correction(
        role=corrected_dec.role,
        what_failed=corrected_dec.what_failed,
        decision_before=corrected_dec.decision_before,
        decision_after=corrected_dec.decision_after,
        result={"semantic": {"judge_votes": []}},
        composite_before="reject",
        composite_after="approve",
        ontology=ont,
    )
    assert wrec["schema_version"] == WITHSTANDS_SCHEMA_VERSION
    assert wrec["corrected_labels"] == [_FP_CODE]
    assert wrec["composite_before"] == "reject" and wrec["composite_after"] == "approve"


def test_frozen_seam_zero_delta():
    """A3: the gate adds ZERO lines to the frozen consensus seam + the per-judge seam
    + the metric + the committed seeds.

    BYOC-1: judges_dspy.py is no longer whole-file-pinned — ``build_judge_lm`` +
    ``build_trio`` are the authorized provider-seam change (driver A6). Its CONSENSUS seam
    (the JudgeSignature, the per-judge seam dict, the finding normalizers, evaluate_dspy)
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
    assert_judges_dspy_consensus_seam_frozen(_REPO)
    assert_compliance_council_carveouts_only(_REPO)
    assert_council_roles_relocated_only(_REPO)
    # PACK-DIST-1: ws0_default.json is now the neutral blank-slate default agent (0 clinical
    # strings; ontology_path → packs/_core); the clinical scribe-replay agent relocated to the
    # external healthcare pack repo, so the old healthcare-ontology_path seed pin is retired.
    # clinical_v1.json's consensus/owner seam stays frozen; only verification_contracts
    # may grow additively (GROUND-FLOOR-1's record_presence contract).
    assert_clinical_ontology_seam_frozen(_REPO)


# ─────────────────────────── full-pipeline exhibit (dspy/openai-gated) ──────────────


# PACK-DIST-2 D5: the MOAT exhibit (test_MOAT_EXHIBIT_gate_flips_composite_and_ground_alone_does_not)
# + its _fp_predictors helper read the relocated clean-negative corpus (examples/proof_case.jsonl) +
# grade through the committed clinical ontology → relocated to the pack repo
# (tests/test_uap3b_withstands_relocated.py). The signals-bus / withstands / frozen-seam NEEDS_PACK
# funcs (which build cases inline) stay here.


def test_consensus_decision_flips_with_validator_disprove():
    """A2′ (consensus coherence) — the validator mode at the CONSENSUS level, which
    post-consensus ground() structurally cannot touch: two judges MED-FP the same code
    (2-judge corroboration → consensus reject); the gate suppresses both pre-consensus
    → the FROZEN _apply_consensus now returns approve. Only openai (the council); no
    dspy — raw seam dicts feed the consensus directly."""
    pytest.importorskip("openai")
    from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil

    ont = load_ontology()
    case = {"transcript": "Patient on zidovudine 300 MG Oral Tablet daily.",
            "patient_profile": {"active_medications": ["zidovudine 300 MG Oral Tablet"]},
            "artifacts": [{"content": "n"}]}
    # both in-lens owners of MEDICATION_NOT_IN_TRANSCRIPT (faithfulness) + a corroborator.
    raw = [
        _seam("faithfulness_judge", "reject", ["MEDICATION_NOT_IN_TRANSCRIPT"]),
        _seam("risk_judge", "reject", ["MEDICATION_NOT_IN_TRANSCRIPT"]),
        _seam("policy_judge", "approve", []),
    ]
    council = ComplianceCouncil()
    raw_consensus = council._apply_consensus([dict(r) for r in raw])

    corrected, decisions = apply_withstands_gate(raw, ontology=ont, case=case)
    gated_consensus = council._apply_consensus(corrected)

    assert raw_consensus["decision"] == "reject"  # 2-judge corroborated MED FP
    assert gated_consensus["decision"] == "approve"  # gate disproved both pre-consensus
    assert all(d.decision == "corrected" for d in decisions if d.role != "policy_judge")
