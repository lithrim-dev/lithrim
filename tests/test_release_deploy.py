"""REL-6 published images + prebuilt compose + SNOMED guide + Agent Skills.

Pins the community-release phase-6 deliverables: the GHCR release workflow
(fork-safe push, both image names, packages:write), the standalone
`deploy/docker-compose.yml` (published images only; parses from a bare tmpdir
with no repo checkout), the `docs/SNOMED_SETUP.md` terminology guide (licensing
reality FIRST, never a licensed-content download URL), the three tracked Agent
Skills (frontmatter + every referenced repo path real), and the README/docs
surfaces that point at all of it. Offline and $0: `docker compose config` runs
only when the docker CLI is present; otherwise the check falls back to a plain
YAML parse (and skips only if PyYAML is also absent).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

_WORKFLOW = REPO / ".github/workflows/release-images.yml"
_DEPLOY_COMPOSE = REPO / "deploy/docker-compose.yml"
_SNOMED_DOC = REPO / "docs/SNOMED_SETUP.md"
_SKILLS = (
    REPO / ".claude/skills/lithrim-docker-up/SKILL.md",
    REPO / ".claude/skills/lithrim-snomed-setup/SKILL.md",
    REPO / ".claude/skills/lithrim-first-grade/SKILL.md",
)


# ── (a) the release-images workflow ──────────────────────────────────────────────────


def test_release_images_workflow_parses_and_is_fork_safe():
    """release-images.yml parses, grants packages:write/contents:read, names both
    published images, and conditions the PUSH on the canonical repository so forks
    build but never push."""
    yaml = pytest.importorskip("yaml")
    assert _WORKFLOW.exists(), "missing .github/workflows/release-images.yml"
    text = _WORKFLOW.read_text(encoding="utf-8")
    wf = yaml.safe_load(text)
    on = wf.get("on", wf.get(True))
    assert "workflow_dispatch" in on, "workflow must be manually dispatchable"
    tags = on["push"]["tags"]
    assert any(str(t).startswith("v") for t in tags), f"must trigger on v* tags, got {tags}"
    perms = wf["permissions"]
    assert perms.get("packages") == "write", "needs packages:write to push to GHCR"
    assert perms.get("contents") == "read", "contents should stay read-only"
    for image in ("ghcr.io/lithrim-dev/lithrim-bff", "ghcr.io/lithrim-dev/lithrim-ui"):
        assert image in text, f"workflow must publish {image}"
    assert re.search(
        r"push:\s*\$\{\{\s*github\.repository\s*==\s*'lithrim-dev/lithrim'\s*\}\}", text
    ), "the push flag must be conditioned on repository == 'lithrim-dev/lithrim' (fork-safe)"
    assert "push: true" not in text, "an unconditional push is not fork-safe"


# ── (b) the standalone prebuilt-image compose file ───────────────────────────────────


def test_deploy_compose_parses_with_no_repo_checkout(tmp_path):
    """deploy/docker-compose.yml is copied ALONE into a tmpdir (no repo files) and must
    still validate: `docker compose config -q` when the docker CLI is present, else a
    plain YAML parse (skips only if PyYAML is also missing)."""
    assert _DEPLOY_COMPOSE.exists(), "missing deploy/docker-compose.yml"
    target = tmp_path / "docker-compose.yml"
    target.write_text(_DEPLOY_COMPOSE.read_text(encoding="utf-8"), encoding="utf-8")
    if shutil.which("docker"):
        probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if probe.returncode == 0:
            res = subprocess.run(
                ["docker", "compose", "-f", str(target), "config", "-q"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"deploy compose does not parse standalone:\n{res.stderr}"
            return
    yaml = pytest.importorskip(
        "yaml", reason="docker CLI absent and PyYAML unavailable for the fallback parse"
    )
    parsed = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert set(parsed["services"]) >= {"bff", "ui", "jute"}


def test_deploy_compose_consumes_only_published_images():
    """No `build:` blocks anywhere; the bff/ui images are the published GHCR names, the
    jute default stays digest-pinned; the ./snomed:ro mount survives; the header carries
    the no-clone quickstart URL."""
    yaml = pytest.importorskip("yaml")
    text = _DEPLOY_COMPOSE.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    services = parsed["services"]
    assert set(services) >= {"bff", "ui", "jute"}, f"services moved: {set(services)}"
    for name, svc in services.items():
        assert "build" not in svc, f"deploy compose service {name!r} must not build"
        assert "image" in svc, f"deploy compose service {name!r} names no image"
    assert "ghcr.io/lithrim-dev/lithrim-bff" in services["bff"]["image"]
    assert "ghcr.io/lithrim-dev/lithrim-ui" in services["ui"]["image"]
    assert "@sha256:" in services["jute"]["image"], "jute default must stay digest-pinned"
    assert "./snomed:/snomed:ro" in services["bff"]["volumes"], "the snomed mount is gone"
    assert "raw.githubusercontent.com/lithrim-dev/lithrim/main/deploy/docker-compose.yml" in text, (
        "header comment must carry the no-clone quickstart curl URL"
    )


# ── (c) the Agent Skills ─────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_BACKTICK_TOKEN_RE = re.compile(r"`([^`\s]+)`")


def _referenced_repo_paths(text: str) -> list[str]:
    """Backticked single tokens that look like repo-relative paths (contain a slash,
    not a URL, not an absolute/container path, no shell metacharacters)."""
    out = []
    for tok in _BACKTICK_TOKEN_RE.findall(text):
        if tok.startswith(("http://", "https://", "/", "$", "-", "<", "~")):
            continue
        if "/" not in tok:
            continue
        if any(c in tok for c in "*{}$()|=?:"):
            continue
        out.append(tok)
    return out


def test_skills_have_frontmatter_and_reference_only_real_paths():
    """Every SKILL.md exists, opens with name+description frontmatter, and every repo
    path it references exists in the tree."""
    for skill in _SKILLS:
        assert skill.exists(), f"missing skill file {skill.relative_to(REPO)}"
        text = skill.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        assert m, f"{skill.relative_to(REPO)} has no --- frontmatter block"
        fm = m.group(1)
        assert re.search(r"^name:\s*\S", fm, re.M), f"{skill.name}: frontmatter lacks name"
        assert re.search(r"^description:\s*\S", fm, re.M), (
            f"{skill.name}: frontmatter lacks description"
        )
        for tok in _referenced_repo_paths(text):
            path = tok.lstrip("./").rstrip("/")
            assert (REPO / path).exists(), (
                f"{skill.relative_to(REPO)} references a path that does not exist: {tok!r}"
            )


def test_skills_are_not_gitignored():
    """.claude/skills/ must be a TRACKED surface: git check-ignore says none of the
    skill files are ignored (the scoped .gitignore exception)."""
    res = subprocess.run(
        ["git", "check-ignore", *(str(s.relative_to(REPO)) for s in _SKILLS)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if res.returncode == 128:
        pytest.skip("not a git checkout; ignore-rule check needs git")
    assert res.returncode == 1, f"skill files are gitignored:\n{res.stdout}"


# ── (d) the SNOMED/Hermes guide ──────────────────────────────────────────────────────


def test_snomed_setup_licensing_first_and_no_licensed_download_urls():
    """docs/SNOMED_SETUP.md leads with the licensing reality (first ## section), names
    MLDS + UMLS, states the repo never redistributes releases, carries NO download URL
    for licensed content, and documents the logback-stderr MCP fix with container paths."""
    assert _SNOMED_DOC.exists(), "missing docs/SNOMED_SETUP.md"
    text = _SNOMED_DOC.read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+(.+)$", text, re.M)
    assert headings, "SNOMED_SETUP.md has no ## sections"
    assert re.search(r"licen[cs]", headings[0], re.I), (
        f"licensing must be the FIRST section, got {headings[0]!r}"
    )
    low = text.lower()
    assert "mlds" in low, "must name SNOMED International MLDS"
    assert "umls" in low, "must name UMLS (the US path)"
    assert re.search(r"never\s+redistribut", low), (
        "must state releases are never redistributed by this repo"
    )
    for url in re.findall(r"https?://\S+", text):
        u = url.rstrip(").,`>*").lower()
        assert not u.endswith(".zip"), f"licensed-release download URL: {u}"
        assert "snomedct_" not in u, f"licensed-release download URL: {u}"
    assert "-Dlogback.configurationFile=/snomed/logback-stderr.xml" in text, (
        "must document the logback-stderr stdout-corruption fix"
    )
    assert "/snomed/hermes.jar" in text, "tool wiring must use CONTAINER paths"
    assert "optional" in low, "must carry the honest optional-component scope note"


# ── (e) the README / docs-index surfaces ─────────────────────────────────────────────


def test_readme_and_docs_index_gain_the_phase6_surfaces():
    """README quickstart names the prebuilt images + the standalone compose path, adds
    the Agent-setup note (.claude/skills), and links the SNOMED guide from the Docs
    section; docs/README.md indexes SNOMED_SETUP.md. (Link RESOLUTION is pinned by the
    existing sweeps in test_release_polish.py.)"""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "ghcr.io/lithrim-dev/lithrim-bff" in readme, "README lacks the prebuilt image"
    assert "deploy/docker-compose.yml" in readme, "README lacks the standalone compose"
    assert ".claude/skills" in readme, "README lacks the Agent-setup note"
    m = re.search(r"^## Docs\n(.*?)(?=^## )", readme, re.M | re.S)
    assert m, "README has no '## Docs' section"
    assert "docs/SNOMED_SETUP.md" in m.group(1), "README Docs section must link the guide"
    docs_index = (REPO / "docs/README.md").read_text(encoding="utf-8")
    assert "SNOMED_SETUP.md" in docs_index, "docs/README.md must index SNOMED_SETUP.md"
