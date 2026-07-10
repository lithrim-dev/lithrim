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
import re
import subprocess
from pathlib import Path

from tests._needles import require_needle

from .test_pack_dist import (
    _DATA_SURFACE,
    _PASSIVE_CARVE_OUT,
    _SYNTHETIC_CLINICAL_SAMPLE,
    _is_sample,
    _needle_hits,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def _tracked_files() -> list[str]:
    return [p for p in _git("ls-files").stdout.splitlines() if p]


def test_no_tracked_file_contains_a_macos_home_path():
    """(a) NO tracked file carries ANY macOS home path — a PATTERN sweep
    (``/Users/<name>``), strictly wider than the old single-username needle and needing
    no needle at all (REL-5f: a pattern wherever a pattern suffices)."""
    out = _git("grep", "-I", "-nE", r"/Users/[a-z0-9_-]+", "--", ".")
    assert out.returncode == 1, f"tracked files leak a home path:\n{out.stdout}"


def test_no_collaborator_name_in_fixtures_or_samples():
    """(b) no tracked file under tests/fixtures/ or samples/ carries the local needle
    (loaded from the untracked ``.release_needles.json``, integrity-pinned; skips where
    the file is absent — see tests/_needles.py)."""
    needle = require_needle("collaborator")
    out = _git("grep", "-I", "-l", "--fixed-strings", needle, "--", "tests/fixtures", "samples")
    assert out.returncode == 1, f"fixtures/samples carry the needle:\n{out.stdout}"


# REL-5f (final-gate B2): a codepoint tuple is a decodable ENCODING, not a redaction.
# This sweep decodes every int-tuple in every tracked text file and fails if any decodes
# to a pinned needle — the pattern that shipped in REL-5e can never return.
_INT_TUPLE_RE = re.compile(r"\(\s*\d{1,3}\s*(?:,\s*\d{1,3}\s*){2,},?\s*\)")


def test_no_tracked_file_encodes_a_pinned_needle_as_an_int_tuple():
    from tests._needles import NEEDLE_PINS

    pins = set(NEEDLE_PINS.values())
    offenders = []
    for rel in _tracked_files():
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in _INT_TUPLE_RE.finditer(text):
            nums = [int(x) for x in re.findall(r"\d{1,3}", m.group(0))]
            decoded = "".join(chr(n) for n in nums)
            if hashlib.sha256(decoded.encode("utf-8")).hexdigest() in pins:
                offenders.append(f"{rel}: {m.group(0)}")
    assert offenders == [], f"decodable needle encoding(s) in the tracked tree: {offenders}"


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
