"""CE-PACK-6b-CLEAN — the demarcation attestation (re-scoped A1 per Fork 1).

The ``build_prompt`` + ``safety_flags`` + ``_build_signature`` clinical residue is GONE
from the core council (A2/A3). The remaining clinical needles in ``runtime/council/`` are
**not** zero — this is NOT a grep-clean claim. They are ENUMERATED here and attributed to
documented out-of-scope buckets; the literal "grep → empty" goal is deferred to the **6c
seam** (relocate ``build_source_message_prompt``; decide ``phi_redaction``'s fate) — see
``docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md`` §4. This test PINS the residual so the
demarcation cannot silently regress (a new clinical needle in an unlisted core file fails).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNCIL = REPO_ROOT / "lithrim_bench" / "runtime" / "council"
# The CE demarcation needle set (the driver A1 grep).
NEEDLES = re.compile(
    r"hipaa|clinical|patient|dosage|allerg|soap|medication|consent|escalat", re.I
)

# The ENUMERATED residual buckets — every non-test core council file that still carries a
# clinical needle, each a DOCUMENTED disposition. (Test files under ``tests/`` exercise the
# healthcare pack's behaviour and are a separate, expected bucket — not pinned here.)
ENUMERATED_RESIDUAL = {
    # build_source_message_prompt + the source_message evaluate branch + retrieval (§4 OUT OF
    # SCOPE this cycle → the 6c seam) AND the PACK-1b/2b carve-out provenance COMMENTS
    # (authorized; the council's clinical DATA provenance) AND the :1932 frozen-file comment.
    "compliance_council.py",
    # the HIPAA / PHI-redaction privacy MECHANISM (the 6c seam decides keep-as-generic vs relocate).
    "phi_redaction.py",
    "settings.py",  # the HIPAA_* PHI-redaction settings (read by phi_redaction.py) — same 6c seam.
    # withstands-lens provenance COMMENTS naming clinical flag codes (FABRICATED_ALLERGY, …).
    "judge_metric.py",
    "judge_assignment.py",  # a single allergy-fabrication provenance comment.
    # the module docstring (:14) + a build_judge_lm comment (:249, the BYOC-1 seam) — Fork 5: LEAVE.
    "judges_dspy.py",
}


def test_build_prompt_and_safety_flags_are_gone():
    """A2: ``def build_prompt`` + its ``get_flag_prompt_section`` import are absent from the
    core council, and the core ``safety_flags.py`` module is deleted (its seed relocated to
    the healthcare pack)."""
    assert not (COUNCIL / "safety_flags.py").exists(), "core safety_flags.py must be deleted (D4)"
    for py in COUNCIL.rglob("*.py"):
        src = py.read_text()
        assert "def build_prompt" not in src, f"build_prompt resurfaced in {py.name}"
        assert "get_flag_prompt_section" not in src, f"get_flag_prompt_section resurfaced in {py.name}"


def test_build_signature_is_clinical_clean():
    """A3: ``_build_signature`` carries 0 clinical needles (``transcript`` survives only as a
    generic I/O field NAME, which is not in the demarcation needle set)."""
    src = (COUNCIL / "judges_dspy.py").read_text()
    start = src.index("def _build_signature")
    end = src.index("return JudgeSignature", start)
    needles = sorted({m.lower() for m in NEEDLES.findall(src[start:end])})
    assert not needles, f"_build_signature must be clinical-clean (S-BS-129/G4); found {needles}"


def test_residual_clinical_needles_only_in_enumerated_buckets():
    """A1 (re-scoped, Fork 1): the build_prompt/safety_flags/_build_signature residue is gone;
    every remaining clinical needle in a NON-test core council file lives ONLY in an enumerated,
    documented bucket. A clinical needle in an unlisted core file FAILS — so the demarcation
    cannot silently regress and any NEW bucket must be documented here."""
    offenders: dict[str, list[str]] = {}
    for py in COUNCIL.glob("*.py"):  # top-level only — the non-test core files
        hits = sorted({m.lower() for m in NEEDLES.findall(py.read_text())})
        if hits and py.name not in ENUMERATED_RESIDUAL:
            offenders[py.name] = hits
    assert not offenders, (
        "clinical needle(s) in a NON-enumerated core council file — the demarcation regressed "
        f"or a new residual bucket needs documenting (+ a 6c follow-on): {offenders}"
    )


def test_enumerated_buckets_are_not_stale():
    """Keep ENUMERATED_RESIDUAL honest: every listed file must still EXIST and still carry a
    needle (else it has been cleaned and should be removed from the list — tightening the bar)."""
    for name in ENUMERATED_RESIDUAL:
        py = COUNCIL / name
        assert py.exists(), f"enumerated residual file is gone (remove from the list): {name}"
        assert NEEDLES.search(py.read_text()), (
            f"enumerated residual file is now clinical-clean (remove from the list to tighten "
            f"the bar): {name}"
        )
