#!/usr/bin/env python
"""Config-driven eval runner — the canonical WS-1 entrypoint.

    load_agent(name) -> grade(replay|live) -> ground(ontology) -> composite + calibration

Everything comes from the SQLite config plane (the Agent eval-profile) + the
ontology: the case, the source/baseline, the contracts, the severity map, the
council disposition. There are NO hardcoded ``--case/--baseline/contracts`` args —
that is the whole point of WS-1 (acceptance A1). ``scripts/run_ws0.py`` is a thin
compat shim that builds an ephemeral Agent from CLI args and delegates to the
:func:`run` core here, so there is exactly ONE grounding path.

Defaults run the captured-baseline REPLAY path (zero new paid calls). ``--live``
opts into a real, paid ``:8002 /v1/pipeline/evaluate`` call and is OFF by default.

    python scripts/run_eval.py                       # agent 'ws0_default', replay
    python scripts/run_eval.py --agent ws0_default
    python scripts/run_eval.py --live                # paid; opt-in only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target  # noqa: E402
from lithrim_bench.harness.config import (  # noqa: E402
    DEFAULT_CONFIG_DB,
    Agent,
    load_agent,
    seed_config_db,
)
from lithrim_bench.harness.correction import (  # noqa: E402
    build_correction,
    build_floor_correction,
    build_withstands_correction,
    emit,
)
from lithrim_bench.harness.grade import grade_inprocess, grade_live, grade_replay  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.grounding_check import audit_grounding_checks  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.persist import persist  # noqa: E402
from lithrim_bench.harness.replay import (  # noqa: E402
    demo_digests,
    grade_signature,
    is_fresh,
    provenance_to_result,
)
from lithrim_bench.harness.report import calibration, composite  # noqa: E402
from lithrim_bench.picklist import (  # noqa: E402
    expected_block,
    load_case,
    normalize_expected_verdict,
)


def _suppressed_entry(s) -> dict:
    entry = {
        "code": s["finding"].get("code"),
        "contract": s["contract"].version,
        "disproved": s["verdict"].disproved,
        "matched_token": s["verdict"].matched_token,
        "evidence": s["verdict"].evidence,
        "reason": s["verdict"].reason,
    }
    edition = getattr(s["verdict"], "terminology_edition", None)
    if edition is not None:
        # REL-OPS-1 O2: the terminology edition that decided this suppression — absent
        # (not null) for non-terminology contracts, so existing blob shapes are unchanged.
        entry["terminology_edition"] = edition
    return entry


def _grounded_block(grounded) -> dict:
    """Serialize a ``ground()`` result to the record/blob shape. LAYER0-READ-1: extracted
    from ``build_record`` so the SAME serialization rides both the API record AND the
    persisted PipelineProvenance blob (``_enrich_run_blob``) — one shape, no read-side drift."""
    return {
        "verdict": grounded.verdict,
        # READ-ATTRIB-1: the floor counterfactual rides the SAME serialization, so the pre/post
        # band can attribute its delta without re-deriving anything read-side.
        "verdict_no_floor": grounded.verdict_no_floor,
        "original_verdict": grounded.original_verdict,
        "active": grounded.active,
        "suppressed": [_suppressed_entry(s) for s in grounded.suppressed],
        "ungrounded": grounded.ungrounded,
        "skipped_non_gradeable": grounded.skipped_non_gradeable,
        "floor_blocks": [
            {
                "flag": (b["injected_finding"] or {}).get("code")
                or b["decl"].params.get("inject_flag_code"),
                "contract_type": b["decl"].contract_type,
                "contract": b["decl"].version,
                "conforms": b["result"].conforms,
                "disposition": b["result"].disposition,
                "injected": b["injected_finding"] is not None,
                "evidence": b["result"].evidence,
                "manifest": b["result"].manifest,
            }
            for b in grounded.floor_blocks
        ],
    }


def build_record(case, result, grounded, comp, cal, corrections, *, grade_path, agent):
    return {
        "case_id": case.get("case_id"),
        "agent": agent.name,
        "result": result,
        "grounded": _grounded_block(grounded),
        "composite": comp,
        "calibration": cal,
        "corrections": corrections,
        "provenance": {
            "ontology_ref": agent.eval_profile.ontology_ref,
            "council_config": agent.eval_profile.council_config,
            "expected_compliance_verdict": case.get("expected_compliance_verdict"),
            "expected_safety_flags": case.get("expected_safety_flags"),
            "grade_path": grade_path,
        },
    }


def _run_sync(coro):
    """Run an async ProvenanceStore call to completion from EITHER a sync (CLI ``run_eval``)
    or an async (the BFF / journey tool handlers run inside ``asyncio.run``) context.
    ``asyncio.run`` raises inside a running loop, so when one is running we complete the
    coroutine in a worker thread — the persist must finish before run-history reads it (the
    side-effect can't be silently dropped, which is exactly the PERSIST-2c-2 regression this
    fixes). PERSIST-2c-2."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _persist_run_provenance(
    result: dict,
    agent: Agent,
    *,
    grade_sig: str | None = None,
    grade_path: str | None = None,
    collections_db: str | Path | None = None,
) -> None:
    """Persist a replay/live run's PipelineProvenance blob to ``PIPELINE_RUNS`` so the
    run is auditable + listed in run-history (S-BS-52). ``agent_id`` is backfilled from
    the eval-profile (the captured baseline carries no agent_id). No-op when the result
    carries no ``pipeline_run_id``. Idempotent on ``pipeline_run_id`` (the doc-shim
    upserts): deterministic replay reuses the baseline's fixed id, so re-running replay
    upserts ONE row per baseline rather than one-per-invocation — by design, not a bug.

    PERSIST-2a: also stamps ``case_id`` (addressable by ``(agent, case_id)``) and the
    ``grade_signature`` (freshness), so the replay/live head is resolvable by
    replay-from-provenance — exactly how ``agent_id`` already rides (an extra doc field,
    NOT a ``PipelineProvenance`` model edit, NOT a projection column)."""
    prov = (result or {}).get("provenance") or {}
    if not prov.get("pipeline_run_id"):
        return
    doc = dict(prov)
    doc.setdefault("agent_id", agent.name)
    doc["case_id"] = agent.dataset.case_id
    if grade_sig is not None:
        doc["grade_signature"] = grade_sig
    # RUNTRAIL-7: stamp HOW this verdict was produced onto the persisted blob (live/replay
    # persist HERE; in_process stamps in ``_enrich_run_blob``). SPEC §3 Identity.
    if grade_path is not None:
        doc["grade_path"] = grade_path
    # PERSIST-2c-2: route through the factory (LITHRIM_DB_URL → PG, else SQLite at
    # collections_db — byte-identical to the prior PIPELINE_RUNS.insert default).
    from lithrim_bench.harness.backend import provenance_store_for

    _run_sync(provenance_store_for(collections_db).save_blob(doc))


def _resolve_from_provenance(
    agent: Agent, grade_sig: str, *, collections_db: str | Path | None = None
) -> dict:
    """PERSIST-2a replay-from-provenance: resolve the persisted HEAD for ``(agent, case_id)``
    as the $0 replay baseline (the blob the prior authorized grade wrote IS the baseline).

    Raises ``SystemExit`` (the BFF maps it -> 400) when the store has no head, or when the
    head is STALE under the drift-aware freshness guard — the config changed since it was
    graded, so serving the cached verdict would be a manufactured consistency (re-grade to
    see the new verdict). Pure read above the frozen seam."""
    from lithrim_bench.harness.backend import provenance_store_for

    store = provenance_store_for(collections_db)  # PERSIST-2c: LITHRIM_DB_URL → PG, else SQLite
    # SIGNATURE-1 (caught live): the baseline must be the newest AUTHORITATIVE grade —
    # latest_for returns ANY newest row, and a replay row (stamped with the CURRENT signature
    # at persist) masqueraded as a fresh head after a criterion edit. Never replay a replay.
    head = _run_sync(store.latest_authoritative_for(agent.name, agent.dataset.case_id))
    if head is None:
        raise SystemExit(
            f"agent {agent.name!r} has no captured baseline — $0 replay is unavailable "
            f"for imported/live-only cases; run it live or in_process instead."
        )
    if not is_fresh(head, grade_sig):
        raise SystemExit(
            f"agent {agent.name!r}: the config changed since case {agent.dataset.case_id!r} "
            f"was last graded — re-grade (run it live or in_process) to see the new verdict."
        )
    return provenance_to_result(head)


def _restamp_replay_identity(
    result: dict, agent: Agent, *, collections_db: str | Path | None = None
) -> dict:
    """RUNTRAIL-1: give a replayed result a FRESH identity that POINTS AT its baseline, so the
    re-grade APPENDS a new audit row instead of overwriting one (SPEC_RUN_AUDIT_TRAIL.md §1).

    Mints a fresh ``pipeline_run_id`` (mirroring the live/in_process ``uuid4`` mint at
    ``orchestrator.py``) and resolves ``replay_of`` to the most-recent AUTHORITATIVE
    (``replay_of``-falsy) grade for ``(agent, case)`` — driver §4: every replay points at the
    real grade, never chaining replay→replay. The baseline's own bytes are untouched
    (``provenance_to_result`` copies the blob). ``replay_of`` is ``None`` when no
    authoritative grade has been persisted yet (e.g. the first committed-baseline replay into
    an empty store). Pure plumbing above the frozen seam; no council/consensus touch."""
    blob = (result or {}).get("provenance") or {}
    from lithrim_bench.harness.backend import provenance_store_for

    store = provenance_store_for(collections_db)
    baseline = _run_sync(store.latest_authoritative_for(agent.name, agent.dataset.case_id))
    replay_of = (baseline or {}).get("pipeline_run_id") if baseline else None
    return provenance_to_result(blob, pipeline_run_id=str(uuid.uuid4()), replay_of=replay_of)


def _enrich_run_blob(
    run_id: str | None,
    withstands_sink: list[Any],
    *,
    in_process: bool,
    case_id: str,
    agent_id: str,
    grade_sig: str,
    grade_path: str | None = None,
    collections_db: str | Path | None = None,
    grounded_block: dict | None = None,
    grade_config: dict | None = None,
) -> None:
    """UAP-3b-2 / S-BS-72: embed the per-judge withstands ruling into the run-PROVENANCE
    blob (stream-2, ``GET /v1/runs/{id}/audit``) — not just the ``AuditLog``/config_audit
    stream-1 emitted above — AND (PERSIST-2a) stamp the blob's ``(agent, case_id)``
    addressability + freshness ``grade_signature``.

    LAYER0-READ-1: also folds ``grounded_block`` (the ``_grounded_block`` serialization —
    post-floor verdict/active/suppressed/floor_blocks) into the blob, and now runs for
    EVERY persisted path (replay/live persist pre-ground via ``_persist_run_provenance``,
    so this post-ground patch is the only point the read surface can learn what the floor
    decided — the hole behind the 2026-07-01 "floor dormant" mis-diagnosis). Additive doc
    field via the same get→patch→save seam; identity re-stamps on replay/live are
    same-value no-ops.

    The in_process orchestrator already saved the ``PipelineProvenance`` blob
    fire-and-forget (``grade.py`` → ``SqliteProvenanceStore.save``), and ``run_eval`` has
    no pre-save handle (``grade.py``). So we patch it POST-save: ``get(run_id)`` →
    patch (``withstands_decisions`` + ``agent_id``/``case_id``/``grade_signature``) →
    re-``insert``. This lives entirely ABOVE the frozen consensus — no ``_apply_consensus``
    edit, no ``PipelineProvenance``-model edit — and the returned ``result`` dict is
    untouched (the byte-identical A6 contract).

    PERSIST-2a: this same-id re-insert now exercises the versioned copy-on-write — the
    orchestrator's bare blob = v1 (archived into ``pipeline_runs_history``), the enriched
    blob = the head, addressable + freshness-signed for replay-from-provenance. The S-BS-68
    re-stamp concern the prior note flagged is RESOLVED here: ``versioned`` insert preserves
    the live row's first-write ``created_at``.

    Runs for any in_process grade (to stamp addressability) even when ``withstands_sink`` is
    empty (the gate only populates it on the authored trio); the withstands patch is guarded
    so an empty sink leaves that field absent."""
    if not run_id:
        return
    # PERSIST-2c-2: get→patch→save through the factory (LITHRIM_DB_URL → PG, else SQLite at
    # collections_db), so the in_process head's addressability stamps reach the SAME backend
    # the orchestrator saved to (else, under PG, this would read an empty SQLite + no-op).
    from lithrim_bench.harness.backend import provenance_store_for

    store = provenance_store_for(collections_db)
    blob = _run_sync(store.find_by_id(run_id))
    if blob is None:
        return
    if withstands_sink:
        blob["withstands_decisions"] = [
            {"role": d.role, **d.to_audit_why()} for d in withstands_sink
        ]
    blob.setdefault("agent_id", agent_id)
    blob["case_id"] = case_id
    blob["grade_signature"] = grade_sig
    # RUNTRAIL-7: stamp grade_path on the in_process head via this existing post-save patch —
    # pure plumbing ABOVE the frozen seam (the orchestrator's PipelineProvenance build /
    # _apply_consensus is untouched). SPEC §3 Identity.
    if grade_path is not None:
        blob["grade_path"] = grade_path
    # LAYER0-READ-1: fold the post-floor grounded block into the blob — the read surface's
    # single source for what the floor decided (suppressions + grounded verdict + evidence).
    if grounded_block is not None:
        blob["grounded"] = grounded_block
    # SIGNATURE-1: the grade-determining inputs (models/criteria/k/temp/demo digests) ride the
    # head beside the opaque hash — the record is self-describing, not correlate-by-timestamp.
    if grade_config is not None:
        blob["grade_config"] = grade_config
    _run_sync(store.save_blob(blob))


def run(
    agent: Agent,
    *,
    live: bool = False,
    in_process: bool = False,
    out_dir: str | Path | None = None,
    ontology_path: str | Path | None = None,
    assignments: dict[str, Any] | None = None,
    models: dict[str, str] | None = None,
    roles: Sequence[str] | None = None,
    samples: dict[str, int] | None = None,
    temperatures: dict[str, float] | None = None,
    criteria: dict[str, str] | None = None,
    collections_db: str | Path | None = None,
) -> dict:
    """Drive one case end-to-end from an Agent eval-profile. Returns the record.

    ``ontology_path`` (UAP-1 R3 / S-BS-26b): ``None`` → the agent's committed seed
    (``agent.ontology_abspath()``, byte-identical to before — A5 back-compat); set →
    that path (a PUT-ed working-copy draft), so an authored flag/threshold actually
    grades ("edit the flag → see it grade"). One resolved ``ontology_src`` feeds BOTH
    committed-seed reads below — the grounding load and the live-inject payload — so
    they can never diverge.

    ``assignments`` (UAP-3 R4 / S-BS-63): role → assigned flag codes, the persisted
    judge authoring (``harness.judges.load_judge``). The ``in_process`` council is
    ALWAYS the AUTHORED DSPy trio (``build_authored_semantic_stage``) — the single live
    prompt source (CE-PACK-6b-ROUTE / OQ-1). When ``assignments`` is set the judges
    grade with that explicit lens; ``None``/absent defaults each judge to its FULL pack
    lens (``pack_lenses()[role]`` over ``pack_production_judges()``), NOT a legacy
    clinical default council (``ComplianceCouncil.build_prompt`` was deleted in 6b-CLEAN).
    Ignored on the replay path (no live council) and on the live ``:8002`` path
    (per-judge assignment-injection is WS-2-backend-gated, HARD-GATE-paused).

    ``models`` (BYOC-1): role → provider/model selector (e.g.
    ``{"risk_judge": "byo-claude"}``), the persisted judge ``model`` binding. Threaded
    into the authored in_process trio (``build_authored_semantic_stage`` →
    ``build_trio(models=)``) so a role can run on the tool-less BYO-Claude LM while the
    rest stay Azure — the model-composition council. ``None``/absent → all-Azure over
    the full-lens-default authored trio. Like ``assignments``, ignored on replay/live.

    ``roles`` (DOGFOOD-1 D2b): an ordered subset of ``V2_ROLES`` selecting a SMALLER
    roster for the judge-set ladder. Threaded into the authored in_process trio
    (``build_authored_semantic_stage`` → ``build_trio(roles=)``). ``None``/absent → the
    full trio. A single-role roster degenerates at the frozen consensus
    (``len(valid) >= 2``); use 2 or 3. Ignored on replay/live.

    ``collections_db`` (UAP-3 R6 / S-BS-52): the doc-shim DB run-provenance persists
    to. ``None`` → ``DEFAULT_COLLECTIONS_DB`` (back-compat). The BFF threads its
    ``get_collections_db`` here so the persisted run lands in the SAME DB
    ``GET /v1/runs`` + ``GET /v1/runs/{id}/audit`` read from."""
    ontology_src = Path(ontology_path) if ontology_path is not None else agent.ontology_abspath()
    ontology = load_ontology(ontology_src)
    case = load_case(agent.dataset.case_id, source=agent.source_abspath())
    if case is None:
        raise SystemExit(
            f"ERROR: case {agent.dataset.case_id!r} not found in {agent.dataset.source}"
        )

    # PERSIST-2a: the grade signature — a stable hash of the grade-DETERMINING config
    # (ontology + the AUTHORED, pre-default ``assignments``/``models`` + ``council_config``).
    # Computed HERE, before the in_process branch fills the full-lens assignments default, so
    # grade-time and replay-resolve-time hash the same authored inputs (the full-lens default
    # is ontology-derived, already in the hash). Stamped on the persisted head; recomputed at
    # replay-resolve for the drift-aware freshness guard.
    ontology_doc = json.loads(ontology_src.read_text())
    # SIGNATURE-1: criterion/k/temperature + the pinned DEMO-PIN-1 demos grade-affect, so they
    # are IN the hash (else an edited criterion replays the pre-edit verdict labeled fresh).
    _demo_sig = demo_digests(out_dir)
    grade_sig = grade_signature(
        ontology_doc,
        assignments=assignments,
        models=models,
        council_config=agent.eval_profile.council_config or {},
        criteria=criteria,
        samples=samples,
        temperatures=temperatures,
        demo_digests=_demo_sig,
    )
    # SIGNATURE-1: the head is SELF-DESCRIBING about its inputs — pinned into the blob by
    # _enrich_run_blob, beside the opaque hash.
    grade_config = {
        "models": models or {},
        "criteria": criteria or {},
        "samples": samples or {},
        "temperatures": temperatures or {},
        "demo_digests": _demo_sig,
    }

    # UAP-3b: the authored stage's withstands-gate appends its per-judge decisions
    # here; empty on the replay/live paths (the gate runs only on the authored
    # in_process trio).
    withstands_sink: list[Any] = []

    if in_process:
        # WS-6c-AGENTIC grade-wire: score the case through the in-process v2 council
        # (no :8002, no Celery) — the first time the council scores real cases
        # through the harness. PAID: the v2 Azure trio makes real calls. Returns the
        # same PipelineResult dict shape as grade_live/replay (the frozen seam), so
        # ground/composite below are unchanged.
        #
        # WS-6d: the in-process grade path opts in to real SQLite provenance (no
        # Mongo). The store is lazily imported so the default-deps replay/live paths
        # above stay import-light; persistence is fire-and-forget behind ``save``, so
        # the record built below is byte-identical with the store on or off (A3).
        from lithrim_bench.harness.backend import provenance_store_for

        sys.stderr.write(
            "WARNING: --in-process runs the in-process v2 council (real paid Azure calls).\n"
        )
        # UAP-3 / S-BS-63: the in-process council is ALWAYS built as the AUTHORED DSPy
        # trio so the council votes with the ontology + role-prompt (authored) lens —
        # the single live source of prompt truth the UI edits (CE-PACK-6b-ROUTE / OQ-1,
        # `generic-ce-demarcation`). When the agent carries explicit per-role assignments
        # those drive the lens; absent any (no assignments/models/roles) each judge
        # defaults to its FULL pack lens (`pack_lenses()[role]` over the production
        # roster), so every judge grades at its full authored scope rather than falling
        # back to a legacy clinical default council. So `semantic_stage` is NEVER None on
        # this path: `ComplianceCouncil.build_prompt` was DELETED in 6b-CLEAN (the authored
        # DSPy stage is the single live prompt source). Lazy import (heavy deps) — the
        # default-deps replay/live paths above never reach it.
        from lithrim_bench.harness.pack import pack_lenses, pack_production_judges
        from lithrim_bench.runtime.council.authored_stage import (
            build_authored_semantic_stage,
        )

        if not (assignments or models or roles):
            # The full-lens default: every production judge grades at its full pack scope
            # (the codes it may raise), the behaviour-honest "no explicit authoring yet"
            # state — NOT the deleted build_prompt's full-taxonomy dump.
            lenses = pack_lenses()
            assignments = {
                role: sorted(lenses[role]) for role in pack_production_judges() if role in lenses
            }

        # DEMO-PIN-1 (S-BS-48): if this workspace optimized a judge, its compiled few-shot demos
        # (``compiled_demos_*_<role>.json`` under out_dir) are pinned into that judge's predict so
        # the grade USES them. Absent → None (demo-less, byte-identical to the pre-pin grade).
        demos: dict[str, Any] | None = None
        if out_dir is not None:
            from lithrim_bench.runtime.council.judge_optimize import load_compiled_demos

            roster = list(roles) if roles else list(pack_production_judges())
            loaded = {}
            for _role in roster:
                _role_demos = load_compiled_demos(out_dir, _role)
                if _role_demos:
                    loaded[_role] = _role_demos
            demos = loaded or None

        # UAP-3b: the authored trio grades THROUGH the pre-consensus withstands-gate
        # (apply_gate default True); the gate's per-judge decisions land in
        # ``withstands_sink`` so they can be audited + emit RLVR correction records
        # after grade (below). BYOC-1: ``models`` selects a per-role provider (the
        # mixed council).
        # REVIEWER-MODE: a single-reviewer roster (``len(roles) == 1``) runs the moat's
        # single-judge consensus path (``_apply_consensus(gate_mode=True)`` relaxes the
        # quorum to 1) so that lone reviewer's findings populate; the case verdict itself
        # comes from ``derive_case_outcome`` either way. Panel (roles None / len > 1) → False.
        gate_mode = bool(roles) and len(roles) == 1
        semantic_stage = build_authored_semantic_stage(
            ontology=ontology,
            assignments=assignments,
            models=models,
            roles=roles,
            gate_mode=gate_mode,
            samples=samples,
            temperatures=temperatures,
            criteria=criteria,
            demos=demos,
            decisions_sink=withstands_sink,
        )
        result = grade_inprocess(
            case,
            semantic_stage=semantic_stage,
            # PERSIST-2c: LITHRIM_DB_URL → the managed Postgres tier, else the local SQLite
            # path (byte-identical to before). Pointing the grade at PG is one env var.
            provenance_store=provenance_store_for(collections_db),
            # REPRO-1 R1b: the ontology's grading_context_fields (user-authored DATA) fold the
            # declared case fields into the judge-visible context — the record reaches the judge.
            # The live path reads the same declaration inside build_request_body.
            context_fields=tuple(ontology_doc.get("grading_context_fields") or ()),
        )
        grade_path = "in_process"
    elif live:
        sys.stderr.write("WARNING: --live makes a real paid council call.\n")
        # WS-2: inject the Agent's stored council_config + ontology so the live
        # council is driven by config, not backend code. The ontology is sent as
        # its committed JSON dict (the faithful "stored ontology"); council_config
        # is the S-BS-6 disposition from the eval-profile. Both are additive —
        # absent => exactly the WS-0/WS-1 body.
        council_config = agent.eval_profile.council_config or None
        result = grade_live(case, council_config=council_config, ontology=ontology_doc)
        grade_path = "live"
    else:
        if agent.dataset.baseline is None:
            # PERSIST-2a: no committed baseline fixture, but the persisted head IS the
            # baseline — resolve replay-from-provenance ($0). The drift-aware freshness guard
            # refuses a stale head (config changed since it was graded); only when the store
            # has nothing do we raise the honest "run it live/in_process" error (the BFF maps
            # SystemExit -> 400, not Path(None) -> 500 / S-BS-108).
            result = _resolve_from_provenance(agent, grade_sig, collections_db=collections_db)
        else:
            result = grade_replay(case, agent.baseline_abspath())
        # RUNTRAIL-1: replay is APPEND-WITH-LINEAGE, not idempotent-overwrite. Mint a FRESH
        # pipeline_run_id for THIS execution and stamp replay_of = the most-recent
        # AUTHORITATIVE grade for (agent, case) (driver §4: point at the real grade, never
        # chain replay→replay). The baseline row is left byte-unchanged; this re-grade
        # APPENDS a new audit row (SPEC §1: the trail grows per execution). Single identity
        # site is provenance_to_result.
        result = _restamp_replay_identity(result, agent, collections_db=collections_db)
        grade_path = "replay"

    # S-BS-52: replay + live runs persist their provenance blob too, so every run is
    # auditable + appears in run-history — not just in_process. The captured baseline
    # (replay) / the :8002 response (live) each carry a full PipelineProvenance under
    # ``result["provenance"]`` (pipeline_run_id/verdict/stage_results/...), the exact
    # doc shape ``/v1/runs/{id}/audit`` reads. in_process already persisted via the
    # orchestrator's SqliteProvenanceStore save seam, so skip it here (no double write).
    # RUNTRAIL-1: a replay is now a FRESH-id record (append-with-lineage, restamped above),
    # so it persists as a NEW history row exactly like a live run — even the
    # replay-from-provenance path (no longer a no-op skip; it appends a distinct replay
    # record that points at its authoritative baseline, never overwriting it).
    if grade_path != "in_process":
        _persist_run_provenance(
            result,
            agent,
            grade_sig=grade_sig,
            grade_path=grade_path,
            collections_db=collections_db,
        )

    grounded = ground(result, case, ontology=ontology)
    comp = composite(grounded)
    # HONEST-1 (W2): an unlabeled case carries no expected verdict -> suppress per-case ECE
    # in the blob too, so the stored record never fabricates a calibration number.
    _labeled = bool(normalize_expected_verdict(case.get("expected_compliance_verdict")))
    cal = calibration(result, expected_block=expected_block(case), labeled=_labeled)

    corrections = []
    for entry in grounded.suppressed:
        rec = build_correction(
            suppressed_entry=entry,
            result=result,
            composite_before=grounded.original_verdict or comp["stage_verdict"],
            composite_after=grounded.verdict,
            ontology=ontology,
        )
        emit(rec)
        corrections.append(rec)
    # WS-3 structural-floor flips emit the inverse correction (council missed it).
    for block in grounded.floor_blocks:
        if block["injected_finding"] is None:
            continue  # inconclusive floor: surfaced in composite, no flip => no correction
        rec = build_floor_correction(
            floor_block=block,
            result=result,
            composite_before=grounded.original_verdict or comp["stage_verdict"],
            composite_after=grounded.verdict,
            ontology=ontology,
        )
        emit(rec)
        corrections.append(rec)

    # UAP-3b: audit each pre-consensus withstands-decision (§2B critique ruling) and
    # emit an RLVR correction record for every CORRECTION (the gate flipped a judge's
    # contribution). A "withstand" admits the judge unchanged (action withstand); a
    # "corrected" decision flipped it (action flip). The AuditRecord lands in the
    # immutable config_audit substrate (the universal §2B record carries run_id /
    # case_id / actor.type=critique). UAP-3b-2 / S-BS-72: the same ruling is ALSO
    # embedded into the run-PROVENANCE blob below (``_enrich_run_blob``), so
    # ``GET /v1/runs/{id}/audit`` (stream-2) carries it, not just ``/v1/audit`` (stream-1).
    run_id = (result.get("provenance") or {}).get("pipeline_run_id")
    case_id = case.get("case_id") or agent.dataset.case_id
    audit_log = AuditLog()
    for d in withstands_sink:
        audit_log.record(
            AuditRecord(
                actor=Actor(type="critique", id="withstands_gate"),
                action="withstand" if d.decision == "withstand" else "flip",
                target=Target(type="verdict", id=str(case_id)),
                why=d.to_audit_why(),
                run_id=run_id,
                case_id=case_id,
            )
        )
        if d.decision == "corrected":
            wrec = build_withstands_correction(
                role=d.role,
                what_failed=d.what_failed,
                decision_before=d.decision_before,
                decision_after=d.decision_after,
                result=result,
                composite_before=d.decision_before,
                composite_after=comp["verdict"],
                ontology=ontology,
            )
            emit(wrec)
            corrections.append(wrec)

    _enrich_run_blob(
        run_id,
        withstands_sink,
        in_process=in_process,
        case_id=agent.dataset.case_id,
        agent_id=agent.name,
        grade_sig=grade_sig,
        grade_path=grade_path,
        collections_db=collections_db,
        # LAYER0-READ-1: the post-floor truth rides the persisted blob for EVERY path.
        grounded_block=_grounded_block(grounded),
        # SIGNATURE-1: the self-describing grade inputs, beside the opaque hash.
        grade_config=grade_config,
    )

    # UAP-3b-2 (the deferred UAP-3b A6): the post-consensus GroundingChecks declared in
    # the eval-profile run as first-class INDEPENDENT entities (§2A / §13 locus=BOTH),
    # each execution audited under actor.type=grounding_check (action run/suppress/
    # floor_block — distinct from the gate's withstand/flip). This is a projection over
    # ``grounded`` — it does NOT re-run or alter ``ground()`` (the verdict + partitions
    # are byte-identical); an undeclared profile (every committed agent) emits nothing.
    for gc_rec in audit_grounding_checks(
        agent.eval_profile.grounding_checks, grounded, run_id=run_id, case_id=case_id
    ):
        audit_log.record(gc_rec)

    out_dir = out_dir or (REPO_ROOT / "out" / "ws0")
    record = build_record(
        case, result, grounded, comp, cal, corrections, grade_path=grade_path, agent=agent
    )
    paths = persist(agent.dataset.case_id, record, out_dir=out_dir)
    record["_persisted"] = paths
    return record


def _print(agent: Agent, record: dict, *, live: bool = False) -> None:
    comp = record["composite"]
    cal = record["calibration"]
    g = record["grounded"]
    grade_path = record.get("provenance", {}).get("grade_path", "live" if live else "replay")
    print(f"=== config-driven eval ({grade_path}) — agent '{agent.name}' ===")
    print(f"case: {record['case_id']} | ontology: {agent.eval_profile.ontology_ref}")
    print(
        f"verdict: {comp['verdict']} (stage {comp['stage_verdict']}, was {g['original_verdict']})"
    )
    print(f"composite score: {comp['score']}")
    print(f"active findings: {comp['active_findings']}")
    print(f"ungrounded (null-code, skip-logged): {comp['ungrounded_count']}")
    print(f"reference (out-of-snapshot, skip-logged): {comp['skipped_non_gradeable_count']}")
    print("--- grounded corrections (S-BS-7) ---")
    if not record["corrections"]:
        print("  (none)")
    for rec in record["corrections"]:
        print(
            f"  {rec['original_label']} -> SUPPRESSED via {rec['contract_version']}: "
            f"{rec['tool_result']['reason']}"
        )
    print("--- calibration (REPORT-ONLY, not a gate) ---")
    print(f"  ECE: {cal['ece']} over {cal['n_with_confidence']} non-null confidence(s)")
    if cal["caveat"]:
        print(f"  caveat: {cal['caveat']}")
    print(f"persisted: {record['_persisted']['blob']} | {record['_persisted']['sqlite']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="config-driven eval runner")
    parser.add_argument("--agent", default="ws0_default")
    parser.add_argument(
        "--case-id",
        default=None,
        help="grade a SPECIFIC case (e.g. an ingested-corpus case) instead of the agent's "
        "dataset.case_id; resolved via load_case's source→PACK_FILES→workspace-corpus fallback",
    )
    parser.add_argument("--config-db", default=str(DEFAULT_CONFIG_DB))
    parser.add_argument(
        "--live",
        action="store_true",
        help="opt into a real, PAID :8002 call (default: replay the baseline)",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="opt into the in-process v2 council (PAID Azure trio; no :8002/Celery)",
    )
    parser.add_argument("--out-dir", default=None)
    parser.add_argument(
        "--ontology-path",
        default=None,
        help="resolved ontology path (BFF draft→grade); None → the agent's committed seed",
    )
    parser.add_argument(
        "--collections-db",
        default=None,
        help="run-provenance doc-shim DB (workspace-scoped); None → the default",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="print the eval record as a __GRADE_JSON__-prefixed line (the BFF subprocess "
        "grade contract: PACK-WS runs the grade in a subprocess bound to the workspace's "
        "LITHRIM_BENCH_PACK, since the frozen council binds its pack at import)",
    )
    args = parser.parse_args()

    db_path = Path(args.config_db)
    # Build the config DB from the committed agent seeds if it does not exist yet
    # (gitignored-built; source-of-truth is data/config/agents/*.json).
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    agent = load_agent(args.agent, db_path=db_path)
    if args.case_id:  # NARR-LOOP: grade a specific corpus case (the BFF subprocess override)
        from dataclasses import replace

        agent = replace(agent, dataset=replace(agent.dataset, case_id=args.case_id))

    # S-BS-63 / BYOC-1: thread any persisted judge authoring (role → assigned flag codes,
    # role → model) into the in-process grade so an authored judge re-votes with its
    # authored lens + provider. Empty before any PUT /v1/judges → run() defaults each judge
    # to its full pack lens / Azure (the authored path is the only in-process grade).
    # CASE-BROWSER-1: the assembly (per-role projections + the GENERALIST-1 unauthored-
    # roster-role lens seeding) lives in the SHARED ``grade_signature_inputs`` — the BFF's
    # baseline-freshness read computes with the same code, so it can never drift from what
    # this grade hashes.
    from lithrim_bench.harness.replay import grade_signature_inputs

    _council_config = agent.eval_profile.council_config or {}
    _si = grade_signature_inputs(db_path, _council_config)
    assignments, models = _si["assignments"], _si["models"]
    samples, temperatures = _si["samples"], _si["temperatures"]
    criteria = _si["criteria"]
    # PHASE2-B: derive the grade roster — production_judges FIRST, then any authored extra role
    # (created via POST /v1/judges) appended — so the authored judge reaches build_trio and votes.
    # ``None`` when there are no extras (the default trio). run() threads roles= → build_trio.
    # REVIEWER-MODE: then the per-agent single/panel override — a len==1 roster becomes the
    # single-judge grade. An extra reviewer (GENERALIST-1) survives the override (allow-set =
    # derived).
    from lithrim_bench.harness.judges import resolve_grade_roster
    from lithrim_bench.harness.pack import pack_production_judges

    roles = resolve_grade_roster(pack_production_judges(), assignments, models, _council_config)

    record = run(
        agent,
        live=args.live,
        in_process=args.in_process,
        out_dir=args.out_dir,
        ontology_path=args.ontology_path,
        assignments=assignments or None,
        models=models or None,
        roles=roles,
        samples=samples or None,
        temperatures=temperatures or None,
        criteria=criteria or None,
        collections_db=args.collections_db,
    )
    if args.emit_json:
        record.pop("_persisted", None)  # local fs/sqlite paths — internal, not API
        print("__GRADE_JSON__" + json.dumps(record))
    else:
        _print(agent, record, live=args.live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
