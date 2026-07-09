"""REL-5a (S-REL-13) — the moat seam guards are DUAL-MODE.

The public release is a fresh-cut orphan history: the ``acc4973`` baseline commit will
not exist there, so ``git show``-based byte-diff attestation is impossible. Vendoring the
baseline is forbidden (it embeds clinical ontology + role prompts). The approved design:

  * baseline RESOLVABLE (private tree) — the existing byte-diff attestation, unchanged;
  * baseline UNRESOLVABLE (public/shallow clone) — pinned SHA-256 hashes over the SAME
    extracted frozen sections (``_FROZEN_SECTION_SHA256``), a real tripwire with no
    baseline text shipped; the pack-relocation guards (ontology / role prompts) SKIP
    with a public-mode reason (the healthcare pack is not part of the public cut).

This file pins (1) the PROVENANCE CHAIN — every pinned hash equals the acc4973-derived
hash, asserted where acc4973 IS resolvable — and (2) the PUBLIC-MODE simulation: with
``_resolve_baseline`` forced to ``None``, the guards pass on the pristine tree via the
hash path, FAIL on tampered section sources (non-vacuity), and shell out to git ZERO times.
"""

from __future__ import annotations

import hashlib
import types
from pathlib import Path

import pytest

import tests._seam_freeze as sf

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tmp_council_repo(tmp_path: Path) -> Path:
    (tmp_path / "lithrim_bench" / "runtime" / "council").mkdir(parents=True)
    return tmp_path


# ── the resolution seam itself ────────────────────────────────────────────────


def test_resolve_baseline_returns_source_or_none():
    """``_resolve_baseline`` is the ONE baseline-resolution seam: a resolvable rel returns
    the acc4973 source text; an unresolvable one returns ``None`` (never raises)."""
    src = sf._resolve_baseline(REPO_ROOT, sf._JUDGES_DSPY_REL)
    if src is not None:  # private tree: the baseline resolves to the real frozen source
        assert "def evaluate_dspy(" in src
    assert sf._resolve_baseline(REPO_ROOT, "no/such/baseline_file.py") is None


# ── provenance chain: pins == acc4973-derived (private mode only) ─────────────


def test_pinned_hashes_equal_acc4973_derived():
    """Every entry in ``_FROZEN_SECTION_SHA256`` equals the hash derived from the acc4973
    extraction (same extraction model on the BASELINE source). This is what makes the
    public pins trustworthy. Skips when the baseline is unresolvable (public clone)."""
    base_judges = sf._resolve_baseline(REPO_ROOT, sf._JUDGES_DSPY_REL)
    base_council = sf._resolve_baseline(REPO_ROOT, sf._COMPLIANCE_COUNCIL_REL)
    if base_judges is None or base_council is None:
        pytest.skip("acc4973 unresolvable (public clone) — provenance attested in the private tree")
    derived = {
        f"compliance_council.py::{name}": _sha(src)
        for name, src in sf._council_frozen_sections(base_council).items()
    }
    derived.update(
        {
            f"judges_dspy.py::{name}": _sha(src)
            for name, src in sf._toplevel_defs(
                base_judges, exclude=sf._AUTHORIZED_JUDGES_SEAM
            ).items()
        }
    )
    assert derived == sf._FROZEN_SECTION_SHA256, (
        "pinned hash dict must be EXACTLY the acc4973-derived section hashes (provenance chain)"
    )


def test_pins_cover_judge_finding_shape_and_consensus():
    """The pin dict covers the driver-named frozen surface: ``_apply_consensus`` +
    ``extract_verdict_confidence`` (compliance_council.py) and the Judge/Finding shape
    (judges_dspy.py frozen section set)."""
    for key in (
        "compliance_council.py::_apply_consensus",
        "compliance_council.py::extract_verdict_confidence",
        "judges_dspy.py::Judge",
        "judges_dspy.py::Finding",
        "judges_dspy.py::EvidenceSpan",
        "judges_dspy.py::evaluate_dspy",
        "judges_dspy.py::_validate_findings",
    ):
        assert key in sf._FROZEN_SECTION_SHA256, f"missing pinned frozen section: {key}"


# ── public-mode simulation: pristine tree PASSES via the hash path ────────────


def test_public_mode_judges_guard_passes_on_pristine_tree(monkeypatch):
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    sf.assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)  # does not raise


def test_public_mode_council_guard_passes_on_pristine_tree(monkeypatch):
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    sf.assert_compliance_council_carveouts_only(REPO_ROOT)  # does not raise


# ── public-mode NON-VACUITY: a tampered frozen section FAILS via the hash path ─


def test_public_mode_judges_guard_trips_on_tampered_frozen_symbol(tmp_path, monkeypatch):
    """Tampering a FROZEN judges_dspy symbol (``evaluate_dspy``) trips the hash pin."""
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    repo = _tmp_council_repo(tmp_path)
    cur = (REPO_ROOT / sf._JUDGES_DSPY_REL).read_text()
    tampered = cur.replace("def evaluate_dspy(", "def evaluate_dspy(  # TAMPERED-FROZEN-EDIT", 1)
    assert tampered != cur
    (repo / sf._JUDGES_DSPY_REL).write_text(tampered)
    with pytest.raises(AssertionError, match="public-mode hash pin"):
        sf.assert_judges_dspy_consensus_seam_frozen(repo)


def test_public_mode_judges_guard_trips_on_smuggled_symbol(tmp_path, monkeypatch):
    """A smuggled NEW top-level symbol changes the pinned symbol set → FAILS (same
    assertion strength as the private-mode set check)."""
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    repo = _tmp_council_repo(tmp_path)
    cur = (REPO_ROOT / sf._JUDGES_DSPY_REL).read_text()
    (repo / sf._JUDGES_DSPY_REL).write_text(
        cur + "\n\ndef _smuggled_backdoor():\n    return True\n"
    )
    with pytest.raises(AssertionError, match="public-mode hash pin"):
        sf.assert_judges_dspy_consensus_seam_frozen(repo)


def test_public_mode_council_guard_trips_on_tampered_apply_consensus(tmp_path, monkeypatch):
    """Tampering INSIDE ``_apply_consensus`` (the frozen consensus IP) trips the hash pin."""
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    repo = _tmp_council_repo(tmp_path)
    cur = (REPO_ROOT / sf._COMPLIANCE_COUNCIL_REL).read_text()
    lines = cur.splitlines(keepends=True)
    idx = next(
        i for i, ln in enumerate(lines) if ln.lstrip().startswith("def _apply_consensus(self")
    )
    lines.insert(idx + 1, "        pass  # TAMPERED-FROZEN-EDIT\n")
    (repo / sf._COMPLIANCE_COUNCIL_REL).write_text("".join(lines))
    with pytest.raises(AssertionError, match="public-mode hash pin"):
        sf.assert_compliance_council_carveouts_only(repo)


def test_public_mode_council_guard_trips_on_deleted_verdict_confidence(tmp_path, monkeypatch):
    """DELETING a pinned council section (``extract_verdict_confidence``) is a missing
    pinned key → FAILS (deletion is caught, not just drift)."""
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    repo = _tmp_council_repo(tmp_path)
    cur = (REPO_ROOT / sf._COMPLIANCE_COUNCIL_REL).read_text()
    src = sf._council_frozen_sections(cur)["extract_verdict_confidence"]
    tampered = cur.replace(src, "def _verdict_confidence_gone():\n    return None", 1)
    assert tampered != cur
    (repo / sf._COMPLIANCE_COUNCIL_REL).write_text(tampered)
    with pytest.raises(AssertionError, match="public-mode hash pin"):
        sf.assert_compliance_council_carveouts_only(repo)


# ── public mode: the pack-relocation guards SKIP (pack is not in the public cut) ─


def test_public_mode_pack_relocation_guards_skip_with_reason(monkeypatch):
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    with pytest.raises(pytest.skip.Exception, match="public-mode"):
        sf.assert_clinical_ontology_seam_frozen(REPO_ROOT)
    with pytest.raises(pytest.skip.Exception, match="public-mode"):
        sf.assert_council_roles_relocated_only(REPO_ROOT)


# ── criterion 6: a _resolve_baseline-returns-None run makes ZERO git show calls ─


def test_public_mode_run_exercises_zero_git_show_calls(monkeypatch):
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)

    def _boom(*a, **k):
        raise AssertionError(f"public-mode guard shelled out: {a} {k}")

    monkeypatch.setattr(sf, "subprocess", types.SimpleNamespace(run=_boom))
    sf.assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)
    sf.assert_compliance_council_carveouts_only(REPO_ROOT)
    with pytest.raises(pytest.skip.Exception):
        sf.assert_clinical_ontology_seam_frozen(REPO_ROOT)
    with pytest.raises(pytest.skip.Exception):
        sf.assert_council_roles_relocated_only(REPO_ROOT)
