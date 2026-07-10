"""LithrimHttpBackend: POST to a live lithrim-backend instance.

Skeleton: thin client over /v1/analyze. Maps the backend's response
shape to BackendVerdict. Does NOT poll /v1/jobs/{id}; for the
determinism protocol the harness expects a synchronous evaluation
endpoint (the backend exposes one for eval workflows). If your
backend requires async polling, subclass and override `evaluate`.

This file imports `httpx` lazily so the rest of the bench works
without it installed.
"""
from __future__ import annotations

from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput

_VERDICT_ALIASES = {"REJECT": "reject", "APPROVE": "approve", "NEEDS_REVIEW": "needs_review"}


class LithrimHttpBackend(BackendClient):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8002",
        api_key: str | None = None,
        judge_model: str | None = None,
        judge_model_version: str | None = None,
        timeout: float = 60.0,
        evaluate_path: str = "/v1/analyze/sync",
    ):
        import httpx  # noqa: F401  (raises ImportError at construction if missing)

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.evaluate_path = evaluate_path
        self._judge_model = judge_model
        self._judge_model_version = judge_model_version

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="LithrimHttpBackend",
            backend_version="0.1.0",
            judge_model=self._judge_model,
            judge_model_version=self._judge_model_version,
            extra={"base_url": self.base_url, "path": self.evaluate_path},
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "transcript": case.get("transcript", ""),
            "artifacts": case.get("artifacts", []),
            "metadata": {
                "case_id": case.get("case_id"),
                "pack": case.get("pack"),
                "agent_type": case.get("agent_type"),
            },
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.base_url + self.evaluate_path, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        return _parse_response(body)


def _parse_response(body: dict[str, Any]) -> BackendVerdict:
    raw_v = body.get("compliance_verdict") or body.get("verdict") or "approve"
    verdict = _VERDICT_ALIASES.get(str(raw_v).upper(), str(raw_v).lower())
    artifact_v = body.get("artifact_verdict") or "PASS"
    flags = body.get("safety_flags") or body.get("flags") or []

    per_judge: dict[str, JudgeOutput] | None = None
    judges_payload = body.get("per_judge") or body.get("council") or None
    if isinstance(judges_payload, dict):
        per_judge = {}
        for name, payload in judges_payload.items():
            j_v_raw = payload.get("verdict") or "approve"
            per_judge[name] = JudgeOutput(
                judge_name=name,
                verdict=_VERDICT_ALIASES.get(str(j_v_raw).upper(), str(j_v_raw).lower()),
                flags=list(payload.get("flags") or []),
            )

    return BackendVerdict(
        compliance_verdict=verdict,
        artifact_verdict=str(artifact_v).upper(),
        flags=list(flags),
        per_judge=per_judge,
        raw=body,
    )
