"""optimize-on-subset (feat/optimize-on-subset): scope the DSPy calibration-trainer to a
CHOSEN case set, not only the whole workspace.

Two hermetic surfaces, $0 (no DSPy, no paid, no spawn):

1. scripts/optimize_judge.py's PURE case-selection helper — filter the workspace cases to an
   id set BEFORE the deterministic split, dropping unknown ids with a note. The existing
   split-refusal (an empty calibration OR held-out split → clean refuse) must still hold for a
   subset that starves a split, and an all-unknown set = the same empty refusal.
2. the BFF seam — OptimizeRequest carries case_ids; the endpoint threads it to the subprocess;
   _optimize_via_subprocess appends --case-ids per id ONLY when provided (None = today's
   whole-workspace cmd, byte-identical). The cost-confirm (confirm=true) is unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _cases():
    return [
        {"case_id": "c1", "expected_safety_flags": ["A"]},
        {"case_id": "c2", "expected_safety_flags": ["B"]},
        {"case_id": "c3", "expected_safety_flags": []},
    ]


# ── 1. the pure case-selection filter (scripts/optimize_judge.py) ──────────────────────────


def test_filter_none_is_whole_corpus_unchanged():
    import optimize_judge as oj

    cases = _cases()
    kept, dropped = oj.filter_cases_by_ids(cases, None)
    assert kept == cases  # None → today's whole-workspace behaviour, untouched
    assert dropped == []


def test_filter_selects_only_the_chosen_ids():
    import optimize_judge as oj

    kept, dropped = oj.filter_cases_by_ids(_cases(), ["c1", "c3"])
    assert [c["case_id"] for c in kept] == ["c1", "c3"]
    assert dropped == []


def test_filter_drops_unknown_ids_with_a_note():
    import optimize_judge as oj

    kept, dropped = oj.filter_cases_by_ids(_cases(), ["c1", "ghost", "c2"])
    assert [c["case_id"] for c in kept] == ["c1", "c2"]
    assert dropped == ["ghost"]  # unknown ids surfaced, not silently swallowed


def test_filter_all_unknown_yields_empty_keep():
    import optimize_judge as oj

    kept, dropped = oj.filter_cases_by_ids(_cases(), ["ghost", "phantom"])
    assert kept == []  # an all-unknown set → empty → the split refusal fires downstream
    assert dropped == ["ghost", "phantom"]


def test_empty_subset_still_hits_the_split_refusal():
    # An empty (or all-unknown) keep set yields 0 calibration + 0 test rows → the SAME refusal
    # the endpoint already raises for a degenerate corpus. Proven via the pure split_counts path
    # (no DSPy): filter → build_calib_rows → split_counts must be the empty refusal shape.
    import optimize_judge as oj

    from lithrim_bench.harness.calib_corpus import build_calib_rows, split_counts

    kept, _ = oj.filter_cases_by_ids(_cases(), ["ghost"])
    rows = build_calib_rows(kept)
    counts = split_counts(rows)
    assert counts["calibration"] == 0 and counts["test"] == 0  # → the clean 422 refusal


# ── 2. the BFF seam ────────────────────────────────────────────────────────────────────────

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_ROLE = "risk_judge"
_FAKE = {"role": _ROLE, "n_train": 6, "n_heldout": 3, "baseline": {}, "optimized": {}, "delta": {}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    calls: list[dict] = []

    def _fake(*, role, ws, collections_db, out_dir, limit, case_ids):
        calls.append({"role": role, "limit": limit, "case_ids": case_ids})
        return {**_FAKE, "role": role}

    monkeypatch.setattr(bff, "_optimize_via_subprocess", _fake)
    monkeypatch.setattr(
        bff.workspace, "get_active_workspace",
        lambda: SimpleNamespace(name="test_ws", pack="healthcare", packs_dir=None),
    )
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "cases.db"
    c = TestClient(bff.app)
    c._calls = calls
    try:
        yield c
    finally:
        bff.app.dependency_overrides.clear()


def test_request_carries_case_ids_and_defaults_none():
    assert bff.OptimizeRequest().case_ids is None  # back-compat: whole-workspace default
    assert bff.OptimizeRequest(case_ids=["c1", "c2"]).case_ids == ["c1", "c2"]


def test_endpoint_threads_case_ids_to_the_subprocess(client):
    client.post(f"/v1/judges/{_ROLE}/optimize", json={"confirm": True, "case_ids": ["c1", "c3"]})
    assert len(client._calls) == 1
    assert client._calls[0]["case_ids"] == ["c1", "c3"]


def test_endpoint_none_case_ids_is_whole_workspace(client):
    client.post(f"/v1/judges/{_ROLE}/optimize", json={"confirm": True})
    assert client._calls[0]["case_ids"] is None  # None → today's whole-workspace behaviour


def test_case_ids_does_not_weaken_the_cost_gate(client):
    # a subset selection is NOT a paid confirm — confirm=true is still required
    res = client.post(f"/v1/judges/{_ROLE}/optimize", json={"case_ids": ["c1"]})
    assert res.status_code == 422
    assert client._calls == []


def test_subprocess_appends_case_ids_only_when_provided(monkeypatch, tmp_path):
    monkeypatch.setattr(bff, "_hydrate_role_bindings_into_env", lambda: None)
    captured: dict = {}

    class _Proc:
        returncode = 0
        stdout = "__OPTIMIZE_JSON__" + '{"role": "risk_judge"}'
        stderr = ""

    def _fake_run(cmd, env=None, **kw):
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(bff.subprocess, "run", _fake_run)
    ws = SimpleNamespace(name="ws", pack="healthcare", packs_dir=None)

    # None → no --case-ids in the cmd (byte-identical to today)
    bff._optimize_via_subprocess(
        role=_ROLE, ws=ws, collections_db=tmp_path / "c.db",
        out_dir=tmp_path / "out", limit=None, case_ids=None,
    )
    assert "--case-ids" not in captured["cmd"]

    # provided → one --case-ids per id
    bff._optimize_via_subprocess(
        role=_ROLE, ws=ws, collections_db=tmp_path / "c.db",
        out_dir=tmp_path / "out", limit=None, case_ids=["c1", "c3"],
    )
    cmd = captured["cmd"]
    idxs = [i for i, tok in enumerate(cmd) if tok == "--case-ids"]
    assert len(idxs) == 2
    assert {cmd[i + 1] for i in idxs} == {"c1", "c3"}
