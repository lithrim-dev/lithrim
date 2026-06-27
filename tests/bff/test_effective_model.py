"""VOTE-MODEL-2 — the reviewer-config surface (GET /v1/judges) shows the model the reviewer
ACTUALLY grades on.

Two separate model-binding mechanisms had drifted apart in the UI:
  * ``jc.model``  — the editable per-judge BYOC override (the JudgeEditor field). EMPTY for the
    default trio.
  * the role_bindings DB — what the user assigned in the Provider Center (risk→gpt-4.1, …).

The roster only echoed ``jc.model`` (blank), so a reviewer the user HAD bound showed no model.
``_effective_model`` resolves the real grading model with a clear precedence + a ``model_source``
tag so the UI can label it. Pure (no ontology / workspace / DB) — unit-tested directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

_REPO = Path(__file__).resolve().parents[2]
_BFF = _REPO / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


class _JC:
    def __init__(self, model: str = "") -> None:
        self.model = model
        self.assigned_flags = []
        self.validator_refs = []


_BINDINGS = {
    "risk_judge": {"provider": "azure", "model": "gpt-4.1"},
    "policy_judge": {"provider": "azure", "model": "Mistral-Large-3"},
    "faithfulness_judge": None,  # unbound
}


def test_byoc_override_wins():
    """A per-judge BYOC override (jc.model set) is authoritative — that exact model grades."""
    model, provider, source = bff._effective_model(_JC("byo-claude"), "risk_judge", _BINDINGS)
    assert (model, source) == ("byo-claude", "override")


def test_falls_back_to_the_provider_center_binding():
    """jc.model empty → the Provider-Center role binding is the effective model (provider + model)."""
    model, provider, source = bff._effective_model(_JC(""), "policy_judge", _BINDINGS)
    assert (model, provider, source) == ("Mistral-Large-3", "azure", "binding")


def test_unbound_role_reports_default():
    """No override AND no binding → empty + 'default' (the Azure deployment default; the UI says so)."""
    model, provider, source = bff._effective_model(_JC(""), "faithfulness_judge", _BINDINGS)
    assert (model, provider, source) == ("", "", "default")


def test_none_jc_is_safe():
    """An unauthored role (jc is None) still resolves via the binding."""
    model, provider, source = bff._effective_model(None, "risk_judge", _BINDINGS)
    assert (model, provider, source) == ("gpt-4.1", "azure", "binding")


def test_judge_summary_carries_effective_fields(monkeypatch):
    """GET /v1/judges projects the effective model: a role bound only in the Provider Center
    (jc.model blank) still reports its bound model + provider + source='binding'."""
    from lithrim_bench.harness.ontology import load_ontology

    monkeypatch.setattr(bff, "_read_role_bindings", lambda: _BINDINGS)
    monkeypatch.setattr(
        bff, "_active_lens_by_role",
        lambda: {"risk_judge": set(), "policy_judge": set(), "faithfulness_judge": set()},
    )
    summary = bff._judge_summary("policy_judge", _JC(""), load_ontology())
    assert summary["model"] == ""  # the editable BYOC field is unchanged (still blank)
    assert summary["effective_model"] == "Mistral-Large-3"
    assert summary["effective_provider"] == "azure"
    assert summary["model_source"] == "binding"
