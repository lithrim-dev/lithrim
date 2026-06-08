"""The authored-lens semantic stage — thread persisted judge assignments into the
in-process grade (UAP-3 / S-BS-63).

This is the missing leg of the prompt↔ontology bridge (UAP-2). UAP-2 made
``build_trio(ontology=, assignments=)`` render each judge's ``role_key_questions``
from its authored assignment; this module turns that authored trio into a semantic
**stage** the in-process orchestrator can run, so an authored judge actually re-votes
with its authored lens when the harness grades a real case.

The seam (plan-review Decision 1 = seam (i)): build the authored trio above the
frozen consensus math, then reuse :func:`run_semantic` for the consensus→StageResult
mapping by passing a ``council_evaluate`` that fans out the trio and returns the SAME
envelope ``ComplianceCouncil.evaluate`` returns (``{consensus, models,
evidence_summary}``). So:

  * ``ComplianceCouncil._apply_consensus`` is only CALLED here, never modified — the
    A2 frozen-seam byte-0-delta holds (this module + ``run_eval`` are the only edits;
    ``compliance_council.py`` / ``judges_dspy.py`` / ``judge_metric.py`` are untouched).
  * NO orchestrator / ``stages.py`` edit — the per-judge seam dict the DSPy
    ``Judge.forward`` emits (``{model, decision, confidence, findings, errors}``) is
    byte-shape-identical to the prompt-council's ``models`` rows, so
    ``_run_council_and_map``'s ``_judge_votes_from_models`` /
    ``_findings_from_evidence_summary`` map it unchanged.

Heavy deps (``dspy`` via ``build_trio``; ``openai`` via ``ComplianceCouncil``) load
only when this module is imported — ``scripts/run_eval`` imports it lazily inside the
``--in-process`` branch, the same posture as the ``SqliteProvenanceStore`` /
``LocalPipelineBackend`` lazy imports, so the default-deps core stays import-clean.

Live ``:8002`` assignment-injection is OUT of scope (WS-2 backend, HARD-GATE-paused):
S-BS-63 closes for the in-process path only this cycle. ``predictors`` is injectable
so offline tests prove the authored→flip deterministically at $0 (no Azure call).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def build_authored_semantic_stage(
    *,
    ontology: Any,
    assignments: dict[str, Sequence[str]] | None,
    predictors: dict[str, Callable[..., Any]] | None = None,
    council: Any = None,
    gate_mode: bool = False,
    apply_gate: bool = True,
    decisions_sink: list[Any] | None = None,
    http_client: Any | None = None,
    models: dict[str, str] | None = None,
    roles: Sequence[str] | None = None,
):
    """Return an async semantic stage that grades via the authored DSPy trio.

    The returned callable matches the orchestrator's ``semantic_stage`` contract
    (``async (PipelineRequest) -> (StageResult, meta)``) and is passed straight to
    :func:`lithrim_bench.harness.grade.grade_inprocess` via its existing
    ``semantic_stage=`` param — no signature change downstream.

    ``ontology`` + ``assignments`` (role → assigned flag codes) drive
    :func:`build_trio` so each judge binds its AUTHORED ``role_key_questions``. With
    ``assignments`` ``None``/empty for a role, that judge renders the seed
    ``council_roles/<role>.txt`` base (A4 parity) — i.e. an unauthored trio grades
    byte-equivalently to the default lens, so authoring is the only thing that moves
    the verdict.

    ``predictors`` (role → callable) is forwarded to :func:`build_trio` for $0
    offline determinism; omit it for the live v2 Azure trio (the paid in-process
    path).

    ``models`` (BYOC-1) is forwarded to :func:`build_trio` as a per-role provider
    selector (e.g. ``{"risk_judge": "byo-claude"}``) so one role runs on the tool-less
    BYO-Claude LM while the rest stay Azure — the model-composition council. ``None``
    (the default) is byte-identical to before.

    ``roles`` (DOGFOOD-1 D2b) is forwarded to :func:`build_trio` to grade with a SMALLER
    roster (the judge-set-ladder rungs). ``None`` (the default) is the full trio,
    byte-identical to before. A 2- or 3-role roster grades normally; a single-role roster
    degenerates at the frozen consensus (``len(valid) >= 2`` guard) — see ``build_trio``.

    UAP-3b (THE MOAT): when ``apply_gate`` is True (default), the per-judge
    **withstands-gate** (:func:`apply_withstands_gate`) runs BETWEEN the trio results
    and the frozen ``_apply_consensus`` — it reconciles each judge's verdict against
    its deterministic signals (assigned ontology rules + validator/grounding outputs)
    and corrects a signal-contradicted finding PRE-consensus. The CORRECTED seam dicts
    feed ``_apply_consensus`` UNCHANGED (byte-0-delta). ``decisions_sink`` (if given)
    receives the :class:`WithstandsDecision`s so the caller (``run_eval``) can audit +
    emit RLVR correction records. ``apply_gate=False`` reproduces the pre-UAP-3b
    behaviour (the no-gate baseline the moat exhibit contrasts against). ``http_client``
    is injectable for the validator-output signals' executors (offline tests).
    """
    from ..pipeline.stages import run_semantic
    from .compliance_council import ComplianceCouncil
    from .judges_dspy import build_trio
    from .withstands import apply_withstands_gate

    trio = build_trio(
        ontology=ontology,
        assignments=assignments,
        predictors=predictors,
        models=models,
        roles=roles,
    )
    council = council or ComplianceCouncil()

    def _evaluator(payload: dict[str, Any]) -> dict[str, Any]:
        # The council context_payload carries the transcript under call_context and
        # the artifact(s) the same way _build_transcript_payload assembles them; the
        # DSPy signature takes the transcript + a single flattened artifact string
        # (the ab_harness precedent).
        transcript = (payload.get("call_context") or {}).get("transcript", "")
        artifact = "\n\n".join(
            (a.get("content") or "")
            for a in (payload.get("artifacts") or [])
            if isinstance(a, dict)
        )
        results = [j.forward(transcript=transcript, artifact=artifact) for j in trio]

        # THE MOAT — the per-judge, pre-consensus withstands-gate (UAP-3b D2). It
        # corrects a signal-contradicted finding ABOVE the frozen seam; the CORRECTED
        # results are what consensus sees. The case the contracts/lens reason over is
        # reassembled from the payload (transcript + artifact) the same way ``ground``
        # reads ``case``.
        if apply_gate:
            case_view = {
                "transcript": transcript,
                "artifacts": payload.get("artifacts") or [],
            }
            results, decisions = apply_withstands_gate(
                results,
                ontology=ontology,
                case=case_view,
                assignments=assignments,
                http_client=http_client,
            )
            if decisions_sink is not None:
                decisions_sink.extend(decisions)

        # The frozen consensus IP — only called. The envelope mirrors
        # ComplianceCouncil.evaluate()'s return so run_semantic's _run_council_and_map
        # maps it exactly as it maps the prompt-council.
        consensus = council._apply_consensus(results, gate_mode=gate_mode)
        return {
            "consensus": consensus,
            "models": results,
            "evidence_summary": consensus.get("evidence_summary", {}),
        }

    async def _stage(request):
        return await run_semantic(request, council_evaluate=_evaluator)

    return _stage
