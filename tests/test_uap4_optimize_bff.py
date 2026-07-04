"""UAP-4 BFF acceptance: POST /v1/judges/{role}/optimize — the calibration-trainer
route (R5), now IN-CORPUS (Phase 2). Hermetic + $0: the PAID optimize runs in a
pack-bound subprocess (``_optimize_via_subprocess``), so every test here INJECTS a fake
for that seam — no spawn, no live call. We prove the route's cost-gate (422 without
confirm), the honest Δ-shape passthrough, the role+limit wiring, and the unknown-role
404 (pack-aware). The real held-out Δ is the cost-gated user-run attestation (A-LIVE),
not an automated test. The active workspace is stubbed to a discoverable pack so the
pack-aware role check resolves hermetically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_ROLE = "risk_judge"

# A representative honest-Δ payload (here a LOSS — the WS-6c-DSPy-3b prior) so the
# route test never assumes a win.
_FAKE_RESULT = {
    "role": _ROLE,
    "n_train": 24,
    "n_heldout": 10,
    "compile_config": {
        "max_bootstrapped_demos": 4,
        "max_labeled_demos": 0,
        "co_raise_aware": True,
        "coverage_aware": True,
        "n_demos_bootstrapped": 4,
        "n_positive_demos": 1,
    },
    "baseline": {"accepted": True, "graded": 0.8, "precision": 0.71, "recall": 0.71,
                 "tp": 5, "fp": 2, "fn": 2, "n": 10},
    "optimized": {"accepted": False, "graded": 0.7, "precision": 0.44, "recall": 0.57,
                  "tp": 4, "fp": 5, "fn": 3, "n": 10},
    "delta": {"graded": -0.1, "precision": -0.27, "recall": -0.14,
              "accepted": (True, False),
              "tp_fp_fn": {"baseline": [5, 2, 2], "optimized": [4, 5, 3]}},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    calls: list[dict] = []

    def _fake_optimize_via_subprocess(*, role, ws, collections_db, out_dir, limit, case_ids=None):
        calls.append({
            "role": role, "limit": limit, "collections_db": str(collections_db),
            "case_ids": case_ids,
        })
        return {**_FAKE_RESULT, "role": role}

    # the PAID optimize is a pack-bound subprocess; inject the seam so no process spawns.
    monkeypatch.setattr(bff, "_optimize_via_subprocess", _fake_optimize_via_subprocess)
    # stub the active workspace to a DISCOVERABLE pack so the pack-aware role check resolves
    # hermetically (the test env discovers ``healthcare``, not the local clinverdict drop-in).
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: SimpleNamespace(name="test_ws", pack="healthcare", packs_dir=None),
    )
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "cases.db"
    c = TestClient(bff.app)
    c._optimize_calls = calls  # surface for assertions
    try:
        yield c
    finally:
        bff.app.dependency_overrides.clear()


def test_optimize_refuses_without_confirm(client):
    """The cost-gate: a PAID run must be explicitly confirmed (the in-DOM modal)."""
    res = client.post(f"/v1/judges/{_ROLE}/optimize", json={})
    assert res.status_code == 422
    assert "confirm=true" in res.json()["detail"]
    assert client._optimize_calls == []  # run_optimize NEVER called


def test_optimize_unknown_role_is_404(client):
    res = client.post("/v1/judges/not_a_judge/optimize", json={"confirm": True})
    assert res.status_code == 404
    assert client._optimize_calls == []


def test_optimize_returns_the_honest_delta_shape(client):
    res = client.post(f"/v1/judges/{_ROLE}/optimize", json={"confirm": True})
    assert res.status_code == 200
    body = res.json()
    assert {"role", "n_train", "n_heldout", "baseline", "optimized", "delta"} <= set(body)
    for arm in ("baseline", "optimized"):
        assert {"graded", "precision", "recall"} <= set(body[arm])
    # the payload is passed through verbatim — a LOSS stays a loss (R1)
    assert body["delta"]["graded"] == -0.1


def test_optimize_subprocess_hydrates_bindings_before_spawn(monkeypatch, tmp_path):
    # GENERALIST-1/Phase-2: the REAL _optimize_via_subprocess must hydrate the per-role provider
    # bindings into os.environ BEFORE it spawns, so the bound model (faithfulness→gpt-4.1) reaches
    # build_judge_lm in the child — else it falls back to the role's default (un-deployed) deployment.
    order: list[str] = []
    monkeypatch.setattr(bff, "_hydrate_role_bindings_into_env", lambda: order.append("hydrate"))

    class _Proc:
        returncode = 0
        stdout = "__OPTIMIZE_JSON__" + json.dumps(_FAKE_RESULT)
        stderr = ""

    captured: dict = {}

    def _fake_run(cmd, env=None, **kw):
        order.append("spawn")
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(bff.subprocess, "run", _fake_run)
    ws = SimpleNamespace(name="ws", pack="healthcare", packs_dir=None)
    res = bff._optimize_via_subprocess(
        role="faithfulness_judge", ws=ws, collections_db=tmp_path / "c.db",
        out_dir=tmp_path / "out", limit=None,
    )
    assert order == ["hydrate", "spawn"]  # hydrate runs FIRST, then the spawn inherits the env
    assert "--role" in captured["cmd"] and "faithfulness_judge" in captured["cmd"]
    assert res["role"] == _FAKE_RESULT["role"]  # the __OPTIMIZE_JSON__ envelope is passed through


def test_optimize_wires_role_and_limit_to_the_subprocess(client):
    # the endpoint threads role + the cost-smoke limit into the pack-bound subprocess; confirm_cost
    # + coverage_aware are pinned INSIDE the subprocess (scripts/optimize_judge.py), not the route.
    client.post(f"/v1/judges/{_ROLE}/optimize", json={"confirm": True, "limit": 2})
    assert len(client._optimize_calls) == 1
    call = client._optimize_calls[0]
    assert call["role"] == _ROLE
    assert call["limit"] == 2
