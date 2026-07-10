"""CRITERION-JUTE-1c — the bidirectional corpus GATE, proven NON-VACUOUS in both directions.

Spec Section 5.3 + 6.2 + 10. This test replays a candidate ``mcp_call`` + ``arguments_jute``
contract over the 44-case bidirectional subsumption corpus (22 upcoded positives + 22
clean-generalization negatives) plus 2 SPAN-BIND analogue positives (cv_mts_104/105 class),
through the REAL ``grounding.McpCallGrounding`` executor (the 1a wire), and asserts the gate:

  GREEN (golden finding-local mapping + true oracle):
    * 22/22 clean-generalization negatives CLEAR (finding disproved -> PASS),
    * 22/22 upcoded positives STAND (finding not disproved -> BLOCK),
    * SPAN-BIND: the fabrication finding STANDS, the generalization finding CLEARS,
    * ``assert_gate_passes`` does NOT raise.

  NON-VACUITY (each MUST make ``assert_gate_passes`` RAISE, naming the right case ids):
    (a) WRONG-DIRECTION mapping (swap concept_id<->subsumer_id) -> negatives stand + positives clear.
    (b) CASE-GLOBAL mapping (ignore the finding, always return a fixed clean pair) -> the SPAN-BIND
        fabrication false-clears.
    (c) SILENCE oracle (always False) -> negatives never clear (never cleared by silence).

HONESTY DISCLOSURE (spec Section 10): this gate tests contract DIRECTION + SPAN-BINDING +
PARTITION given CORRECT terminology facts. It does NOT re-derive the SNOMED is-a facts — those
are integration-proven LIVE via Hermes SNOMED (edition 20260501) in the prototype
``scratchpad/toolground_proto.py`` (Alzheimer's 26929004 is-a Dementia 52448006 == True; the
reverse == False). The offline ``snomed_oracle`` here shares the corpus's own parent/child
annotation (the child is-a the parent, both directions False for a fabrication). That is a
BOUNDED, DISCLOSED circularity — the terminology-fact source, held constant so the gate can
isolate the CONTRACT's direction/span-binding/partition behaviour — not hidden self-grading.

Networkless: :3031 (the live JUTE-apply) is DOWN, so a fake ``jute_apply`` stands in for the
pinned transform; Hermes (the live SNOMED server) is replaced by the offline ``snomed_oracle``.
Both seams are injected by ``argshape_gate.gate_contract_over_corpus`` into the real executor.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from lithrim_bench.verification.argshape_gate import (
    GateFailure,
    assert_gate_passes,
    gate_contract_over_corpus,
)

FIXTURES = Path(__file__).parent / "fixtures" / "subsumption_bidirectional"

# The source corpus (a maintainer-local research tree) — read ONLY to derive the
# disclosed-circularity oracle's parent/child annotation (the fixtures themselves are blind).
# Override with LITHRIM_BENCH_SUBSUMPTION_SOURCE_DIR. If it is absent (a fresh clone), the
# oracle falls back to the case-expectation-derived direction, which is equivalent for these
# labels.
SOURCE_DIR = Path(
    os.environ.get(
        "LITHRIM_BENCH_SUBSUMPTION_SOURCE_DIR",
        str(Path(__file__).resolve().parents[1] / "docs" / "clinverdict" / "bidirectional_proposal"),
    )
)


# --------------------------------------------------------------------------- #
# corpus loading
# --------------------------------------------------------------------------- #
def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def negatives() -> list[dict]:
    return _load_jsonl(FIXTURES / "clean_generalization_negatives.jsonl")


@pytest.fixture(scope="module")
def positives() -> list[dict]:
    return _load_jsonl(FIXTURES / "upcoded_positives.jsonl")


@pytest.fixture(scope="module")
def span_bind() -> list[dict]:
    return _load_jsonl(FIXTURES / "span_bind_positives.jsonl")


@pytest.fixture(scope="module")
def corpus(positives, negatives, span_bind) -> list[dict]:
    return [*positives, *negatives, *span_bind]


# --------------------------------------------------------------------------- #
# the SNOMED oracle — derived, not hand-transcribed
# --------------------------------------------------------------------------- #
def _child_parent_of_source_case(case: dict) -> tuple[str, str] | None:
    """(child_code, parent_code) from a SOURCE case's parent/child annotation, or None."""
    sub = case.get("pinned", {}).get("subsumption", {})

    def clean(x):
        return None if x is None else str(x).split("(")[0].strip()

    if "record_parent_snomed" in sub:  # upcoded: record=parent, note=child
        return clean(sub.get("note_child_snomed")), clean(sub.get("record_parent_snomed"))
    if "record_child_snomed" in sub:  # clean: record=child, note=parent
        return clean(sub.get("record_child_snomed")), clean(sub.get("note_parent_snomed"))
    return None


def build_snomed_oracle(positives, negatives, span_bind):
    """Build ``snomed_oracle(call, args) -> bool`` from the corpus's child/parent annotation.

    The single is-a fact per pair: the CHILD (specific) is-a the PARENT (general), so
    ``subsumed_by(concept_id=child, subsumer_id=parent) == True`` and the reverse ``== False``.
    Every SPAN-BIND fabrication pair returns False BOTH ways (declared, by construction). Any
    pair not in the fact table returns False (never cleared by an unknown fact).
    """
    is_a: dict[tuple[int, int], bool] = {}

    # (1) the disclosed-circularity fact table from the source annotation (parent/child names).
    for name in ("upcoded_positives.jsonl", "clean_generalization_negatives.jsonl"):
        src = SOURCE_DIR / name
        if not src.exists():
            continue
        for case in _load_jsonl(src):
            cp = _child_parent_of_source_case(case)
            if not cp or None in cp:
                continue
            child, parent = int(cp[0]), int(cp[1])
            is_a[(child, parent)] = True  # child is-a parent
            is_a.setdefault((parent, child), False)  # reverse is NOT is-a

    # (2) fallback for any blind pair whose direction the source didn't cover: use the case
    #     expectation. A negative (PASS) means subsumed_by(record, note)=True; a positive
    #     (BLOCK) means subsumed_by(record, note)=False.
    for case in negatives:
        for f in case.get("_synth_findings", []):
            c = int(f["subsumption_codes"]["record_snomed"])
            s = int(f["subsumption_codes"]["note_snomed"])
            is_a.setdefault((c, s), True)
            is_a.setdefault((s, c), False)
    for case in positives:
        for f in case.get("_synth_findings", []):
            c = int(f["subsumption_codes"]["record_snomed"])
            s = int(f["subsumption_codes"]["note_snomed"])
            is_a.setdefault((c, s), False)
            is_a.setdefault((s, c), True)

    # (3) SPAN-BIND: generalizations follow the true is-a; fabrications are False both ways.
    for case in span_bind:
        for f in case.get("_synth_findings", []):
            c = int(f["subsumption_codes"]["record_snomed"])
            s = int(f["subsumption_codes"]["note_snomed"])
            if f.get("_fabrication"):
                is_a[(c, s)] = False
                is_a[(s, c)] = False
            else:  # a clean generalization: record child is-a note parent
                is_a.setdefault((c, s), True)
                is_a.setdefault((s, c), False)

    def snomed_oracle(call: str, args: dict) -> dict:
        assert call == "subsumed_by", call
        c, s = int(args["concept_id"]), int(args["subsumer_id"])
        return {"subsumedBy": bool(is_a.get((c, s), False))}

    return snomed_oracle


# --------------------------------------------------------------------------- #
# the GOLDEN finding-local mapping (the pinned transform under test)
# --------------------------------------------------------------------------- #
# The pinned arguments_jute text is DOCUMENTARY here — :3031 (the live apply) is down, so the
# fake jute_apply stands in for it. The text below is the exact shape the prototype proved
# (concept_id <- the record code, subsumer_id <- the note code, both int-coerced) and its
# sha256 is set so the 1a hash-verify in _shape_arguments passes.
GOLDEN_ARGUMENTS_JUTE = (
    "$let:\n"
    "  codes: $ resource.finding.subsumption_codes\n"
    "$body:\n"
    "  concept_id: $ num(codes.record_snomed)\n"
    "  subsumer_id: $ num(codes.note_snomed)\n"
)
GOLDEN_SHA256 = hashlib.sha256(GOLDEN_ARGUMENTS_JUTE.encode("utf-8")).hexdigest()


def _contract_params(arguments_jute: str) -> dict:
    return {
        "tool": "gate_snomed_subsumption",
        "call": "subsumed_by",
        "arguments_jute": arguments_jute,
        "arguments_jute_sha256": hashlib.sha256(arguments_jute.encode("utf-8")).hexdigest(),
        "authority": "corroborated",
        "match": "subsumedBy",
    }


# --- the jute_apply seams (stand in for the pinned :3031 transform) --------------------------
def golden_jute_apply(case: dict, finding: dict) -> dict:
    """The FINDING-LOCAL shaper: concept_id <- the finding's record code, subsumer_id <- its note."""
    codes = finding["subsumption_codes"]
    return {
        "compiled": True,
        "output": {
            "concept_id": int(codes["record_snomed"]),
            "subsumer_id": int(codes["note_snomed"]),
        },
    }


def wrong_direction_jute_apply(case: dict, finding: dict) -> dict:
    """Mutant (a): swap concept_id<->subsumer_id -> tests subsumed_by(note, record)."""
    codes = finding["subsumption_codes"]
    return {
        "compiled": True,
        "output": {
            "concept_id": int(codes["note_snomed"]),
            "subsumer_id": int(codes["record_snomed"]),
        },
    }


def make_case_global_jute_apply(clean_pair: tuple[int, int]):
    """Mutant (b): ignore the finding entirely, always return a fixed CLEAN (child, parent) pair.

    On a span-bind case this false-clears the fabrication finding once ANY clean pair matches
    the oracle, because the arguments no longer bind to the finding's own spans.
    """

    def apply(case: dict, finding: dict) -> dict:
        return {
            "compiled": True,
            "output": {"concept_id": clean_pair[0], "subsumer_id": clean_pair[1]},
        }

    return apply


# --------------------------------------------------------------------------- #
# GREEN: golden mapping + true oracle
# --------------------------------------------------------------------------- #
def test_green_golden_mapping_clears_negatives_and_stands_positives(
    corpus, positives, negatives, span_bind
):
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    report = gate_contract_over_corpus(
        _contract_params(GOLDEN_ARGUMENTS_JUTE),
        corpus,
        jute_apply=golden_jute_apply,
        snomed_oracle=oracle,
    )
    assert report.negatives_total == 22
    assert report.negatives_cleared == 22, report.negative_stands
    assert report.positives_total == 24  # 22 upcoded + 2 span-bind positives
    assert report.positives_standing == 24, report.positive_clears
    assert report.span_bind_cases == 2
    assert report.span_bind_ok == 2, report.span_bind_fabrication_clears
    assert report.failures == []
    assert report.passed is True
    # does NOT raise
    assert_gate_passes(report)


def test_green_span_bind_partition(positives, negatives, span_bind):
    """The two findings on each span-bind case partition correctly: fabrication STANDS, gen CLEARS."""
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    report = gate_contract_over_corpus(
        _contract_params(GOLDEN_ARGUMENTS_JUTE),
        span_bind,
        jute_apply=golden_jute_apply,
        snomed_oracle=oracle,
    )
    by_role = {(r.case_id, r.role): r.cleared for r in report.findings}
    for case in span_bind:
        cid = case["case_id"]
        assert by_role[(cid, "fabrication_stands")] is False, "fabrication must STAND"
        assert by_role[(cid, "generalization_clears")] is True, "generalization must CLEAR"
    assert report.span_bind_ok == 2


def test_green_hash_pins_the_transform(positives, negatives, span_bind):
    """A drifted arguments_jute (sha256 mismatch) makes _shape_arguments REFUSE -> finding stands.

    Proves the golden GREEN clears only because the pinned transform's hash verifies; a tampered
    transform never grades through (so a negative would then wrongly stand). Guards the 1a wire is
    actually reached, not bypassed."""
    bad_params = _contract_params(GOLDEN_ARGUMENTS_JUTE)
    bad_params["arguments_jute_sha256"] = "0" * 64  # deliberate drift
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    report = gate_contract_over_corpus(
        bad_params, negatives, jute_apply=golden_jute_apply, snomed_oracle=oracle
    )
    # every negative now STANDS (transform refused) -> gate fails
    assert report.negatives_cleared == 0
    with pytest.raises(GateFailure):
        assert_gate_passes(report)


# --------------------------------------------------------------------------- #
# NON-VACUITY (a): WRONG-DIRECTION mapping -> negatives stand + positives clear
# --------------------------------------------------------------------------- #
def test_nonvacuity_a_wrong_direction_fails(corpus, positives, negatives, span_bind):
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    report = gate_contract_over_corpus(
        _contract_params(GOLDEN_ARGUMENTS_JUTE),
        corpus,
        jute_apply=wrong_direction_jute_apply,
        snomed_oracle=oracle,
    )
    # negatives now STAND (subsumed_by(note, record) is False for a clean generalization)
    assert report.negatives_cleared == 0
    assert len(report.negative_stands) == 22
    # the 22 upcoded positives now CLEAR (subsumed_by(note=child, record=parent) is True)
    upcode_ids = {c["case_id"] for c in positives}
    assert upcode_ids.issubset(set(report.positive_clears))
    with pytest.raises(GateFailure) as ei:
        assert_gate_passes(report)
    msg = str(ei.value)
    assert "false block" in msg and "false clear" in msg


# --------------------------------------------------------------------------- #
# NON-VACUITY (b): CASE-GLOBAL mapping -> span-bind fabrication false-clears
# --------------------------------------------------------------------------- #
def test_nonvacuity_b_case_global_fails_span_bind(positives, negatives, span_bind):
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    # a fixed CLEAN (child, parent) pair the oracle subsumes: Alzheimer's is-a Dementia.
    case_global = make_case_global_jute_apply((26929004, 52448006))
    report = gate_contract_over_corpus(
        _contract_params(GOLDEN_ARGUMENTS_JUTE),
        span_bind,
        jute_apply=case_global,
        snomed_oracle=oracle,
    )
    # every finding (incl. the fabrication) now clears -> the fabrication false-cleared
    assert set(report.span_bind_fabrication_clears) == {c["case_id"] for c in span_bind}
    with pytest.raises(GateFailure) as ei:
        assert_gate_passes(report)
    assert "span-bind false clear" in str(ei.value)


# --------------------------------------------------------------------------- #
# NON-VACUITY (c): SILENCE oracle -> negatives never clear
# --------------------------------------------------------------------------- #
def test_nonvacuity_c_silence_oracle_fails(negatives):
    def silent_oracle(call: str, args: dict) -> dict:
        return {"subsumedBy": False}

    report = gate_contract_over_corpus(
        _contract_params(GOLDEN_ARGUMENTS_JUTE),
        negatives,
        jute_apply=golden_jute_apply,
        snomed_oracle=silent_oracle,
    )
    # corroborated authority clears ONLY on a positive match; silence never clears
    assert report.negatives_cleared == 0
    assert len(report.negative_stands) == 22
    with pytest.raises(GateFailure) as ei:
        assert_gate_passes(report)
    assert "false block" in str(ei.value)
