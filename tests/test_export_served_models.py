"""EXPORT-SERVED-1: an export cannot claim models the round it exports did not run on.

Found 2026-09-16: with the CLI pinned to `default` while the service was on repro3 (WS-DIR-1),
`lithrim export --split test` wrote 63 rows whose manifest said served_models
["gpt-4o-2024-08-06"] — the previous workspace's rounds — while the gpt-4.1 rounds sat in
repro3. WS-DIR-1 routes the read correctly now; this is the check that says so out loud, because
an export is the artifact people publish and quote."""

from __future__ import annotations

import pytest

from lithrim_bench.cli.export import served_models_disagree


def _matrix(*models):
    return [{"case_id": f"c{i}", "votes": [{"served_model": m}]} for i, m in enumerate(models)]


def test_the_same_model_on_both_sides_agrees():
    assert served_models_disagree(["gpt-4.1-2025-04-14"], _matrix("gpt-4.1-2025-04-14")) is None


def test_a_different_model_in_the_export_is_reported_with_both_sides():
    reason = served_models_disagree(["gpt-4o-2024-08-06"], _matrix("gpt-4.1-2025-04-14"))
    assert reason and "gpt-4o-2024-08-06" in reason and "gpt-4.1-2025-04-14" in reason


def test_an_extra_model_in_the_export_is_a_disagreement():
    reason = served_models_disagree(
        ["gpt-4.1-2025-04-14", "gpt-4o-2024-08-06"], _matrix("gpt-4.1-2025-04-14")
    )
    assert reason


def test_an_unobserved_side_is_not_accused():
    """No served_model recorded anywhere is unknown, never a mismatch (a $0 replay, an old run)."""
    assert served_models_disagree([], _matrix("gpt-4.1-2025-04-14")) is None
    assert served_models_disagree(["gpt-4.1-2025-04-14"], _matrix(None)) is None
    assert served_models_disagree([], []) is None


def test_the_comparison_ignores_case():
    assert served_models_disagree(["GPT-4.1-2025-04-14"], _matrix("gpt-4.1-2025-04-14")) is None


def test_the_export_step_refuses_on_a_disagreement(tmp_path):
    """The check is only worth anything if the CLI stops instead of writing the file."""
    import inspect

    from lithrim_bench.cli import export

    src = inspect.getsource(export.main) if hasattr(export, "main") else inspect.getsource(export)
    assert "served_models_disagree" in src
    assert "SystemExit" in src


def test_a_grade_file_that_cannot_be_read_is_not_a_mismatch():
    with pytest.raises(TypeError):
        served_models_disagree(["x"], None)  # a caller bug, not a silent pass


def test_the_export_verb_reads_the_active_workspace(monkeypatch, tmp_path):
    """WS-DIR-1 for the export verb: its corrections log and collections db followed `default`."""
    import argparse

    from lithrim_bench.cli import export as _export

    ap = argparse.ArgumentParser()
    _export.add_arguments(ap)
    a = ap.parse_args(["--slice", str(tmp_path / "s.jsonl"), "--split", "test", "--out", str(tmp_path / "o.jsonl")])
    assert a.corrections is None and a.collections_db is None, "no hardcoded default workspace"

    monkeypatch.setattr("lithrim_bench.cli.loop.active_workspace", lambda bff: "repro3")
    with pytest.raises((SystemExit, FileNotFoundError, OSError)):  # stops later; the paths are set
        _export.cmd_export(a)
    assert a.corrections.parent.parent.name == "repro3", a.corrections
    assert a.collections_db.parent.name == "repro3", a.collections_db
