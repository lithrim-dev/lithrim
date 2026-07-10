"""Dry-run finding (2026-07-03 stranger journey): the provider/bind probe pinged litellm with
``max_tokens: 1, temperature: 0`` — current reasoning-family models (e.g. gpt-5.5) reject BOTH
(min completion budget ≥ 16; only the default temperature supported), so binding a perfectly
valid frontier model failed with an opaque BadRequestError. The probe must be
parameter-minimal: a small-but-accepted token budget and NO temperature override.

Also pins the anthropic probe's default model is a CURRENT id (the retired
claude-3-5-haiku-latest default made connecting Anthropic fail out of the box).
$0/offline — litellm/anthropic are faked.
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


def test_grading_probe_is_parameter_minimal(monkeypatch):
    captured: dict = {}

    class _FakeLitellm:
        @staticmethod
        def completion(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

    monkeypatch.setitem(sys.modules, "litellm", _FakeLitellm)
    res = bff._probe_provider(plane="grading", provider="openai", api_key="sk-x", model="gpt-5.5")
    assert res == {"ok": True}
    assert "temperature" not in captured  # a temperature override breaks reasoning-family models
    assert captured.get("max_tokens", 0) >= 16  # the min completion budget modern models accept


def test_anthropic_probe_default_model_is_current(monkeypatch):
    captured: dict = {}

    class _Messages:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

    class _Client:
        def __init__(self, api_key):
            self.messages = _Messages()

    monkeypatch.setitem(
        sys.modules, "anthropic", type("m", (), {"Anthropic": _Client})
    )
    res = bff._probe_provider(plane="grading", provider="anthropic", api_key="sk-x")
    assert res == {"ok": True}
    assert "3-5-haiku" not in captured.get("model", "")  # the retired default
    assert captured.get("max_tokens", 0) >= 16
