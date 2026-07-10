"""LAUNCH-PREP D1 / A1: the standalone council-backend resolver.

The OSS core must run a real council with NO :8002/lithrim-backend and NO Mongo —
a human's explicit paid run defaults to the bundled in-process v2 council (BYO key).
``_resolve_run_backend`` is that routing: it maps a RunEvalRequest + the
``LITHRIM_COUNCIL_BACKEND`` env to the ``(live_http, in_process)`` pair fed to
``run_eval.run``. These checks are HERMETIC — they assert the resolver tuple, NOT a
live grade, so no Azure/:8002 call is made.

Non-vacuity: flip the default in ``_resolve_run_backend`` (return ``(True, False)``
for the unset-env live case) and ``test_live_defaults_to_in_process`` MUST start
FAILING — that case is the load-bearing "no :8002 by default" guarantee.

A-SAFE: the resolver lives at the human's run_eval endpoint, NOT the agent loop's
deny-hook. ``test_replay_stays_replay`` pins that a $0 replay request never routes
to a paid backend regardless of env.

Requires the [bff] extra (fastapi); skips cleanly when absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def test_live_defaults_to_in_process(monkeypatch):
    """Env unset: the shell's "Run live" (live=true) routes to the bundled in-process
    council — NOT :8002. This is the standalone-OSS-core guarantee (A1)."""
    monkeypatch.delenv("LITHRIM_COUNCIL_BACKEND", raising=False)
    req = bff.RunEvalRequest(live=True)
    assert bff._resolve_run_backend(req) == (False, True)


def test_live_in_process_explicit_env(monkeypatch):
    monkeypatch.setenv("LITHRIM_COUNCIL_BACKEND", "in_process")
    req = bff.RunEvalRequest(live=True)
    assert bff._resolve_run_backend(req) == (False, True)


def test_live_http_opt_in(monkeypatch):
    """LITHRIM_COUNCIL_BACKEND=http opts a lithrim-backend deployment back into :8002."""
    monkeypatch.setenv("LITHRIM_COUNCIL_BACKEND", "http")
    req = bff.RunEvalRequest(live=True)
    assert bff._resolve_run_backend(req) == (True, False)


def test_in_process_request_always_in_process(monkeypatch):
    """An explicit in_process=true (CLI/SDK) runs in-process irrespective of the env."""
    monkeypatch.setenv("LITHRIM_COUNCIL_BACKEND", "http")
    req = bff.RunEvalRequest(in_process=True)
    assert bff._resolve_run_backend(req) == (False, True)


def test_replay_stays_replay(monkeypatch):
    """A $0 replay request (live=false, in_process=false) never routes to a paid
    backend, under either env value (A-SAFE: no env can lift replay into a paid run)."""
    for val in ("http", "in_process"):
        monkeypatch.setenv("LITHRIM_COUNCIL_BACKEND", val)
        assert bff._resolve_run_backend(bff.RunEvalRequest()) == (False, False)
    monkeypatch.delenv("LITHRIM_COUNCIL_BACKEND", raising=False)
    assert bff._resolve_run_backend(bff.RunEvalRequest()) == (False, False)
