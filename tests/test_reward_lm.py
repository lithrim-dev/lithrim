"""F8-PROVIDER — a reward-model eval service (Composo-shaped) as a first-class judge provider.

The research's F8 finding: the strongest commodity judge is a purpose-built reward model —
deterministic, graded — and the honest architecture is that judge IN the commodity slot with the
deterministic floor beneath it. This wires that slot: ``provider: composo`` binds per-role through
the SAME seam every provider uses (``build_judge_lm``'s per-role env binding), and the sampling
layer maps score→verdict deterministically:

  * the reward API returns a 0–1 score (LOW = unsafe); verdict = threshold at 0.5 (reviewer config);
  * the RAW scores land in ``scores_raw`` — same direction as the decision scalars
    (reject=0.0 / approve=1.0), so the verdict-card K-split chip renders the graded score honestly
    (0.26 → "B", 0.74 → "P", 0.44 → borderline "R");
  * NO fabricated artifacts: findings stay empty (a reward judge types no defect codes), confidence
    stays None (no logprobs), usage stays None (no token report);
  * a transport failure DECLINES (needs_review) — never a manufactured verdict.

The key rides the per-role env binding / write-only ``.provider_env`` exactly like every provider
secret; it must never appear in a repr or a response."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.runtime.council.reward_lm import (  # noqa: E402
    COMPOSO_DEFAULT_API_BASE,
    RewardModelLM,
    build_composo_reward_lm,
)
from lithrim_bench.runtime.council.sampling import judge_call  # noqa: E402


class _Transport:
    """A fake HTTP transport: records (url, headers, payload) per call; yields queued
    responses (a dict) or raises (an Exception instance in the queue)."""

    def __init__(self, *responses):
        self.calls: list[tuple[str, dict, dict]] = []
        self._queue = list(responses)

    def __call__(self, url: str, headers: dict, payload: dict) -> dict:
        self.calls.append((url, dict(headers), payload))
        out = self._queue.pop(0) if self._queue else {"score": 0.5, "explanation": ""}
        if isinstance(out, Exception):
            raise out
        return out


def _lm(*responses, **kwargs) -> tuple[RewardModelLM, _Transport]:
    t = _Transport(*responses)
    return RewardModelLM(api_key="sk-test-reward", transport=t, **kwargs), t


# ── the wire contract ─────────────────────────────────────────────────────────


def test_wire_shape_messages_and_criteria():
    lm, t = _lm({"score": 0.26, "explanation": "omits the refusal"})
    out = lm.evaluate("USER TEXT", "ASSISTANT NOTE", "Reward only safe notes.")
    assert out["score"] == 0.26
    url, headers, payload = t.calls[0]
    assert url == f"{COMPOSO_DEFAULT_API_BASE}/api/v1/evals/reward"
    assert headers["API-Key"] == "sk-test-reward"
    assert payload["messages"] == [
        {"role": "user", "content": "USER TEXT"},
        {"role": "assistant", "content": "ASSISTANT NOTE"},
    ]
    assert payload["evaluation_criteria"] == "Reward only safe notes."


def test_api_base_override():
    lm, t = _lm({"score": 0.9, "explanation": ""}, api_base="http://localhost:9999/")
    lm.evaluate("u", "a", "c")
    assert t.calls[0][0] == "http://localhost:9999/api/v1/evals/reward"


def test_repr_never_leaks_the_key():
    lm, _ = _lm()
    assert "sk-test-reward" not in repr(lm) + str(lm)


def test_marker_attrs_for_the_sampling_layer():
    lm, _ = _lm()
    assert lm.is_reward_lm is True
    assert lm.supports_n is False  # never native-n sampled
    assert lm.model  # a display model string for vote attribution


# ── judge_call: score → deterministic verdict ─────────────────────────────────


def test_judge_call_blocks_below_threshold_with_raw_scores():
    lm, t = _lm(*[{"score": 0.26, "explanation": "omits the refusal"}] * 3)
    res = judge_call(
        "TRANSCRIPT", model=lm, k=3, artifact="NOTE",
        role_key_questions="Reward the note only if safe to file.",
    )
    assert res.decision == "reject"
    assert res.scores_raw == [0.26, 0.26, 0.26]  # RAW reward scores, not decision scalars
    assert res.k == 3 and len(t.calls) == 3  # k independent evaluations
    assert res.findings == []  # a reward judge types no defect codes — never fabricated
    assert res.usage is None  # no token report — never fabricated
    assert "omits the refusal" in res.rationale
    assert abs(res.score_mean - 0.26) < 1e-9
    # the criterion defaults to the reviewer's authored role prompt
    assert t.calls[0][2]["evaluation_criteria"] == "Reward the note only if safe to file."
    # REWARD-SEMANTICS-1 (measured, case09 six-call table): a reward model scores "did the
    # assistant serve the request", so the user message must BE a request — the source wrapped
    # in a task instruction, never a bare source dump (bare → faithfulness pressure collapses).
    user = t.calls[0][2]["messages"][0]["content"]
    assert "TRANSCRIPT" in user and user != "TRANSCRIPT"
    assert user.startswith("Source material:")
    assert "faithful artifact" in user  # the generic default task instruction
    assert t.calls[0][2]["messages"][1]["content"] == "NOTE"


def test_task_instruction_is_sme_overridable():
    lm, t = _lm({"score": 0.9, "explanation": ""},
                task_instruction="Generate a faithful clinical SOAP note from this encounter.")
    judge_call("TX", model=lm, k=1, artifact="a", role_key_questions="c")
    user = t.calls[0][2]["messages"][0]["content"]
    assert user.endswith("Generate a faithful clinical SOAP note from this encounter.")
    assert "TX" in user


def test_judge_call_passes_above_threshold():
    lm, _ = _lm({"score": 0.74, "explanation": "clean"})
    res = judge_call("t", model=lm, k=1, artifact="a", role_key_questions="c")
    assert res.decision == "approve"
    assert res.scores_raw == [0.74]


def test_judge_call_borderline_still_blocks():
    # F8's threshold-sensitivity note: 0.44 (case09) sits under the 0.5 cut → BLOCK.
    lm, _ = _lm({"score": 0.44, "explanation": "borderline"})
    res = judge_call("t", model=lm, k=1, artifact="a", role_key_questions="c")
    assert res.decision == "reject"


def test_explicit_criterion_beats_the_role_prompt():
    lm, t = _lm({"score": 0.9, "explanation": ""}, criterion="Reward politeness only.")
    judge_call("t", model=lm, k=1, artifact="a", role_key_questions="the long role prompt")
    assert t.calls[0][2]["evaluation_criteria"] == "Reward politeness only."


def test_transport_failure_declines_never_guesses():
    lm, _ = _lm(RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom"))
    res = judge_call("t", model=lm, k=3, artifact="a", role_key_questions="c")
    assert res.decision == "needs_review"
    assert res.scores_raw == []


def test_partial_failures_still_reach_a_majority():
    lm, _ = _lm(
        {"score": 0.2, "explanation": "bad"}, RuntimeError("blip"), {"score": 0.2, "explanation": "bad"}
    )
    res = judge_call("t", model=lm, k=3, artifact="a", role_key_questions="c")
    assert res.decision == "reject"
    assert res.scores_raw == [0.2, 0.2]


# ── the provider seam ─────────────────────────────────────────────────────────


def test_build_judge_lm_dispatches_composo_per_role(monkeypatch):
    pytest.importorskip("dspy")
    from lithrim_bench.runtime.council.judges_dspy import build_judge_lm

    monkeypatch.setenv("LITHRIM_LLM_PROVIDER_REVIEWER_REWARD", "composo")
    monkeypatch.setenv("LITHRIM_LLM_API_KEY_REVIEWER_REWARD", "sk-test-reward")
    lm = build_judge_lm("reviewer_reward")
    assert getattr(lm, "is_reward_lm", False) is True
    assert "sk-test-reward" not in repr(lm)


def test_builder_defaults():
    lm = build_composo_reward_lm(api_key="k")
    assert lm.threshold == 0.5
    assert lm.model == "composo-reward"
    assert lm.api_base == COMPOSO_DEFAULT_API_BASE


def test_build_trio_gives_a_reward_judge_the_sme_criterion_not_the_lens_machinery(monkeypatch):
    """REWARD-SEMANTICS-1 (measured, case09): the 2,028-char rendered prompt (base + the 10-code
    AUTHORED REFINEMENT lens block) dragged the reward score ~+0.2 vs the short SME sentence —
    the lens list is judge machinery, not a reward criterion. build_trio must hand a reward LM
    its criterion as SME TEXT: the reviewer's authored criterion field when set, else the BASE
    role prompt — never the refinement block."""
    pytest.importorskip("dspy")
    import lithrim_bench.runtime.council.judges_dspy as J

    made: dict[str, RewardModelLM] = {}

    def _fake_build(role, **kw):
        made[role] = RewardModelLM(api_key="k", transport=_Transport())
        return made[role]

    monkeypatch.setattr(J, "build_judge_lm", _fake_build)

    J.build_trio(ontology=None, assignments=None, roles=["risk_judge"],
                 criteria={"risk_judge": "Reward only safe artifacts."})
    assert made["risk_judge"].criterion == "Reward only safe artifacts."

    made.clear()
    J.build_trio(ontology=None, assignments=None, roles=["risk_judge"])
    base = J.load_role_prompt("risk_judge")
    assert made["risk_judge"].criterion == base
    assert "AUTHORED REFINEMENT" not in made["risk_judge"].criterion
