"""NARR-5 D3 + D4 — the multi-model council SEAM (offline, $0) + the LENGTH_VIOLATION
positive-catch MOCK proof.

D3 (SEAM / WIRING — NOT judge quality): the Claude/GPT/Llama mixed-provider council is
ALREADY config-only. ``build_trio(ontology=<narrative>, models={'risk_judge': 'byo-claude'})``
— with NO ``predictors`` (``build_trio`` is all-or-nothing on ``predictors``: passing it makes
EVERY role take the predictor branch and the ``build_judge_lm`` / ``ClaudeCliLM`` routing is
never reached) — routes ``risk_judge`` to the tool-less ``ClaudeCliLM`` and the other two roles
to Azure ``dspy.LM`` constructed WITHOUT any network call ($0). This proves the SEAM: a mixed
council is assemblable by config alone, no engine edit. The cheap gate that de-risks the PAID
live D5 before spending. Mirrors ``tests/test_byoc_provider.py::test_build_trio_models_*``.

D4 (MOCK positive-catch — the REAL live catch is D5): NARR-4 DEMOTED ``LENGTH_VIOLATION`` out of
the deterministic floor → the ``policy_judge`` LENS. So the positive catch now lives in the JUDGE
layer. With a ``policy_judge`` PREDICTOR (a MOCK, not a real LM) that fires ``LENGTH_VIOLATION``
on an over-length-preamble scene, the trio's ``policy_judge`` seam carries ``LENGTH_VIOLATION``
with an evidence span (and survives ``_validate_findings`` because it is a known narrative
taxonomy code). This proves the WIRING of the judge-lens catch; whether a REAL ``policy_judge``
LM fires it on a genuine over-length scene is the honest live D5 obligation (S-BS-NARR4-1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.pack import active_pack, pack_ontology_path  # noqa: E402
from lithrim_bench.runtime.council import judges_dspy as J  # noqa: E402
from lithrim_bench.runtime.council.settings import settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# D3/D4 assert NARRATIVE-pack taxonomy behavior (LENGTH_VIOLATION is a narrative policy_judge
# lens code; under pack=healthcare it is not a KNOWN code and _validate_findings drops it). The
# canonical narrative env is LITHRIM_BENCH_PACK=narrative — skip the module otherwise so the
# pack=healthcare regression gate stays 0-new.
pytestmark = pytest.mark.skipif(
    active_pack() != "narrative",
    reason="narrative multi-model seam proof — set LITHRIM_BENCH_PACK=narrative",
)

ONT = load_ontology(pack_ontology_path()) if active_pack() == "narrative" else None


# ── D3 — the multi-model SEAM/WIRING (offline, $0; NOT judge quality) ──────────────────


def test_multimodel_seam_build_trio_models_routes_per_role_offline(monkeypatch):
    """D3 SEAM: build_trio(models={'risk_judge':'byo-claude'}) over the NARRATIVE ontology routes
    risk_judge → ClaudeCliLM and the other two roles → Azure dspy.LM, each constructed with NO
    network call ($0). This proves a Claude/GPT/Llama mixed council is config-only — the WIRING,
    not judge quality. Mirrors test_byoc_provider.py:164."""
    # the two non-byo roles are the Azure trio — select it explicitly (the default openai provider
    # now routes to the single-key OpenAI council, BYOK Cycle 1). These are config attrs, never a
    # network call (mirrors test_byoc_provider.py:165-166).
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "azure")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "mistral-large-3")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK", "llama-4-maverick")

    trio = J.build_trio(ontology=ONT, models={"risk_judge": "byo-claude"})

    kinds = {j.role: type(j.predict.lm).__name__ for j in trio}
    assert kinds == {
        "risk_judge": "ClaudeCliLM",  # the BYO-Claude tool-less seat
        "policy_judge": "LM",  # Azure dspy.LM
        "faithfulness_judge": "LM",  # Azure dspy.LM
    }
    # the two Azure seats are bound to their per-role deployments (the _ROLE_DEPLOYMENT seam)
    azure = {j.role: str(j.predict.lm.model) for j in trio if type(j.predict.lm).__name__ == "LM"}
    assert azure["policy_judge"] == "azure/mistral-large-3"
    assert azure["faithfulness_judge"] == "azure/llama-4-maverick"
    # the trio assembles as 3 role-bound judges over the narrative ontology
    assert [j.role for j in trio] == list(J.V2_ROLES)


def test_multimodel_seam_frozen_consensus_output_shape_offline(monkeypatch):
    """D3 SEAM (cont.): the mixed trio feeds the FROZEN _apply_consensus via evaluate_dspy and
    yields the {consensus, ...} output shape — proving the mixed-provider council plugs into the
    untouched moat. Each judge runs a MOCK predictor here (the consensus PLUMBING is under test,
    not the LMs); a real run is D5."""
    def _approve(*, role_key_questions="", **_kw):
        return {"decision": "approve", "findings": []}

    trio = J.build_trio(ontology=ONT, predictors={r: _approve for r in J.V2_ROLES})
    out = J.evaluate_dspy(trio, transcript="t", artifact="a")
    # the frozen-consensus output shape (the _apply_consensus contract) is intact
    assert isinstance(out, dict)
    assert {"consensus", "decision", "artifact_verdict", "evidence_summary"} <= set(out)
    assert out["decision"] == "approve" and out["artifact_verdict"] == "PASS"


# ── D4 — the LENGTH_VIOLATION positive-catch (MOCK predictor; the real catch is D5) ────

_OVER_LENGTH_SCENE = (
    "The wind rose. The dunes shifted. The night fell. The cold came. The fire died. "
    "The road waited. She turned to the window and the long dark gave no answer at all."
)


def _policy_fires_length_violation(*, role_key_questions="", **_kw):
    """A MOCK policy_judge predictor that fires LENGTH_VIOLATION with an evidence span. This is
    NOT a real LM — it stands in for the judge-lens catch the live D5 council must prove."""
    return {
        "decision": "reject",
        "findings": [
            {
                "taxonomy_code": "LENGTH_VIOLATION",
                "evidence_spans": [
                    {"quote": "The wind rose. The dunes shifted.", "turn_ids": []}
                ],
            }
        ],
    }


def _approve(*, role_key_questions="", **_kw):
    return {"decision": "approve", "findings": []}


def test_policy_judge_fires_length_violation_with_evidence_MOCK():
    """D4 MOCK: a policy_judge PREDICTOR (a mock, not a real LM) fires LENGTH_VIOLATION on an
    over-length-preamble scene; the policy_judge seam carries the code with a non-empty evidence
    span, surviving _validate_findings (LENGTH_VIOLATION is a known narrative taxonomy code). The
    REAL live catch (S-BS-NARR4-1) is D5."""
    predictors = {r: _approve for r in J.V2_ROLES}
    predictors["policy_judge"] = _policy_fires_length_violation
    trio = J.build_trio(ontology=ONT, predictors=predictors)

    by_role = {
        j.role: j.forward(transcript="prior beat", artifact=_OVER_LENGTH_SCENE) for j in trio
    }
    policy = by_role["policy_judge"]
    codes = {f["taxonomy_code"] for f in policy["findings"]}
    assert "LENGTH_VIOLATION" in codes, f"policy_judge did not carry LENGTH_VIOLATION: {policy}"
    lv = next(f for f in policy["findings"] if f["taxonomy_code"] == "LENGTH_VIOLATION")
    assert lv["evidence_spans"], "LENGTH_VIOLATION finding must carry an evidence span"
    assert lv["evidence_spans"][0]["quote"].strip()
    # non-vacuous: the other roles did NOT fire it (the catch is the policy_judge lens, isolated)
    assert "LENGTH_VIOLATION" not in {
        f["taxonomy_code"] for f in by_role["risk_judge"]["findings"]
    }
    assert by_role["risk_judge"]["decision"] == "approve"
