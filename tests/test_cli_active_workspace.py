"""WS-DIR-1: the CLI writes into the workspace the SERVICE is on, not always `default`.

Found 2026-09-16 in the reproduction: after POST /v1/workspace switched the service to repro3,
`lithrim load` ingested into repro3 (the service resolves the workspace itself) but the CLI kept
writing its own workspace files to out/workspaces/default/out, because --workspace-out is a
hardcoded default. calibrate pinned demos into `default`, and the next `lithrim grade` in repro3
refused for a baseline because it found that pin. The CLI now asks the service which workspace is
active (GET /v1/workspaces `active`), or takes --workspace; an explicit --workspace-out still
wins, and an unreachable service falls back to today's path rather than failing."""

from __future__ import annotations

from pathlib import Path

from lithrim_bench.cli.loop import workspace_out_for

ROOT = Path("/app/out")


def test_it_follows_the_services_active_workspace():
    got = workspace_out_for(ROOT, active=lambda: "repro3", workspace=None, explicit=None)
    assert got == ROOT / "workspaces" / "repro3" / "out"


def test_an_explicit_workspace_name_wins_over_the_service():
    got = workspace_out_for(ROOT, active=lambda: "repro3", workspace="other", explicit=None)
    assert got == ROOT / "workspaces" / "other" / "out"


def test_an_explicit_path_wins_over_both():
    path = Path("/somewhere/else")
    assert workspace_out_for(ROOT, active=lambda: "repro3", workspace="other", explicit=path) == path


def test_an_unreachable_service_falls_back_to_default():
    def _boom():
        raise OSError("connection refused")

    assert workspace_out_for(ROOT, active=_boom, workspace=None, explicit=None) == (
        ROOT / "workspaces" / "default" / "out"
    )


def test_a_service_that_names_no_active_workspace_falls_back_to_default():
    assert workspace_out_for(ROOT, active=lambda: None, workspace=None, explicit=None) == (
        ROOT / "workspaces" / "default" / "out"
    )


def test_a_workspace_name_that_is_a_path_is_refused():
    """The name becomes a directory under the out root; it may not climb out of it."""
    import pytest

    for bad in ("../elsewhere", "/etc", "a/b"):
        with pytest.raises(SystemExit):
            workspace_out_for(ROOT, active=lambda name=bad: name, workspace=None, explicit=None)


def test_active_workspace_reads_the_services_answer(monkeypatch):
    from lithrim_bench.cli import loop

    monkeypatch.setattr(loop.http, "get", lambda bff, path, **kw: {"active": "repro3"})
    assert loop.active_workspace("http://bff:8787") == "repro3"
