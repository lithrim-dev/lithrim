"""REL-2 tree-sanitization acceptance (community-release phase 2).

Pins the public-tree hygiene invariants for the community release:

(a) no tracked file carries a maintainer-local absolute home path;
(b) no tracked fixture/sample names the physician collaborator;
(c) the ``data/synthea_sample_data_csv_latest`` symlink is untracked;
(d) ``journeys/`` + ``samples/injected_snomed/`` are dropped from the tracked tree;
(e) ``docs/specs/SPEC_TOOL_CONNECTORS.md`` IS tracked (README/CONTRIBUTING links resolve);
(f) the public ``CLAUDE.md`` references no gitignored path (deny-list);
(g) the A2 clinical sweep still CATCHES planted clinical content outside the
    sanctioned surfaces (negative self-test for the REL-2 allowlist widening).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .test_pack_dist import (
    _DATA_SURFACE,
    _PASSIVE_CARVE_OUT,
    _SYNTHETIC_CLINICAL_SAMPLE,
    _is_sample,
    _needle_hits,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# REL-5e (critic finding): the sensitive needles are ASSEMBLED at runtime from codepoints so
# neither string ever appears in this (published) source — a visible split like
# "/Users/" + <name> still ships the name. Integrity-pinned below so a codepoint typo
# cannot silently neuter the sweeps.
_MAINTAINER_USER = "".join(chr(c) for c in (97, 114, 101, 103, 101, 101))
_COLLABORATOR = "".join(chr(c) for c in (83, 104, 97, 114, 105, 102))


def test_assembled_needles_are_intact():
    """Planted-needle-grade self-check: the assembled needles hash to their pins, so the
    sweeps below are proven to hunt the REAL strings (never visible in source)."""
    assert (
        hashlib.sha256(("/Users/" + _MAINTAINER_USER).encode()).hexdigest()
        == "45ca16eb3eb4f7a554ed0ec89390ba752e506099d51b11742a5137391b98992d"
    )
    assert (
        hashlib.sha256(_COLLABORATOR.encode()).hexdigest()
        == "524b30f818bf83fc541d0cb25109686e77c39fbed86bf11da3db0130f49e5e15"
    )


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def _tracked_files() -> list[str]:
    return [p for p in _git("ls-files").stdout.splitlines() if p]


def test_no_tracked_file_contains_the_maintainer_home_path():
    """(a) the maintainer's absolute home path appears in NO tracked file (git grep over the
    tracked tree). The needle is runtime-assembled (integrity-pinned above) so this tripwire
    never trips itself and never publishes the username."""
    needle = "/Users/" + _MAINTAINER_USER
    out = _git("grep", "-I", "-l", "--fixed-strings", needle, "--", ".")
    assert out.returncode == 1, f"tracked files leak a personal path:\n{out.stdout}"


def test_no_collaborator_name_in_fixtures_or_samples():
    """(b) no tracked file under tests/fixtures/ or samples/ names the collaborator. The
    surname is runtime-assembled (integrity-pinned above) — it must not appear in THIS file
    either (it is a published test)."""
    out = _git("grep", "-I", "-l", "--fixed-strings", _COLLABORATOR, "--", "tests/fixtures", "samples")
    assert out.returncode == 1, f"fixtures/samples still name the collaborator:\n{out.stdout}"


def test_synthea_symlink_is_untracked():
    """(c) the personal-path symlink is out of the tracked tree (cohort ships by manifest)."""
    assert "data/synthea_sample_data_csv_latest" not in _tracked_files()


def test_journeys_and_injected_snomed_are_dropped():
    """(d) journeys/ + samples/injected_snomed/ (unusable without private deps) are untracked."""
    tracked = _tracked_files()
    leftovers = [
        p for p in tracked if p.startswith(("journeys/", "samples/injected_snomed/"))
    ]
    assert leftovers == [], f"dropped surfaces still tracked: {leftovers}"


def test_spec_tool_connectors_is_tracked():
    """(e) the sanitized connector spec ships, so README/CONTRIBUTING links resolve."""
    assert "docs/specs/SPEC_TOOL_CONNECTORS.md" in _tracked_files()


# Gitignored paths the PUBLIC CLAUDE.md must not send a contributor to (deny-list — the
# internal playbook that cites them lives in the untracked CLAUDE.local.md).
_CLAUDE_MD_DENYLIST = (
    ".devloop/",
    "docs/PAPER_OUTLINE.md",
    "docs/LITHRIM_BENCH_PRODUCT_SPEC.md",
    "docs/CLAUDE_MD_ARCHIVE.md",
    "docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md",
    "docs/specs/SPEC_CONVERSATIONAL_FIRST.md",
    "docs/specs/SPEC_PLUGIN_ARCHITECTURE.md",
    "docs/clinverdict/",
    "docs/research/",
    "docs/guides/",
    "docs/_internal/",
    "docs/paper_draft/",
)


def test_public_claude_md_references_no_gitignored_paths():
    """(f) the public CLAUDE.md points only at tracked files — never at the local-only docs."""
    body = (REPO_ROOT / "CLAUDE.md").read_text()
    offenders = [d for d in _CLAUDE_MD_DENYLIST if d in body]
    assert offenders == [], f"public CLAUDE.md references gitignored paths: {offenders}"


def test_a2_sweep_catches_planted_clinical_outside_sanctioned_dirs(tmp_path):
    """(g) the widened A2 sweep is still a live tripwire: samples/ + the subsumption fixture
    dir are SWEPT (and sanctioned by prefix), and a planted clinical file at a swept,
    non-sanctioned path yields needle hits — i.e. A2 would FAIL on it."""
    # the REL-2 widening: the new surfaces are swept …
    assert "samples" in _DATA_SURFACE
    assert "tests/fixtures/subsumption_bidirectional" in _DATA_SURFACE
    # … and sanctioned EXACTLY by these prefixes.
    assert "samples/quickstart/" in _SYNTHETIC_CLINICAL_SAMPLE
    assert "tests/fixtures/subsumption_bidirectional/" in _SYNTHETIC_CLINICAL_SAMPLE

    rel = "samples/planted_vendor_notes.jsonl"
    (tmp_path / "samples").mkdir()
    (tmp_path / rel).write_text(
        '{"note": "patient prescribed a medication dosage for a clinical diagnosis"}\n'
    )
    # the plant is NOT excused by the carve-out or the sanctioned-sample prefixes …
    assert rel not in _PASSIVE_CARVE_OUT
    assert not _is_sample(rel)
    # … and the sweep's needle scan catches it.
    hits = _needle_hits([rel], root=tmp_path)
    assert hits, "the A2 sweep failed to catch planted clinical content outside sanctioned dirs"
