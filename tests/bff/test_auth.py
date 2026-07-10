"""BFF-AUTH-1 — the configurable inbound auth gate (Community Release v1, Cycle 4).

A single FastAPI middleware gates the BFF behind a static bearer token. The token
is read PER-REQUEST from ``LITHRIM_BFF_TOKEN`` (via ``_bff_auth_token()``), so:

  * **unset/empty → gate OPEN** (the local single-user one-command run is unchanged —
    this is the critical non-regression: the rest of tests/bff/* run with no token set
    and must stay green).
  * **set → gate ON** (every request needs ``Authorization: Bearer <token>`` or
    ``X-API-Key: <token>``, constant-time compared), EXCEPT ``OPTIONS`` (CORS preflight)
    and ``GET /health`` (the liveness probe), which always pass.

Acceptance (driver §TESTS — RED first):
  * A — OFF by default: ``/health`` AND a ``/v1`` route return non-401 (today's behavior).
  * B — ON, no token presented → 401 on a ``/v1`` route.
  * C — ON, wrong token → 401.
  * D — ON, correct ``Authorization: Bearer <token>`` → passes (non-401).
  * E — ON, correct ``X-API-Key: <token>`` → passes.
  * F — ``/health`` open even when ON (liveness never gated).
  * G — ``OPTIONS`` preflight passes even when ON (CORS not broken).
  * H — non-vacuous: a near-miss (correct prefix + extra suffix) and a too-short token
        → 401 (proves WHOLE-VALUE matching — no prefix/length/``==`` partial match; the
        constant-TIME property of ``compare_digest`` is a code-review invariant, not unit-testable).
  * I — the ``Bearer`` scheme is matched case-insensitively (RFC 7235) — a lowercase
        ``authorization: bearer <token>`` from a standard client still passes.
  * J — a cross-origin 401 carries ``Access-Control-Allow-Origin`` (CORS is the OUTERMOST
        middleware, wrapping the gate) so a browser SPA reads a clean 401, not an opaque
        "Failed to fetch". (Surfaced by the live UI validation — the gate's 401 must not skip CORS.)

Requires the ``[bff]`` extra (fastapi); skipped cleanly if absent. Hermetic — a tmp config
DB via the get_config_db override (the tests/bff/ TestClient pattern); no network, no live
:8002, pack-independent. The token is toggled with monkeypatch.setenv/delenv per test (the
middleware reads it per request, so no app re-instantiation is needed).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_TOKEN = "s3cret-bff-token-abc123"
# A representative, side-effect-free /v1 GET (it seeds a tmp config DB via the override).
_V1_ROUTE = "/v1/agents"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "bench_config.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_off_by_default_health_and_v1_open(client, monkeypatch):
    """A: token unset → the gate is OPEN — ``/health`` AND a ``/v1`` route return non-401 (the
    critical non-regression: today's behavior is byte-unchanged with no token set)."""
    monkeypatch.delenv("LITHRIM_BFF_TOKEN", raising=False)

    health = client.get("/health")
    assert health.status_code == 200, health.text

    v1 = client.get(_V1_ROUTE)
    assert v1.status_code != 401, v1.text


def test_on_no_token_rejects(client, monkeypatch):
    """B: gate ON, no token presented → 401 on a ``/v1`` route, with a WWW-Authenticate hint."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.get(_V1_ROUTE)
    assert resp.status_code == 401, resp.text
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_on_wrong_token_rejects(client, monkeypatch):
    """C: gate ON, a wholly wrong token → 401."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.get(_V1_ROUTE, headers={"Authorization": "Bearer totally-wrong"})
    assert resp.status_code == 401, resp.text


def test_on_correct_bearer_passes(client, monkeypatch):
    """D: gate ON, the correct ``Authorization: Bearer <token>`` → passes (non-401)."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.get(_V1_ROUTE, headers={"Authorization": f"Bearer {_TOKEN}"})
    assert resp.status_code != 401, resp.text


def test_on_correct_x_api_key_passes(client, monkeypatch):
    """E: gate ON, the correct ``X-API-Key: <token>`` convenience header → passes."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.get(_V1_ROUTE, headers={"X-API-Key": _TOKEN})
    assert resp.status_code != 401, resp.text


def test_health_open_even_when_on(client, monkeypatch):
    """F: ``/health`` is the liveness probe — never gated, even with the token set + absent."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok"}


def test_options_preflight_passes_even_when_on(client, monkeypatch):
    """G: a CORS ``OPTIONS`` preflight passes even when ON (the gate must not break CORS)."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    resp = client.options(
        _V1_ROUTE,
        headers={
            "Origin": "http://localhost:5180",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code != 401, resp.text


def test_near_miss_tokens_reject(client, monkeypatch):
    """H: non-vacuous — a near-miss (correct prefix + extra suffix) and a too-short token both
    401. This proves WHOLE-VALUE matching: a prefix/length partial-``==`` bug that accepted
    ``_TOKEN + 'x'`` or ``_TOKEN[:8]`` would fail here. (The constant-TIME property of
    ``compare_digest`` — that it doesn't leak via response timing — is a code-review invariant,
    not expressible as a unit test; this asserts the functional whole-value guarantee.)"""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    longer = client.get(_V1_ROUTE, headers={"Authorization": f"Bearer {_TOKEN}x"})
    assert longer.status_code == 401, longer.text

    prefix = client.get(_V1_ROUTE, headers={"Authorization": f"Bearer {_TOKEN[:-1]}"})
    assert prefix.status_code == 401, prefix.text

    short = client.get(_V1_ROUTE, headers={"Authorization": f"Bearer {_TOKEN[:8]}"})
    assert short.status_code == 401, short.text


def test_bearer_scheme_is_case_insensitive(client, monkeypatch):
    """I: the auth-scheme token is case-insensitive per RFC 7235 — a lowercase ``bearer`` (and a
    mixed-case ``BeArEr``) with the correct credential still passes, so a standard client isn't
    wrongly rejected. The credential after the scheme stays case-sensitive (it's the secret)."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)

    lower = client.get(_V1_ROUTE, headers={"Authorization": f"bearer {_TOKEN}"})
    assert lower.status_code != 401, lower.text

    mixed = client.get(_V1_ROUTE, headers={"Authorization": f"BeArEr {_TOKEN}"})
    assert mixed.status_code != 401, mixed.text


def test_cross_origin_401_carries_cors_header(client, monkeypatch):
    """J: a cross-origin request (browser ``Origin``) that the gate REJECTS must still carry
    ``Access-Control-Allow-Origin`` — else the browser blocks the SPA from reading the 401 and it
    surfaces as an opaque "Failed to fetch". This holds only because CORS is the OUTERMOST
    middleware (wraps ``_auth_gate``); a regression that re-ordered them would strip the header
    off the 401. (Surfaced by the live UI validation.) The granted 200 carries it too."""
    monkeypatch.setenv("LITHRIM_BFF_TOKEN", _TOKEN)
    origin = "http://localhost:5180"

    rejected = client.get(_V1_ROUTE, headers={"Origin": origin})
    assert rejected.status_code == 401, rejected.text
    assert rejected.headers.get("access-control-allow-origin") == origin, dict(rejected.headers)

    granted = client.get(_V1_ROUTE, headers={"Origin": origin, "Authorization": f"Bearer {_TOKEN}"})
    assert granted.status_code != 401, granted.text
    assert granted.headers.get("access-control-allow-origin") == origin
