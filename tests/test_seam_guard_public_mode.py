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
import re
import subprocess
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


# ── S-REL-18 (REL-5b): the SITE tests route baseline resolution through the seam ─
# Six files (+ test_plugin_phase1.py, caught by the sweep below) ran a raw list-form
# git-show subprocess on the seam baseline with ``check=True`` — an ERROR, not a skip,
# on a public fresh-cut clone. Each forced-public-mode test below proves its site now
# either PASSES via the ``_FROZEN_SECTION_SHA256`` hash pins or SKIPS with a
# "public-mode:" reason — with the site's own ``subprocess`` booby-trapped, so any raw
# shell-out (instead of routing through ``sf._resolve_baseline``) is a hard failure.


def _no_git(*a, **k):
    raise AssertionError(f"S-REL-18: a site test shelled out to git under public mode: {a} {k}")


def _force_public_mode(monkeypatch, site_mod):
    monkeypatch.setattr(sf, "_resolve_baseline", lambda *a, **k: None)
    monkeypatch.setattr(site_mod, "subprocess", types.SimpleNamespace(run=_no_git), raising=False)


def test_public_mode_consensus_pillar_t4_body_passes_via_hash_pin(monkeypatch):
    """Site 1a (test_consensus_pillar_invariant.py): the ``_apply_consensus`` body attestation
    is a pinned section → public mode PASSES via the hash pin, zero git."""
    import tests.test_consensus_pillar_invariant as site

    _force_public_mode(monkeypatch, site)
    site.test_t4_apply_consensus_body_byte_identical_to_acc4973()


def test_public_mode_consensus_pillar_t4_guard_tests_skip(monkeypatch):
    """Site 1b: the carve-outs-only diff + the marker non-vacuity need the REAL baseline text
    (not pin-expressible) → public mode SKIPS with the public-mode reason."""
    import tests.test_consensus_pillar_invariant as site

    _force_public_mode(monkeypatch, site)
    with pytest.raises(pytest.skip.Exception, match="public-mode"):
        site.test_t4_seam_guard_passes_with_the_pillar_carveout()
    with pytest.raises(pytest.skip.Exception, match="public-mode"):
        site.test_t4_marker_is_load_bearing_non_vacuity(monkeypatch)


def test_public_mode_pack_dist_a5_passes_via_hash_pin(monkeypatch):
    """Site 2 (test_pack_dist.py): ``_apply_consensus`` + ``extract_verdict_confidence`` are
    both pinned sections → public mode PASSES via the hash pins, zero git."""
    import tests.test_pack_dist as site

    _force_public_mode(monkeypatch, site)
    site.test_a5_moat_byte_identical_vs_acc4973()


def test_public_mode_pack_layer1b_guard_nonvacuity_skips(monkeypatch):
    """Site 3 (test_pack_layer1b.py): the guard non-vacuity tests feed the REAL baseline to
    the pure predicate (not pin-expressible) → public mode SKIPS with the reason."""
    import tests.test_pack_layer1b as site

    _force_public_mode(monkeypatch, site)
    for fn in (
        site.test_freeze_guard_fails_on_an_unauthorized_edit,
        site.test_freeze_guard_fails_on_reverting_the_taxonomy_carveout,
        site.test_freeze_guard_fails_on_reverting_the_prompts_carveout,
    ):
        with pytest.raises(pytest.skip.Exception, match="public-mode"):
            fn()


def test_public_mode_pack_layer2b_guard_nonvacuity_skips(monkeypatch):
    """Site 4 (test_pack_layer2b.py): same class as site 3 → public mode SKIPS."""
    import tests.test_pack_layer2b as site

    _force_public_mode(monkeypatch, site)
    for fn in (
        site.test_freeze_guard_fails_on_reverting_the_owners_carveout,
        site.test_freeze_guard_fails_on_a_smuggled_code_line_in_an_authorized_hunk,
    ):
        with pytest.raises(pytest.skip.Exception, match="public-mode"):
            fn()


def test_public_mode_pack_layer2c_guard_nonvacuity_skips(monkeypatch):
    """Site 5 (test_pack_layer2c.py): same class as site 3 → public mode SKIPS."""
    import tests.test_pack_layer2c as site

    _force_public_mode(monkeypatch, site)
    for fn in (
        site.test_freeze_guard_fails_on_reverting_the_roster_carveout,
        site.test_freeze_guard_fails_on_a_smuggled_line_in_the_roster_hunk,
    ):
        with pytest.raises(pytest.skip.Exception, match="public-mode"):
            fn()


def test_public_mode_6bclean_guard_families_skip(monkeypatch):
    """Site 6 (test_6bclean_seam_guard.py): all three guard families route through the ONE
    baseline helper; each needs REAL baseline text (they tamper it) → public mode SKIPS.
    One representative per family (council / judges_dspy / ontology)."""
    import tests.test_6bclean_seam_guard as site

    _force_public_mode(monkeypatch, site)
    for fn in (
        site.test_authorized_build_prompt_deletion_and_raise_pass,
        site.test_signature_genericization_is_authorized,
        site.test_unauthorized_flag_edit_still_fails,
    ):
        with pytest.raises(pytest.skip.Exception, match="public-mode"):
            fn()


def test_public_mode_plugin_phase1_a5_passes_via_hash_pin(monkeypatch):
    """Site 7 (test_plugin_phase1.py — outside the driver's six, forced by the sweep below):
    the same two pinned sections as site 2 → public mode PASSES via the hash pins."""
    import tests.test_plugin_phase1 as site

    _force_public_mode(monkeypatch, site)
    site.test_a5_moat_apply_consensus_byte_identical_vs_acc4973()


# ── S-REL-18 sweep: no test file outside the seam module git-shows the baseline ─

# The list-form subprocess invocation (how every site did it — the baseline ref rides in a
# separate f-string arg, so it must be caught pack-wide via the file-level conjunction below).
_GIT_SHOW_LIST_FORM = re.compile(r"""["']git["']\s*,\s*["']show["']""")
# The inline shell form, baseline-adjacent (defense in depth for a shell=True variant).
_GIT_SHOW_BASELINE_INLINE = re.compile(r"git\s+show\s+\S*acc4973")
_BASELINE_REF = re.compile(r"acc4973|_SEAM_BASELINE")


def test_no_test_file_outside_the_seam_module_git_shows_the_baseline():
    """S-REL-18 regression sweep: ``tests/_seam_freeze.py::_resolve_baseline`` is the ONE
    place allowed to ``git show`` the seam baseline. A tracked test file that both invokes
    the list-form git-show AND references the baseline (or inlines the two) fails here, so
    a raw-``git show``-on-acc4973 site can never come back."""
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    offenders = []
    for rel in tracked:
        if rel == "tests/_seam_freeze.py":
            continue
        p = Path(rel)
        if not (p.name.startswith("test_") or p.name == "conftest.py" or "tests" in p.parts):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        list_form_on_baseline = _GIT_SHOW_LIST_FORM.search(text) and _BASELINE_REF.search(text)
        if list_form_on_baseline or _GIT_SHOW_BASELINE_INLINE.search(text):
            offenders.append(rel)
    assert offenders == [], (
        "S-REL-18: test file(s) git-show the seam baseline directly (route through "
        f"tests/_seam_freeze.py::_resolve_baseline instead): {offenders}"
    )
