"""LAYER2-SUPPRESS-1 — corpus-gated suppress contracts by measured form.

Two deliverables, tests-first:

1. ``EvidencePresence`` (contract_type ``evidence_presence``): a finding whose OWN
   evidence spans are verbatim (normalized) present in the source disproves itself —
   the judge cites the source text as its evidence for a claim about the artifact.
   Pure-stdlib, conservative (no spans / short quotes / not-found ⇒ stands).

2. Contract COMPOSITION in ``ground()``: multiple suppress declarations per flag_code
   run as a chain in declaration order, first disprove wins. This removes the
   one-contract-per-code binding (``contracts[decl.flag_code] = ...`` last-wins) that
   made the drop-in's ``observation_form`` undeclarable next to ``snomed_subsumption``.
   The frozen withstands read (``signals.py`` → ``Ontology.contract_for``, FIRST match)
   stays byte-identical.

The corpus gate (the hard referee: clears FPs, touches 0 gold TPs on the 173-record
clean run) is pinned at the bottom, env-gated like test_finding_units' A6.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import (
    FlagDefinition,
    Ontology,
    SeverityMap,
    VerificationContractDecl,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

TRANSCRIPT = (
    "Doctor: How are you feeling today?\n"
    "Patient: Well, I had a skin rash and hives, so I discontinued the medicine.\n"
    "Doctor: Any burning pain with the Cetaphil cleansing lotion?\n"
)


def _flag(code: str) -> FlagDefinition:
    return FlagDefinition(
        flag=code, category="faithfulness", definition="d", when_to_use="w",
        when_NOT_to_use="n", owner_roles=("faithfulness_judge",), tier="tier1",
        gradeable=True, reliability_pillar=None,
    )


def _decl(code: str, version: str, mode: str | None = None, **params) -> VerificationContractDecl:
    p = dict(params)
    if mode is not None:
        p["mode"] = mode
    return VerificationContractDecl(
        flag_code=code, question="does the evidence refute itself?",
        contract_type="evidence_presence", params=p, version=version,
    )


def _ontology(*decls: VerificationContractDecl, codes: tuple[str, ...] = ("INTERNAL_INCONSISTENCY",)) -> Ontology:
    return Ontology(
        ontology_version="test/1", domain="test",
        flags=tuple(_flag(c) for c in codes), questions=(), contracts=tuple(decls),
        severity_map=SeverityMap(
            weights={"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2},
            block_at_or_above=0.6, warn_above=0.2,
        ),
    )


def _result(code: str, quotes: list[str], verdict: str = "reject") -> dict:
    return {
        "verdict": verdict,
        "findings": [{"code": code, "severity": "HIGH", "detail": f"{code} (judges=1)"}],
        "semantic": {
            "evidence": [
                {"violation_code": code, "spans": [{"quote": q} for q in quotes]}
            ]
        },
    }


def _case() -> dict:
    return {"case_id": "t1", "transcript": TRANSCRIPT}


IN_SRC = "I had a skin rash and hives, so I discontinued the medicine."
NOT_IN_SRC = "Patient denies any history of hepatic encephalopathy at this visit."


# ── E: the EvidencePresence executor ────────────────────────────────────────────────────
def _run(decl: VerificationContractDecl, quotes: list[str], case: dict | None = None):
    from lithrim_bench.harness.grounding import EvidencePresence

    contract = EvidencePresence(decl)
    finding = {"code": decl.flag_code, "_evidence_spans": [{"quote": q} for q in quotes]}
    return contract.check(finding, case or _case())


def test_e1_any_mode_disproves_on_one_source_verbatim_span():
    v = _run(_decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1", mode="any"),
             [IN_SRC, NOT_IN_SRC])
    assert v.disproved is True
    assert IN_SRC.lower()[:20] in (v.evidence or "").lower()


def test_e2_all_mode_requires_every_span():
    mixed = _run(_decl("INTERNAL_INCONSISTENCY", "v1", mode="all"), [IN_SRC, NOT_IN_SRC])
    assert mixed.disproved is False
    both = _run(
        _decl("INTERNAL_INCONSISTENCY", "v1", mode="all"),
        [IN_SRC, "Any burning pain with the Cetaphil cleansing lotion?"],
    )
    assert both.disproved is True


def test_e2b_default_mode_is_all():
    # conservative by default: an undeclared mode must NOT fire on a partial match
    v = _run(_decl("INTERNAL_INCONSISTENCY", "v1"), [IN_SRC, NOT_IN_SRC])
    assert v.disproved is False


def test_e3_conservative_stands():
    # no spans at all — never clear by silence
    assert _run(_decl("X", "v1", mode="any"), []).disproved is False
    # every quote below min_quote_chars — inconclusive, stands
    assert _run(_decl("X", "v1", mode="any"), ["skin rash"]).disproved is False
    # nothing found in the source — stands
    assert _run(_decl("X", "v1", mode="any"), [NOT_IN_SRC]).disproved is False
    # a too-short quote must not satisfy ALL-mode vacuously alongside a real match
    assert _run(_decl("X", "v1", mode="all"), [IN_SRC, "rash"]).disproved is False


def test_e3b_min_quote_chars_floor_rejected_at_construction():
    """Critic close-out: an authored ``min_quote_chars=0`` would let a 1-char span quote
    fire an any-mode contract. Rejected at __init__ (the author-time gate 422s it; at
    grade time GRADE-GUARD-1 skip-logs it as malformed — never a silent wildcard)."""
    from lithrim_bench.harness.grounding import EvidencePresence

    with pytest.raises(ValueError, match="min_quote_chars"):
        EvidencePresence(_decl("X", "v1", mode="any", min_quote_chars=0))


def test_e4_normalized_containment():
    # case / punctuation / whitespace differences still match verbatim source content
    v = _run(
        _decl("X", "v1", mode="any"),
        ["I HAD A SKIN RASH,  AND HIVES; so i discontinued the medicine"],
    )
    assert v.disproved is True


def test_e5_source_path_resolution():
    # explicit dotted source_path
    case = {"case_id": "t2", "notes": {"source": TRANSCRIPT}}
    v = _run(_decl("X", "v1", mode="any", source_path="notes.source"), [IN_SRC], case)
    assert v.disproved is True
    # default falls back transcript -> context (the ingest normalization seam)
    v2 = _run(_decl("X", "v1", mode="any"), [IN_SRC], {"case_id": "t3", "context": TRANSCRIPT})
    assert v2.disproved is True
    # an absent source never clears
    v3 = _run(_decl("X", "v1", mode="any"), [IN_SRC], {"case_id": "t4"})
    assert v3.disproved is False


# ── C: composition — a chain of suppress contracts per flag_code ────────────────────────
def test_c1_chain_second_contract_disproves():
    # first decl inert (all-mode over a mixed span set), second fires (any-mode)
    ont = _ontology(
        _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1-all", mode="all"),
        _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1-any", mode="any"),
    )
    g = ground(_result("INTERNAL_INCONSISTENCY", [IN_SRC, NOT_IN_SRC]), _case(), ontology=ont)
    assert g.active == []
    assert len(g.suppressed) == 1
    assert g.suppressed[0]["contract"].version == "evidence-presence/v1-any"
    assert g.verdict == "PASS"


def test_c2_chain_first_disprove_wins():
    # declaration ORDER is authority order: the first firing contract is recorded
    ont = _ontology(
        _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1-any", mode="any"),
        _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1-all", mode="all"),
    )
    g = ground(_result("INTERNAL_INCONSISTENCY", [IN_SRC, NOT_IN_SRC]), _case(), ontology=ont)
    assert len(g.suppressed) == 1
    assert g.suppressed[0]["contract"].version == "evidence-presence/v1-any"


def test_c3_single_decl_unchanged():
    ont = _ontology(_decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1", mode="any"))
    fired = ground(_result("INTERNAL_INCONSISTENCY", [IN_SRC]), _case(), ontology=ont)
    assert fired.active == [] and len(fired.suppressed) == 1 and fired.verdict == "PASS"
    stands = ground(_result("INTERNAL_INCONSISTENCY", [NOT_IN_SRC]), _case(), ontology=ont)
    assert len(stands.active) == 1 and stands.suppressed == [] and stands.verdict == "BLOCK"


class _Boom:
    """A suppress executor whose check always raises (a dead service)."""

    def __init__(self, decl):
        self.flag_code = decl.flag_code
        self.version = decl.version

    def check(self, finding, case):
        raise RuntimeError("terminology service unreachable")


def test_c4_chain_survives_executor_error(monkeypatch):
    import lithrim_bench.harness.grounding as gr

    monkeypatch.setitem(gr._CONTRACT_EXECUTORS, "boom", _Boom)
    boom = VerificationContractDecl(
        flag_code="INTERNAL_INCONSISTENCY", question="q",
        contract_type="boom", params={}, version="boom/v1",
    )
    # a later contract in the chain still gets its say after an executor error…
    ont = _ontology(boom, _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1", mode="any"))
    g = ground(_result("INTERNAL_INCONSISTENCY", [IN_SRC]), _case(), ontology=ont)
    assert g.active == [] and len(g.suppressed) == 1
    # …and when nothing disproves, the finding STANDS carrying the error for audit
    ont2 = _ontology(boom, _decl("INTERNAL_INCONSISTENCY", "evidence-presence/v1", mode="all"))
    g2 = ground(_result("INTERNAL_INCONSISTENCY", [IN_SRC, NOT_IN_SRC]), _case(), ontology=ont2)
    assert len(g2.active) == 1
    assert "_grounding_error" in g2.active[0]


def test_c5_contract_for_stays_first_match():
    """The frozen withstands read (signals.py:182) binds via contract_for — FIRST declared.
    Composition must not change that pick."""
    ont = _ontology(
        _decl("INTERNAL_INCONSISTENCY", "first/v1", mode="all"),
        _decl("INTERNAL_INCONSISTENCY", "second/v1", mode="any"),
    )
    assert ont.contract_for("INTERNAL_INCONSISTENCY").version == "first/v1"
    assert [d.version for d in ont.contracts_for("INTERNAL_INCONSISTENCY")] == [
        "first/v1", "second/v1",
    ]
    assert ont.contracts_for("NOPE") == ()


# ── CG: the corpus gate — the hard referee over the 173-record clean run ────────────────
# Env-gated exactly like test_finding_units' A6: needs the clean-run records
# (LITHRIM_BENCH_CLEANRUN_DIR) + the untracked clinverdict drop-in pack.
_CLEANRUN = os.environ.get("LITHRIM_BENCH_CLEANRUN_DIR")
_DROPIN = REPO_ROOT / "packs-dropin" / "clinverdict"


@pytest.mark.skipif(
    not (_CLEANRUN and Path(_CLEANRUN).is_dir() and _DROPIN.is_dir()),
    reason="corpus gate needs LITHRIM_BENCH_CLEANRUN_DIR + the clinverdict drop-in pack",
)
def test_cg_corpus_gate_24_fps_zero_tp_touch(monkeypatch):
    """The Layer-2 declarations (observation_form on HALLUCINATED_DETAIL;
    evidence_presence on HALLUCINATED_DETAIL + INTERNAL_INCONSISTENCY) clear exactly the
    measured FPs and touch ZERO gold TPs on the 2026-07-01 clean-run snapshot —
    exercised through the REAL ground() + the REAL drop-in ontology declarations.

    The pin is 24 under observation-form/v2 (sentence-level): the 2026-07-02 measurement
    pass caught the v1 whole-span regex-search clearing a GOLD whose judge span mixed a
    negation cue with the injected positive fabrication (cv_mts_118). v2 requires every
    SENTENCE to be a nonfab form — 0 golds on BOTH passes (v1 was 19 FP here but unsafe;
    v2 keeps 4 of them + the 20 evidence_presence clears)."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", "clinverdict")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(REPO_ROOT / "packs-dropin"))

    from lithrim_bench.harness import ontology as ont_mod

    raw = json.loads((_DROPIN / "ontology.json").read_text())
    # only the NEW Layer-2 contracts: the snomed decls need live Hermes (out of scope here;
    # their effect is already IN the stored grounded.active baseline).
    raw["verification_contracts"] = [
        c for c in raw.get("verification_contracts", [])
        if c["contract_type"] in ("observation_form", "evidence_presence")
    ]
    assert raw["verification_contracts"], "the Layer-2 decls must exist in the drop-in ontology"
    ontology = ont_mod.from_dict(raw)

    corpus = {}
    with open(_DROPIN / "examples" / "clinverdict_mts_v1.jsonl") as fh:
        for line in fh:
            row = json.loads(line)
            corpus[row["case_id"]] = row

    cleared_fp = cleared_tp = 0
    for path in sorted(Path(_CLEANRUN).glob("cv_mts_*.json")):
        rec = json.loads(path.read_text())
        case = corpus.get(rec["case_id"])
        if case is None:
            continue
        gold = set(case.get("expected_safety_flags") or [])
        stored_active = {
            (f.get("code") or f.get("flag_code"))
            for f in (rec.get("grounded") or {}).get("active", [])
        }
        g = ground(rec["result"], case, ontology=ontology)
        assert g.skipped_malformed == [], f"{rec['case_id']}: {g.skipped_malformed}"
        new_active = {f.get("code") for f in g.active}
        suppressed_codes = {e["finding"].get("code") for e in g.suppressed}
        for code in suppressed_codes:
            if code in stored_active and code not in new_active:
                if code in gold:
                    cleared_tp += 1
                else:
                    cleared_fp += 1
    assert cleared_tp == 0, f"the corpus gate is broken: {cleared_tp} gold TPs suppressed"
    assert cleared_fp == 24, f"expected the measured 24 cleared FPs (v2 form), got {cleared_fp}"
