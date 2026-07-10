"""The grading seam: compose-over-live, with a replay path for offline work.

``grade_live`` POSTs the production sync orchestrator at
``:8002 /v1/pipeline/evaluate`` (the seam proven live 2026-05-30) and returns the
parsed ``PipelineResult`` dict. ``grade_replay`` loads a captured baseline of that
same shape. WS-0 acceptance runs through ``grade_replay`` only — the live path is
present but opt-in (``--live``), so the cycle costs $0 in new paid calls.

The two functions return the *same* dict shape (a parsed PipelineResult), so every
downstream stage (persist / ground / report) is agnostic to which path produced it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lithrim_bench.backends.lithrim_pipeline import _build_context

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = REPO_ROOT / ".live_env"


def _load_env(path: str | Path) -> dict[str, str]:
    """Parse a ``KEY=value`` env file (``.live_env``). Missing file -> empty."""
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def grade_replay(case: dict[str, Any], baseline_path: str | Path) -> dict[str, Any]:
    """Load a captured ``/v1/pipeline/evaluate`` baseline (the WS-0 path).

    ``case`` is accepted for signature parity with ``grade_live`` (so a caller can
    swap one for the other behind a ``--live`` switch); the baseline itself carries
    the graded result, so the case row is not re-sent.
    """
    return json.loads(Path(baseline_path).read_text())


def build_request_body(
    case: dict[str, Any],
    *,
    org_id: str,
    council_config: dict[str, Any] | None = None,
    ontology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the ``/v1/pipeline/evaluate`` request body for one case.

    Factored out so the WS-2 config injection is inspectable offline (no paid
    call). ``council_config`` + ``ontology`` are the Agent's *stored* config
    (S-BS-6 disposition + the domain ontology); each is included **only when
    truthy**, so a caller with no stored config produces exactly the WS-0/WS-1
    body and the backend's Optional-with-default fields see ``None``.
    """
    artifacts = case.get("artifacts") or []
    if not artifacts:
        raise ValueError("case has no artifacts to grade")
    artifact = artifacts[0]

    # REPRO-1 R1b: the ontology's grading_context_fields (user-authored DATA) fold declared
    # case fields into the context as SOURCE RECORD sections — the record reaches the judge.
    context_fields = tuple((ontology or {}).get("grading_context_fields") or ())
    body: dict[str, Any] = {
        "artifact": artifact["content"],
        "artifact_type": artifact.get("type"),
        "context_kind": "transcript",
        "context": _build_context(case, artifacts, context_fields=context_fields),
        "org_id": org_id,
        "eval_mode": True,
    }
    if council_config:
        body["council_config"] = council_config
    if ontology:
        body["ontology"] = ontology
    return body


def grade_live(
    case: dict[str, Any],
    *,
    env: str | Path = DEFAULT_ENV,
    base_url: str = "http://localhost:8002",
    timeout: float = 180.0,
    council_config: dict[str, Any] | None = None,
    ontology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST one case to the live council and return the parsed PipelineResult dict.

    Builds the ``PipelineRequest`` body (transcript + artifact), with ``org_id``
    from ``.live_env`` **in the body** and ``eval_mode=true`` for a deterministic
    per-(case, judge) seed (driver §2.1). Auth = ``X-API-Key``.

    WS-2: when the Agent has a stored ``council_config`` / ``ontology``, they are
    injected into the body (additive, backward-compatible — the backend reads them
    as Optional-with-default). This is the WS-1 "stored-only" disposition becoming
    "injected" — a new domain drives the live council via its ontology row, not a
    backend code change.

    NOTE: this is the live, paid path. WS-0/WS-2 offline acceptance does NOT
    exercise it; it is reachable only via ``run_eval.py --live`` (paid).
    """
    import httpx

    cfg = _load_env(env)
    api_key = cfg.get("LITHRIM_API_KEY", "").strip()
    org_id = cfg.get("LITHRIM_ORG_ID", "").strip()
    if not api_key or not org_id:
        raise ValueError(f"LITHRIM_API_KEY / LITHRIM_ORG_ID missing from {env}")

    body = build_request_body(case, org_id=org_id, council_config=council_config, ontology=ontology)

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            base_url.rstrip("/") + "/v1/pipeline/evaluate",
            json=body,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()


def grade_inprocess(
    case: dict[str, Any],
    *,
    org_id: str = "local",
    semantic_stage: Any = None,
    provenance_store: Any = None,
    context_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run the in-process v2 council and return the parsed PipelineResult dict.

    This is the WS-6c-AGENTIC grade-wire: the recomposed in-process pipeline
    (``LocalPipelineBackend`` → the v2 Azure trio, semantic-only, NoOp provenance)
    scores a real case behind the frozen grade seam — the first time the council
    scores real cases through the harness, with no ``:8002`` and no Celery.

    The return is ``PipelineResult.model_dump(mode="json")``, byte-shape-identical
    to what ``grade_replay`` / ``grade_live`` return (same ``verdict`` /
    ``gate_decision`` / ``findings`` / ``semantic.{evidence,judge_votes}`` keys), so
    every downstream stage (``ground`` / ``composite`` / ``calibration``) is agnostic
    to which path produced it (the §6/§7 frozen-contract property).

    ``semantic_stage`` is injectable for offline/deterministic runs (A1): a fake
    stage returns a canned ``(StageResult, meta)`` so no Azure call is made. Default
    ``None`` → the live v2 trio (the paid path, opt-in via ``run_eval --in-process``).
    ``LocalPipelineBackend`` is imported lazily so this module stays importable on
    default deps (the council pulls in ``openai``), mirroring ``grade_live``'s lazy
    ``httpx`` import.

    ``provenance_store`` is injectable (WS-6d): ``None`` → ``NoOpProvenanceStore``
    (hermetic — the default for direct/test calls); ``run_eval --in-process`` passes
    a ``SqliteProvenanceStore`` so the product path persists each run. Persistence is
    a fire-and-forget side-effect behind ``save`` — the returned dict is byte-identical
    with the store on or off (the frozen-contract A3).
    """
    from lithrim_bench.backends.local_pipeline import LocalPipelineBackend

    backend = LocalPipelineBackend(
        org_id=org_id, semantic_stage=semantic_stage, provenance_store=provenance_store,
        context_fields=context_fields,
    )
    result = backend.evaluate_pipeline(case)
    if result is None:
        raise ValueError("case has no artifacts to grade")
    return result.model_dump(mode="json")
