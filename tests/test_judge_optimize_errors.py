"""A judge call that raises during the held-out evaluation is an ERROR vote, not an abort.

Observed 2026-09-09: an Azure content-filter refusal on one RAGTruth news source killed a whole
``run_optimize`` before the baseline score existed. The refused case must score as a vote that
raised nothing (a miss on a positive, never a credited pass) and be counted under ``errors``."""

from __future__ import annotations

from lithrim_bench.runtime.council import judge_optimize as jo

ROLE = "risk_judge"
IN_LENS = sorted(jo.LENS_BY_ROLE[ROLE])[0]


def _case(cid: str, flags: list[str]) -> dict:
    return {
        "case_id": cid,
        "transcript": "source",
        "artifacts": [{"type": "generated_response", "content": f"response {cid}"}],
        "expected_safety_flags": flags,
    }


class _Program:
    """Raises on the case whose artifact names it; otherwise raises the in-lens code iff gold."""

    def __init__(self, refuse: str):
        self.refuse = refuse

    def __call__(self, *, transcript, artifact, role_key_questions, taxonomy_context):
        if self.refuse in artifact:
            raise RuntimeError("ContentPolicyViolationError: filtered")
        raised = [{"taxonomy_code": IN_LENS}] if artifact.endswith("pos") else []
        return {"decision": "reject" if raised else "approve", "findings": raised, "reason": "x"}


def test_a_refused_case_is_an_error_vote_never_a_pass():
    cases = [_case("pos", [IN_LENS]), _case("neg", []), _case("refused-pos", [IN_LENS])]
    res = jo.evaluate_program(
        _Program(refuse="refused-pos"), cases, role=ROLE, role_prompt="p", taxonomy_context="t"
    )
    assert res["errors"] == 1
    assert res["error_cases"][0]["case_id"] == "refused-pos"
    assert "filtered" in res["error_cases"][0]["error"]
    # the refused positive is a MISS: recall < 1 and the run is not "accepted"
    assert res["recall"] < 1.0 and res["accepted"] is False
    # the two readable cases were judged normally
    assert res["precision"] == 1.0


def test_no_errors_leaves_the_score_dict_untouched_but_counted():
    cases = [_case("pos", [IN_LENS]), _case("neg", [])]
    res = jo.evaluate_program(
        _Program(refuse="never"), cases, role=ROLE, role_prompt="p", taxonomy_context="t"
    )
    assert res["errors"] == 0 and res["error_cases"] == []
    assert res["accepted"] is True and res["recall"] == 1.0
