"""OBS-FORM-1 — the floor-able SUBSET of HALLUCINATED_DETAIL.

`HALLUCINATED_DETAIL` is not wholesale floor-able (a fabricated exam finding is textually
indistinguishable from a real one — both are objective note content absent from the transcript).
But its false positives fall into deterministic FORMS that a *fabricated positive finding* never
takes: a **vitals measurement** (BP/HR/RR/Temp/SpO2 + numbers) or a **negated/normal finding**
(no / denies / intact / unremarkable …). A fabricated exam finding is, by construction, a positive
abnormal assertion — so suppressing the vitals/negation forms clears ~43% of the FPs while touching
ZERO of the 7 by-construction true positives (validated offline on the clinverdict_mts corpus).

The 7 TP forms this MUST preserve (from the injection recipes, defect=hallucinate_exam_finding):
  "mild pitting edema noted bilaterally", "Positive Phalen's test bilaterally",
  "Limited abduction of the right eye", "lip smacking movements were noted", etc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DROPIN = REPO_ROOT / "packs-dropin"

pytestmark = pytest.mark.skipif(
    not (DROPIN / "clinverdict" / "floors.py").exists(),
    reason="clinverdict drop-in pack not present",
)


@pytest.fixture()
def floor():
    import sys

    if str(DROPIN) not in sys.path:
        sys.path.insert(0, str(DROPIN))
    F = pytest.importorskip("clinverdict.floors")
    from lithrim_bench.harness.ontology import VerificationContractDecl

    decl = VerificationContractDecl(
        flag_code="HALLUCINATED_DETAIL",
        question="q",
        contract_type="observation_form",
        params={},
        version="v1",
    )
    return F.ObservationFormGrounding(decl)


def _finding(*quotes: str):
    return {"code": "HALLUCINATED_DETAIL", "_evidence_spans": [{"quote": q} for q in quotes]}


# the 7 by-construction TRUE positives — a fabricated POSITIVE exam finding. MUST stand.
TP_SPANS = [
    "On examination, mild pitting edema was noted bilaterally in the lower extremities.",
    "Ankle dorsiflexion limited to -5 degrees bilaterally with knee extended.",
    "Skin exam reveals erythematous, lichenified plaques over bilateral antecubital fossae.",
    "During episodes, lip smacking movements were noted by the mother.",
    "Mild serous drainage noted at the inferior graft margin.",
    "Positive Phalen's test bilaterally, right greater than left.",
    "Limited abduction of the right eye on examination.",
]

# false-positive FORMS a fabricated finding never takes.
VITALS_SPANS = [
    "Vital signs: BP 128/76 mmHg, HR 72 bpm, RR 14, Temp 98.4 F, SpO2 98% on room air.",
    "OBJECTIVE:\nVitals: BP 140/84 mmHg, HR 70 bpm regular, RR 16, Temp 98.5 F.",
]
NEG_SPANS = [
    "No focal neurological deficits on exam.",
    "Sensation intact to light touch throughout.",
    "Abdomen soft, nontender, no organomegaly.",
]


@pytest.mark.parametrize("span", TP_SPANS)
def test_true_positive_exam_findings_are_never_suppressed(floor, span):
    """The safety bar: a fabricated positive exam finding must always STAND."""
    assert floor.check(_finding(span), {}).disproved is False


@pytest.mark.parametrize("span", VITALS_SPANS)
def test_vitals_lines_are_suppressed(floor, span):
    v = floor.check(_finding(span), {})
    assert v.disproved is True


@pytest.mark.parametrize("span", NEG_SPANS)
def test_negated_normal_findings_are_suppressed(floor, span):
    v = floor.check(_finding(span), {})
    assert v.disproved is True


def test_mixed_spans_stand_if_any_is_a_positive_assertion(floor):
    """Conservative: a finding that flags BOTH a vitals line AND a positive fabrication stands —
    the positive assertion could be the real defect, so the whole finding is preserved."""
    v = floor.check(_finding(VITALS_SPANS[0], TP_SPANS[0]), {})
    assert v.disproved is False


def test_no_span_stands(floor):
    """Never clear by silence — a finding with no evidence span cannot be confirmed as a form."""
    assert floor.check(_finding(), {}).disproved is False


def test_registered_as_suppress_executor():
    import sys

    if str(DROPIN) not in sys.path:
        sys.path.insert(0, str(DROPIN))
    F = pytest.importorskip("clinverdict.floors")
    assert F.SUPPRESS_EXECUTORS.get("observation_form") is F.ObservationFormGrounding
