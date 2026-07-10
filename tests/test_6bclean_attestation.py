"""CE-PACK-6c — the demarcation attestation (extends CE-PACK-6b-CLEAN's re-scoped A1).

The last LIVE clinical CODE is GONE from the core council: ``build_prompt`` +
``safety_flags`` + ``_build_signature`` (6b-CLEAN) and now ``build_source_message_prompt``
(6c — the source_message stage reroutes to the authored stage, so ``evaluate()`` builds no
prompt). The remaining clinical needles in ``runtime/council/`` are **not** zero — this is
NOT a grep-clean claim, and was never achievable while the FROZEN carve-out/provenance
comments + the load-bearing ``HIPAA_*`` config keys stay (CE-PACK-6c Fork D, the honest
bar). They are ENUMERATED here and attributed to documented buckets — all now PASSIVE
(comments / config-key names / a dead-after-raise role-select / inert retrieval helpers),
no live clinical code. ``test_no_live_clinical_code`` pins the positive bar; the
enumeration pins that the demarcation cannot silently regress (a new clinical needle in an
unlisted core file fails). See ``docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md`` §4.
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
    # CE-PACK-6c: build_source_message_prompt is DELETED + the evaluate source_message branch
    # raises (no live clinical CODE). The surviving needles are all PASSIVE: the PACK-1b/2b
    # carve-out provenance COMMENTS (authorized; the council's clinical DATA provenance), the
    # frozen-file doc-comments, the dead-after-raise _invoke_openai source_message role-select
    # (monitor-ruled LEAVE — no clinical-needle CODE), and the inert _format_kb_citations helpers.
    "compliance_council.py",
    # CE-PACK-6c Fork B: the PII/PHI-redaction privacy MECHANISM is KEPT-AS-GENERIC in core (prose
    # genericized); the HIPAA_* config-key names + the MRN "patient id" regex keep a needle.
    "phi_redaction.py",
    "settings.py",  # the HIPAA_* PHI-redaction config keys (read by phi_redaction.py) — kept (compat).
    # withstands-lens provenance COMMENTS naming clinical flag codes (FABRICATED_ALLERGY, …) — Fork C: LEAVE.
    "judge_metric.py",
    "judge_assignment.py",  # a single allergy-fabrication provenance comment — Fork C: LEAVE.
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


def test_no_live_clinical_code():
    """CE-PACK-6c A1/A2 (the positive bar): no live clinical PROMPT-BUILDER remains in the core
    council. Neither ``def build_source_message_prompt`` nor ``def build_prompt`` is defined in
    any council module, and ``evaluate()`` builds no prompt (no live ``self.build_*_prompt(``
    call). This is the honest 6c bar — 'no live clinical CODE', distinct from literal grep-empty
    (the enumerated residual above is all PASSIVE: comments / config keys / dead-after-raise code).
    Non-vacuous: it would FAIL the instant the builder or a live call to it is re-introduced."""
    for py in COUNCIL.rglob("*.py"):
        src = py.read_text()
        assert "def build_source_message_prompt" not in src, (
            f"build_source_message_prompt resurfaced in {py.name}"
        )
        assert "def build_prompt" not in src, f"build_prompt resurfaced in {py.name}"
        assert "self.build_source_message_prompt(" not in src, (
            f"a live call to build_source_message_prompt resurfaced in {py.name}"
        )
        assert "self.build_prompt(" not in src, f"a live call to build_prompt resurfaced in {py.name}"
    # Positive: evaluate()'s source_message branch actively raises (it builds no prompt).
    cc = (COUNCIL / "compliance_council.py").read_text()
    assert "CE-PACK-6c: evaluate() no longer builds prompts" in cc, (
        "evaluate()'s source_message branch must raise the CE-PACK-6c sentinel (no prompt built)"
    )


def test_phi_redaction_mechanism_works():
    """CE-PACK-6c A3 (Fork B): phi_redaction is KEPT-AS-GENERIC in core — after genericizing its
    prose, ``redact_text`` + ``sanitize_prompt`` still redact PII/PHI (the mechanism is intact)."""
    from lithrim_bench.runtime.council.phi_redaction import redact_text, sanitize_prompt

    assert redact_text("SSN 123-45-6789 email a@b.com") == "SSN [REDACTED_SSN] email [REDACTED_EMAIL]"
    assert sanitize_prompt("contact 123-45-6789", "openai") == "contact [REDACTED_SSN]"
