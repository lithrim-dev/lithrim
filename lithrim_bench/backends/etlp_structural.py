"""EtlpStructuralBackend: HTTP client for the etlp-mapper Jute validator.

Posts HL7 messages or FHIR resources to a running etlp-mapper service
(default localhost:3031, overridable via ``LITHRIM_JUTE_URL`` — the mapper
is an opt-in add-on). The validator is the deterministic structural
layer in the paper's worst-of composition — it produces a structural
verdict (BLOCK if any field-level check fails) independently of any
semantic judge.

Wire contract (verified live against etlp-mapper, 2026-05-29):

  HL7 (artifact_type "hl7_adt_a04"):
    POST /parse-hl7          {"message": <raw_hl7>}      -> {"parsed": <resource>, ...}
    POST /mappings/93/apply  {"data": {"resource": <parsed["parsed"]>}}
    Mapping 93 = hl7-adt-a04-validator-strict. The inner parsed resource
    (NOT the whole parse envelope) is what the mapping reads; it expects it
    wrapped under `resource`. Lenient parse (no `strict`) is used so a
    malformed field surfaces as a failed field-level check rather than a
    400 on a segment-structure short-circuit.

  FHIR:
    POST /mappings/{id}/apply {"data": {"resource": <fhir_json>}}
    fhir_patient -> 23 (fhir-patient-validator)
    fhir_claim   -> 24 (fhir-claim-validator)

The /apply response carries a `checks` list of
{name, field, status: "pass"|"fail", message, value} somewhere under
`result` (either `result.checks` or `result.<root>.checks` depending on
the mapping); `_extract_checks` locates it. A check name is the structural
finding code as emitted by the validator (e.g. "dob-format-valid"); the
mapping check-name -> taxonomy-code reconciliation is a separate concern,
not done here.

Other artifact types are reported as PASS (no applicable mapping); the
analysis layer is responsible for filtering to artifact types this
backend can score. This backend leaves semantic fields empty —
compliance_verdict='approve', flags=[]. Compose with a semantic backend
(LithrimPipelineBackend) in WorstOfBackend to exercise the worst-of rule.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict

_HL7_MAPPING_ID = 93
_FHIR_MAPPING: dict[str, int] = {
    "fhir_patient": 23,
    "fhir_claim": 24,
}


def _default_base_url() -> str:
    """The configurable JUTE mapper (:3031) URL: ``LITHRIM_JUTE_URL`` if set, else the ``etlp_jute``
    plugin manifest default (``http://localhost:3031``). The mapper is an opt-in add-on; this is the
    SAME env→manifest resolution the BFF ingest uses, so an unset env is byte-compat with the old
    hardcoded localhost:3031. Read at call time, never logged."""
    from lithrim_bench.harness import plugins

    return os.environ.get("LITHRIM_JUTE_URL") or plugins.etlp_jute_default_base_url()


class EtlpStructuralBackend(BackendClient):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        treat_unknown_artifact_as: str = "PASS",
        hl7_mapping_id: int = _HL7_MAPPING_ID,
        fhir_mapping: dict[str, int] | None = None,
    ):
        import httpx  # noqa: F401

        self.base_url = (base_url if base_url is not None else _default_base_url()).rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.treat_unknown_artifact_as = treat_unknown_artifact_as
        self.hl7_mapping_id = hl7_mapping_id
        self.fhir_mapping = dict(fhir_mapping) if fhir_mapping is not None else dict(_FHIR_MAPPING)

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="EtlpStructuralBackend",
            backend_version="0.2.0",
            judge_model=None,
            judge_model_version=None,
            extra={
                "base_url": self.base_url,
                "hl7_mapping_id": self.hl7_mapping_id,
                "fhir_mapping": self.fhir_mapping,
            },
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
                envelope = self._call(client, "/parse-hl7", {"message": artifact["content"]})
                inner = envelope.get("parsed")
                if not inner:
                    return self._parse_failure(envelope)
                mapping_id = self.hl7_mapping_id
                resp = self._call(
                    client, f"/mappings/{mapping_id}/apply", {"data": {"resource": inner}}
                )
            elif atype in self.fhir_mapping:
                try:
                    fhir = json.loads(artifact["content"])
                except (TypeError, ValueError):
                    return self._neutral("unparseable artifact content")
                mapping_id = self.fhir_mapping[atype]
                resp = self._call(
                    client, f"/mappings/{mapping_id}/apply", {"data": {"resource": fhir}}
                )
            else:
                return self._neutral(f"no mapping for artifact type {atype!r}")

        checks = _extract_checks(resp)
        failed_rich = [c for c in checks if c.get("status") == "fail"]
        failed = _failed_checks(checks)
        verdict = "BLOCK" if failed else "PASS"
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict=verdict,
            flags=[],
            structural_verdict=verdict,
            structural_findings=failed,
            structural_findings_rich=failed_rich,
            raw={
                "artifact_type": atype,
                "mapping_id": mapping_id,
                "total_checks": len(checks),
                "passed_checks": len(checks) - len(failed),
            },
        )

    def _call(self, client: Any, path: str, body: dict[str, Any]) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = client.post(self.base_url + path, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def _parse_failure(self, envelope: dict[str, Any]) -> BackendVerdict:
        """The HL7 message could not be parsed at all — a structural BLOCK."""
        errors = envelope.get("errors") or []
        findings = [e.get("type") or e.get("message") or "PARSE_ERROR" for e in errors] or [
            "PARSE_ERROR"
        ]
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict="BLOCK",
            flags=[],
            structural_verdict="BLOCK",
            structural_findings=findings,
            structural_findings_rich=list(errors),
            raw={"parse_failed": True, "conformance": envelope.get("conformance")},
        )

    def _neutral(self, why: str) -> BackendVerdict:
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict=self.treat_unknown_artifact_as,
            flags=[],
            structural_verdict=self.treat_unknown_artifact_as,
            structural_findings=[],
            raw={"skipped": why},
        )


def _extract_checks(body: Any) -> list[dict[str, Any]]:
    """Locate the first list of check dicts in an /apply response.

    etlp-mapper places the checks list under `result` but the exact nesting
    varies by mapping (`result.checks` for some, `result.<root>.checks` for
    others). Recurse and return the first list whose items look like checks
    (carry a `status`).
    """
    found: list[dict[str, Any]] = []

    def walk(x: Any) -> None:
        if found:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                if (
                    k == "checks"
                    and isinstance(v, list)
                    and v
                    and isinstance(v[0], dict)
                    and "status" in v[0]
                ):
                    found.extend(v)
                    return
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(body)
    return found


def _failed_checks(checks: list[dict[str, Any]]) -> list[str]:
    """Names of failed checks from an etlp-mapper /apply checks list.

    Each check is {name, field, status: "pass"|"fail", message, value}.
    """
    return [c.get("name", "<unnamed>") for c in checks if c.get("status") == "fail"]
