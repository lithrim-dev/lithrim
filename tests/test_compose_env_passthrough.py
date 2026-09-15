"""COMPOSE-ENV-1: the knobs the service documents are settable from a compose `.env`.

Found 2026-09-15 reviewing v0.1.30: the BFF reads LITHRIM_ALLOWED_ORIGINS (serving the UI from
a LAN address, an iPad), LITHRIM_OPTIMIZE_TIMEOUT_S and LITHRIM_GRADE_TIMEOUT_S (a pilot-scale
calibration is documented as raising the first), but neither compose file passed them through —
so setting them in `.env` beside the compose file did nothing and the only way in was to edit
the compose file or hand-write an override."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = [REPO_ROOT / "docker-compose.yml", REPO_ROOT / "deploy" / "docker-compose.yml"]
PASSTHROUGH = ["LITHRIM_ALLOWED_ORIGINS", "LITHRIM_OPTIMIZE_TIMEOUT_S", "LITHRIM_GRADE_TIMEOUT_S"]


@pytest.mark.parametrize("compose", COMPOSE_FILES, ids=lambda p: p.parent.name or p.name)
@pytest.mark.parametrize("var", PASSTHROUGH)
def test_the_bff_service_passes_the_var_through_from_the_environment(compose, var):
    text = compose.read_text()
    assert f"{var}: ${{{var}" in text, f"{compose.name} does not pass {var} through"


@pytest.mark.parametrize("var", PASSTHROUGH)
def test_deploy_documents_the_knob(var):
    assert var in (REPO_ROOT / "docs" / "DEPLOY.md").read_text()
