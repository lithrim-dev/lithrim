"""Regression: load_case must not crash when the pinned ``source`` is a DIRECTORY.

A workspace agent with no dataset source file resolves ``source_abspath()`` to the repo
root (``/app`` in the container) — a DIRECTORY. ``load_case`` guarded on ``source.exists()``
(true for a directory) and called ``source.open()``, raising ``IsADirectoryError`` → a 500 on
``GET /v1/case`` for an ingested case. The guard must be ``is_file()`` so a non-file source
falls through to the pack / workspace-corpus resolution (where the ingested case lives).
"""

from __future__ import annotations

import json

from lithrim_bench.picklist import load_case


def test_load_case_directory_source_falls_through(tmp_path):
    # tmp_path is a DIRECTORY (the sourceless-agent /app case). Must NOT raise; with no
    # pack/corpus match it returns None — proving it fell through instead of opening the dir.
    assert load_case("no_such_case_xyz", source=tmp_path) is None


def test_load_case_file_source_still_reads(tmp_path):
    # back-compat: a real jsonl source FILE is still read + pinned (the S-BS-9 source-pin).
    src = tmp_path / "cases.jsonl"
    src.write_text(json.dumps({"case_id": "c1", "context": "hi"}) + "\n")
    row = load_case("c1", source=src)
    assert row is not None and row["case_id"] == "c1"
