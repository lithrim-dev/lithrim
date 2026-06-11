"""CE-PACK-6b-CLEAN D5/C4 — the frozen-seam guards stay NON-VACUOUS after authorizing
the ``build_prompt`` deletion + the ``_build_signature`` genericization.

Each guard is proven in BOTH directions on SYNTHESIZED inputs (the test_pack_layer2c
pattern), so the authorization can never silently pass an unauthorized edit:

  * council carve-out guard — the authorized build_prompt deletion + transcript-branch
    raise PASS; an unauthorized deletion (``_apply_consensus``) and a raise WITHOUT the
    ``6b-CLEAN`` sentinel FAIL.
  * judges_dspy seam guard — genericizing ``_build_signature`` PASSES (excluded); editing
    a frozen symbol (``evaluate_dspy``) FAILS.
  * clinical-ontology guard — a flags / ``_provenance.flag_source`` edit FAILS (this is
    what pins the D2-a decision to keep ``flag_source`` VERBATIM).
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from tests._seam_freeze import (
    _CLINICAL_ONTOLOGY_BASELINE_REL,
    _COMPLIANCE_COUNCIL_REL,
    _JUDGES_DSPY_REL,
    _SEAM_BASELINE,
    _assert_clinical_ontology_frozen,
    _assert_judges_dspy_seam_frozen,
    assert_council_carveouts_only,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git_show(rel: str) -> str:
    return subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{rel}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


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
    return _git_show(_COMPLIANCE_COUNCIL_REL).splitlines(keepends=True)


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
    """A5 upper bound: the FULL post-D4 state (4 pack carve-outs + the build_prompt
    deletion + the import deletion + the 6b-CLEAN transcript raise) is admitted."""
    cur = _council_cur_text()
    simulated = _simulate_d4(cur)
    # the synthesis actually applied (else the test is vacuous)
    assert "def build_prompt" not in simulated
    assert "get_flag_prompt_section" not in simulated
    assert "6b-CLEAN" in simulated
    assert_council_carveouts_only(_council_base_lines(), simulated)  # does not raise


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
    """C4: the transcript-branch raise MUST carry the ``6b-CLEAN`` sentinel — a raise
    lacking it is a marker-less replace line → the S-BS-124 per-line bar FAILS it."""
    cur = _council_cur_text()
    tampered = cur.replace(
        "            prompt = self.build_prompt(context_payload)",
        '            raise ValueError("transcript not supported")',  # no 6b-CLEAN marker
    )
    with pytest.raises(AssertionError, match="unauthorized"):
        assert_council_carveouts_only(_council_base_lines(), tampered)


# ── judges_dspy seam guard (_assert_judges_dspy_seam_frozen) ─────────────────


def test_signature_genericization_is_authorized():
    """A5: changing ``_build_signature``'s clinical prose is admitted (it is in the
    authorized seam) — the D3 genericization passes."""
    base = _git_show(_JUDGES_DSPY_REL)
    needle = "HIPAA / clinical-safety compliance council"
    assert base.count(needle) == 1  # the prose lives only in _build_signature
    tampered = base.replace(needle, "audit council")
    _assert_judges_dspy_seam_frozen(base, tampered)  # does not raise


def test_unauthorized_edit_to_evaluate_dspy_still_fails():
    """C4(b): editing a FROZEN symbol (``evaluate_dspy``, the ``_apply_consensus`` call)
    drifts it → the guard FAILS."""
    base = _git_show(_JUDGES_DSPY_REL)
    assert base.count("def evaluate_dspy(") == 1
    tampered = base.replace(
        "def evaluate_dspy(", "def evaluate_dspy(  # TAMPERED-FROZEN-EDIT", 1
    )
    with pytest.raises(AssertionError, match="drifted"):
        _assert_judges_dspy_seam_frozen(base, tampered)


def test_unauthorized_new_symbol_in_judges_dspy_still_fails():
    """C4(b) addendum: a smuggled NEW top-level symbol changes the symbol set → FAILS."""
    base = _git_show(_JUDGES_DSPY_REL)
    tampered = base + "\n\ndef _smuggled_backdoor():\n    return True\n"
    with pytest.raises(AssertionError, match="symbol set changed"):
        _assert_judges_dspy_seam_frozen(base, tampered)


# ── clinical-ontology guard (_assert_clinical_ontology_frozen) ───────────────


def _ontology_base() -> dict:
    return json.loads(_git_show(_CLINICAL_ONTOLOGY_BASELINE_REL))


def test_unauthorized_flag_edit_still_fails():
    """C4(c): editing a flag definition trips the ontology seam guard."""
    base = _ontology_base()
    tampered = copy.deepcopy(base)
    tampered["flags"][0]["definition"] = "TAMPERED-FLAG-DEFINITION"
    with pytest.raises(AssertionError, match="seam drifted"):
        _assert_clinical_ontology_frozen(copy.deepcopy(base), tampered)


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
