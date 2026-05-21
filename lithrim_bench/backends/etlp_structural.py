"""EtlpStructuralBackend: HTTP client for the etlp-mapper Jute validator.

Posts HL7 messages or FHIR resources to a running etlp-mapper service
(default localhost:3031). The validator is the deterministic structural
layer in the paper's worst-of composition — it produces a structural
verdict (BLOCK if any field-level check fails) independently of any
semantic judge.

For HL7 artifacts, the protocol is:
    POST /parse-hl7         body: {hl7: <raw_text>}      -> parsed JSON
    POST /mappings/25/apply body: {resource: <parsed>}   -> check results

For FHIR Patient artifacts:
    POST /mappings/18/apply body: {resource: <fhir>}    -> check results
For FHIR Claim artifacts:
    POST /mappings/19/apply body: {resource: <fhir>}

Other artifact types are reported as PASS (no applicable mapping); the
analysis layer is responsible for filtering to artifact types this
backend can score.

This backend leaves semantic fields empty — compliance_verdict='approve',
flags=[]. Compose with LithrimHttpBackend (semantic) in the harness to
exercise the worst-of rule end-to-end.
"""
from __future__ import annotations

from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict

_HL7_MAPPING_ID = 25
_FHIR_MAPPING: dict[str, int] = {
    "fhir_patient": 18,
    "fhir_claim": 19,
}


class EtlpStructuralBackend(BackendClient):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:3031",
        api_key: str | None = None,
        timeout: float = 30.0,
        treat_unknown_artifact_as: str = "PASS",
    ):
        import httpx  # noqa: F401

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.treat_unknown_artifact_as = treat_unknown_artifact_as

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="EtlpStructuralBackend",
            backend_version="0.1.0",
            judge_model=None,
            judge_model_version=None,
            extra={"base_url": self.base_url, "hl7_mapping_id": _HL7_MAPPING_ID},
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        import httpx

        artifacts = case.get("artifacts") or []
        if not artifacts:
            return self._neutral("no artifacts")
        artifact = artifacts[0]
        atype = artifact.get("type")

        with httpx.Client(timeout=self.timeout) as client:
            if atype == "hl7_adt_a04":
                parsed = self._call(
                    client, "/parse-hl7", {"hl7": artifact["content"]}
                )
                checks = self._call(
                    client, f"/mappings/{_HL7_MAPPING_ID}/apply", {"resource": parsed}
                )
            elif atype in _FHIR_MAPPING:
                import json
                try:
                    fhir = json.loads(artifact["content"])
                except (TypeError, ValueError):
                    return self._neutral("unparseable artifact content")
                checks = self._call(
                    client,
                    f"/mappings/{_FHIR_MAPPING[atype]}/apply",
                    {"resource": fhir},
                )
            else:
                return self._neutral(f"no mapping for artifact type {atype!r}")

        failed = _failed_checks(checks)
        verdict = "BLOCK" if failed else "PASS"
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict=verdict,
            flags=[],
            structural_verdict=verdict,
            structural_findings=failed,
            raw={"checks": checks, "artifact_type": atype},
        )

    def _call(self, client: Any, path: str, body: dict[str, Any]) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = client.post(self.base_url + path, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def _neutral(self, why: str) -> BackendVerdict:
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict=self.treat_unknown_artifact_as,
            flags=[],
            structural_verdict=self.treat_unknown_artifact_as,
            structural_findings=[],
            raw={"skipped": why},
        )


def _failed_checks(checks: Any) -> list[str]:
    """Extract names of failed checks from an etlp-mapper /apply response.

    The response shape from etlp-mapper is a dict whose values are
    either {pass: bool, message: str} per-check, or a list of such
    dicts. Defensive enough to handle either layout.
    """
    failed: list[str] = []
    if isinstance(checks, dict):
        for name, payload in checks.items():
            if isinstance(payload, dict) and payload.get("pass") is False:
                failed.append(name)
    elif isinstance(checks, list):
        for entry in checks:
            if isinstance(entry, dict) and entry.get("pass") is False:
                failed.append(entry.get("name", "<unnamed>"))
    return failed
