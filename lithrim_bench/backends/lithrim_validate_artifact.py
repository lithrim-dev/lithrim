"""LithrimValidateArtifactBackend: live structural validator via Lithrim middleware.

POSTs /v1/validate-artifact on lithrim-backend (default :8002), which
proxies to etlp-mapper through Lithrim's profile lookup + circuit
breaker + audit pipeline. Use this for paper-grade structural-recall
measurements; use EtlpStructuralBackend if you want to bypass Lithrim
and hit the validator directly.

Auth: X-API-Key header. Pass an API key minted via /v1/api-keys (after
/auth/login). The bench does not handle login or key minting; that's a
caller responsibility.
"""
from __future__ import annotations

from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict

_VERDICT_LIFT = {"PASS": "approve", "WARN": "needs_review", "BLOCK": "reject"}


class LithrimValidateArtifactBackend(BackendClient):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8002",
        api_key: str,
        etlp_mapping_id: int | None = None,
        artifact_type_override: str | None = None,
        timeout: float = 60.0,
    ):
        import httpx  # noqa: F401

        if not api_key:
            raise ValueError("api_key is required (mint one via /v1/api-keys)")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.etlp_mapping_id = etlp_mapping_id
        self.artifact_type_override = artifact_type_override
        self.timeout = timeout

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="LithrimValidateArtifactBackend",
            backend_version="0.1.0",
            judge_model=None,
            judge_model_version=None,
            extra={
                "base_url": self.base_url,
                "etlp_mapping_id": self.etlp_mapping_id,
                "artifact_type_override": self.artifact_type_override,
            },
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        import httpx

        artifacts = case.get("artifacts") or []
        if not artifacts:
            return self._neutral("no artifacts")
        artifact = artifacts[0]

        body: dict[str, Any] = {
            "artifact": artifact["content"],
            "artifact_type": self.artifact_type_override or artifact.get("type"),
        }
        if self.etlp_mapping_id is not None:
            body["etlp_mapping_id"] = self.etlp_mapping_id

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                self.base_url + "/v1/validate-artifact",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": self.api_key,
                },
            )
            resp.raise_for_status()
            payload = resp.json()

        structural_verdict = payload.get("verdict") or "PASS"
        findings = [
            f.get("check_name") or f.get("detail", "<unnamed>")
            for f in (payload.get("findings") or [])
            if f.get("type") == "structural"
        ]

        return BackendVerdict(
            compliance_verdict=_VERDICT_LIFT.get(structural_verdict, "approve"),
            artifact_verdict=structural_verdict,
            flags=[],
            structural_verdict=structural_verdict,
            structural_findings=findings,
            raw={
                "passed_checks": payload.get("passed_checks"),
                "total_checks": payload.get("total_checks"),
                "duration_ms": payload.get("duration_ms"),
                "checks": payload.get("checks"),
                "skipped_reason": payload.get("skipped_reason"),
            },
        )

    def _neutral(self, why: str) -> BackendVerdict:
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict="PASS",
            flags=[],
            structural_verdict="PASS",
            structural_findings=[],
            raw={"skipped": why},
        )
