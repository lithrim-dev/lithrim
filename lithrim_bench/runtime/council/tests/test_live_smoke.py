"""ONE cost-confirmed live Azure smoke for the v2 trio (WS-6c, A5).

SKIPPED unless the real Azure env is present, so a bare offline ``pytest`` stays
green and $0. To run it (a separate, explicit go):

    LITHRIM_LLM_PROVIDER=azure \
    AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... \
    AZURE_OPENAI_DEPLOYMENT_COUNCIL=gpt-4.1 \
    AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3=... \
    AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK=... \
    pytest lithrim_bench/runtime/council/tests/test_live_smoke.py -s

Cost envelope: 3 chat completions (gpt-4.1 + Mistral-Large-3 + Llama-4-Maverick)
on ONE case ≈ $0.05–0.10, one-shot, no batching.

The smoke proves three things against the offline oracle on LIVE data:
  1. the v2 trio actually runs cross-provider (deployment-id substitution, Q2);
  2. the None-confidence tolerance is real — Mistral returns confidence=None;
  3. a by-construction fabrication case lands on the offline-expected verdict.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("openai")  # council package needs the [council] extra

_REQUIRED = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3",
    "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
)
_AZURE_READY = os.environ.get("LITHRIM_LLM_PROVIDER") == "azure" and all(
    os.environ.get(k) for k in _REQUIRED
)

pytestmark = pytest.mark.skipif(
    not _AZURE_READY,
    reason="live Azure smoke: set LITHRIM_LLM_PROVIDER=azure + AZURE_OPENAI_* (separate go)",
)

# By-construction smoke case = build_prompt's OWN canonical "COMPLETE FABRICATION
# RULE" example (compliance_council.py:554-563): a pure-scheduling transcript +
# an artifact that invents a Type-2-diabetes history (ICD E11.9) with ZERO
# transcript support -> FABRICATED_HISTORY + HALLUCINATED_DETAIL, which the
# prompt says "MUST be reject" / "Always flag it". These are Tier-2 (no
# owner-gating), so 2+ judges firing -> artifact BLOCK -> reject; robust and
# clear of the S-BS-31 owner-orphan minefield (e.g. an NKDA->allergy flip would
# steer to VALUE_MISMATCH, which has no v2 production owner). Payload shape
# matters: transcript lives under call_context.transcript and artifacts is a
# list of {type, content} (build_prompt + _prepare_full_analysis_payload).
SMOKE_PAYLOAD = {
    "call_context": {
        "transcript": (
            "Agent: Thanks for calling — how can I help today?\n"
            "Patient: I just need to reschedule my appointment to next Tuesday.\n"
            "Agent: Done — you're moved to Tuesday at 2pm. Anything else?\n"
            "Patient: No, that's everything. Thanks!"
        ),
    },
    "artifacts": [
        {
            "type": "clinical_note",
            "content": (
                "CLINICAL NOTE\n"
                "History of present illness: established Type 2 diabetes mellitus "
                "(ICD-10 E11.9), on metformin 1000mg BID.\n"
                "Assessment: diabetic follow-up, well controlled.\n"
                "Plan: continue metformin; repeat A1c in 3 months."
            ),
        }
    ],
    "agent_metadata": {"name": "Scheduling Assistant", "category": "scheduling"},
}
EXPECTED_VERDICT = "reject"


def test_v2_trio_live_smoke():
    from lithrim_bench.runtime.council import llm_provider
    from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil

    llm_provider.reset_clients()  # drop any client cached by the offline tests
    council = ComplianceCouncil()
    assert [m.name for m in council.models] == [
        "risk_judge",
        "policy_judge",
        "faithfulness_judge",
    ], "live smoke must run the v2 trio (set COMPLIANCE_COUNCIL_VERSION=v2)"

    result = council.evaluate(SMOKE_PAYLOAD, case_id="ws6c_live_smoke_fabricated_history")

    consensus = result["consensus"]
    models = result["models"]
    print("\n=== WS-6c live Azure smoke (v2 trio) ===")
    print(f"prompt chars (proxy for input tokens): {len(council.build_prompt(SMOKE_PAYLOAD))}")
    for m in models:
        print(
            f"  {m.get('model'):20} decision={m.get('decision'):12} "
            f"confidence={m.get('confidence')!r:8} errors={m.get('errors')}"
        )
    print(f"  CONSENSUS decision={consensus['decision']!r} confidence={consensus['confidence']!r}")
    print("  cost: 3 completions (gpt-4.1 + Mistral-Large-3 + Llama-4-Maverick), one case")

    # (1) all three judges attempted
    assert len(models) == 3
    by_role = {m["model"]: m for m in models}

    # (2) None-confidence tolerance on LIVE data: Mistral has no logprobs
    if not by_role["policy_judge"].get("errors"):
        assert by_role["policy_judge"].get("confidence") is None, (
            "Mistral (policy_judge) must surface confidence=None on live Azure — "
            "never synthesized to 1.0/0.0"
        )

    # (3) verdict matches the offline/by-construction expectation
    assert consensus["decision"] == EXPECTED_VERDICT
