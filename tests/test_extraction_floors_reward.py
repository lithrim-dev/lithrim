"""REWARD-EXTRACTOR-1 — a criterion-conditioned reward model as the bounded-extraction floor's
extractor, alongside the existing chat-LM path.

Why this seam is worth having: the reason a reward model needs an adapter to JUDGE is that it
types no defect codes (findings stay empty by design). The floor never asks it to — the contract
already declares ``inject_flag_code`` — so the property that blocks it as a judge is irrelevant
here, and what remains is exactly what a reward model is built for: one authored criterion,
answered on a 0-1 scale, deterministically.

The bug this pins (found live 2026-07-22): ``RewardModelLM`` deliberately does NOT subclass
``dspy.BaseLM``, so it is NOT callable. The floor's chat path does ``lm(prompt)``, which raises
``TypeError``, which the per-sample guard swallows as "extraction failed" — every contract then
DECLINES with "extraction LM unavailable". That failure is indistinguishable from a real
cannot-ground result, so a mis-wired reward extractor would look exactly like a genuine finding.
``test_reward_lm_binding_does_not_silently_decline`` is the regression guard, and it drives the
real ``RewardModelLM`` through an injected transport so the wire shape is covered too.

Conservatism is unchanged and non-negotiable: a score inside the dead band, a transport failure,
or a non-numeric score all DECLINE (``conforms=None``). Only a confident score either way moves a
verdict. $0/offline throughout — the reward LM is injected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.verification.extraction_floors import (  # noqa: E402
    FactPreservationTool,
    SpeakerAttributionTool,
)
from lithrim_bench.verification.spec import Claim, VerificationSpec  # noqa: E402

_CASE = {
    "case_id": "cv10_splinter",
    "transcript": (
        "Patient: I am an American farmer by blood.\n"
        "Doctor: When was your last tetanus shot?\n"
        "Patient: But I don't want any tetanus vaccine now.\n"
        "Patient: I get a bad reaction to vaccines so I don't want it."
    ),
}
_NOTE_ERASED = "Chief complaint: splinter. Plan: tetanus prophylaxis discussed."
_FACT = "the patient refused the tetanus vaccine because of a bad reaction to vaccines"


def _spec(tool, reference):
    return VerificationSpec(
        tool=tool, applies_to_flags=("DISSENT_ERASURE",), locus="",
        reference=reference, version="test/1",
    )


def _claim(subject=_NOTE_ERASED, source=_CASE):
    return Claim(
        claim_type="structural_conformance", flag_code="DISSENT_ERASURE",
        subject=subject, locus="", source=source,
    )


class _FakeRewardLM:
    """A reward LM with the shipped shape: ``is_reward_lm`` marker, ``evaluate``, NOT callable."""

    is_reward_lm = True

    def __init__(self, score=0.1, explanation="", raises=None, model="composo-reward"):
        self.model = model
        self._score, self._explanation, self._raises = score, explanation, raises
        self.calls = []

    def evaluate(self, user: str, assistant: str, criterion: str):
        self.calls.append({"user": user, "assistant": assistant, "criterion": criterion})
        if self._raises is not None:
            raise self._raises
        return {"score": self._score, "explanation": self._explanation}


def _verify(lm, ref=None, tool_cls=FactPreservationTool, claim=None):
    ref = {"fact": _FACT} if ref is None else ref
    return tool_cls(lm=lm).verify(claim or _claim(), _spec(tool_cls.name, ref))


# ── the tri-state, driven by the score ────────────────────────────────────────


def test_low_score_is_a_violation_and_blocks():
    """Criterion 'the note preserves <fact>' scored low = the fact was erased = enforce."""
    lm = _FakeRewardLM(score=0.04, explanation="the refusal is absent from the note")
    res = _verify(lm)
    assert res.conforms is False
    assert res.evidence["score"] == pytest.approx(0.04)
    assert "absent" in res.evidence["explanation"]


def test_high_score_is_satisfied_and_never_blocks():
    res = _verify(_FakeRewardLM(score=0.97))
    assert res.conforms is True


@pytest.mark.parametrize("score", [0.4, 0.5, 0.6])
def test_dead_band_declines_rather_than_guessing(score):
    """The floor's whole value is that an uncertain answer never moves a verdict."""
    res = _verify(_FakeRewardLM(score=score))
    assert res.conforms is None
    assert res.evidence["score"] == pytest.approx(score)


def test_band_is_overridable_from_the_contract():
    ref = {"fact": _FACT, "reward_band": [0.2, 0.8]}
    assert _verify(_FakeRewardLM(score=0.3), ref).conforms is None
    assert _verify(_FakeRewardLM(score=0.1), ref).conforms is False
    assert _verify(_FakeRewardLM(score=0.9), ref).conforms is True


# ── conservatism: every failure mode declines ─────────────────────────────────


def test_transport_failure_declines_and_does_not_raise():
    res = _verify(_FakeRewardLM(raises=RuntimeError("502 from the reward API")))
    assert res.conforms is None
    assert "502" in str(res.evidence.get("reason", ""))


def test_non_numeric_score_declines():
    res = _verify(_FakeRewardLM(score="high"))
    assert res.conforms is None


# ── the wire: what actually gets sent ─────────────────────────────────────────


def test_source_and_artifact_map_onto_the_two_messages():
    lm = _FakeRewardLM()
    _verify(lm)
    call = lm.calls[0]
    assert "don't want any tetanus vaccine" in call["user"], "source must ride the user message"
    assert call["assistant"] == _NOTE_ERASED, "artifact must ride the assistant message"


def test_criterion_uses_an_accepted_reward_prefix():
    """LIVE-PINNED: the reward API 422s any criterion not starting with Reward / Penalize /
    Passes if / Fails if ("Evaluation criteria must start with one of the following"). A bare
    declarative sentence is rejected outright, so the prefix is part of the contract, not style.
    'Passes if' is the binary form and separated 1.0 vs 0.0 on the splinter pair where
    'Reward responses that' gave 0.98 vs 0.20."""
    lm = _FakeRewardLM()
    _verify(lm)
    crit = lm.calls[0]["criterion"]
    assert crit.startswith(("Reward", "Penalize", "Passes if", "Fails if")), crit
    assert _FACT in crit
    assert not crit.strip().endswith("?"), "a reward model scores satisfaction, not a question"


def test_speaker_criterion_also_carries_an_accepted_prefix():
    lm = _FakeRewardLM(score=0.02)
    _verify(lm, ref={"statement": "the patient is taking their seizure medication"},
            tool_cls=SpeakerAttributionTool)
    assert lm.calls[0]["criterion"].startswith(("Reward", "Penalize", "Passes if", "Fails if"))


def test_speaker_attribution_builds_its_own_criterion():
    lm = _FakeRewardLM(score=0.02)
    res = _verify(lm, ref={"statement": "the patient is taking their seizure medication"},
                  tool_cls=SpeakerAttributionTool)
    assert res.conforms is False
    assert "seizure medication" in lm.calls[0]["criterion"]


def test_reward_path_defaults_to_one_call():
    """A reward model is deterministic per (messages, criterion), so the k-repeat majority the
    chat path needs is pure cost here. Default k=1; an explicit k is still honoured."""
    lm = _FakeRewardLM()
    _verify(lm)
    assert len(lm.calls) == 1
    lm2 = _FakeRewardLM()
    _verify(lm2, ref={"fact": _FACT, "k": 3})
    assert len(lm2.calls) == 3


# ── the manifest stays honest ─────────────────────────────────────────────────


def test_manifest_names_the_reward_extraction_and_records_the_raw_score():
    lm = _FakeRewardLM(score=0.04, model="composo-reward-2026-01-15")
    res = _verify(lm)
    m = res.manifest
    assert m["extraction"] == "reward-model", "must never masquerade as the chat-LM path"
    assert m["deterministic"] is False
    assert m["model"] == "composo-reward-2026-01-15", "a dated id must survive into provenance"
    assert m["band"] == [0.4, 0.6]
    assert res.evidence["score"] == pytest.approx(0.04), "the RAW score is the honest artifact"


# ── regressions: the chat path is untouched, and the live bug is dead ─────────


def test_chat_lm_path_is_unchanged():
    """A plain callable LM must still take the strict-JSON k-majority route."""
    calls = []

    def lm(prompt: str) -> str:
        calls.append(prompt)
        return ('{"stated_in_source": true, "source_quote": "x", '
                '"preserved_in_artifact": false, "artifact_quote_or_empty": ""}')

    res = _verify(lm)
    assert res.conforms is False
    assert res.manifest["extraction"] == "bounded-llm"
    assert len(calls) == 3, "the chat path keeps its k=3 majority"


def test_reward_lm_binding_does_not_silently_decline():
    """THE regression guard for the 2026-07-22 live bug: the shipped RewardModelLM is not
    callable, so the chat path raised TypeError and every contract DECLINED with
    'extraction failed' — a wiring bug wearing the costume of a real cannot-ground finding."""
    from lithrim_bench.runtime.council.reward_lm import build_composo_reward_lm

    sent = {}

    def transport(url, headers, payload):
        sent["url"], sent["payload"] = url, payload
        return {"score": 0.03, "explanation": "the refusal does not appear in the note"}

    lm = build_composo_reward_lm(api_key="k", transport=transport)
    assert not callable(lm), "precondition: the shipped reward LM is not a chat LM"

    res = _verify(lm)
    assert res.conforms is False, "must enforce, NOT decline with an extraction-failed reason"
    assert "extraction failed" not in str(res.evidence)
    assert sent["payload"]["evaluation_criteria"]
    assert len(sent["payload"]["messages"]) == 2
