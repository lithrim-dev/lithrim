"""The Lithrim shell BFF — the judge-capability API v1 (WS-5-BFF).

A small FastAPI backend-for-frontend that fronts the Python harness for the
React/Tauri shell (SPEC_PRODUCT_SHELL §5). It imports ``lithrim_bench.harness``
+ ``scripts/run_eval`` and exposes the v1 surface (SPEC §10 ratified):

    POST /v1/run-eval     {agent?, live?}  -> run_eval.run() record + folded
                                              calibration_check([record]) + council view
    GET  /v1/case         {agent?}         -> the case the shell displays (== graded)
    GET  /v1/corpus                        -> corpus.read_corpus() rows
    POST /v1/eval-pack/run {pack_id, agents[], live?}
                                           -> batch a pack via build_pack; frozen pack
                                              + run ids (UAP-3 R6, replay $0 default)
    GET  /v1/ontology     {agent?}         -> the agent's ontology JSON (working copy
                                              if a PUT wrote one, else committed seed)
    PUT  /v1/ontology     {agent?} <body>  -> validate + persist an edited ontology to a
                                              non-committed working copy (WS-5d)
    GET/PUT /v1/agent     {name?} <body>   -> assemble + persist an Agent to the config
                                              plane (UAP-1 R1; attributed + audit-logged)
    GET  /v1/judges       {agent?}         -> list each v2 role + bound model + assigned
                                              lens + derived questions + validator refs
    GET  /v1/judges/{role} {agent?, assigned_flags?}
                                           -> that judge's config + the rendered
                                              role_key_questions ($0 prompt preview); the
                                              assigned_flags query drives a live before/after
    PUT  /v1/judges/{role} <body>          -> assign a flag lens + model + validator refs;
                                              owner↔emit + snapshot 422; attributed audit
                                              (UAP-2 R2; the prompt↔ontology bridge target)
    GET  /v1/runs                          -> run-history: persisted runs newest-first,
                                              each addressable by run_id (UAP-3 R6/S-BS-56)
    GET  /v1/audit · /v1/runs/{id}/audit   -> the §2B why/when/who/what reports (UAP-1 R0)
    GET  /v1/kb/{ns}/search {q, ...}       -> KB-grounding check (WS-7b): composes over
                                              the harness KbRagTool, which fronts the
                                              backend KB at :8002/v1/kb/{ns}/search; returns
                                              the grounding verdict + the retrieved matches

Replay (``live=false``) is the default + the $0 path. ``live=true`` opts into
exactly one real, paid ``:8002`` council call (run_eval warns on stderr).

PUT /v1/ontology (WS-5d, SPEC §10:144) is clobber-safe by construction: it NEVER
writes the committed ``data/ontology/clinical_v1.json`` seed — it validates the body
(round-trip through ``ontology.from_dict`` + the S-BS-10/12 snapshot lint, import-only)
and persists to an agent-scoped working copy under the BFF out-dir. GET prefers that
working copy so a PUT then GET round-trips. The working copy is a DRAFT — it does not
feed an eval run, which still reads the committed seed (run_eval.py:118); wiring edits
into grading is a later phase (open seam, recorded at close).

Strangler-fig (SPEC_PRODUCT_SERVICE_TOPOLOGY, sequencing B): this targets the
harness, which composes over live :8002/:3031. No Mongo, no ../lithrim-backend.

Run:  uvicorn app:app --app-dir apps/bff --port 8787   (needs the [bff] extra)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = REPO_ROOT / "scripts"
for _p in (str(REPO_ROOT), str(_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_eval  # noqa: E402  (scripts/ — the canonical run entry; mirrors tests/test_ws4a.py)
import seed_ontology  # noqa: E402  (scripts/ — import-only: snapshot lint for the PUT gate)

from lithrim_bench.harness import corpus, evalpack  # noqa: E402
from lithrim_bench.harness.audit import (  # noqa: E402
    Actor,
    AuditLog,
    AuditRecord,
    Target,
    make_actor,
)
from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS  # noqa: E402
from lithrim_bench.harness.config import (  # noqa: E402
    DEFAULT_CONFIG_DB,
    agent_from_dict,
    agent_to_dict,
    load_agent,
    save_agent,
    seed_config_db,
)
from lithrim_bench.harness.judges import (  # noqa: E402
    JudgeConfig,
    list_judges,
    load_judge,
    save_judge,
)
from lithrim_bench.harness.ontology import from_dict as ontology_from_dict  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.report import calibration_check  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402  (the case the shell displays)
from lithrim_bench.runtime.council.judge_assignment import (  # noqa: E402  (council-light; no openai)
    render_role_questions,
)
from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE  # noqa: E402  (pure; no openai)
from lithrim_bench.runtime.council.judge_optimize import (  # noqa: E402  (import-safe: no dspy/openai at import; lazily pulled inside run_optimize)
    run_optimize,
)
from lithrim_bench.verification.spec import (  # noqa: E402  (pure constants: no [verification] heavy deps)
    TOOL_DOSAGE_GROUNDING,
    TOOL_IN_ROW,
    TOOL_JUTE_GEN,
    TOOL_KB_RAG,
    TOOL_RECORD_RAG,
    TOOL_STRUCTURAL_JUTE,
)

DEFAULT_AGENT = "ws0_default"
# Where PUT /v1/ontology persists edited ontologies. A non-committed working dir —
# NEVER data/ontology/ (the committed seed is the source of truth, clobber-safe).
DEFAULT_ONTOLOGY_WORKDIR = REPO_ROOT / "out" / "bff" / "ontology"
# Module-level Body singleton: the FastAPI idiom for a whole-request-body param,
# hoisted out of the default to satisfy ruff B008 (the ruff.toml allowance only
# whitelists Depends/Query; this avoids widening it).
_ONTOLOGY_BODY = Body(...)
_AGENT_BODY = Body(...)
_JUDGE_BODY = Body(...)

# The persisted smart-contract validators a judge may REFERENCE + execute (never
# generate) — the verification toolbox names (verification/spec.py). Ref-only this
# cycle: per-evaluation execution is the §2A withstands-gate (UAP-3b).
_KNOWN_VALIDATORS = (
    TOOL_DOSAGE_GROUNDING,
    TOOL_STRUCTURAL_JUTE,
    TOOL_KB_RAG,
    TOOL_JUTE_GEN,
    TOOL_IN_ROW,
    TOOL_RECORD_RAG,
)


def get_config_db() -> Path:
    """The SQLite config plane the BFF resolves agents from. Override in tests."""
    return Path(DEFAULT_CONFIG_DB)


def get_out_dir() -> Path | None:
    """Where run_eval persists its blob/sqlite (None -> run_eval default). Override in tests."""
    return None


def get_calib_corpus_path() -> Path:
    """The by-construction judge-calibration corpus the optimize trainer reads (the
    recipe=label trainset/held-out, lint-gated). Override in tests so the offline
    optimize-route test never reads the committed corpus."""
    return REPO_ROOT / "examples" / "judge_calib_v1.jsonl"


def get_ontology_workdir() -> Path:
    """Where PUT /v1/ontology persists working copies (never the committed seed). Override in tests."""
    return DEFAULT_ONTOLOGY_WORKDIR


def get_kb_service() -> str:
    """The backend KB base URL the KbRagTool composes over (:8002). Override in tests."""
    return os.environ.get("LITHRIM_KB_SERVICE", "http://localhost:8002")


def get_kb_http_client() -> Any | None:
    """The httpx-like client KbRagTool uses for :8002 (None -> the tool creates one
    lazily; tests inject a fake so no live call is made)."""
    return None


def get_collections_db() -> Path:
    """The doc-shim DB the BFF reads run-provenance blobs from (PIPELINE_RUNS).
    Override in tests so the run-audit read is hermetic."""
    return Path(DEFAULT_COLLECTIONS_DB)


def get_actor() -> Actor:
    """The dev-default 'who' for a write with no X-Actor header. An honest, NON-SME
    handle (monitor N5) — a real SME attributes via the X-Actor header. Override in
    tests / deployment. The §2B invariant: no config write is silently un-attributed."""
    return Actor(type="system", id="dev-default")


def _resolve_actor(x_actor: str | None, default: Actor) -> Actor:
    """The X-Actor header (a real SME handle) wins; else the configured dev default."""
    return make_actor(x_actor) if x_actor else default


def _resolve_ontology_path(agent, workdir: Path) -> tuple[Path, str]:
    """Prefer the working-copy DRAFT a PUT /v1/ontology wrote (R3 draft→grade), else
    the committed seed. Returns (path, source) where source is 'draft' | 'committed'.
    Shared by GET /v1/ontology and POST /v1/run-eval so read + grade resolve identically."""
    wc = Path(workdir) / f"{agent.name}.json"
    if wc.exists():
        return wc, "draft"
    return agent.ontology_abspath(), "committed"


def _load_agent(name: str, db_path: Path):
    # Build the config DB from the committed agent seeds on first use, exactly as
    # scripts/run_eval.py main() does (gitignored-built; source-of-truth is JSON).
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    try:
        return load_agent(name, db_path=db_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class RunEvalRequest(BaseModel):
    agent: str = DEFAULT_AGENT
    live: bool = False  # :8002 backend council (HTTP, paid)
    in_process: bool = (
        False  # the in-process v2 Azure council (paid Azure calls) — a fresh real run
    )


class OptimizeRequest(BaseModel):
    # PAID: a bootstrap compile over the trainset + two held-out evals × the judge
    # (mirrors run_optimize's confirm_cost gate). The route refuses (422) without it,
    # so the cost-confirm is explicit — the shell surfaces an in-DOM modal (S-BS-69).
    confirm: bool = False
    limit: int | None = None  # cap each split for a cheaper smoke (per-call cost check)


class ChatTurn(BaseModel):
    # ONB-0 (S-BS-87): one prior conversation turn, client-replayed for memory. TEXT-ONLY
    # by construction — only {role, content}; `extra="forbid"` REJECTS any smuggled paid
    # knob (confirm/live/in_process) or tool arg, so history can never widen the A-SAFE
    # surface. Replayed as context (a transcript preamble), never re-executed (loop._fold_history).
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # UAP-5b / R11: one user utterance for the conversational shell's agent loop. NO
    # paid knob — the loop's tools are author/read/REPLAY only (the agent can never
    # spend; a paid run is the human's in-DOM cost-confirm calling the existing gate).
    # ONB-0 (S-BS-87): `history` is the client-replayed prior turns (text-only ChatTurn;
    # default empty -> back-compatible). It carries NO paid field and NO tool arg — it is
    # folded into a context preamble, never re-run. (The Phase-1 `mode` field is NOT here.)
    message: str
    agent: str = DEFAULT_AGENT
    history: list[ChatTurn] = []


app = FastAPI(title="Lithrim judge-capability API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5180", "http://127.0.0.1:5180"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/run-eval")
def run_eval_endpoint(
    req: RunEvalRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """Drive one case end-to-end and return the eval-report payload.

    Folds ``calibration_check([record])`` into the response (run_eval.run() itself
    returns only the per-case ``calibration``; the run-level summary mirrors
    tests/test_ws4a.py). The folded summary is a degenerate N=1 DIAGNOSTIC on the
    WS-0 baseline (ece==0.5, small-N caveat) — NOT the WS-4b locked calibration gate.

    R3 (draft→grade): the run reads the agent's working-copy ontology if a PUT wrote
    one (else the committed seed), so an authored flag/threshold actually grades. The
    chosen source is surfaced as ``ontology_source`` ('draft' | 'committed').
    """
    agent = _load_agent(req.agent, db_path)
    ontology_path, ontology_source = _resolve_ontology_path(agent, workdir)
    # S-BS-63: thread the persisted judge authoring through to the in-process grade so
    # an authored judge re-votes with its authored lens (the static→live close). Read
    # from the SAME config DB the BFF resolves agents from (tests override get_config_db).
    judges_cfg = list_judges(db_path=db_path)
    assignments = {
        role: jc.assigned_flags for role, jc in judges_cfg.items() if jc.assigned_flags
    }
    # BYOC-1: thread the persisted per-judge ``model`` binding so a judge authored on
    # ``byo-claude`` runs on the tool-less BYO-Claude LM (the mixed-provider council);
    # roles with no/empty model stay Azure (the default, byte-identical to before).
    models = {role: jc.model for role, jc in judges_cfg.items() if jc.model}
    try:
        record = run_eval.run(
            agent,
            live=req.live,
            in_process=req.in_process,
            out_dir=out_dir,
            ontology_path=ontology_path,
            assignments=assignments or None,
            models=models or None,
            collections_db=collections_db,
        )
    except SystemExit as exc:  # run_eval raises this when the case is missing
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record.pop("_persisted", None)  # local fs/sqlite paths — internal, not API
    record["calibration_check"] = calibration_check([record])
    record["grade_path"] = record["provenance"].get("grade_path")
    record["ontology_source"] = ontology_source  # R3: which ontology graded (audit context)
    record["council"] = _council_view(record)
    # S-BS-56: surface the run's pipeline_run_id so the caller can address the run
    # (run-history + the run→audit leg). It lives on the graded PipelineResult's
    # provenance (replay carries the baseline's id; in_process/live carry a fresh id).
    record["pipeline_run_id"] = _pipeline_run_id(record)
    return record


def _pipeline_run_id(record: dict) -> str | None:
    """The graded run's pipeline_run_id (None if the result carries none)."""
    return ((record.get("result") or {}).get("provenance") or {}).get("pipeline_run_id")


def _council_view(record: dict) -> dict:
    """Project the REALIZED per-judge council votes for the JudgeTab (D0).

    The votes the council actually cast on this case live in
    ``record["result"]["semantic"]["judge_votes"]`` (the live/replay grade carries
    them). This is the per-case truth — what each judge voted — not the configured
    roster. ``confidence`` is ``float | null`` (WS-6a D-E) and passed through as-is.
    The configured roster (best-effort, diagnostic-only) comes off the grade's
    provenance ``council_config.judges``.
    """
    result = record.get("result") or {}
    semantic = result.get("semantic") or {}
    votes = [
        {
            "judge_role": v.get("judge_role"),
            "vote": v.get("vote"),
            "confidence": v.get("confidence"),  # float | null
            "model": v.get("model"),
            "reason": v.get("reason"),
        }
        for v in (semantic.get("judge_votes") or [])
    ]
    prov_council = (result.get("provenance") or {}).get("council_config") or {}
    return {"votes": votes, "configured": list(prov_council.get("judges") or [])}


@app.get("/v1/case")
def case_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """The agent's case content — so the shell DISPLAYS the same case the council GRADES
    (no mockup mismatch). The transcript + the first artifact + the patient record."""
    ag = _load_agent(agent, db_path)
    case = load_case(ag.dataset.case_id, source=ag.source_abspath())
    if case is None:
        raise HTTPException(status_code=404, detail=f"case {ag.dataset.case_id!r} not found")
    artifacts = case.get("artifacts") or []
    pp = case.get("patient_profile") or {}
    return {
        "case_id": case.get("case_id"),
        "transcript": case.get("transcript"),
        "artifact": (
            artifacts[0].get("content") if artifacts and isinstance(artifacts[0], dict) else None
        ),
        "conditions": pp.get("conditions") or [],
        "expected_safety_flags": case.get("expected_safety_flags") or [],
        "injection_recipe": case.get("injection_recipe"),
    }


@app.get("/v1/corpus")
def corpus_endpoint() -> dict:
    """The correction-corpus rows (corpus-row/1). Empty list when none written yet."""
    return {"rows": list(corpus.read_corpus())}


class EvalPackRunRequest(BaseModel):
    pack_id: str
    agents: list[str] = [DEFAULT_AGENT]
    live: bool = False  # :8002 backend council (HTTP, paid) — replay ($0) by default


@app.post("/v1/eval-pack/run")
def eval_pack_run_endpoint(
    req: EvalPackRunRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """Batch a pack of agents through the canonical grade and freeze a thin eval-pack
    (R6 — the "did it move the number?" loop). Runs each agent via
    ``evalpack.build_pack`` over ``run_eval.run``; replay (``live=false``) is the $0
    default, ``live=true`` opts into one paid ``:8002`` call per agent. Each run's
    provenance persists to the run-history DB, so the returned outcomes' run ids
    round-trip to ``GET /v1/runs`` + ``GET /v1/runs/{id}/audit``.

    Batch scope this cycle = replay/live (the ``build_pack`` primitive has no
    in_process param); a batched in_process path is a follow-on.
    """
    agents = [_load_agent(name, db_path) for name in req.agents]
    try:
        pack = evalpack.build_pack(
            req.pack_id,
            agents,
            live=req.live,
            out_dir=out_dir,
            collections_db=collections_db,
        )
    except SystemExit as exc:  # a missing case bubbles up as SystemExit from run_eval
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run_ids = [o.get("pipeline_run_id") for o in pack["outcomes"]]
    return {"pack": pack, "run_ids": run_ids}


# ── R1: GET/PUT /v1/agent — assemble + persist an Agent to the config plane ───


@app.get("/v1/agent")
def get_agent_endpoint(
    name: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """Load an assembled Agent (judges + ontology + tools + kb) from the config DB.
    404 on unknown, mirroring _load_agent."""
    return agent_to_dict(_load_agent(name, db_path))


@app.put("/v1/agent")
def put_agent_endpoint(
    agent: dict = _AGENT_BODY,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Assemble + persist an Agent to the config plane (R1), with an actor-attributed,
    immutable audit record (R0). Validates the body via an ``agent_from_dict`` round-trip
    (422 on malformed, the WS-5d pattern). NEVER writes the committed seed
    ``data/config/agents/*.json`` — only the (non-committed) config DB. The actor is the
    X-Actor header (a real SME) or the dev default; the agent upsert + its audit row are
    one transaction (config.save_agent, N4)."""
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    try:
        ag = agent_from_dict(agent)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"malformed agent: {exc}") from exc
    actor = _resolve_actor(x_actor, default_actor)
    save_agent(
        ag,
        db_path=db_path,
        actor=actor,
        audit_log=AuditLog(db_path=db_path),
        rationale=rationale,
    )
    return {"status": "ok", "name": ag.name, "actor": actor.model_dump()}


# ── UAP-2 R2: GET/PUT /v1/judges — author a judge via ontology-assignment ──────


def _judge_summary(role: str, jc, ontology) -> dict:
    """Project one judge: role + bound model + the assigned lens + the assignable
    flags (LENS_BY_ROLE — the owned+emitted code set, per-flag tier/when_to_use from
    the ontology) + the derived refinement questions (ontology ``questions_for``) +
    the attached validator refs. An unauthored role serves a derived default (empty
    assignment → the seed ``.txt`` base on render; A4 parity)."""
    lens = sorted(LENS_BY_ROLE[role])
    assigned = list(jc.assigned_flags) if jc else []
    available = []
    for code in lens:
        fd = ontology.flag(code)
        available.append(
            {
                "flag": code,
                "tier": (fd.tier if fd else None),
                "when_to_use": (fd.when_to_use if fd else ""),
                "gradeable": (fd.gradeable if fd else False),
                "assigned": code in assigned,
            }
        )
    questions = [
        {"ordinal": q.ordinal, "text": q.text}
        for q in sorted(ontology.questions_for(role), key=lambda q: q.ordinal)
    ]
    return {
        "role": role,
        "model": (jc.model if jc else ""),
        "assigned_flags": assigned,
        "validator_refs": (list(jc.validator_refs) if jc else []),
        "available_flags": available,
        "available_validators": list(_KNOWN_VALIDATORS),
        "questions": questions,
        "authored": jc is not None,
    }


def _validate_judge_assignment(
    role: str, assigned_flags: list[str], validator_refs: list[str]
) -> None:
    """The PUT gate (422 on violation):
    - ``role`` is a known v2 judge role (LENS_BY_ROLE / _TIER1_OWNERS authority);
    - **owner↔emit** (CLAUDE.md invariant #4, S-BS-31/42): every assigned flag is in
      the role's ``LENS_BY_ROLE`` — the owned-AND-emitted code set, owner-consistent
      vs ``_TIER1_OWNERS`` by the council guard test
      (``test_every_tier1_lens_code_is_owner_resident``). The ontology's
      ``owner_roles`` are NOT the authority — they are stale v1 roles
      (behavior/source_message, no faithfulness_judge) never re-snapshotted to the
      v2 trio (CITATION-DRIFT, logged at close; the seed fix is a deferred seam);
    - **snapshot** (defense + S-BS-12): every assigned flag is in the taxonomy
      snapshot;
    - ``validator_refs`` ⊆ the persisted toolbox (execute-only; never authored here).
    """
    if role not in LENS_BY_ROLE:
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    lens = LENS_BY_ROLE[role]
    off_lens = sorted(c for c in assigned_flags if c not in lens)
    if off_lens:
        raise HTTPException(
            status_code=422,
            detail=(
                f"owner↔emit: {role} may only be assigned codes it owns+emits "
                f"{sorted(lens)}; offenders: {off_lens}"
            ),
        )
    off_snapshot = sorted(c for c in assigned_flags if c not in seed_ontology.load_snapshot_codes())
    if off_snapshot:
        raise HTTPException(
            status_code=422,
            detail=f"assigned flags outside taxonomy snapshot (re-snapshot, do not hand-edit): {off_snapshot}",
        )
    bad_refs = sorted(r for r in validator_refs if r not in _KNOWN_VALIDATORS)
    if bad_refs:
        raise HTTPException(
            status_code=422,
            detail=f"unknown validator refs (execute-only, choose from {list(_KNOWN_VALIDATORS)}): {bad_refs}",
        )


@app.get("/v1/judges")
def list_judges_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """List the v2 judge trio: each role + bound model + assigned lens + derived
    questions + validator refs. Questions/flag-metadata resolve against the agent's
    ontology (the working-copy draft if a PUT wrote one, else the committed seed),
    so authored flags are reflected. Does NOT render prompts (no [council] pull) —
    the rendered preview is the per-role GET."""
    saved = list_judges(db_path=db_path)
    ag = _load_agent(agent, db_path)
    ont_path, _src = _resolve_ontology_path(ag, workdir)
    ontology = load_ontology(ont_path)
    judges = [_judge_summary(role, saved.get(role), ontology) for role in sorted(LENS_BY_ROLE)]
    return {
        "judges": judges,
        "roles": sorted(LENS_BY_ROLE),
        "validators": list(_KNOWN_VALIDATORS),
    }


@app.get("/v1/judges/{role}")
def get_judge_endpoint(
    role: str,
    agent: str = DEFAULT_AGENT,
    assigned_flags: str | None = Query(
        None,
        description="CSV flags for a live $0 prompt preview; omit to render the saved/default assignment",
    ),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """One judge's full config + the **rendered ``role_key_questions``** the bridge
    will send ($0, no model). ``base_prompt`` is the unassigned render (== the seed
    ``.txt``, A4 parity); ``rendered_prompt`` is the render for the *effective*
    assignment — the ``assigned_flags`` query (the live before/after preview) if
    given, else the saved/default assignment. This is the demonstrable
    assignment→prompt link (A8), exact because it calls the same
    ``render_role_questions`` the council uses."""
    if role not in LENS_BY_ROLE:
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    saved = load_judge(role, db_path=db_path)
    ag = _load_agent(agent, db_path)
    ont_path, _src = _resolve_ontology_path(ag, workdir)
    ontology = load_ontology(ont_path)
    summary = _judge_summary(role, saved, ontology)
    if assigned_flags is not None:
        effective = [c.strip() for c in assigned_flags.split(",") if c.strip()]
    else:
        effective = summary["assigned_flags"]
    summary["preview_flags"] = effective
    summary["base_prompt"] = render_role_questions(ontology, role)
    summary["rendered_prompt"] = render_role_questions(ontology, role, assigned_flags=effective)
    return summary


@app.put("/v1/judges/{role}")
def put_judge_endpoint(
    role: str,
    judge: dict = _JUDGE_BODY,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Author a judge = assign a flag lens + bind a model + attach validator refs
    (R2). Validates owner↔emit + snapshot + validator-refs → **422** on violation
    (``_validate_judge_assignment``); persists to the config-plane ``judges`` store
    with an actor-attributed, immutable audit record (``target.type='judge'``, R0)
    in one transaction (N4). NEVER generates a validator (execute-only) and NEVER
    writes the committed seed. Body = ``{model, assigned_flags[], validator_refs[]}``;
    the role is the path."""
    assigned = list(judge.get("assigned_flags") or [])
    validator_refs = list(judge.get("validator_refs") or [])
    model = judge.get("model", "") or ""
    _validate_judge_assignment(role, assigned, validator_refs)
    actor = _resolve_actor(x_actor, default_actor)
    jc = JudgeConfig(
        role=role,
        model=model,
        assigned_flags=tuple(assigned),
        validator_refs=tuple(validator_refs),
    )
    save_judge(
        jc, db_path=db_path, actor=actor, audit_log=AuditLog(db_path=db_path), rationale=rationale
    )
    return {
        "status": "ok",
        "role": role,
        "actor": actor.model_dump(),
        "assigned_flags": assigned,
    }


@app.post("/v1/judges/{role}/optimize")
def optimize_judge_endpoint(
    role: str,
    req: OptimizeRequest,
    corpus_path: Path = Depends(get_calib_corpus_path),
    out_dir: Path | None = Depends(get_out_dir),
) -> dict:
    """The calibration trainer (R5, UAP-4): optimize ``role`` against the bench-accept
    metric on the by-construction calibration split, then measure the **honest held-out
    Δ** (precision/recall before→after) on the FIXED test split. Returns
    ``{role, n_train, n_heldout, baseline, optimized, delta, compile_config}`` — a
    measured Δ, **including ≤0**, is the loop-closure; the accept-gate is NEVER loosened
    to manufacture a win (the ``run_optimize`` contract + the WS-6c-DSPy-3b precedent).

    PAID: ``run_optimize`` makes real Azure calls. The route REFUSES (422) without
    ``confirm=true`` so the cost-confirm is explicit; the shell gates it behind an
    in-DOM modal (S-BS-69). Coverage-aware demo selection is ON (S-BS-49) — the
    compile admits ≥1 positive exemplar when the teacher can produce one. No
    bind/persist of the compiled demos this cycle (the round-trip is UAP-4-opt)."""
    if role not in LENS_BY_ROLE:
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    if not req.confirm:
        raise HTTPException(
            status_code=422,
            detail=(
                "optimize makes PAID Azure calls (a bootstrap compile over the trainset "
                "+ two held-out evals × the judge). Resend with confirm=true only after "
                "an explicit cost check."
            ),
        )
    resolved_out = out_dir if out_dir is not None else (REPO_ROOT / "out" / "bff" / "optimize")
    try:
        return run_optimize(
            role,
            corpus_path=corpus_path,
            confirm_cost=True,
            out_dir=resolved_out,
            limit=req.limit,
            coverage_aware=True,
        )
    except HTTPException:
        raise
    except Exception as exc:  # the live Azure/dspy path can fail — surface, don't 500-silently
        raise HTTPException(status_code=502, detail=f"optimize run failed: {exc}") from exc


@app.get("/v1/ontology")
def ontology_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """The agent's ontology JSON. Prefers a working copy a prior PUT wrote (so a
    PUT then GET round-trips); else the committed seed (the same 'stored ontology'
    the live council is sent at run_eval.py:142). Shares ``_resolve_ontology_path``
    with POST /v1/run-eval so read + grade resolve to the same file (R3)."""
    ag = _load_agent(agent, db_path)
    path, _source = _resolve_ontology_path(ag, workdir)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"ontology not found: {path}")
    return json.loads(path.read_text())


def _validate_ontology(ontology: dict) -> None:
    """The PUT gate: reject malformed or snapshot-violating ontologies (HTTP 422).

    Two checks, both import-only over the harness (no edits to lithrim_bench / scripts):
      1. structural round-trip through ``ontology.from_dict`` (the eval-load path);
      2. the S-BS-10/12 snapshot lint — a ``gradeable`` flag outside
         ``taxonomy/taxonomy_snapshot.json`` is rejected loudly (the CLAUDE.md core
         invariant: never silently score a flag the contract-of-record has not blessed).
    """
    try:
        ontology_from_dict(ontology)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"malformed ontology: {exc}") from exc
    offenders = seed_ontology.gradeable_flags_outside_snapshot(
        ontology.get("flags") or [], seed_ontology.load_snapshot_codes()
    )
    if offenders:
        raise HTTPException(
            status_code=422,
            detail=f"gradeable flags outside taxonomy snapshot (re-snapshot, do not hand-edit): {offenders}",
        )


@app.put("/v1/ontology")
def put_ontology_endpoint(
    ontology: dict = _ONTOLOGY_BODY,
    agent: str = DEFAULT_AGENT,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Validate + persist an edited ontology to a non-committed working copy (WS-5d) +
    emit an actor-attributed, immutable audit record (R0 — audit across all config
    writes).

    Clobber-safe by construction: the write target is ``workdir/<agent>.json``, never
    the committed seed. Validation (``_validate_ontology``) rejects malformed or
    snapshot-violating bodies with 422 before anything lands. The audit record carries
    the canonical before (the prior served ontology — working copy if one exists, else
    the committed seed) → after (the new body) diff + why={rationale}.
    """
    _validate_ontology(ontology)
    ag = _load_agent(agent, db_path)
    before_path, _src = _resolve_ontology_path(ag, workdir)
    before = json.loads(before_path.read_text()) if before_path.exists() else None
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{agent}.json"
    path.write_text(json.dumps(ontology, indent=2, sort_keys=True))
    actor = _resolve_actor(x_actor, default_actor)
    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=actor,
            action="edit",
            target=Target(type="ontology", id=agent),
            why={"rationale": rationale},
            before=before,
            after=ontology,
        )
    )
    return {"status": "ok", "agent": agent, "working_copy": str(path)}


# ── R0: the two §2B audit streams as why/when/who/what reports ────────────────


@app.get("/v1/audit")
def get_audit_endpoint(
    actor: str | None = Query(None, description="Filter by actor id (the SME handle)"),
    target_type: str | None = Query(None, description="judge | flag | ontology | agent | ..."),
    target_id: str | None = Query(None, description="The acted-upon object id"),
    since: str | None = Query(None, description="Inclusive ISO8601 lower bound on ts"),
    db_path: Path = Depends(get_config_db),
) -> dict:
    """The config-change audit stream (§2B stream 1): who/when/what/why for every
    authoring write, oldest-first, append-only. Filters are ANDed."""
    records = AuditLog(db_path=db_path).query(
        actor=actor, target_type=target_type, target_id=target_id, since=since
    )
    return {"records": records}


def _run_audit_report(doc: dict, run_id: str) -> dict:
    """Project a persisted PipelineProvenance blob into the §2B run-provenance report
    (stream 2): who (the agent) / when (the run ts) / what (the verdict) / why (each
    judge's vote + reasoning + evidence + the final verdict). A faithful, minimal
    projection — the richer query/diff views are UAP-3."""
    semantic = (doc.get("stage_results") or {}).get("semantic") or {}
    judges = [
        {
            "judge_role": v.get("judge_role"),
            "vote": v.get("vote"),
            "confidence": v.get("confidence"),  # float | null
            "model": v.get("model"),
            "reasoning": v.get("reason"),
            "findings": v.get("findings") or [],
            "evidence": semantic.get("evidence") or [],
        }
        for v in (semantic.get("judge_votes") or [])
    ]
    return {
        "run_id": run_id,
        "ts": doc.get("timestamp"),
        "actor": {"type": "agent", "id": doc.get("agent_id")},
        "verdict": doc.get("verdict"),
        "gate_decision": doc.get("gate_decision"),
        "verdict_flipped_by_stage": doc.get("verdict_flipped_by_stage"),
        "judges": judges,
        # UAP-3b-2 / S-BS-72: the per-judge withstands ruling (§2B critique stream),
        # embedded into the run-blob by run_eval post-save. Empty on non-gated runs.
        "withstands": doc.get("withstands_decisions") or [],
        "findings": doc.get("findings") or [],
        "stages_executed": doc.get("stages_executed") or [],
    }


def _run_summary(doc: dict) -> dict:
    """Newest-first run-history row: the addressable id + the headline verdict +
    who/when, projected from a persisted PipelineProvenance blob (S-BS-56)."""
    return {
        "run_id": doc.get("pipeline_run_id"),
        "verdict": doc.get("verdict"),
        "gate_decision": doc.get("gate_decision"),
        "verdict_flipped_by_stage": doc.get("verdict_flipped_by_stage"),
        "agent": doc.get("agent_id"),
        "ts": doc.get("timestamp"),
    }


@app.get("/v1/runs")
def list_runs_endpoint(
    limit: int = Query(50, ge=1, le=500),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The run-history list (R6 read half / S-BS-56): persisted runs newest-first,
    each addressable via its ``run_id`` (round-trips to ``GET /v1/runs/{id}/audit``).
    Replay + in_process + live all persist a provenance blob (S-BS-52), so the $0
    replay default appears here too. Empty list before any run is persisted."""
    docs = PIPELINE_RUNS.list_all(db_path=collections_db, limit=limit)
    return {"runs": [_run_summary(d) for d in docs]}


@app.get("/v1/runs/{run_id}/audit")
def get_run_audit_endpoint(
    run_id: str,
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The run-provenance audit report (§2B stream 2) for a persisted run. Reads the
    SqliteProvenanceStore blob SYNCHRONOUSLY via the doc-shim's sync .get (no event
    loop in the sync handler) and projects the per-judge votes/reasoning/evidence +
    final verdict.

    UAP-3 (S-BS-52): replay + live + in_process all persist a provenance blob now, so
    any run that actually ran is auditable. An unknown / never-run id is still a clean
    404 — never a 500 (monitor N1)."""
    doc = PIPELINE_RUNS.get(run_id, db_path=collections_db)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id!r} not found (no persisted provenance blob for this run id)",
        )
    return _run_audit_report(doc, run_id)


@app.get("/v1/kb/{namespace}/search")
def kb_search_endpoint(
    namespace: str,
    q: str = Query(..., min_length=1, description="The claim text to ground against the KB"),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float = Query(0.0),
    match: str | None = Query(None, description="Corroboration predicate (e.g. 'claim_in_chunk')"),
    service: str = Depends(get_kb_service),
    http_client: Any | None = Depends(get_kb_http_client),
) -> dict:
    """KB-grounding check (WS-7b, the first Phase-3 slice) — compose over the harness
    ``KbRagTool``, which fronts the backend KB at ``GET :8002/v1/kb/{namespace}/search``.

    Additive + thin: it builds a ``Claim`` from ``q`` and returns the tool's tri-state
    grounding verdict (``conforms``: True=KB grounds the claim, None=inconclusive) plus
    the retrieved matches and the determinism manifest. The heavy retrieval stays in
    lithrim-backend (no vector store here). ``http_client`` is injectable so tests mock
    :8002; in production it is ``None`` and the tool creates an ``httpx.Client`` lazily
    (the ``[bff]`` extra carries httpx). A KB / transport error degrades to
    ``conforms=None`` with the error surfaced in ``manifest`` — never a fabricated hit.
    """
    from lithrim_bench.verification import (
        REFERENCE_CONFORMANCE,
        Claim,
        KbRagTool,
        VerificationSpec,
    )

    reference: dict[str, Any] = {"namespace": namespace, "service": service, "top_k": top_k}
    if min_score:
        reference["min_score"] = min_score
    if match:
        reference["match"] = match
    try:
        spec = VerificationSpec(
            tool="kb_rag",
            applies_to_flags=(),
            locus="",
            reference=reference,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"bad kb spec: {exc}") from exc

    claim = Claim(claim_type=REFERENCE_CONFORMANCE, flag_code=None, subject=q)
    result = KbRagTool(http_client=http_client).verify(claim, spec)
    return {
        "namespace": namespace,
        "query": q,
        "conforms": result.conforms,
        "disposition": result.disposition,
        "evidence": result.evidence,
        "manifest": result.manifest,
    }


def _build_tool_context(
    req_agent: str,
    db_path: Path,
    out_dir: Path | None,
    workdir: Path,
    collections_db: Path,
    actor: Actor,
    x_actor: str | None,
):
    """Bind the EXISTING endpoint functions (deps resolved) into a ToolContext for the
    agent loop (UAP-5b D3). The closures call the FROZEN ops directly — every gate
    (owner↔emit / snapshot) + the audited write path stay intact. apps/bff/agent never
    imports app.py; app.py injects the ops here → no circular import.

    A-SAFE: ``run_eval_replay`` hardcodes ``live=in_process=False`` — there is NO
    branch, here or in the tool, that yields a paid run. The agent proposes a paid run
    in prose; only the human's in-DOM cost-confirm hits the existing confirm-gated path.
    """
    from agent import ToolContext  # lazy: keep [agent] off app import (no SDK pulled here)

    def _author_judge(
        role: str, assigned_flags: list[str], rationale: str, model: str = ""
    ) -> dict:
        # BYOC-1 (resolves NB-2): ``model`` is the provider selector — "" binds the
        # default Azure LM, "byo-claude" binds the tool-less BYO-Claude judge. Persisted
        # via the unchanged ``put_judge_endpoint`` (audited; not a paid run).
        body = {"assigned_flags": assigned_flags, "validator_refs": [], "model": model or ""}
        return put_judge_endpoint(
            role,
            judge=body,
            rationale=rationale,
            db_path=db_path,
            default_actor=actor,
            x_actor=x_actor,
        )

    def _get_judge(role: str) -> dict:
        # S-BS-82: pass assigned_flags=None EXPLICITLY. Calling an endpoint as a plain
        # function bypasses the FastAPI router, so an omitted Query(...)/Header(...)
        # param keeps its FieldInfo sentinel — Query(None) is `not None`, so the live
        # `assigned_flags.split(",")` crashed. Binding rule (applies to EVERY closure
        # here): pass all Query/Header params explicitly when calling an op directly.
        return get_judge_endpoint(
            role, agent=req_agent, assigned_flags=None, db_path=db_path, workdir=workdir
        )

    def _run_eval_replay(agent: str) -> dict:
        return run_eval_endpoint(
            RunEvalRequest(agent=agent, live=False, in_process=False),
            db_path=db_path,
            out_dir=out_dir,
            workdir=workdir,
            collections_db=collections_db,
        )

    # ── UAP-5c: the journey-completing closures (Domain / Flag / Review). Each wraps a
    # FROZEN op and (per the S-BS-82 rule) passes every Query/Header param explicitly.
    def _get_agent(name: str) -> dict:
        return get_agent_endpoint(name=name, db_path=db_path)

    def _author_flag(flag_code: str, tier=None, gradeable=None, rationale: str = "") -> dict:
        # Edit an EXISTING flag's tier/gradeable in the current ontology, then PUT the
        # merged ontology through the FROZEN audited op (clobber-safe working copy). We
        # never fabricate owner_roles or invent a flag — that stays the human's act.
        ag = _load_agent(req_agent, db_path)
        ont_path, _src = _resolve_ontology_path(ag, workdir)
        ontology = json.loads(ont_path.read_text())
        match = next((f for f in (ontology.get("flags") or []) if f.get("flag") == flag_code), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"unknown flag {flag_code!r} (edit an existing flag)")
        if tier is not None:
            match["tier"] = tier
        if gradeable is not None:
            match["gradeable"] = bool(gradeable)
        put = put_ontology_endpoint(
            ontology=ontology,
            agent=req_agent,
            rationale=rationale,
            db_path=db_path,
            workdir=workdir,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {"flag": flag_code, "tier": match["tier"], "gradeable": match["gradeable"], **put}

    def _review_runs(limit: int = 5) -> dict:
        listing = list_runs_endpoint(limit=limit, collections_db=collections_db)
        runs = listing.get("runs") or []
        latest_id = runs[0].get("run_id") if runs else None
        latest_audit = None
        if latest_id:
            try:
                latest_audit = get_run_audit_endpoint(latest_id, collections_db=collections_db)
            except HTTPException:
                latest_audit = None
        return {"runs": runs, "latest_run_id": latest_id, "latest_audit": latest_audit}

    # ── UAP-5c-2: the eval-pack BATCH closure (the first wrapper over a PAID-CAPABLE op).
    def _run_eval_pack(pack_id: str, agents: list[str]) -> dict:
        # A-SAFE crux: eval_pack_run_endpoint's `live` knob fires one paid :8002 call per
        # agent. The wrapper HARDCODES live=False — there is NO branch, here or in the tool,
        # that yields a paid batch (mirrors _run_eval_replay). Per the S-BS-82 rule, pass
        # every Depends param explicitly (a direct call bypasses the FastAPI router).
        return eval_pack_run_endpoint(
            EvalPackRunRequest(pack_id=pack_id, agents=agents, live=False),
            db_path=db_path,
            out_dir=out_dir,
            collections_db=collections_db,
        )

    # ── UAP-5c-2: the Domain-assembly WRITE closure (EDIT-ONE-FACET: the judges roster).
    def _assemble_agent(
        name: str, add_judge=None, remove_judge=None, rationale: str = ""
    ) -> dict:
        # EDIT-ONE-FACET (the judges roster): load the current Agent dict via the FROZEN GET
        # op, add/remove ONE KNOWN v2 judge (LENS_BY_ROLE is the role authority — refuse an
        # unknown role, never fabricate a judge), then PUT the merged dict through the FROZEN
        # audited op (422 on malformed). We never trust a full agent dict from the model. Per
        # the S-BS-82 rule, pass every Query/Header param to put_agent_endpoint explicitly.
        current = get_agent_endpoint(name=name, db_path=db_path)  # 404 on unknown agent
        judges = list(current["eval_profile"].get("judges") or [])
        if not add_judge and not remove_judge:
            raise HTTPException(status_code=400, detail="specify add_judge or remove_judge")
        if add_judge:
            if add_judge not in LENS_BY_ROLE:
                raise HTTPException(
                    status_code=404,
                    detail=f"unknown judge role {add_judge!r} (known: {sorted(LENS_BY_ROLE)})",
                )
            if add_judge not in judges:
                judges.append(add_judge)
        if remove_judge and remove_judge in judges:
            judges.remove(remove_judge)
        current["eval_profile"]["judges"] = judges
        put = put_agent_endpoint(
            agent=current,
            rationale=rationale,
            db_path=db_path,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {"name": name, "judges": judges, **put}

    return ToolContext(
        author_judge=_author_judge,
        get_judge=_get_judge,
        run_eval_replay=_run_eval_replay,
        get_agent=_get_agent,
        author_flag=_author_flag,
        review_runs=_review_runs,
        run_eval_pack=_run_eval_pack,
        assemble_agent=_assemble_agent,
        default_agent=req_agent,
    )


@app.post("/v1/chat")
async def chat_endpoint(
    req: ChatRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> StreamingResponse:
    """The conversational-shell agent loop (UAP-5b / R11): host ClaudeSDKClient over
    the in-process SDK-MCP tools (the CORE author/read/REPLAY spine) and STREAM the
    multi-turn loop to the shell chat pane as SSE. BYO-Claude (local ``claude`` CLI /
    desktop auth — no API key; proven in D0). Every tool-call that writes config goes
    through the existing audited path → **the conversation IS the audit log** (R0).

    The SDK is loaded LAZILY by the loop (A5 — not at app import). Event frames are
    ``data: <json>\\n\\n`` (assistant_delta / tool_call / tool_result-as-gen-UI-part /
    error / done). A-SAFE: no tool can fire a paid run; the loop's ``run_eval`` is
    replay-only ($0), and the loop's own Claude calls are the human's BYO subscription.
    """
    from agent import run_chat, sse_format  # lazy: SDK loads here, on a real chat only

    actor = _resolve_actor(x_actor, default_actor)
    ctx = _build_tool_context(
        req.agent, db_path, out_dir, workdir, collections_db, actor, x_actor
    )

    # ONB-0: text-only prior turns, replayed as context (folded into the loop's query preamble)
    history = [t.model_dump() for t in req.history]

    async def _events():
        async for event in run_chat(req.message, ctx, history=history):
            yield sse_format(event)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
