"""GROUND-FLOOR-1 offline acceptance: the record_presence suppress floor.

No network, no LLM, $0. Everything runs against the committed corpus
(``examples/judge_calib_v1.jsonl`` + ``examples/proof_case.jsonl``) and the
committed ontology (``data/ontology/clinical_v1.json``, which now declares the
``record_presence`` / ``FABRICATED_HISTORY`` contract). The result dicts are
synthesized — the corpus rows are eval *inputs*; this exercises the suppress
mechanism by feeding a FABRICATED_HISTORY finding into ``ground()`` and asserting
it is suppressed iff the documented PMH is grounded in the patient record.

Covers driver §5 A1–A6 (offline subset): A1 wired, A2 demo-pair flip (non-vacuous),
A3 16/16 non-regression (exact class counts), A4 non-SOAP guard, A5 additive
identity, A6 import isolation. Plus the empty-PMH guard and the D-D withstands-gate
verdict-neutrality parity.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from lithrim_bench.harness import grounding
from lithrim_bench.harness.grounding import _decode_artifact_soap, ground
from lithrim_bench.harness.ontology import from_dict, load_ontology

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIB = REPO_ROOT / "examples" / "judge_calib_v1.jsonl"

CLEAN_ID = "bench_scribe_v1_clean_negative_aaecd73c3bcf"
VIOL_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"


def _load_case(cid: str) -> dict:
    for line in CALIB.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if (o.get("case_id") or o.get("id")) == cid:
            return o
    raise AssertionError(f"case {cid} not in {CALIB}")


def _fab_result(severity: str = "HIGH") -> dict:
    """A synthetic council result whose only finding is a FABRICATED_HISTORY block.

    HIGH (weight 1.0 >= block_at_or_above 0.5) so the pre-grounding verdict is
    unambiguously BLOCK — the flip under test is genuine, not a pre-passing case.
    """
    return {
        "verdict": "BLOCK",
        "findings": [
            {"code": "FABRICATED_HISTORY", "severity": severity, "detail": "PMH fabricated"}
        ],
    }


@pytest.fixture
def ont_with_rp():
    """The committed ontology — declares record_presence / FABRICATED_HISTORY."""
    return load_ontology()


@pytest.fixture
def ont_without_rp():
    """The same ontology with the record_presence contract removed — the pre-floor
    baseline, so a flip is attributable to the floor and nothing else."""
    data = json.loads((REPO_ROOT / "data" / "ontology" / "clinical_v1.json").read_text())
    data["verification_contracts"] = [
        c for c in data["verification_contracts"] if c["contract_type"] != "record_presence"
    ]
    return from_dict(data)


# --------------------------------------------------------------------------- #
# A1 — wired
# --------------------------------------------------------------------------- #
def test_record_presence_registered_and_buildable(ont_with_rp):
    assert "record_presence" in grounding._CONTRACT_EXECUTORS
    assert "record_presence" not in grounding._HTTP_CONTRACT_TYPES  # pure stdlib, no http
    decl = ont_with_rp.contract_for("FABRICATED_HISTORY")
    assert decl is not None and decl.contract_type == "record_presence"
    contract = grounding._build_contract(decl)  # built from the declaration alone
    assert isinstance(contract, grounding.RecordPresence)


# --------------------------------------------------------------------------- #
# A2 — the demo pair flip (non-vacuous: BLOCK before, PASS after on clean)
# --------------------------------------------------------------------------- #
def test_demo_pair_flip_offline(ont_with_rp, ont_without_rp):
    clean = _load_case(CLEAN_ID)
    viol = _load_case(VIOL_ID)

    # pre-floor baseline: BOTH block (the finding stands when no contract runs).
    assert ground(_fab_result(), clean, ontology=ont_without_rp).verdict == "BLOCK"
    assert ground(_fab_result(), viol, ontology=ont_without_rp).verdict == "BLOCK"

    # with the floor: clean SUPPRESSES (BLOCK -> PASS); viol STANDS (BLOCK -> BLOCK).
    g_clean = ground(_fab_result(), clean, ontology=ont_with_rp)
    assert g_clean.original_verdict == "BLOCK"
    assert g_clean.verdict == "PASS"
    assert {s["finding"]["code"] for s in g_clean.suppressed} == {"FABRICATED_HISTORY"}
    assert g_clean.active == []

    g_viol = ground(_fab_result(), viol, ontology=ont_with_rp)
    assert g_viol.verdict == "BLOCK"
    assert g_viol.suppressed == []
    assert {f.get("code") for f in g_viol.active} == {"FABRICATED_HISTORY"}


# --------------------------------------------------------------------------- #
# A3 — no false-regression: 16/16 (12 inject stand, 4 clean suppressible)
# --------------------------------------------------------------------------- #
def test_no_false_regression_16(ont_with_rp):
    stands = 0
    suppressible = 0
    for line in CALIB.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        cid = o.get("case_id") or o.get("id")
        if "inject_condition" in cid:
            g = ground(_fab_result(), o, ontology=ont_with_rp)
            assert g.verdict == "BLOCK", f"{cid}: a true fabrication was cleared"
            assert g.suppressed == [], f"{cid}: suppressed a true positive"
            stands += 1
        elif cid.startswith("bench_scribe_v1_clean_negative_"):
            g = ground(_fab_result(), o, ontology=ont_with_rp)
            assert g.verdict == "PASS", f"{cid}: a clean negative did not suppress"
            assert {s["finding"]["code"] for s in g.suppressed} == {"FABRICATED_HISTORY"}
            suppressible += 1
    assert stands == 12, f"expected 12 inject_condition true positives, got {stands}"
    assert suppressible == 4, f"expected 4 scribe clean negatives, got {suppressible}"
    assert stands + suppressible == 16


# --------------------------------------------------------------------------- #
# A4 — non-SOAP guard: inconclusive, never suppressed, no crash
# --------------------------------------------------------------------------- #
def test_non_soap_artifact_inconclusive(ont_with_rp):
    """A scheduling/triage conversation row has no content[0].attachment.data ->
    decode None -> the finding STANDS (never suppressed by silence)."""
    sched = None
    for line in CALIB.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        cid = o.get("case_id") or o.get("id")
        if cid.startswith("bench_scheduling_v1_"):
            sched = o
            break
    assert sched is not None
    assert _decode_artifact_soap(sched) is None  # the guard fires before any crash
    g = ground(_fab_result(), sched, ontology=ont_with_rp)
    assert g.suppressed == []
    assert {f.get("code") for f in g.active} == {"FABRICATED_HISTORY"}
    assert g.verdict == "BLOCK"


# --------------------------------------------------------------------------- #
# empty-PMH guard: zero extracted items -> inconclusive (vacuous-conform trap)
# --------------------------------------------------------------------------- #
def test_empty_pmh_is_inconclusive_not_suppressed(ont_with_rp):
    """InRowTool conforms vacuously on [] PMH items; the executor must NOT read that
    as 'all grounded'. A SOAP note with no PMH section -> the finding stands."""
    no_pmh_soap = "SUBJECTIVE: cough.\nASSESSMENT: viral URI.\nPLAN: rest."
    doc = {"content": [{"attachment": {"data": no_pmh_soap}}]}
    case = {
        "patient_profile": {"conditions": ["Anemia (disorder)"]},
        "artifacts": [{"content": json.dumps(doc)}],
    }
    assert _decode_artifact_soap(case) == no_pmh_soap
    decl = ont_with_rp.contract_for("FABRICATED_HISTORY")
    v = grounding._build_contract(decl).check({"code": "FABRICATED_HISTORY"}, case)
    assert v.disproved is False
    assert "nothing to ground" in v.reason


# --------------------------------------------------------------------------- #
# A5 — additive identity: ground() unchanged for non-FABRICATED_HISTORY cases
# --------------------------------------------------------------------------- #
def test_additive_identity_non_fab(ont_with_rp, ont_without_rp):
    """For a result that carries no FABRICATED_HISTORY finding, adding the
    record_presence contract changes nothing — same active / suppressed / verdict."""
    clean = _load_case(CLEAN_ID)
    other = {
        "verdict": "BLOCK",
        "findings": [{"code": "WRONG_DOSAGE", "severity": "HIGH", "detail": "dose drift"}],
    }
    a = ground(copy.deepcopy(other), clean, ontology=ont_without_rp)
    b = ground(copy.deepcopy(other), clean, ontology=ont_with_rp)
    assert a.verdict == b.verdict == "BLOCK"
    assert [f.get("code") for f in a.active] == [f.get("code") for f in b.active]
    assert a.suppressed == b.suppressed == []


def test_med_presence_check_still_fires(ont_with_rp):
    """The pre-existing MEDICATION_NOT_IN_TRANSCRIPT presence_check is unaffected by
    the new contract — it still suppresses a med FP whose token is in the transcript."""
    case = {
        "transcript": "Doctor: continue your zidovudine 300 MG Oral Tablet daily.",
        "patient_profile": {"active_medications": ["zidovudine 300 MG Oral Tablet"]},
    }
    result = {
        "verdict": "BLOCK",
        "findings": [
            {"code": "MEDICATION_NOT_IN_TRANSCRIPT", "severity": "HIGH", "detail": "not present"}
        ],
    }
    g = ground(result, case, ontology=ont_with_rp)
    assert {s["finding"]["code"] for s in g.suppressed} == {"MEDICATION_NOT_IN_TRANSCRIPT"}
    assert g.verdict == "PASS"


# --------------------------------------------------------------------------- #
# D-D — withstands-gate verdict-neutrality: signals.py routes through the SAME
# _build_contract; the pre-consensus disproved must match the post-consensus one.
# --------------------------------------------------------------------------- #
def test_withstands_gate_parity(ont_with_rp):
    from lithrim_bench.runtime.council.signals import build_judge_signals

    for cid, expect_disproved in [(CLEAN_ID, True), (VIOL_ID, False)]:
        case = _load_case(cid)
        # post-consensus (ground): the suppress decision.
        g = ground(_fab_result(), case, ontology=ont_with_rp)
        post_disproved = bool(g.suppressed)
        assert post_disproved is expect_disproved

        # pre-consensus (withstands-gate): the same contract over a seam finding.
        seam = {"findings": [{"taxonomy_code": "FABRICATED_HISTORY", "evidence_spans": []}]}
        sig = build_judge_signals(
            seam, role="faithfulness_judge", ontology=ont_with_rp, case=case
        )
        rp = [v for v in sig.validator_outputs if v.contract_type == "record_presence"]
        assert len(rp) == 1, f"{cid}: record_presence validator not run pre-consensus"
        assert rp[0].disproved is expect_disproved  # verdict-neutral across stages


# --------------------------------------------------------------------------- #
# A6 — import isolation: grounding stays stdlib-only (no httpx/dspy/onnx pulled)
# --------------------------------------------------------------------------- #
def test_import_isolation_stdlib_only():
    import subprocess
    import sys

    code = (
        "import sys; import lithrim_bench.harness.grounding;"
        "leaked=[m for m in ('httpx','dspy','onnxruntime','pinecone') if m in sys.modules];"
        "print(leaked); assert leaked==[], leaked"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]"
