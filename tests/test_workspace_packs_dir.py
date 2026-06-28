"""NARR-9 — a workspace pinned to an EXTERNALLY-DISTRIBUTED pack self-describes where that pack
lives (``packs_dir``), so the grade subprocess can find it regardless of the BFF's ambient env.

Diagnosis (live dogfood 2026-06-17): the `clinical_scribe` workspace pinned `pack=healthcare` (an
external pack at ../lithrim-pack-healthcare) but recorded `packs_dir: null`. The grade subprocess
(`_grade_via_subprocess` sets LITHRIM_BENCH_PACKS_DIR only from `ws.packs_dir`) then crashed
`FileNotFoundError: pack 'healthcare' not found` unless the BFF's own shell happened to export the
dir. A workspace must carry its pack's location, not depend on ambient env (the multi-tenant shape).

Contract: `create_workspace(pack=<external>)` with no explicit `packs_dir` captures the external
packs-dir; an in-repo pack (`_core`/`narrative`), an entry-point pack, or a not-yet-discoverable
pack leaves it `None` (no crash, no spurious capture); an explicit `packs_dir` is honored verbatim.

Offline: a fake external packs-dir via `LITHRIM_BENCH_PACKS_DIR`; no network, no real pack.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lithrim_bench.harness import pack as P
from lithrim_bench.harness import workspace as W


def _fake_external_pack(ext: Path, pack_id: str) -> None:
    (ext / pack_id).mkdir(parents=True, exist_ok=True)
    (ext / pack_id / "pack.json").write_text(
        json.dumps({"id": pack_id, "tier": "core", "domain": "demo", "version": "1"})
    )


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Tmp WORKSPACES_DIR + a clean _pack_root cache so each test's env is honored."""
    monkeypatch.setattr(W, "WORKSPACES_DIR", tmp_path / "workspaces")
    if hasattr(P._pack_root, "cache_clear"):
        P._pack_root.cache_clear()
    yield tmp_path
    if hasattr(P._pack_root, "cache_clear"):
        P._pack_root.cache_clear()


def test_external_pack_captures_packs_dir(isolated, monkeypatch):
    ext = isolated / "ext_packs"
    _fake_external_pack(ext, "demopack")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(ext))
    P._pack_root.cache_clear()

    ws = W.create_workspace("t-ext", pack="demopack", seed=False)
    assert ws.packs_dir is not None
    assert Path(ws.packs_dir).resolve() == ext.resolve()  # the dir CONTAINING the pack


def test_default_pack_leaves_packs_dir_none(isolated, monkeypatch):
    monkeypatch.delenv("LITHRIM_BENCH_PACKS_DIR", raising=False)
    ws = W.create_workspace("t-core", pack=W.DEFAULT_PACK, seed=False)
    assert ws.packs_dir is None  # the neutral in-repo default never needs a packs_dir


def test_in_repo_pack_leaves_packs_dir_none(isolated, monkeypatch):
    # an external dir is set but does NOT contain `narrative` → narrative resolves in-repo →
    # its parent is the in-repo packs/ dir, NOT the external dir → nothing captured.
    ext = isolated / "ext_packs"
    _fake_external_pack(ext, "demopack")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(ext))
    P._pack_root.cache_clear()

    ws = W.create_workspace("t-narr", pack="narrative", seed=False)
    assert ws.packs_dir is None


def test_undiscoverable_pack_does_not_crash(isolated, monkeypatch):
    monkeypatch.delenv("LITHRIM_BENCH_PACKS_DIR", raising=False)
    P._pack_root.cache_clear()
    # a pack discoverable nowhere → create still succeeds (ambient env / a later install resolves it)
    ws = W.create_workspace("t-ghost", pack="nonexistent_pack_xyz", seed=False)
    assert ws.packs_dir is None


def test_explicit_packs_dir_is_honored(isolated, monkeypatch):
    ext = isolated / "ext_packs"
    _fake_external_pack(ext, "demopack")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(ext))
    P._pack_root.cache_clear()
    # an explicit packs_dir is never overwritten by the auto-capture
    ws = W.create_workspace("t-explicit", pack="demopack", packs_dir="/my/custom/dir", seed=False)
    assert ws.packs_dir == "/my/custom/dir"
