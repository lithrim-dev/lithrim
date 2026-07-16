"""Dry-run finding (2026-07-16 public-cut rerun): the openai_compatible connect probe has no
default-model entry, so a UI connect (which sends NO model) pinged ``openai/gpt-4o`` against the
user's api_base — hosts that don't serve gpt-4o (e.g. Featherless) fail every connect with an
opaque NotFoundError and the key is never stored. The probe must discover a model the host
actually serves (``GET {api_base}/models``) and run the bounded completion on THAT, so the key
gate stays non-vacuous even where ``/models`` is unauthenticated. A model-carrying probe (the
roles-bind re-probe) is unchanged. $0/offline — litellm/httpx are faked.
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


class _FakeLitellm:
    def __init__(self):
        self.captured: dict = {}

    def completion(self, **kwargs):
        self.captured.update(kwargs)
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


def test_openai_compatible_probe_discovers_hosted_model(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(payload={"data": [{"id": HOSTED}, {"id": "other/model"}]})
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    assert res == {"ok": True}
    # discovery hit the host's own listing, authenticated
    assert len(httpx.calls) == 1
    assert httpx.calls[0]["url"] == f"{API_BASE}/models"
    assert httpx.calls[0]["headers"]["Authorization"] == "Bearer sk-x"
    # the non-vacuous key check: a bounded completion on a model the host serves — not gpt-4o
    assert litellm.captured["model"] == f"openai/{HOSTED}"
    assert litellm.captured["api_base"] == API_BASE
    assert litellm.captured.get("max_tokens", 0) >= 16


def test_openai_compatible_probe_with_model_skips_discovery(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(payload={"data": [{"id": "other/model"}]})
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x",
        endpoint=API_BASE, model=HOSTED,
    )
    assert res == {"ok": True}
    assert httpx.calls == []  # the roles-bind re-probe path is byte-identical: no discovery
    assert litellm.captured["model"] == f"openai/{HOSTED}"


def test_openai_compatible_probe_falls_back_when_listing_unavailable(monkeypatch):
    litellm = _FakeLitellm()
    httpx = _FakeHttpx(error=RuntimeError("connect timeout"))
    monkeypatch.setitem(sys.modules, "litellm", litellm)
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    res = bff._probe_provider(
        plane="grading", provider="openai_compatible", api_key="sk-x", endpoint=API_BASE
    )
    # discovery failure degrades to the old default-model completion, never a crash
    assert res == {"ok": True}
    assert litellm.captured["model"] == "openai/gpt-4o"
