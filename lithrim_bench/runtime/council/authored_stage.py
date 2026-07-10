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

# REPRO-1 R1b: the structured source-record field(s) a case supplies (an account state, a
# problem list, any config-declared context object the grounding floor reasons over) that the
# authored stage renders into the judge-visible context. A council whose only context is
# transcript + artifact grades the fidelity check on incomplete input; folding the record in
# makes the record-vs-artifact behaviour reproducible. Fully data-driven: the field NAMES come
# from config (the agent's `grading_context_fields`, carried onto the payload under `record`) —
# core hardcodes NO field name, and renders whatever the case supplies.


def _render_record_section(name: str, value: Any) -> str:
    """One delimited SOURCE RECORD section (strings verbatim, scalar lists as bullets,
    anything structured as sorted JSON) — the same rendering the request-body fold uses, so a
    record is presented identically whichever path folds it. Never called for an empty value."""
    import json as _json

    if isinstance(value, str):
        body = value
    elif isinstance(value, list) and all(isinstance(x, (str, int, float)) for x in value):
        body = "\n".join(f"- {x}" for x in value)
    else:
        body = _json.dumps(value, indent=2, sort_keys=True)
    return f"--- SOURCE RECORD: {name} ---\n{body}"


def _fold_record_into_transcript(transcript: str, call_context: dict[str, Any]) -> str:
    """Append the case's structured source record (the config-named fields carried on
    ``call_context['record']``) to the transcript as delimited SOURCE RECORD sections, so EVERY
    judge votes on the record alongside the conversation. Field NAMES are config/DATA (never a
    core constant); a field that is absent/empty is skipped; no record → the transcript is
    returned byte-unchanged (the default-path parity guard). Pure; no LM. Deterministic order
    (sorted by field name) so the folded prompt is stable."""
    record = call_context.get("record")
    if not isinstance(record, dict) or not record:
        return transcript or ""
    context = transcript or ""
    for name in sorted(record):
        value = record.get(name)
        if value in (None, "", [], {}):
            continue
        # idempotent: if the declared grading_context_fields fold already rendered this record
        # into the transcript string (the same `SOURCE RECORD: <name>` header), do not double-render.
        if f"SOURCE RECORD: {name}" in context:
            continue
        context = f"{context}\n\n{_render_record_section(name, value)}"
    return context


def _fold_usage(r: dict, jr: Any) -> None:
    """LAYER0-READ-1: copy a JudgeResult's captured token spend onto its per-judge seam
    dict (where the frozen stages.py cost_tokens sum reads ``usage``). Never clobbers an
    existing ``usage`` and never fabricates one (absent/None → the dict is untouched)."""
    usage = getattr(jr, "usage", None) if jr is not None else None
    if usage and not r.get("usage"):
        r["usage"] = usage


def _fold_rationale(r: dict, jr: Any) -> None:
    """F8-RATIONALE: copy a findings-less JudgeResult's prose rationale onto its seam dict
    (where ``stages._judge_votes_from_models`` reads ``rationale`` ahead of the synthesized
    reason). A verdict-only reviewer — a reward-model judge — types no defect codes, so
    ``_synth_reason`` has nothing to reconstruct from and its vote rendered mute; the captured
    explanation is its only "why". Scoped to the findings-less case so a coded judge's
    synthesized ``decision — CODES`` reason stays byte-identical; never clobbers, never
    fabricates (no rationale / no JudgeResult → the dict is untouched)."""
    if jr is None or r.get("rationale") or (r.get("findings") or []):
        return
    rationale = str(getattr(jr, "rationale", "") or "")
    if rationale:
        r["rationale"] = rationale


def build_authored_evaluator(
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
    judge_samples: int | None = None,
    samples: dict[str, int] | None = None,
    temperatures: dict[str, float] | None = None,
    criteria: dict[str, str] | None = None,
    demos: dict[str, Sequence[Any]] | None = None,
):
    """Build the authored DSPy-trio council evaluator — the ``council_evaluate`` seam
    (``payload -> {consensus, models, evidence_summary}``) that mirrors
    ``ComplianceCouncil.evaluate``'s envelope.

    :func:`build_authored_semantic_stage` wraps this into the orchestrator
    ``semantic_stage`` contract; ``runtime/pipeline/stages.py``'s default
    ``context_kind=transcript`` path (CE-PACK-6b-CLEAN D1) calls it DIRECTLY when no
    evaluator is injected, so the default in-process transcript grade IS the authored
    path and the legacy ``ComplianceCouncil.build_prompt`` default council is never
    reached (OQ-1: the authored path is the single live prompt source).

    ``ontology`` + ``assignments`` (role → assigned flag codes) drive
    :func:`build_trio` so each judge binds its AUTHORED ``role_key_questions``. With
    ``assignments`` ``None``/empty for a role, that judge renders the seed
    ``council_roles/<role>.txt`` base (A4 parity) — i.e. an unauthored trio grades
    byte-equivalently to the default lens, so authoring is the only thing that moves
    the verdict.

    ``predictors`` (role → callable) is forwarded to :func:`build_trio` for $0
    offline determinism; omit it for the live v2 Azure trio (the paid in-process
    path). ``models`` (BYOC-1) is the per-role provider selector; ``roles`` (DOGFOOD-1)
    grades with a SMALLER roster (``None`` = the full trio, byte-identical to before;
    a single-role roster degenerates at the frozen consensus ``len(valid) >= 2`` guard).

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
    from .compliance_council import ComplianceCouncil, CouncilModel
    from .judges_dspy import build_trio
    from .withstands import apply_withstands_gate

    trio = build_trio(
        ontology=ontology,
        assignments=assignments,
        predictors=predictors,
        models=models,
        roles=roles,
        judge_samples=judge_samples,
        samples=samples,
        temperatures=temperatures,
        criteria=criteria,
        demos=demos,
    )
    # REL-OPS-1 O4: the dated-model-alias check, ONCE at bind time. ``build_judge_lm`` is
    # frozen (the O1 fingerprint-deferral precedent), so the check reads the ``llm_model``
    # VOTE-MODEL-1 stamps on each judge — here, the non-frozen construction site. Default
    # WARN + record (provenance reads the registry); refuse rides
    # LITHRIM_BENCH_REQUIRE_DATED_MODELS and raises BEFORE any grade. Offline judges
    # (``predictors=`` → llm_model None) record ``dated: None`` and never warn/refuse.
    from lithrim_bench.harness.model_policy import check_model_bindings

    check_model_bindings({j.role: getattr(j, "llm_model", None) for j in trio})
    # Capture each reviewer's build-time role prompt (incl. its global criterion) so the
    # per-CASE policy criterion can be layered on per grade and restored after — the trio is
    # shared, so we never let a per-case prompt leak into the next grade. ``getattr`` keeps
    # the fixtured/fake judges (no ``role_prompt``) working — they just can't be overridden.
    _base_prompts = {j.role: getattr(j, "role_prompt", "") for j in trio}
    # PHASE2-B: construct the council with an EXPLICIT models list (the trio's roles) so the
    # FROZEN default-council `__init__` branch (models is None → `_ROLE_DEPLOYMENT[role]` for each
    # `pack_production_judges()` entry) is SKIPPED. That branch KeyErrors on an AUTHORED judge
    # spliced into `production_judges` but absent from the core-side `_ROLE_DEPLOYMENT` trio
    # (PHASE2-A's splice creates exactly this). The authored stage runs its OWN trio and only needs
    # `_apply_consensus` (which ignores `self.models`), so a name-only `CouncilModel` per role is
    # sufficient — the frozen seam (`compliance_council.py` / `_apply_consensus`) is UNTOUCHED.
    council = council or ComplianceCouncil(
        models=[CouncilModel(name=j.role, provider="authored", model=j.role) for j in trio]
    )

    def _evaluator(payload: dict[str, Any]) -> dict[str, Any]:
        # The council context_payload carries the transcript under call_context and
        # the artifact(s) the same way _build_transcript_payload assembles them; the
        # DSPy signature takes the transcript + a single flattened artifact string
        # (the ab_harness precedent).
        call_context = payload.get("call_context") or {}
        # REPRO-1 R1b: fold the case's config-declared structured record into the transcript every
        # judge votes on, so the record-vs-artifact check sees the full input. No record on the
        # payload → byte-unchanged (the default-path parity guard).
        transcript = _fold_record_into_transcript(call_context.get("transcript", ""), call_context)
        artifact = "\n\n".join(
            (a.get("content") or "")
            for a in (payload.get("artifacts") or [])
            if isinstance(a, dict)
        )

        # Case-level Policy criterion (the criteria are case-level for Policy, not global):
        # layer the case's ``policy_criterion`` onto the policy reviewer's prompt for THIS grade
        # only, then restore in ``finally`` so the shared trio doesn't carry it forward.
        policy_criterion = str(payload.get("policy_criterion") or "").strip()
        _overridden: list[Any] = []
        if policy_criterion:
            for j in trio:
                if j.role == "policy_judge":
                    j.role_prompt = (
                        f"{_base_prompts.get(j.role, j.role_prompt)}"
                        f"\n\nEvaluation criterion: {policy_criterion}"
                    )
                    _overridden.append(j)
        try:
            results = [j.forward(transcript=transcript, artifact=artifact) for j in trio]
        finally:
            for j in _overridden:
                j.role_prompt = _base_prompts.get(j.role, j.role_prompt)

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

        # VOTE-MODEL-1: attribute each per-judge seam dict to the REAL deployment it graded on
        # (``Judge.forward`` emits only the role name under ``model``; build_trio stamped the
        # resolved model on each judge as ``llm_model``). Keyed by role so it survives the gate's
        # per-judge rewrites; the orchestrator's ``_judge_votes_from_models`` prefers it. Done
        # here (the authored evaluator) so the frozen ``Judge`` seam is untouched.
        _model_by_role = {j.role: getattr(j, "llm_model", None) for j in trio}
        for r in results:
            if isinstance(r, dict) and not r.get("llm_model"):
                r["llm_model"] = _model_by_role.get(r.get("model"))

        # Sampling-layer telemetry: attach each judge's JudgeResult distribution
        # (score_mean/variance/scores_raw/k) to its seam dict so the orchestrator folds
        # it into provenance. Keyed by role so it survives the gate's per-judge rewrites;
        # the frozen ``_apply_consensus`` ignores the extra key. Absent on the offline
        # ``predictors=`` path unless a fake predictor returns a ``JudgeResult``.
        _sampling_by_role = {
            j.role: getattr(j, "_sampling_holder", {}).get("last") for j in trio
        }
        for r in results:
            if not isinstance(r, dict):
                continue
            jr = _sampling_by_role.get(r.get("model"))
            if jr is not None and not r.get("sampling"):
                r["sampling"] = {
                    "score_mean": jr.score_mean,
                    "score_variance": jr.score_variance,
                    "scores_raw": list(jr.scores_raw),
                    "k": jr.k,
                }
            # LAYER0-READ-1: fold the sampled call's real token spend onto the seam dict —
            # the frozen stages.py cost_tokens sum reads ``usage.input_tokens/output_tokens``
            # here, which nothing populated (every persisted blob said cost 0). Absent usage
            # (offline predictors, no-usage LMs) leaves the dict byte-identical.
            _fold_usage(r, jr)
            # F8-RATIONALE: a verdict-only reviewer's prose explanation is its only "why" —
            # fold it so the vote's reason renders instead of an empty synth. Coded judges
            # are untouched (the guard is inside the helper).
            _fold_rationale(r, jr)

        # Independent-axes case outcome (the rule table) — computed ABOVE the frozen seam
        # from each reviewer's OWN verdict + variance; never an aggregate score. This, not
        # the consensus decision, is the case verdict the orchestrator maps.
        from .outcomes import derive_case_outcome

        case_outcome = derive_case_outcome(results)

        # The frozen consensus IP — still called for findings/evidence_summary (its
        # aggregated decision is no longer the case verdict). Byte-0-delta.
        consensus = council._apply_consensus(results, gate_mode=gate_mode)
        return {
            "consensus": consensus,
            "models": results,
            "evidence_summary": consensus.get("evidence_summary", {}),
            "case_outcome": case_outcome,
        }

    return _evaluator


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
    judge_samples: int | None = None,
    samples: dict[str, int] | None = None,
    temperatures: dict[str, float] | None = None,
    criteria: dict[str, str] | None = None,
    demos: dict[str, Sequence[Any]] | None = None,
):
    """Return an async semantic stage that grades via the authored DSPy trio.

    The returned callable matches the orchestrator's ``semantic_stage`` contract
    (``async (PipelineRequest) -> (StageResult, meta)``) and is passed straight to
    :func:`lithrim_bench.harness.grade.grade_inprocess` via its existing
    ``semantic_stage=`` param — no signature change downstream. It wraps
    :func:`build_authored_evaluator` (which carries the trio + THE MOAT withstands-gate
    + the frozen ``_apply_consensus`` call); every keyword is forwarded unchanged, so
    the stage behaviour is byte-identical to before the evaluator was factored out.
    """
    from ..pipeline.stages import run_semantic

    evaluator = build_authored_evaluator(
        ontology=ontology,
        assignments=assignments,
        predictors=predictors,
        council=council,
        gate_mode=gate_mode,
        apply_gate=apply_gate,
        decisions_sink=decisions_sink,
        http_client=http_client,
        models=models,
        roles=roles,
        judge_samples=judge_samples,
        samples=samples,
        temperatures=temperatures,
        criteria=criteria,
        demos=demos,
    )

    async def _stage(request):
        return await run_semantic(request, council_evaluate=evaluator)

    return _stage
