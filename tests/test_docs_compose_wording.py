"""B1 docs quirks: the compose files consume published images (no ``build:`` block), so no
quickstart may tell the reader to ``up --build``; the setup-journey sentence names every rail
step the shell actually renders; the prebuilt-image compose does not call the in-repo file a
build-from-source sibling it no longer is."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def _compose_has_build(path: Path) -> bool:
    doc = yaml.safe_load(path.read_text())
    return any("build" in (svc or {}) for svc in (doc.get("services") or {}).values())


def test_no_quickstart_says_up_build_when_compose_pulls_images():
    assert not _compose_has_build(REPO / "docker-compose.yml")
    for name in ("README.md", "SETUP.md", "docs/DEPLOY.md"):
        text = (REPO / name).read_text()
        assert "up --build" not in text, f"{name} tells the reader to build; compose pulls"
        assert "first run builds" not in text, name


def test_the_setup_journey_sentence_names_every_rail_step():
    js = (REPO / "apps/shell/src/data.jsx").read_text()
    steps = re.findall(r'\{\s*name:\s*"([^"]+)"', js.split("export const STEPS")[1].split("];")[0])
    assert len(steps) >= 6
    setup = (REPO / "SETUP.md").read_text()
    line = next(ln for ln in setup.splitlines() if "Setup journey" in ln or "setup journey" in ln)
    for step in steps:
        assert step in line, f"SETUP.md's journey sentence omits the {step!r} step: {line}"


def test_the_prebuilt_compose_does_not_call_the_repo_file_build_from_source():
    text = (REPO / "deploy/docker-compose.yml").read_text()
    assert "build-from-source" not in text
    assert not _compose_has_build(REPO / "deploy/docker-compose.yml")


def test_the_journey_page_states_the_acceptance_test_and_is_linked():
    """UI-JOURNEY-1 (B11): the definition of done is written down where a reader finds it."""
    page = (REPO / "docs/reproduction/RAGTRUTH_LOOP_UI.md").read_text()
    for phrase in ("uninvolved person", "without opening a terminal", "own Azure", "both vocabularies"):
        assert phrase in page, phrase
    assert "RAGTRUTH_LOOP_UI.md" in (REPO / "docs/README.md").read_text()
    assert "RAGTRUTH_LOOP_UI.md" in (REPO / "README.md").read_text()
    assert "RAGTRUTH_LOOP_UI.md" in (REPO / "docs/reproduction/RAGTRUTH_LOOP.md").read_text()


def test_the_kpi_and_otel_page_is_linked_and_names_both_contract_types():
    page = (REPO / "docs/KPI_CONTRACTS.md").read_text()
    for needle in ("kpi_threshold", "field_in_set", "resourceSpans", "never a violation"):
        assert needle in page, needle
    assert "KPI_CONTRACTS.md" in (REPO / "docs/README.md").read_text()
    assert "KPI_CONTRACTS.md" in (REPO / "README.md").read_text()
    assert "kpi_threshold" in (REPO / "docs/CAPABILITY_CARD.md").read_text()


def test_both_loop_pages_say_how_held_out_is_chosen():
    """HOLDOUT-DEV-1: the reader can see that the gate scores on a dev slice, not the test cut."""
    for page in ("docs/reproduction/RAGTRUTH_LOOP.md", "docs/reproduction/RAGTRUTH_LOOP_UI.md"):
        text = (REPO / page).read_text()
        assert "source-disjoint" in text and "30%" in text and "dev" in text, page
    assert "0.68 against the pinned 0.76" in (REPO / "docs/reproduction/RAGTRUTH_LOOP.md").read_text()
