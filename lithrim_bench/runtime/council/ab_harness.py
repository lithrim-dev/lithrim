"""DSPy-council A/B harness — offline harness-logic test (WS-6c-DSPy-2).

Emits a structured diff over per-judge seam dicts: per-case composite-verdict
agreement, per-role raised-code-set agreement, per-role calibration (``None``-aware),
and each arm's :func:`judge_metric.score_judge` result on the role's
``LENS_BY_ROLE`` lens.

* **offline-structural** (``$0``, deterministic) — BOTH arms are fed FIXTURED
  per-judge seam dicts; each arm's composite verdict is computed by routing those
  dicts through the SHARED ported ``ComplianceCouncil._apply_consensus``. This
  exercises the harness's own diff + scoring logic deterministically. It is a
  **HARNESS-LOGIC test only**: because both arms share the same consensus and are
  fed hand-authored inputs, it produces **zero real prompt-vs-DSPy signal**. Never
  present offline-structural output as an "A/B result".

The original ``live`` mode — the prompt-council control arm (``ComplianceCouncil.evaluate``
→ the legacy ``build_prompt``) against the live DSPy trio — was **RETIRED in
CE-PACK-6b-CLEAN**: ``build_prompt`` is deleted (the authored DSPy stage is the single
live prompt source, OQ-1), so the prompt-vs-DSPy comparison no longer has a prompt arm.
The harness now only carries the offline-structural HARNESS-LOGIC test.

The consensus math is the ported IP, called UNCHANGED below the per-judge seam;
this harness adds nothing to it (``RECOMPOSITION_PLAN_ws6.md`` §6).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .judge_metric import LENS_BY_ROLE, raised_codes, score_judge

V2_ROLES = ("risk_judge", "policy_judge", "faithfulness_judge")

# Both arms in offline-structural mode are fed fixtured per-judge dicts and share
# the ported _apply_consensus, so the diff is over the harness's logic, not the
# two councils' behavior. Surfaced everywhere the offline result is emitted.
OFFLINE_NOTE = (
    "HARNESS-LOGIC ONLY: both arms fed fixtured per-judge dicts through the shared "
    "_apply_consensus; zero real prompt-vs-DSPy signal. Do not report as an A/B result."
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class ArmCaseResult:
    """One arm's outcome on one case: the composite verdict + each role's raised
    code-set and confidence (``None`` for a logprob-less judge, never coerced)."""

    case_id: str
    verdict: str
    per_role: dict[str, dict[str, Any]]  # role -> {"codes": set[str], "confidence": float|None}


def _arm_result_from_seams(
    case_id: str, seams: Mapping[str, dict[str, Any]], council: Any
) -> ArmCaseResult:
    """Normalize ``{role: seam_dict}`` into an :class:`ArmCaseResult`. The composite
    verdict is the ported ``_apply_consensus`` over the seam dicts (unchanged IP)."""
    consensus = council._apply_consensus(list(seams.values()))
    per_role = {
        role: {"codes": raised_codes(seam), "confidence": _get(seam, "confidence")}
        for role, seam in seams.items()
    }
    return ArmCaseResult(case_id=case_id, verdict=consensus["decision"], per_role=per_role)


def diff_case(
    prompt: ArmCaseResult, dspy: ArmCaseResult, *, roles: Iterable[str]
) -> dict[str, Any]:
    """The per-case diff record: composite-verdict agreement + per-role code-set
    agreement + per-role calibration delta (``None`` when either side is ``None``)."""
    per_role: dict[str, Any] = {}
    for role in roles:
        p = prompt.per_role.get(role, {"codes": set(), "confidence": None})
        d = dspy.per_role.get(role, {"codes": set(), "confidence": None})
        p_conf, d_conf = p["confidence"], d["confidence"]
        per_role[role] = {
            "prompt_codes": sorted(p["codes"]),
            "dspy_codes": sorted(d["codes"]),
            "codes_agree": set(p["codes"]) == set(d["codes"]),
            "prompt_conf": p_conf,
            "dspy_conf": d_conf,
            "conf_delta": (None if p_conf is None or d_conf is None else round(d_conf - p_conf, 4)),
        }
    return {
        "case_id": prompt.case_id,
        "prompt_verdict": prompt.verdict,
        "dspy_verdict": dspy.verdict,
        "verdict_agree": prompt.verdict == dspy.verdict,
        "per_role": per_role,
    }


def _calibration_deltas(per_case: list[dict[str, Any]], roles: Iterable[str]) -> dict[str, Any]:
    """Mean signed confidence delta (dspy − prompt) per role over the cases where
    BOTH arms reported a float (None-confidence cases are skipped, not zero-filled)."""
    out: dict[str, Any] = {}
    for role in roles:
        deltas = [
            r["per_role"][role]["conf_delta"]
            for r in per_case
            if r["per_role"][role]["conf_delta"] is not None
        ]
        out[role] = {
            "n_paired": len(deltas),
            "mean_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
        }
    return out


def _score_both_arms(
    cases: list[dict[str, Any]],
    arm_seams: Mapping[str, Mapping[str, Mapping[str, dict[str, Any]]]],
    *,
    roles: Iterable[str],
) -> dict[str, Any]:
    """Per-arm, per-role ``score_judge`` on the role's lens (``LENS_BY_ROLE``).

    ``arm_seams[arm][case_id][role]`` is that arm's seam dict for the role on the
    case; a missing role scores as a silent judge (no findings)."""
    per_role_score: dict[str, Any] = {}
    for arm, by_case in arm_seams.items():
        per_role_score[arm] = {}
        for role in roles:
            lens = LENS_BY_ROLE.get(role)

            def run_judge(case: Any, _arm_by_case=by_case, _role=role) -> dict[str, Any]:
                return _arm_by_case.get(case["case_id"], {}).get(_role, {"findings": []})

            per_role_score[arm][role] = score_judge(run_judge, cases, lens_codes=lens)
    return per_role_score


def run_offline_structural(
    cases: Iterable[dict[str, Any]],
    *,
    council: Any = None,
    roles: Iterable[str] = V2_ROLES,
) -> dict[str, Any]:
    """Run the deterministic harness-logic A/B over fixtured both-arm seams.

    Each case: ``{case_id, expected_safety_flags, arms: {prompt: {role: seam},
    dspy: {role: seam}}}``. Returns the full diff + per-arm per-role scores. No
    network, no dspy import. See :data:`OFFLINE_NOTE` — this is a logic test, not
    a real comparison.
    """
    from .compliance_council import ComplianceCouncil

    council = council or ComplianceCouncil()
    roles = tuple(roles)
    cases = list(cases)

    per_case: list[dict[str, Any]] = []
    arm_seams: dict[str, dict[str, dict[str, dict[str, Any]]]] = {"prompt": {}, "dspy": {}}
    for case in cases:
        cid = case["case_id"]
        arms = case["arms"]
        prompt_res = _arm_result_from_seams(cid, arms["prompt"], council)
        dspy_res = _arm_result_from_seams(cid, arms["dspy"], council)
        per_case.append(diff_case(prompt_res, dspy_res, roles=roles))
        arm_seams["prompt"][cid] = dict(arms["prompt"])
        arm_seams["dspy"][cid] = dict(arms["dspy"])

    n = len(per_case)
    agree = sum(1 for r in per_case if r["verdict_agree"])
    return {
        "mode": "offline-structural",
        "note": OFFLINE_NOTE,
        "n": n,
        "verdict_agreement_pct": round(100.0 * agree / n, 2) if n else 0.0,
        "per_case": per_case,
        "per_role_score": _score_both_arms(cases, arm_seams, roles=roles),
        "calibration": _calibration_deltas(per_case, roles),
    }


def _context_payload(case: Mapping[str, Any]) -> dict[str, Any]:
    """Build the prompt-council ``evaluate`` context from a bench case row.

    The transcript MUST be nested under ``call_context`` — that is the only place
    ``_prepare_full_analysis_payload`` reads it (``compliance_council.py:1159-1161``;
    the documented ``SMOKE_PAYLOAD`` shape, ``test_live_smoke.py:54-62``). A
    top-level ``transcript`` is silently dropped, leaving the prompt arm with an
    empty transcript + a populated artifact, which the COMPLETE FABRICATION RULE
    (``compliance_council.py:567-575``) then false-rejects on every case. Artifacts
    are read top-level (``:552``), so they stay top-level here."""
    return {
        "call_context": {"transcript": case.get("transcript", "")},
        "artifacts": case.get("artifacts") or [],
    }


def _artifact_text(case: Mapping[str, Any]) -> str:
    """Flatten a bench case's artifacts into the single string the DSPy signature's
    ``artifact`` input takes."""
    return "\n\n".join((_get(a, "content", "") or "") for a in (case.get("artifacts") or []))


# ``run_live`` (the paid prompt-council-vs-DSPy A/B) was RETIRED in CE-PACK-6b-CLEAN:
# its control arm called ``ComplianceCouncil.evaluate`` → the legacy ``build_prompt``,
# which is now deleted (the authored DSPy stage is the single live prompt source, OQ-1).
# A prompt-vs-DSPy comparison with no prompt arm is moot; ``run_offline_structural``
# (the HARNESS-LOGIC diff/scoring test) is what remains. The live DSPy grade is covered
# by ``scripts/run_eval.py --in-process`` + the CE-STANDALONE-1 live smoke.
