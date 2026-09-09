"""SERVED-MODEL-1: every stored vote carries what the provider actually served.

Observed 2026-09-09: a judge bound to the Azure deployment "gpt-4.1" was graded by
"gpt-4.1-2025-04-14" (the response's ``model``), with a ``system_fingerprint`` and a service
latency, all sitting in the LM history the engine already reads for token usage while the
persisted vote said only "azure/gpt-4.1". The binding is what was asked; this is what answered."""

from __future__ import annotations

from types import SimpleNamespace

from lithrim_bench.runtime.council import sampling
from lithrim_bench.runtime.pipeline.models import JudgeVote


class _LM:
    def __init__(self, history):
        self.history = history


def _entry(model="gpt-4.1-2025-04-14", fp="fp_861cf8a3da", latency=525):
    usage = {"prompt_tokens": 14, "completion_tokens": 2}
    if latency is not None:
        usage["latency_checkpoint"] = {"service_ttlt_ms": latency, "engine_ttlt_ms": 29}
    return {"response": SimpleNamespace(model=model, system_fingerprint=fp), "usage": usage}


def test_served_reads_the_entries_this_call_appended():
    lm = _LM([_entry(model="old-call"), _entry()])
    assert sampling._served(lm, history_before=1) == {
        "served_model": "gpt-4.1-2025-04-14",
        "system_fingerprint": "fp_861cf8a3da",
        "latency_ms": 525,
    }


def test_served_is_none_when_nothing_was_served():
    assert sampling._served(None, 0) is None
    assert sampling._served(_LM([]), 0) is None
    assert (
        sampling._served(_LM([{"response": SimpleNamespace(model=None), "usage": {}}]), 0) is None
    )
    no_latency = sampling._served(_LM([_entry(latency=None)]), 0)
    assert no_latency["latency_ms"] is None and no_latency["served_model"] == "gpt-4.1-2025-04-14"


def test_stored_vote_carries_the_served_fields_and_legacy_blobs_still_parse():
    v = JudgeVote(judge_role="r", vote="PASS", served_model="gpt-4.1-2025-04-14", latency_ms=525)
    assert v.served_model == "gpt-4.1-2025-04-14" and v.system_fingerprint is None
    legacy = JudgeVote(judge_role="r", vote="PASS")
    assert legacy.served_model is None and legacy.latency_ms is None
