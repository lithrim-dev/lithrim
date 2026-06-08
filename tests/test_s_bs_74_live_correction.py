"""S-BS-74 — the LIVE grounding-correction demo, proven OFFLINE ($0) at BOTH loci.

The live attestation (A-LIVE) fires one paid :8002 run over the by-construction
clean-negative ``bench_s_bs_74_med_overfire_clean_negative_*`` and hopes the prompt
council over-fires ``MEDICATION_NOT_IN_TRANSCRIPT`` on a medication that is verbatim
in the transcript, so the post-hoc ``ground()`` floor disproves+suppresses it and the
composite flips reject->approve. This module is its DETERMINISTIC twin: it feeds the
SAME over-fire (a faked lone-MEDIUM MED finding, mirroring the live faithfulness_judge
raise in run 8a41ef3e) and proves the flip with no paid call.

Two loci, one cycle:
  * FLOOR (this file, net-new): the post-consensus ``ground()`` presence-check. ON =>
    the MED FP is suppressed, the active set drops to empty, composite PASS/approve;
    OFF (the same fn/case/finding, only the contract removed) => BLOCK/reject. The flip
    is therefore SUPPRESSION-ATTRIBUTABLE — a property of the contract, not the case.
  * GATE (reuse-assert): the pre-consensus withstands-gate flip is already proven by
    tests/test_uap3b_withstands.py::test_MOAT_EXHIBIT_…; we import-and-call it so this
    file proves both loci.

The floor-locus test runs on DEFAULT deps (pure ground/composite — no dspy/openai). The
gate-locus reuse-assert is dspy/openai-gated (debuglithrim), $0 via injected predictors.

Run ``python -m tests.test_s_bs_74_live_correction`` for the §3.3 $0 dry-run that prints
the before/after — the suppress-to-empty math to confirm BEFORE spending the paid run.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case

_REPO = Path(__file__).resolve().parents[1]
_CASE_ID = "bench_s_bs_74_med_overfire_clean_negative_74de0c0117a2"
_CASE_SRC = _REPO / "examples" / "s_bs_74_med_overfire_demo.jsonl"
_MED_CODE = "MEDICATION_NOT_IN_TRANSCRIPT"


def _med_overfire_result() -> dict:
    """A council result with a single MEDIUM MED over-fire on the clean case — the
    faked twin of the live faithfulness_judge raise in run 8a41ef3e, self-refuting
    span included (the judge cites the very transcript line that contains the med)."""
    return {
        "verdict": "BLOCK",
        "findings": [
            {
                "type": "semantic",
                "severity": "MEDIUM",
                "code": _MED_CODE,
                "detail": f"{_MED_CODE} (judges=1)",
            }
        ],
        "semantic": {
            "evidence": [
                {
                    "violation_code": _MED_CODE,
                    "spans": [
                        {
                            "quote": "Continue zidovudine 300 MG Oral Tablet 300 MG daily",
                            "turn_ids": [],
                        },
                        {
                            "quote": "Dr: I see you're on zidovudine 300 MG Oral Tablet. "
                            "Continue taking 300 MG daily.",
                            "turn_ids": [],
                        },
                    ],
                }
            ]
        },
    }


def _case() -> dict:
    case = load_case(_CASE_ID, source=str(_CASE_SRC))
    assert case is not None, f"case {_CASE_ID} not found in {_CASE_SRC}"
    return case


def test_clean_negative_is_admissible_by_construction():
    """A1 (in-test guard): the new case is a clean negative — expected approve, no
    injected defect, no expected flags. The over-fire is a genuine LLM false positive
    the floor corrects, never a manufactured defect."""
    case = _case()
    assert case["clean_negative"] is True
    assert case["expected_compliance_verdict"] == "approve"
    assert case["expected_safety_flags"] == []
    assert case["injection_recipes"] == []
    # the presence-check scaffold: the med is verbatim in BOTH the med_source and the transcript.
    assert case["patient_profile"]["active_medications"] == ["zidovudine 300 MG Oral Tablet"]
    assert "zidovudine" in case["transcript"].lower()


def test_floor_locus_med_overfire_flips_composite_and_the_contract_is_the_cause():
    """A2 — the FLOOR-locus flip, non-vacuous + suppression-attributable.

    Same fn (``ground``), same case, same lone-MEDIUM MED over-fire; only the
    presence_check contract differs between the two halves, so the reject->approve flip
    is caused by the suppression, not by the case being clean."""
    ont = load_ontology()
    case = _case()
    result = _med_overfire_result()

    # ground ON (committed clinical ontology, which carries med-presence-check/v1).
    g_on = ground(result, case, ontology=ont)
    comp_on = composite(g_on)
    assert [s["finding"]["code"] for s in g_on.suppressed] == [_MED_CODE]
    sup = g_on.suppressed[0]
    assert sup["verdict"].disproved is True
    assert sup["verdict"].matched_token == "zidovudine"
    assert g_on.active == []  # nothing else fired -> the active set is empty
    assert comp_on["stage_verdict"] == "PASS"
    assert comp_on["verdict"] == "approve"  # THE FLIP

    # ground OFF/bypassed = the SAME ground() with the contract removed (the
    # suppression-attributable twin). The MED FP now flows through as a lone MEDIUM.
    ont_off = dataclasses.replace(ont, contracts=())
    g_off = ground(result, case, ontology=ont_off)
    comp_off = composite(g_off)
    assert g_off.suppressed == []
    assert [f.get("code") for f in g_off.active] == [_MED_CODE]
    assert comp_off["stage_verdict"] == "BLOCK"
    assert comp_off["verdict"] == "reject"

    # belt-and-suspenders: a lone MED is a BLOCK-driving MEDIUM by the ontology map
    # (weight 0.5 >= block_at_or_above 0.5), so the OFF half is not vacuous.
    assert ont.severity_map.rescore(result["findings"]) == "BLOCK"


def test_gate_locus_moat_exhibit_still_green():
    """A3 — the SECOND locus. The pre-consensus withstands-gate flip is already proven
    by the MOAT exhibit; reuse-assert it stays green so S-BS-74 covers both loci
    without duplicating the gate machinery. dspy/openai-gated; $0 (injected predictors)."""
    pytest.importorskip("dspy")
    pytest.importorskip("openai")
    from .test_uap3b_withstands import (
        test_MOAT_EXHIBIT_gate_flips_composite_and_ground_alone_does_not as moat_exhibit,
    )

    moat_exhibit()


if __name__ == "__main__":
    # §3.3 $0 dry-run: prove suppress-to-empty on the REAL case BEFORE the paid run.
    _ont = load_ontology()
    _case_row = _case()
    _result = _med_overfire_result()
    _off = composite(ground(_result, _case_row, ontology=dataclasses.replace(_ont, contracts=())))
    _on = composite(ground(_result, _case_row, ontology=_ont))
    print(
        f"[dry-run] ground OFF (no contract): {_off['verdict']} / {_off['stage_verdict']} "
        f"active={_off['active_findings']}"
    )
    print(
        f"[dry-run] ground ON  (presence_check): {_on['verdict']} / {_on['stage_verdict']} "
        f"active={_on['active_findings']} "
        f"suppressed={[a['matched_token'] for a in _on['grounded_adjustments']]}"
    )
    _flip = _off["verdict"] == "reject" and _on["verdict"] == "approve"
    print("[dry-run] FLIP PROVEN — safe to spend the paid run" if _flip else "[dry-run] NO FLIP")
