"""The Lithrim shell BFF — the judge-capability API v1 (WS-5-BFF).

A small FastAPI backend-for-frontend that fronts the Python harness for the
React/Tauri shell (SPEC_PRODUCT_SHELL §5). It imports ``lithrim_bench.harness``
+ ``scripts/run_eval`` and exposes the locked v1 surface:

    POST /v1/run-eval     {agent?, live?}  -> run_eval.run() record + folded
                                              calibration_check([record]) + council view
    GET  /v1/corpus                        -> corpus.read_corpus() rows
    GET  /v1/ontology     {agent?}         -> the agent's ontology JSON (working copy
                                              if a PUT wrote one, else committed seed)
    PUT  /v1/ontology     {agent?} <body>  -> validate + persist an edited ontology to a
                                              non-committed working copy (WS-5d)

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
import sys
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = REPO_ROOT / "scripts"
for _p in (str(REPO_ROOT), str(_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_eval  # noqa: E402  (scripts/ — the canonical run entry; mirrors tests/test_ws4a.py)
import seed_ontology  # noqa: E402  (scripts/ — import-only: snapshot lint for the PUT gate)

from lithrim_bench.harness import corpus  # noqa: E402
from lithrim_bench.harness.config import (  # noqa: E402
    DEFAULT_CONFIG_DB,
    load_agent,
    seed_config_db,
)
from lithrim_bench.harness.ontology import from_dict as ontology_from_dict  # noqa: E402
from lithrim_bench.harness.report import calibration_check  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402  (the agent's case, for the shell to display)

DEFAULT_AGENT = "ws0_default"
# Where PUT /v1/ontology persists edited ontologies. A non-committed working dir —
# NEVER data/ontology/ (the committed seed is the source of truth, clobber-safe).
DEFAULT_ONTOLOGY_WORKDIR = REPO_ROOT / "out" / "bff" / "ontology"
# Module-level Body singleton: the FastAPI idiom for a whole-request-body param,
# hoisted out of the default to satisfy ruff B008 (the ruff.toml allowance only
# whitelists Depends/Query; this avoids widening it).
_ONTOLOGY_BODY = Body(...)


def get_config_db() -> Path:
    """The SQLite config plane the BFF resolves agents from. Override in tests."""
    return Path(DEFAULT_CONFIG_DB)


def get_out_dir() -> Path | None:
    """Where run_eval persists its blob/sqlite (None -> run_eval default). Override in tests."""
    return None


def get_ontology_workdir() -> Path:
    """Where PUT /v1/ontology persists working copies (never the committed seed). Override in tests."""
    return DEFAULT_ONTOLOGY_WORKDIR


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
    in_process: bool = False  # the in-process v2 Azure council (paid Azure calls) — a fresh real run


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
) -> dict:
    """Drive one case end-to-end and return the eval-report payload.

    Folds ``calibration_check([record])`` into the response (run_eval.run() itself
    returns only the per-case ``calibration``; the run-level summary mirrors
    tests/test_ws4a.py). The folded summary is a degenerate N=1 DIAGNOSTIC on the
    WS-0 baseline (ece==0.5, small-N caveat) — NOT the WS-4b locked calibration gate.
    """
    agent = _load_agent(req.agent, db_path)
    try:
        record = run_eval.run(agent, live=req.live, in_process=req.in_process, out_dir=out_dir)
    except SystemExit as exc:  # run_eval raises this when the case is missing
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record.pop("_persisted", None)  # local fs/sqlite paths — internal, not API
    record["calibration_check"] = calibration_check([record])
    record["grade_path"] = record["provenance"].get("grade_path")
    record["council"] = _council_view(record)
    return record


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
        "artifact": (artifacts[0].get("content") if artifacts and isinstance(artifacts[0], dict) else None),
        "conditions": pp.get("conditions") or [],
        "expected_safety_flags": case.get("expected_safety_flags") or [],
        "injection_recipe": case.get("injection_recipe"),
    }


@app.get("/v1/corpus")
def corpus_endpoint() -> dict:
    """The correction-corpus rows (corpus-row/1). Empty list when none written yet."""
    return {"rows": list(corpus.read_corpus())}


@app.get("/v1/ontology")
def ontology_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """The agent's ontology JSON. Prefers a working copy a prior PUT wrote (so a
    PUT then GET round-trips); else the committed seed (the same 'stored ontology'
    the live council is sent at run_eval.py:118)."""
    wc = workdir / f"{agent}.json"
    if wc.exists():
        return json.loads(wc.read_text())
    ag = _load_agent(agent, db_path)
    path = ag.ontology_abspath()
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
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """Validate + persist an edited ontology to a non-committed working copy (WS-5d).

    Clobber-safe by construction: the write target is ``workdir/<agent>.json``, never
    the committed seed. Validation (``_validate_ontology``) rejects malformed or
    snapshot-violating bodies with 422 before anything lands.
    """
    _validate_ontology(ontology)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{agent}.json"
    path.write_text(json.dumps(ontology, indent=2, sort_keys=True))
    return {"status": "ok", "agent": agent, "working_copy": str(path)}
