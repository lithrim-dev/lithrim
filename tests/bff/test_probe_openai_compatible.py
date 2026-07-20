"""Dry-run findings, the openai_compatible connect probe.

2026-07-16 (public-cut rerun): the probe had no default-model entry for openai_compatible, so a
UI connect (which sends NO model) pinged ``openai/gpt-4o`` against the user's api_base — hosts
that don't serve gpt-4o (e.g. Featherless) failed every connect with an opaque NotFoundError
and the key was never stored.

2026-07-16 (Option A hardening): discovering ``data[0]`` from ``GET {api_base}/models`` is not
enough — Featherless serves 22k models and ``/models`` is UNAUTHENTICATED (200 with no key), so
(a) the listing can't validate the key on its own and (b) the arbitrary first model may be
gated/offline/non-chat, making the model-less connect fail non-deterministically per user. The
probe must therefore (1) try discovered candidates in order, skipping a model that fails for a
model-shaped reason, until one COMPLETES (the non-vacuous key gate), and (2) fail FAST on an
auth-shaped error (a bad key never "falls through" to the next candidate). A model-carrying
probe (the roles-bind re-probe) is unchanged. $0/offline — litellm/httpx are faked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

API_BASE = "https://api.featherless.ai/v1"
HOSTED = "aaditya/Llama3-OpenBioLLM-70B"


class _ModelError(Exception):
    """A model-shaped failure (unservable / not found) — the probe should try the next candidate."""

    status_code = 404


class _AuthError(Exception):
    """An auth-shaped failure — the probe must fail fast (a bad key, no candidate helps)."""

    status_code = 401


class _FakeLitellm:
    """Records every completion call; ``rule(model)`` may return an exception to raise for that
    model (None = success)."""

    def __init__(self, rule=None):
        self.calls: list[dict] = []
        self.captured: dict = {}
        self._rule = rule or (lambda _model: None)

    def completion(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.captured = dict(kwargs)
        exc = self._rule(kwargs.get("model"))
        if exc is not None:
            raise exc
        return {"ok": True}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHttpx:
    def __init__(self, payload=None, error: Exception | None = None):
        self.calls: list[dict] = []
        self._payload = payload
        self._error = error

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._payload)


def _listing(*ids):
    return {"data": [{"id": i} for i in ids]}


def test_openai_compatible_probe_discovers_hosted_model(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(payload=_listing(HOSTED, "other/model"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    assert res == {"ok": True}
    assert len(httpx.calls) == 1
    assert httpx.calls[0]["url"] == f"{API_BASE}/models"
    assert httpx.calls[0]["headers"]["Authorization"] == "Bearer sk-x"
    # non-vacuous key check: a bounded completion on a served model — not gpt-4o
    assert litellm.captured["model"] == f"openai/{HOSTED}"
    assert litellm.captured["api_base"] == API_BASE
    assert litellm.captured.get("max_tokens", 0) >= 16
    assert len(litellm.calls) == 1  # first candidate served → one attempt


def test_openai_compatible_probe_with_model_skips_discovery(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(payload=_listing("other/model"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x",
        endpoint=API_BASE, model=HOSTED,
    )
    assert res == {"ok": True}
    assert httpx.calls == []  # the roles-bind re-probe path: no discovery
    assert litellm.captured["model"] == f"openai/{HOSTED}"


def test_openai_compatible_probe_falls_back_when_listing_unavailable(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(error=RuntimeError("connect timeout"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    assert res == {"ok": True}
    assert litellm.captured["model"] == "openai/gpt-4o"


def test_probe_skips_unservable_model_and_tries_next(monkeypatch):
    # first discovered model is gated/offline (model-shaped error) → probe advances to the next.
    bad, good = "gated/offline-model", HOSTED
    litellm = _FakeLitellm(rule=lambda m: _ModelError("no such model") if m.endswith(bad) else None)
    httpx = _FakeHttpx(payload=_listing(bad, good, "third/model"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    assert res == {"ok": True}
    tried = [c["model"] for c in litellm.calls]
    assert tried == [f"openai/{bad}", f"openai/{good}"]  # advanced past the unservable one, stopped at ok


def test_probe_fails_fast_on_auth_error(monkeypatch):
    # a bad key returns auth-shaped on the FIRST candidate — the probe must NOT try more models
    # (else a bad key could "pass" on some later public model and store an invalid credential).
    litellm = _FakeLitellm(rule=lambda _m: _AuthError("invalid api key"))
    httpx = _FakeHttpx(payload=_listing("a/one", "b/two", "c/three"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-bad", endpoint=API_BASE
    )
    assert res["ok"] is False
    assert len(litellm.calls) == 1  # failed fast, did not fall through to other candidates


def test_probe_fails_when_all_candidates_unservable(monkeypatch):
    litellm = _FakeLitellm(rule=lambda _m: _ModelError("unservable"))
    httpx = _FakeHttpx(payload=_listing("a/one", "b/two"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    assert res["ok"] is False
    assert len(litellm.calls) >= 2  # exhausted the bounded candidate set, none served
