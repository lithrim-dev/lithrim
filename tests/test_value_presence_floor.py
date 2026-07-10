"""FAUTH-4 / NARR-FLOOR-1 — the deterministic ``value_presence`` completeness floor.

The INVERSE of ``dosage_grounding``: a value spoken in a ``source_path`` (default
``transcript``) MUST appear in the artifact (``artifacts[0].content``). When a required
value is ABSENT from the artifact the floor injects a BLOCK the council missed (the
FLOOR direction, run by ``_run_floor`` in ``harness/grounding.py``); when nothing is
parseable it is inconclusive and NEVER flips by silence. This is the case-10 mechanism:
a transcript records a vaccine refusal, the SOAP note ERASES it → the floor flips
PASS→BLOCK deterministically, independent of any judge.

Per ``SPEC_CLINICAL_SCRIBE_SELF_SERVE.md:122-124`` the tool class + executor ship pack-local
(``packs/narrative/floors.py``, BracketLeakTool is the template); only the NAME is
registered once in core (``_KNOWN_TOOLS`` + ``_REQUIRED_REFERENCE_KEYS``). The oracle is
deterministic surface-form matching (``re.findall(value_regex, source)`` → normalized
substring presence) — no LLM inference (OQ-3).

Written FIRST (RED): the ``value_presence`` tool, its ``_KNOWN_TOOLS`` registration, and
its ``FLOOR_EXECUTORS`` entry do not exist yet, so ``VerificationSpec`` raises "unknown
tool", ``floors.ValuePresenceTool`` is absent, and ``ground()`` has no executor for the
contract_type. A1..A5 map to the driver acceptance criteria.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "narrative"

# ── the case-10-shaped crafted pair (a transcript records a refusal; the SOAP keeps / erases it) ──
TRANSCRIPT = (
    "Clinician: Your tetanus booster is due today. "
    "Patient: I refused the tetanus shot last time and I'm declining it again."
)
SOAP_ERASED = (
    "ASSESSMENT: Adult preventive visit, no acute concerns. "
    "PLAN: Continue current medications. Return to clinic in one year."
)
SOAP_KEPT = (
    "ASSESSMENT: Adult preventive visit; patient refused the tetanus booster (informed refusal "
    "documented). PLAN: revisit immunization at next encounter."
)
NO_REFUSAL_TRANSCRIPT = "Clinician: Your tetanus booster is due. Patient: Sure, go ahead."

# the SME pin: extract the refusal assertion from the transcript; it must appear in the note.
# match="any" = concept-presence (the refusal recorded in ANY accepted surface form is enough);
# the default match="all" is the strict every-distinct-value-preserved completeness check (A2).
_REF = {"value_regex": r"refused|declining|declined", "source_path": "transcript", "match": "any"}


def _narrative_floors_registered() -> bool:
    """The value_presence executor is registered only when pack=narrative is the ACTIVE pack
    (floor_executors() resolves via the active pack). The A4 ground()-integration tests need it;
    under pack=healthcare it is absent → skip (A1-A3 load floors.py directly + are pack-agnostic)."""
    from lithrim_bench.harness.grounding import floor_executors

    return "value_presence" in floor_executors()


_NEEDS_NARRATIVE_PACK = pytest.mark.skipif(
    not _narrative_floors_registered(),
    reason="value_presence not registered under the active pack (set LITHRIM_BENCH_PACK=narrative)",
)


def _claim(subject, *, source=None):
    from lithrim_bench.verification import STRUCTURAL_CONFORMANCE, Claim

    return Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code=None,
        subject=subject,
        locus="",
        source=source or {},
    )


def _spec(reference):
    from lithrim_bench.verification import VerificationSpec

    return VerificationSpec(
        tool="value_presence",
        applies_to_flags=("X",),
        locus="",
        reference=reference,
        version="v1",
    )


# ── CORE-FLOOR-1 — value_presence is a CORE floor, available on EVERY pack (incl. healthcare) ──


def test_value_presence_is_a_core_floor_available_to_every_pack():
    """CORE-FLOOR-1: value_presence is a domain-agnostic completeness floor — a CORE floor merged
    into every pack's registry, NOT narrative-only. The _core + in-repo narrative packs prove the
    merge in ANY checkout (so a bare CE run still proves the floor is standalone-domain-agnostic);
    the EXTERNAL healthcare pack is asserted separately (NEEDS_PACK — skips in bare CE)."""
    from lithrim_bench.harness.grounding import floor_executors

    assert "value_presence" in floor_executors("_core"), "must be a CORE floor, not pack-gated"
    # narrative is in-repo (core tier): proves the core-merge reaches a domain pack in bare CE
    assert "value_presence" in floor_executors("narrative")


def test_value_presence_available_on_the_clinical_scribe_pack():
    """The CORE-FLOOR-1 merge reaches the in-repo clinical_scribe sample pack too, so a clinician can
    author the floor on a clinical workspace (self-contained against the public fixture pack — no
    external healthcare Pro pack required)."""
    from lithrim_bench.harness.grounding import floor_executors

    assert "value_presence" in floor_executors("clinical_scribe"), (
        "must be available on the clinical pack"
    )


# ── A1 — ValuePresenceTool fires on absence, clears on presence, inconclusive otherwise ──


def test_value_presence_violation_clean_and_inconclusive():
    from lithrim_bench.verification import ValuePresenceTool

    tool = ValuePresenceTool()
    spec = _spec(dict(_REF))

    # VIOLATION: the transcript records the refusal; the SOAP ERASED it → conforms=False (absent→BLOCK)
    r = tool.verify(_claim(SOAP_ERASED, source={"transcript": TRANSCRIPT}), spec)
    assert r.conforms is False
    assert r.evidence["concept_in_artifact"] is False  # match='any' = concept co-presence
    assert any("refus" in t.lower() for t in r.evidence["required"])

    # CLEAN: the SOAP records the refusal (any accepted form) → conforms=True (no inject)
    assert tool.verify(_claim(SOAP_KEPT, source={"transcript": TRANSCRIPT}), spec).conforms is True

    # PARAPHRASE ROBUSTNESS (concept co-presence, FAUTH-4b): the source says "refused"/"declining";
    # a faithful note recording it in a DIFFERENT accepted form ("declined") must NOT false-block.
    paraphrased = "ASSESSMENT: preventive visit. PLAN: patient declined the booster; documented."
    assert tool.verify(_claim(paraphrased, source={"transcript": TRANSCRIPT}), spec).conforms is True

    # INCONCLUSIVE: no source transcript → nothing parseable → None (never flip by silence)
    assert tool.verify(_claim(SOAP_ERASED, source={}), spec).conforms is None

    # INCONCLUSIVE: transcript present but the required value never spoken → None (no false block)
    assert (
        tool.verify(_claim(SOAP_ERASED, source={"transcript": NO_REFUSAL_TRANSCRIPT}), spec).conforms
        is None
    )

    # INCONCLUSIVE: empty / non-str artifact → None
    assert tool.verify(_claim("", source={"transcript": TRANSCRIPT}), spec).conforms is None
    assert tool.verify(_claim(None, source={"transcript": TRANSCRIPT}), spec).conforms is None


# ── A2 — dotted source_path resolution + a malformed regex is inconclusive, never aborts ──


def test_value_presence_dotted_source_path_and_bad_regex():
    from lithrim_bench.verification import ValuePresenceTool

    tool = ValuePresenceTool()
    spec = _spec({"value_regex": r"penicillin", "source_path": "transcript.text"})

    case = {"transcript": {"text": "Patient is allergic to penicillin."}}
    # 'penicillin' is NOT a substring of 'amoxicillin' → absent → False
    assert tool.verify(_claim("PLAN: prescribe amoxicillin.", source=case), spec).conforms is False
    assert (
        tool.verify(_claim("ALLERGIES: penicillin. PLAN: avoid beta-lactams.", source=case), spec).conforms
        is True
    )

    # a malformed pinned regex must be inconclusive (conservative), NOT raise into ground()'s loop
    bad = _spec({"value_regex": r"(", "source_path": "transcript.text"})
    assert tool.verify(_claim("anything", source=case), bad).conforms is None


def test_value_presence_match_all_requires_every_distinct_value():
    """The default match='all' = the strict completeness check: EVERY distinct value spoken in the
    source must appear in the artifact (non-vacuous both ways)."""
    from lithrim_bench.verification import ValuePresenceTool

    tool = ValuePresenceTool()
    # extract two distinct dose values from the transcript; both must be preserved in the SOAP
    spec = _spec({"value_regex": r"\b\d+\s*mg\b", "source_path": "transcript"})  # default match='all'
    case = {"transcript": "Start metoprolol 25 mg and atorvastatin 40 mg."}

    # the SOAP dropped one of the two doses → conforms=False (a silent completeness gap)
    r = tool.verify(_claim("PLAN: metoprolol 25 mg daily.", source=case), spec)
    assert r.conforms is False and any("40" in m for m in r.evidence["missing"])

    # both doses preserved → conforms=True
    assert (
        tool.verify(_claim("PLAN: metoprolol 25 mg, atorvastatin 40 mg.", source=case), spec).conforms
        is True
    )


def test_value_presence_match_all_is_word_boundary_not_substring():
    """F4: match='all' must use WORD-BOUNDARY matching, not substring — a dropped '5 mg' must NOT be
    satisfied by '25 mg' in the artifact (the dosage-inverse false-negative the critic caught)."""
    from lithrim_bench.verification import ValuePresenceTool

    tool = ValuePresenceTool()
    spec = _spec({"value_regex": r"\b\d+\s*mg\b", "source_path": "transcript"})  # default match='all'
    case = {"transcript": "Start aspirin 5 mg daily."}
    # the SOAP only has 25 mg — the spoken 5 mg dose was dropped → conforms=False (NOT a substring pass)
    r = tool.verify(_claim("PLAN: aspirin 25 mg daily.", source=case), spec)
    assert r.conforms is False and any("5" in m for m in r.evidence["missing"])
    # the same dose preserved → conforms=True
    assert tool.verify(_claim("PLAN: aspirin 5 mg daily.", source=case), spec).conforms is True


# ── A3 — value_presence registered in core _KNOWN_TOOLS, ADDITIVELY (the 9 prior intact) ──


def test_value_presence_known_tool_is_additive():
    from lithrim_bench.verification import spec as spec_mod

    prior = {
        spec_mod.TOOL_IN_ROW,
        spec_mod.TOOL_STRUCTURAL_JUTE,
        spec_mod.TOOL_RECORD_RAG,
        spec_mod.TOOL_KB_RAG,
        spec_mod.TOOL_JUTE_GEN,
        spec_mod.TOOL_DOSAGE_GROUNDING,
        spec_mod.TOOL_BRACKET_LEAK,
        spec_mod.TOOL_LENGTH_VIOLATION,
        spec_mod.TOOL_SILENT_DEGRADATION,
    }
    assert prior <= spec_mod._KNOWN_TOOLS, "the 9 prior tool-names must remain (additive)"
    assert spec_mod.TOOL_VALUE_PRESENCE == "value_presence"
    assert spec_mod.TOOL_VALUE_PRESENCE in spec_mod._KNOWN_TOOLS
    assert spec_mod.TOOL_VALUE_PRESENCE not in prior
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_VALUE_PRESENCE] == {"value_regex"}
    # the prior shapes are untouched
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_DOSAGE_GROUNDING] == {"dose_regex"}
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_BRACKET_LEAK] == set()


# ── A4 — ground() flips PASS→BLOCK via the floor; clean stays PASS; inconclusive stands ──

_VP_FLAG = {
    "flag": "VALUE_DROPPED",
    "category": "completeness",
    "definition": "",
    "when_to_use": "",
    "when_NOT_to_use": "",
    "owner_roles": ["faithfulness_judge"],
    "tier": "TIER_1",
    "gradeable": True,
}
_VP_ONT_DICT = {
    "ontology_version": "value_presence_test_v1",
    "domain": "narrative",
    "flags": [_VP_FLAG],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "VALUE_DROPPED",
            "question": "Is every value spoken in the transcript preserved in the note?",
            "contract_type": "value_presence",
            "version": "v1",
            "params": {
                "value_regex": r"refused|declining|declined",
                "source_path": "transcript",
                "match": "any",
                "inject_flag_code": "VALUE_DROPPED",
                "inject_severity": "HIGH",
            },
        }
    ],
    "severity_map": {
        "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
        "block_at_or_above": 0.5,
        "warn_above": 0.0,
    },
}
_COUNCIL_PASS = {
    "verdict": "PASS",
    "findings": [],
    "semantic": {"judge_votes": [{"judge_role": "faithfulness_judge", "vote": "PASS", "findings": []}]},
}


def _vp_ontology():
    from lithrim_bench.harness.ontology import from_dict

    return from_dict(_VP_ONT_DICT)


def _case(soap, *, transcript=None):
    case = {"artifacts": [{"type": "scribe_soap", "content": soap}]}
    if transcript is not None:
        case["transcript"] = transcript
    return case


@_NEEDS_NARRATIVE_PACK
def test_value_presence_flips_pass_to_block():
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.report import composite

    g = ground(_COUNCIL_PASS, _case(SOAP_ERASED, transcript=TRANSCRIPT), ontology=_vp_ontology())
    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"
    assert composite(g)["verdict"] == "reject"
    injected = [b for b in g.floor_blocks if b["injected_finding"] is not None]
    assert {b["injected_finding"]["code"] for b in injected} == {"VALUE_DROPPED"}
    assert "VALUE_DROPPED" in [f.get("code") for f in g.active]


@_NEEDS_NARRATIVE_PACK
def test_value_presence_clean_case_stays_pass():
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.report import composite

    g = ground(_COUNCIL_PASS, _case(SOAP_KEPT, transcript=TRANSCRIPT), ontology=_vp_ontology())
    assert g.verdict == "PASS"
    assert composite(g)["verdict"] == "approve"
    assert [b for b in g.floor_blocks if b["injected_finding"] is not None] == []


@_NEEDS_NARRATIVE_PACK
def test_value_presence_inconclusive_never_flips():
    from lithrim_bench.harness.grounding import ground

    # no transcript → nothing parseable → inconclusive; the finding STANDS, no inject
    g = ground(_COUNCIL_PASS, _case(SOAP_ERASED), ontology=_vp_ontology())
    assert g.verdict == "PASS"
    vp = [b for b in g.floor_blocks if b["decl"].contract_type == "value_presence"]
    assert len(vp) == 1 and vp[0]["injected_finding"] is None


# ── A5 — subprocess grade under pack=narrative (always-runs durable flip + zero clinical leakage) ──

_GRADE_SCRIPT = r"""
import json
import sys

_opened = []


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        p = args[0].decode() if isinstance(args[0], bytes) else args[0]
        _opened.append(p)


sys.addaudithook(_audit)

from lithrim_bench.harness.grounding import ground, floor_executors
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.harness.pack import active_pack
from lithrim_bench.harness.report import composite

ONT = from_dict(json.loads(__ONT_JSON__))
COUNCIL_PASS = {"verdict": "PASS", "findings": [],
                "semantic": {"judge_votes": [{"judge_role": "faithfulness_judge", "vote": "PASS", "findings": []}]}}

TRANSCRIPT = __TRANSCRIPT__
SOAP_ERASED = __SOAP_ERASED__
SOAP_KEPT = __SOAP_KEPT__


def _case(soap, transcript=None):
    c = {"artifacts": [{"type": "scribe_soap", "content": soap}]}
    if transcript is not None:
        c["transcript"] = transcript
    return c


g_viol = ground(COUNCIL_PASS, _case(SOAP_ERASED, TRANSCRIPT), ontology=ONT)
g_clean = ground(COUNCIL_PASS, _case(SOAP_KEPT, TRANSCRIPT), ontology=ONT)
g_inconc = ground(COUNCIL_PASS, _case(SOAP_ERASED), ontology=ONT)


def _norm(p):
    return p.replace("\\", "/")


healthcare_reads = sorted({_norm(p) for p in _opened if "packs/healthcare" in _norm(p)})

print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "value_presence_registered": "value_presence" in floor_executors(),
    "violation_verdict": g_viol.verdict,
    "violation_codes": [f.get("code") for f in g_viol.active],
    "violation_composite": composite(g_viol)["verdict"],
    "clean_verdict": g_clean.verdict,
    "clean_floor_blocks": len([b for b in g_clean.floor_blocks if b["injected_finding"] is not None]),
    "inconclusive_verdict": g_inconc.verdict,
    "healthcare_reads": healthcare_reads,
}))
"""


def _run_grade() -> dict:
    script = (
        _GRADE_SCRIPT.replace("__ONT_JSON__", repr(json.dumps(_VP_ONT_DICT)))
        .replace("__TRANSCRIPT__", repr(TRANSCRIPT))
        .replace("__SOAP_ERASED__", repr(SOAP_ERASED))
        .replace("__SOAP_KEPT__", repr(SOAP_KEPT))
    )
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = PACK
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"value_presence grade subprocess failed:\n--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_value_presence_grades_under_pack_narrative():
    out = _run_grade()
    assert out["active_pack"] == PACK
    assert out["value_presence_registered"] is True
    # the headline flip — deterministic, always-runs, $0
    assert out["violation_verdict"] == "BLOCK"
    assert out["violation_composite"] == "reject"
    assert "VALUE_DROPPED" in out["violation_codes"]
    # the clean twin does not false-block; the inconclusive case stands
    assert out["clean_verdict"] == "PASS"
    assert out["clean_floor_blocks"] == 0
    assert out["inconclusive_verdict"] == "PASS"
    # admissibility: zero clinical leakage under pack=narrative
    assert out["healthcare_reads"] == [], f"healthcare leaked under pack=narrative: {out['healthcare_reads']}"
