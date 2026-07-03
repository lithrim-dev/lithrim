"""REPRO-1 R4a/R4b — the bounded-extraction floors: ``fact_preservation`` (a pinned fact the
source states must be preserved in the artifact) and ``speaker_attribution`` (a statement the
artifact ascribes to a speaker must actually come from that speaker in the source).

The mechanism (the thesis §"what the deterministic layer actually is"): an LM does BOUNDED
extraction only (narrow question, temperature 0, K-repeat) — the VERDICT is deterministic logic
over the extracted booleans, majority-gated, and CONSERVATIVE: anything unconfirmed (fact not in
the source, parse garbage, LM unavailable) DECLINES (``conforms=None``) rather than guessing.
The manifest is honest: ``deterministic: False`` with the extraction model + k recorded — an
extraction floor never masquerades as a lookup.

Core + domain-agnostic: the FACT/STATEMENT text is SME-authored params (UI data), the LM rides
the product's provider seam (injectable here — $0/offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.verification.extraction_floors import (  # noqa: E402
    FactPreservationTool,
    SpeakerAttributionTool,
)
from lithrim_bench.verification.spec import Claim, VerificationSpec  # noqa: E402

_CASE = {
    "case_id": "c10",
    "transcript": "Patient: But I don't want any tetanus vaccine now. I get a bad reaction.",
}
_NOTE = "Chief complaint: splinter. Allergies: horse serum. Plan: tetanus vaccine administered."


def _spec(tool, reference):
    return VerificationSpec(
        tool=tool, applies_to_flags=("DISSENT_ERASURE",), locus="", reference=reference,
        version="test/1",
    )


def _claim(subject=_NOTE, source=_CASE):
    return Claim(
        claim_type="structural_conformance", flag_code="DISSENT_ERASURE",
        subject=subject, locus="", source=source,
    )


def _lm_returning(*payloads):
    """A fake LM: each call returns the next canned completion (cycled)."""
    calls = {"n": 0, "prompts": []}

    def lm(prompt: str) -> str:
        calls["prompts"].append(prompt)
        out = payloads[min(calls["n"], len(payloads) - 1)]
        calls["n"] += 1
        return out if isinstance(out, str) else json.dumps(out)

    return lm, calls


# ── fact_preservation ─────────────────────────────────────────────────────────


def test_fact_stated_but_erased_blocks_with_evidence():
    lm, calls = _lm_returning(
        {"stated_in_source": True, "source_quote": "I don't want any tetanus vaccine",
         "preserved_in_artifact": False, "artifact_quote": ""},
    )
    tool = FactPreservationTool(lm=lm)
    res = tool.verify(
        _claim(),
        _spec("fact_preservation", {"fact": "the patient refused the tetanus vaccine", "k": 3}),
    )
    assert res.conforms is False
    assert res.evidence["n_violated"] == 3 and res.evidence["k"] == 3
    assert "tetanus" in json.dumps(res.evidence)
    assert res.manifest["deterministic"] is False  # the honest extraction manifest
    assert res.manifest["k"] == 3
    assert calls["n"] == 3  # K independent extractions
    assert "refused the tetanus vaccine" in calls["prompts"][0]  # the pinned fact reaches the LM


def test_fact_preserved_does_not_fire():
    lm, _ = _lm_returning(
        {"stated_in_source": True, "source_quote": "q",
         "preserved_in_artifact": True, "artifact_quote": "Allergies: horse serum."},
    )
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "the patient is allergic to horse serum", "k": 5})
    )
    assert res.conforms is True


def test_fact_not_in_source_declines_never_guesses():
    lm, _ = _lm_returning(
        {"stated_in_source": False, "source_quote": "", "preserved_in_artifact": False,
         "artifact_quote": ""},
    )
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "a fact never stated", "k": 3})
    )
    assert res.conforms is None  # cannot ground → decline, never a manufactured verdict


def test_majority_gates_an_unstable_extraction():
    lm, _ = _lm_returning(
        {"stated_in_source": True, "preserved_in_artifact": False},
        {"stated_in_source": True, "preserved_in_artifact": True},
        {"stated_in_source": True, "preserved_in_artifact": False},
    )
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "f", "k": 3})
    )
    assert res.conforms is False  # 2/3 violated → majority blocks
    assert res.evidence["n_violated"] == 2


def test_parse_garbage_and_lm_failure_decline():
    lm, _ = _lm_returning("NOT JSON AT ALL")
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "f", "k": 3})
    )
    assert res.conforms is None

    def boom(prompt):
        raise RuntimeError("no provider")

    res2 = FactPreservationTool(lm=boom).verify(
        _claim(), _spec("fact_preservation", {"fact": "f", "k": 3})
    )
    assert res2.conforms is None
    assert "unavailable" in (res2.evidence.get("reason") or "") or "fail" in json.dumps(res2.evidence).lower()


def test_dict_shaped_completions_parse(monkeypatch):
    """DRYRUN-2026-07-03 (live-caught): a logprobs-enabled dspy.LM returns
    {'text': ..., 'logprobs': ...} per completion — the default extractor wrapper must unwrap
    the text, not stringify the dict into an unparseable sample."""
    import lithrim_bench.verification.extraction_floors as ef

    class _DictLM:
        def __call__(self, prompt):
            return [{"text": json.dumps({"stated_in_source": True, "source_quote": "q",
                                         "preserved_in_artifact": False,
                                         "artifact_quote_or_empty": ""}),
                     "logprobs": object()}]

    monkeypatch.setattr(
        "lithrim_bench.runtime.council.judges_dspy.build_judge_lm",
        lambda role: _DictLM(),
        raising=False,
    )
    lm = ef._build_extractor_lm("reviewer_x")
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "f", "k": 3})
    )
    assert res.conforms is False  # the dict-shaped completion parsed → violated majority


def test_unparseable_sample_retains_truncated_raw():
    lm, _ = _lm_returning("TOTALLY NOT JSON " * 30)
    res = FactPreservationTool(lm=lm).verify(
        _claim(), _spec("fact_preservation", {"fact": "f", "k": 1})
    )
    raw = res.evidence["samples"][0].get("raw") or ""
    assert raw.startswith("TOTALLY NOT JSON") and len(raw) <= 160


# ── speaker_attribution ───────────────────────────────────────────────────────


def test_proxy_statement_misattributed_blocks():
    lm, calls = _lm_returning(
        {"source_speaker": "guardian/proxy", "source_quote": "Yeah, she is on medication.",
         "artifact_attributes_to": "patient", "artifact_quote": "The patient reports being on medication"},
    )
    res = SpeakerAttributionTool(lm=lm).verify(
        _claim(subject="The patient reports being on medication."),
        _spec("speaker_attribution", {
            "statement": "the report that the patient is on medication", "k": 5,
        }),
    )
    assert res.conforms is False
    assert res.evidence["n_violated"] == 5
    assert "guardian" in json.dumps(res.evidence)
    assert res.manifest["deterministic"] is False


def test_correct_attribution_does_not_fire():
    lm, _ = _lm_returning(
        {"source_speaker": "patient", "source_quote": "I take it daily.",
         "artifact_attributes_to": "patient", "artifact_quote": "Patient reports taking it daily."},
    )
    res = SpeakerAttributionTool(lm=lm).verify(
        _claim(), _spec("speaker_attribution", {"statement": "s", "k": 3})
    )
    assert res.conforms is True


def test_unclear_attribution_declines():
    lm, _ = _lm_returning(
        {"source_speaker": "unknown", "source_quote": "",
         "artifact_attributes_to": "unclear", "artifact_quote": ""},
    )
    res = SpeakerAttributionTool(lm=lm).verify(
        _claim(), _spec("speaker_attribution", {"statement": "s", "k": 3})
    )
    assert res.conforms is None


# ── registration: both floors are CORE contract types (the clean-surface requirement) ──


def test_extraction_floors_register_as_core_floor_executors(monkeypatch):
    monkeypatch.delenv("LITHRIM_BENCH_PACK", raising=False)
    from lithrim_bench.harness import grounding as g

    g._core_floor_executors.cache_clear()
    try:
        core = g._core_floor_executors()
        assert "fact_preservation" in core
        assert "speaker_attribution" in core
        # the reference builders lift the SME params
        ref = core["fact_preservation"].reference_builder(
            {"fact": "the refusal", "k": 5, "source_path": "transcript"}
        )
        assert ref["fact"] == "the refusal" and ref["k"] == 5
        ref2 = core["speaker_attribution"].reference_builder({"statement": "s"})
        assert ref2["statement"] == "s"
    finally:
        g._core_floor_executors.cache_clear()
