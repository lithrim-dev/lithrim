"""UAP-4 BFF acceptance: POST /v1/judges/{role}/optimize — the calibration-trainer
route (R5). Hermetic + $0: ``run_optimize`` is the PAID Azure entrypoint, so every
test here INJECTS a fake (monkeypatch bff.run_optimize) — no live call. We prove the
route's cost-gate (422 without confirm), the honest Δ-shape passthrough, the
coverage-aware + confirm_cost wiring, and the unknown-role 404. The real held-out Δ
is the cost-gated user-run attestation (A-LIVE), not an automated test.
"""

from __future__ import annotations

import sys
from pathlib import Path

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

    def _fake_run_optimize(role, **kwargs):
        calls.append({"role": role, **kwargs})
        return {**_FAKE_RESULT, "role": role}

    monkeypatch.setattr(bff, "run_optimize", _fake_run_optimize)
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_calib_corpus_path] = lambda: tmp_path / "corpus.jsonl"
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


def test_optimize_wires_confirm_cost_and_coverage_aware(client):
    client.post(f"/v1/judges/{_ROLE}/optimize", json={"confirm": True, "limit": 2})
    assert len(client._optimize_calls) == 1
    call = client._optimize_calls[0]
    assert call["role"] == _ROLE
    assert call["confirm_cost"] is True  # the route opts into the paid path explicitly
    assert call["coverage_aware"] is True  # S-BS-49 fix is ON
    assert call["limit"] == 2
