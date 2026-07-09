"""CE-PACK-6b-CLEAN D5/C4 — the frozen-seam guards stay NON-VACUOUS after authorizing
the ``build_prompt`` deletion + the ``_build_signature`` genericization.

Each guard is proven in BOTH directions on SYNTHESIZED inputs (the test_pack_layer2c
pattern), so the authorization can never silently pass an unauthorized edit:

  * council carve-out guard — the authorized build_prompt deletion + transcript-branch
    raise PASS; an unauthorized deletion (``_apply_consensus``) and a raise WITHOUT the
    ``6b-CLEAN`` sentinel FAIL.
  * council carve-out guard, CE-PACK-6c — the authorized ``build_source_message_prompt``
    deletion + the ``CE-PACK-6c`` source_message raise PASS; deleting an UN-authorized
    method (``_format_kb_citations``) and a source_message raise WITHOUT the ``CE-PACK-6c``
    sentinel FAIL (the deletion auth is keyed to the SPECIFIC marker, not 'any deletion').
  * judges_dspy seam guard — genericizing ``_build_signature`` PASSES (excluded); editing
    a frozen symbol (``evaluate_dspy``) FAILS.
  * clinical-ontology guard — a flags / ``_provenance.flag_source`` edit FAILS (this is
    what pins the D2-a decision to keep ``flag_source`` VERBATIM).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests._seam_freeze import (
    _CLINICAL_ONTOLOGY_BASELINE_REL,
    _COMPLIANCE_COUNCIL_REL,
    _JUDGES_DSPY_REL,
    _assert_clinical_ontology_frozen,
    _assert_judges_dspy_seam_frozen,
    assert_council_carveouts_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _baseline_or_skip(rel: str) -> str:
    """The acc4973 baseline text for ``rel`` via the ONE resolution seam (S-REL-18) —
    public-mode SKIP when the baseline commit is unavailable (fresh-cut public history).
    Every guard family here tampers REAL baseline text, so none is pin-expressible."""
    import tests._seam_freeze as sf

    base = sf._resolve_baseline(REPO_ROOT, rel)
    if base is None:
        pytest.skip("public-mode: baseline commit unavailable; attested in the private history")
    return base


# ── council carve-out guard (assert_council_carveouts_only) ──────────────────

# The transcript-branch raise is a SINGLE line carrying the ``6b-CLEAN`` sentinel — the
# S-BS-124 per-line bar requires EVERY added code line to carry a marker, so a multi-line
# raise (whose closing paren line has none) is correctly rejected. D4 uses this exact line.
_RAISE_6BCLEAN = (
    '            raise ValueError(f"6b-CLEAN: evaluate() no longer grades transcripts '
    '(the authored stage is the single live prompt source); context_kind={context_kind!r} '
    'is source_message-only")'
)


def _council_base_lines() -> list[str]:
    return _baseline_or_skip(_COMPLIANCE_COUNCIL_REL).splitlines(keepends=True)


def _council_cur_text() -> str:
    return (REPO_ROOT / _COMPLIANCE_COUNCIL_REL).read_text()


def _simulate_d4(cur: str) -> str:
    """Apply the D4 frozen edits to ``cur`` in-memory: delete build_prompt + its import,
    raise on the transcript branch (with the 6b-CLEAN sentinel)."""
    start = cur.index("    def build_prompt(self")
    end = cur.index("    # ── Source-message prompt family")
    cur = cur[:start] + cur[end:]
    cur = cur.replace("from .safety_flags import get_flag_prompt_section\n", "")
    cur = cur.replace(
        "            prompt = self.build_prompt(context_payload)", _RAISE_6BCLEAN
    )
    return cur


def test_authorized_build_prompt_deletion_and_raise_pass():
    """A5 upper bound: the FULL post-D4 state (4 pack carve-outs + the build_prompt deletion +
    the import deletion + the 6b-CLEAN transcript raise) is admitted by the guard. Pre-D4 this
    is synthesized from the current tree (pre-validating the frozen edit); post-D4 the real tree
    already carries it, so the guard is asserted on the real state directly."""
    cur = _council_cur_text()
    if "def build_prompt" in cur:  # pre-D4: synthesize the deletion to pre-validate
        cur = _simulate_d4(cur)
    assert "def build_prompt" not in cur and "get_flag_prompt_section" not in cur
    assert "6b-CLEAN" in cur  # the authorized transcript raise
    assert_council_carveouts_only(_council_base_lines(), cur)  # does not raise


def test_unauthorized_deletion_of_consensus_still_fails():
    """C4(a): deleting the frozen consensus IP (``_apply_consensus``) carries no
    authorized-deletion marker → the guard FAILS."""
    cur = _council_cur_text()
    lines = cur.splitlines(keepends=True)
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("    def _apply_consensus(self"))
    tampered = "".join(lines[:idx] + lines[idx + 15 :])  # drop 15 lines of the method
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(_council_base_lines(), tampered)


def test_transcript_raise_without_6bclean_marker_fails():
    """C4: the transcript-branch raise MUST carry the ``6b-CLEAN`` sentinel — a raise lacking
    it is a marker-less replace line → the S-BS-124 per-line bar FAILS it. Robust to both the
    pre-D4 (``prompt = self.build_prompt(...)``) and post-D4 (the real 6b-CLEAN raise) tree."""
    cur = _council_cur_text()
    bad = '            raise ValueError("transcript not supported")'  # no 6b-CLEAN marker
    pre = "            prompt = self.build_prompt(context_payload)"
    if pre in cur:  # pre-D4
        tampered = cur.replace(pre, bad)
    else:  # post-D4: swap the real 6b-CLEAN transcript raise for a marker-less one
        lines = cur.splitlines(keepends=True)
        hits = [i for i, ln in enumerate(lines) if "6b-CLEAN: evaluate() no longer grades" in ln]
        assert len(hits) == 1
        lines[hits[0]] = bad + "\n"
        tampered = "".join(lines)
    assert tampered != cur
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(_council_base_lines(), tampered)


# ── council carve-out guard, CE-PACK-6c (build_source_message_prompt) ────────


def test_authorized_source_message_deletion_and_raise_pass():
    """A4/A5 upper bound (CE-PACK-6c): the real post-6c tree — ``build_source_message_prompt``
    DELETED + the ``CE-PACK-6c`` source_message raise — is admitted by the guard (it also
    still carries the 6b-CLEAN build_prompt deletion + the transcript raise, untouched)."""
    cur = _council_cur_text()
    assert "def build_source_message_prompt" not in cur
    assert "CE-PACK-6c" in cur  # the authorized source_message raise
    assert "6b-CLEAN" in cur  # the 6b transcript raise is still present (untouched)
    assert_council_carveouts_only(_council_base_lines(), cur)  # does not raise


def test_unauthorized_method_deletion_still_fails():
    """C4 (CE-PACK-6c): deleting an UN-authorized method (``_format_kb_citations``, an inert
    source_message helper that is NOT on the authorized-deletion list) carries no marker → the
    guard FAILS. Proves the deletion auth is keyed to the SPECIFIC marker (``def build_prompt`` /
    ``def build_source_message_prompt``), not 'any deletion' — so retiring the leftover retrieval
    helpers is a deliberate future decision, not something this authorization waved through."""
    cur = _council_cur_text()
    lines = cur.splitlines(keepends=True)
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("    def _format_kb_citations("))
    tampered = "".join(lines[:idx] + lines[idx + 15 :])  # drop 15 lines of the method (no marker)
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(_council_base_lines(), tampered)


def test_source_message_raise_without_6c_marker_fails():
    """C4 (CE-PACK-6c): the source_message-branch raise MUST carry the ``CE-PACK-6c`` sentinel —
    a raise lacking it is a marker-less replace line → the S-BS-124 per-line bar FAILS it (so the
    branch body can't be swapped for arbitrary code under cover of the authorized hunk)."""
    cur = _council_cur_text()
    lines = cur.splitlines(keepends=True)
    hits = [i for i, ln in enumerate(lines) if "CE-PACK-6c: evaluate() no longer builds" in ln]
    assert len(hits) == 1
    lines[hits[0]] = '            raise ValueError("source_message not supported")\n'  # no marker
    tampered = "".join(lines)
    assert tampered != cur
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(_council_base_lines(), tampered)


# ── judges_dspy seam guard (_assert_judges_dspy_seam_frozen) ─────────────────


def test_signature_genericization_is_authorized():
    """A5: changing ``_build_signature``'s clinical prose is admitted (it is in the
    authorized seam) — the D3 genericization passes."""
    base = _baseline_or_skip(_JUDGES_DSPY_REL)
    needle = "HIPAA / clinical-safety compliance council"
    assert base.count(needle) == 1  # the prose lives only in _build_signature
    tampered = base.replace(needle, "audit council")
    _assert_judges_dspy_seam_frozen(base, tampered)  # does not raise


def test_unauthorized_edit_to_evaluate_dspy_still_fails():
    """C4(b): editing a FROZEN symbol (``evaluate_dspy``, the ``_apply_consensus`` call)
    drifts it → the guard FAILS."""
    base = _baseline_or_skip(_JUDGES_DSPY_REL)
    assert base.count("def evaluate_dspy(") == 1
    tampered = base.replace(
        "def evaluate_dspy(", "def evaluate_dspy(  # TAMPERED-FROZEN-EDIT", 1
    )
    with pytest.raises(AssertionError, match="drifted"):
        _assert_judges_dspy_seam_frozen(base, tampered)


def test_unauthorized_new_symbol_in_judges_dspy_still_fails():
    """C4(b) addendum: a smuggled NEW top-level symbol changes the symbol set → FAILS."""
    base = _baseline_or_skip(_JUDGES_DSPY_REL)
    tampered = base + "\n\ndef _smuggled_backdoor():\n    return True\n"
    with pytest.raises(AssertionError, match="symbol set changed"):
        _assert_judges_dspy_seam_frozen(base, tampered)


# ── clinical-ontology guard (_assert_clinical_ontology_frozen) ───────────────


def _ontology_base() -> dict:
    return json.loads(_baseline_or_skip(_CLINICAL_ONTOLOGY_BASELINE_REL))


def test_unauthorized_flag_edit_still_fails():
    """C4(c): editing a flag definition trips the ontology seam guard."""
    base = _ontology_base()
    tampered = copy.deepcopy(base)
    tampered["flags"][0]["definition"] = "TAMPERED-FLAG-DEFINITION"
    with pytest.raises(AssertionError, match="seam drifted"):
        _assert_clinical_ontology_frozen(copy.deepcopy(base), tampered)


def test_authorized_additive_flags_do_not_trip_but_unlisted_ones_do():
    """Owner-ratified post-acc4973 evolution (2026-06-30): the 2 authorized additive flags
    (PROXY_MISATTRIBUTION, HISTORY_OMISSION) added to the flag set do NOT trip the seam guard
    (additive carve-out, like verification_contracts), but ANY unlisted new flag still does —
    so the carve-out is non-vacuous."""
    base = _ontology_base()
    ok = copy.deepcopy(base)
    ok["flags"].append({"flag": "PROXY_MISATTRIBUTION", "definition": "ratified", "gradeable": True})
    ok["flags"].append({"flag": "HISTORY_OMISSION", "definition": "ratified", "gradeable": True})
    _assert_clinical_ontology_frozen(copy.deepcopy(base), ok)  # authorized → no raise

    bad = copy.deepcopy(base)
    bad["flags"].append({"flag": "SOME_UNLISTED_FLAG", "definition": "z", "gradeable": True})
    with pytest.raises(AssertionError, match="seam drifted"):
        _assert_clinical_ontology_frozen(copy.deepcopy(base), bad)


def test_changing_flag_source_provenance_would_trip_the_guard():
    """C4(c) / D2-a pin: changing ``_provenance.flag_source`` to the NEW pack path WOULD
    trip the ontology seam guard — which is exactly why D2-a keeps the literal VERBATIM
    (the moat-frozen ontology stays byte-identical; no _provenance guard exemption)."""
    base = _ontology_base()
    tampered = copy.deepcopy(base)
    tampered["_provenance"]["flag_source"] = (
        "packs/healthcare/safety_flags_seed.py:SAFETY_FLAG_DEFINITIONS"
    )
    with pytest.raises(AssertionError, match="seam drifted"):
        _assert_clinical_ontology_frozen(copy.deepcopy(base), tampered)
