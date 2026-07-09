"""REL-4 README + docs polish: the public front door is real, linked, and local.

Pins the community-release phase-4 deliverables (seams S-REL-8/10/11): the README
carries a real in-repo logo, a badges row, and the real clone URL (no `<repo>`
placeholder); pyproject declares [project.urls]; the shell fetches no external
fonts; no personal-name literal remains under apps/shell/src; the BFF README no
longer links the deleted QUICKSTART; docs/README.md indexes the tracked docs; and
every relative link in README/SETUP/docs-index resolves to a tracked file.
Stdlib-only text parses: $0, offline, no extras required to run this file.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

_MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_HTML_SRC_RE = re.compile(r'(?:src|srcset|href)="([^"]+)"')


def _tracked_files() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout; tracked-file link check needs git")
    return set(out.splitlines())


def _relative_targets(text: str, base: Path) -> list[tuple[str, str]]:
    """(raw, repo-relative) for every relative md/html link target in `text`."""
    raw = _MD_LINK_RE.findall(text) + _HTML_SRC_RE.findall(text)
    out = []
    for target in raw:
        if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            continue
        path = target.split("#")[0]
        if not path:
            continue
        resolved = (base / path).resolve().relative_to(REPO)
        out.append((target, str(resolved)))
    return out


def test_readme_logo_is_an_in_repo_asset():
    """(a) The header image must reference a tracked repo asset, not a hotlink."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    tracked = _tracked_files()
    srcs = [
        t
        for t in _MD_LINK_RE.findall(readme) + _HTML_SRC_RE.findall(readme)
        if t.split("#")[0].lower().endswith((".png", ".svg", ".gif", ".jpg"))
        and not t.startswith(("http://", "https://"))
    ]
    assert srcs, "README has no image tag referencing an in-repo asset"
    for src in srcs:
        assert src.split("#")[0] in tracked, f"README image {src!r} is not a tracked file"


def test_readme_badges_row():
    """(a) CI + license + python + DOI badges."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for needle, what in [
        ("actions/workflows/ci.yml/badge.svg", "CI workflow badge"),
        ("Apache--2.0", "Apache-2.0 license badge"),
        ("python-3.10", "Python 3.10+ badge"),
        ("zenodo.org/badge/DOI/10.5281/zenodo.21270268.svg", "DOI badge"),
    ]:
        assert needle in readme, f"README badges row is missing the {what}"


def test_clone_urls_are_real():
    """(a)+(b) README and SETUP clone with the real URL; no `<repo>` placeholder."""
    for name in ("README.md", "SETUP.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "<repo>" not in text, f"{name} still carries the <repo> placeholder"
        assert "git clone https://github.com/lithrim-dev/lithrim" in text, (
            f"{name} must clone the real public URL"
        )


def test_pyproject_has_project_urls():
    """(c) [project.urls] with the repo and the research DOI."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.urls]" in text, "pyproject.toml has no [project.urls] table"
    for needle in (
        "https://github.com/lithrim-dev/lithrim",
        "https://github.com/lithrim-dev/lithrim/issues",
        "https://doi.org/10.5281/zenodo.21270268",
    ):
        assert needle in text, f"[project.urls] is missing {needle}"


def test_shell_fetches_no_external_fonts():
    """(d) index.html must not reach fonts.googleapis/gstatic; the CSS tokens
    already carry a system-stack fallback."""
    html = (REPO / "apps/shell/index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis" not in html, "index.html still fetches Google Fonts CSS"
    assert "fonts.gstatic" not in html, "index.html still preconnects fonts.gstatic"


# REL-5f (final-gate B2): the needle comes from the UNTRACKED local file — no decodable
# form (tuple / concatenation / base64) may live in tracked source. Integrity pins + skip
# semantics live in tests/_needles.py.


def test_collaborator_needle_detection_self_check():
    """Planted-needle self-check: the sweep's containment check fires on a synthetic text
    carrying the locally loaded needle and stays quiet on clean text (skips where the
    local needles file is absent; the needle is integrity-pinned on load)."""
    from tests._needles import require_needle

    needle = require_needle("collaborator")
    planted = "attribution: reviewed by Dr. " + needle + " (panel)"
    assert needle in planted
    assert needle not in "attribution: reviewed by the physician collaborator"


def test_no_personal_name_under_shell_src():
    """(e) S-REL-8: no collaborator-surname literal in any tracked file under
    apps/shell/src (needle from the untracked local file; skips where absent)."""
    from tests._needles import require_needle

    needle = require_needle("collaborator")
    tracked = _tracked_files()
    hits = []
    for rel in sorted(tracked):
        if not rel.startswith("apps/shell/src/"):
            continue
        text = (REPO / rel).read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            hits.append(rel)
    assert not hits, f"personal-name literal under apps/shell/src: {hits}"


def test_bff_readme_has_no_dead_quickstart_link():
    """(f) S-REL-11: docs/QUICKSTART.md does not exist; the BFF README must not
    reference it."""
    text = (REPO / "apps/bff/README.md").read_text(encoding="utf-8")
    assert "QUICKSTART" not in text.upper(), (
        "apps/bff/README.md still references the nonexistent QUICKSTART doc"
    )


def test_docs_index_exists_and_links_resolve():
    """(g) docs/README.md exists and every relative link resolves to a tracked file."""
    index = REPO / "docs/README.md"
    assert index.exists(), "docs/README.md (the docs index) does not exist"
    tracked = _tracked_files()
    targets = _relative_targets(index.read_text(encoding="utf-8"), index.parent)
    assert targets, "docs/README.md indexes nothing"
    for raw, rel in targets:
        assert rel in tracked, f"docs/README.md link {raw!r} -> {rel} is not tracked"


def test_readme_docs_section_links_resolve():
    """(h) The README Docs section links the named docs and every link resolves."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## Docs\n(.*?)(?=^## )", readme, re.M | re.S)
    assert m, "README has no '## Docs' section"
    section = m.group(1)
    for needle in (
        "SETUP.md",
        "docs/CAPABILITY_CARD.md",
        "docs/ARCHITECTURE.md",
        "docs/JUTE_MAPPER_ADDON.md",
        "REPRODUCING.md",
        "CONTRIBUTING.md",
    ):
        assert needle in section, f"README Docs section does not link {needle}"
    tracked = _tracked_files()
    for raw, rel in _relative_targets(section, REPO):
        assert rel in tracked, f"README Docs link {raw!r} -> {rel} is not tracked"


def test_all_readme_and_setup_relative_links_resolve():
    """(4) Every relative link in README.md and SETUP.md resolves to a tracked file."""
    tracked = _tracked_files()
    for name in ("README.md", "SETUP.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        for raw, rel in _relative_targets(text, REPO):
            assert rel in tracked, f"{name} link {raw!r} -> {rel} is not tracked"
