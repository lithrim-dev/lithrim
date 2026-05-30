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


def grade_live(
    case: dict[str, Any],
    *,
    env: str | Path = DEFAULT_ENV,
    base_url: str = "http://localhost:8002",
    timeout: float = 180.0,
) -> dict[str, Any]:
    """POST one case to the live council and return the parsed PipelineResult dict.

    Builds the ``PipelineRequest`` body inline (transcript + artifact), with
    ``org_id`` from ``.live_env`` **in the body** and ``eval_mode=true`` for a
    deterministic per-(case, judge) seed (driver §2.1). Auth = ``X-API-Key``.

    NOTE: this is the live, paid path. WS-0 acceptance does NOT exercise it; it is
    reachable only via ``run_ws0.py --live``. Composing over ``:8002`` here is the
    walking-skeleton intent — no backend change (``council_config`` injection = WS-2).
    """
    import httpx

    cfg = _load_env(env)
    api_key = cfg.get("LITHRIM_API_KEY", "").strip()
    org_id = cfg.get("LITHRIM_ORG_ID", "").strip()
    if not api_key or not org_id:
        raise ValueError(f"LITHRIM_API_KEY / LITHRIM_ORG_ID missing from {env}")

    artifacts = case.get("artifacts") or []
    if not artifacts:
        raise ValueError("case has no artifacts to grade")
    artifact = artifacts[0]

    body: dict[str, Any] = {
        "artifact": artifact["content"],
        "artifact_type": artifact.get("type"),
        "context_kind": "transcript",
        "context": _build_context(case, artifacts),
        "org_id": org_id,
        "eval_mode": True,
    }

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            base_url.rstrip("/") + "/v1/pipeline/evaluate",
            json=body,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()
