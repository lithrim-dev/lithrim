"""LithrimPipelineBackend: live council + structural via /v1/pipeline/evaluate.

POSTs the production sync orchestrator endpoint and maps the
PipelineResult shape (StageResult per stage + per-judge votes) onto
BackendVerdict. One round-trip returns both semantic and structural
stage outputs plus the live worst-of verdict — the closest thing to
the paper's claim observed in actual production behavior.

Maps:
  PipelineResult.verdict           -> artifact_verdict
  PipelineResult.gate_decision     -> compliance_verdict via _GATE_TO_COMPLIANCE
  PipelineResult.semantic.status   -> kept as a per-judge metadata pin
  PipelineResult.semantic.findings -> flags (Finding.code list)
  PipelineResult.semantic.judge_votes -> per_judge (judge_role -> verdict + findings)
  PipelineResult.structural.status -> structural_verdict
  PipelineResult.structural.findings -> structural_findings (check_name list)

Requires `org_id` (read from --api-key context / .live_env). The
artifact_type is taken from the case's first artifact; override via
`artifact_type_override` if needed (e.g. to route to a different
profile).
"""

from __future__ import annotations

from typing import Any

from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput

_GATE_TO_COMPLIANCE = {"allow": "approve", "regenerate": "needs_review", "escalate": "reject"}
_STAGE_STATUS_NORMALIZE = {
    "PASS": "PASS",
    "WARN": "WARN",
    "BLOCK": "BLOCK",
    "not_applicable": "not_applicable",  # BRS-0b: preserve distinct status, was: "PASS"
}


class LithrimPipelineBackend(BackendClient):
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8002",
        api_key: str,
        org_id: str,
        agent_id: str | None = None,
        validator_id: str | None = None,
        gate_mode: bool = False,
        artifact_type_override: str | None = None,
        timeout: float = 180.0,
    ):
        import httpx  # noqa: F401

        if not api_key:
            raise ValueError("api_key is required")
        if not org_id:
            raise ValueError("org_id is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.org_id = org_id
        self.agent_id = agent_id
        self.validator_id = validator_id
        self.gate_mode = gate_mode
        self.artifact_type_override = artifact_type_override
        self.timeout = timeout

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="LithrimPipelineBackend",
            backend_version="0.1.0",
            judge_model="live-council",
            judge_model_version="gpt-4.1+gate",
            extra={
                "base_url": self.base_url,
                "org_id": self.org_id,
                "agent_id": self.agent_id,
                "validator_id": self.validator_id,
                "gate_mode": self.gate_mode,
                "artifact_type_override": self.artifact_type_override,
            },
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        import httpx

        artifacts = case.get("artifacts") or []
        if not artifacts:
            return self._neutral("no artifacts")
        artifact = artifacts[0]
        artifact_type = self.artifact_type_override or artifact.get("type")

        body: dict[str, Any] = {
            "artifact": artifact["content"],
            "artifact_type": artifact_type,
            "context_kind": "transcript",
            "context": _build_context(case, artifacts),
            "org_id": self.org_id,
            "gate_mode": self.gate_mode,
        }
        if self.agent_id:
            body["agent_id"] = self.agent_id
        if self.validator_id:
            body["validator_id"] = self.validator_id

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                self.base_url + "/v1/pipeline/evaluate",
                json=body,
                headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            payload = resp.json()

        return _parse(payload)

    def _neutral(self, why: str) -> BackendVerdict:
        return BackendVerdict(
            compliance_verdict="approve",
            artifact_verdict="PASS",
            flags=[],
            structural_verdict="PASS",
            structural_findings=[],
            raw={"skipped": why},
        )


def _render_record_section(name: str, value: Any) -> str:
    """One delimited SOURCE RECORD section for a declared grading-context field. Deterministic:
    strings verbatim, scalar lists as bullets, anything structured as sorted JSON."""
    import json as _json

    if isinstance(value, str):
        body = value
    elif isinstance(value, list) and all(isinstance(x, (str, int, float)) for x in value):
        body = "\n".join(f"- {x}" for x in value)
    else:
        body = _json.dumps(value, indent=2, sort_keys=True)
    return f"--- SOURCE RECORD: {name} ---\n{body}"


def _build_context(
    case: dict[str, Any],
    artifacts: list[dict[str, Any]],
    context_fields: tuple[str, ...] = (),
) -> str:
    """Transcript plus any documentation-of-record artifacts.

    The artifact under test is artifacts[0]. A case may carry
    secondary documentation artifacts (e.g. a coding case carries the
    FHIR Claim under test plus a fhir_document_reference clinical
    note). The note is the documentation the codes must be faithful
    to, so its text is folded into the context the council sees.

    ``context_fields`` (REPRO-1 R1b): user-declared case fields (the ontology's
    ``grading_context_fields`` — DATA, never code) folded in as delimited SOURCE RECORD
    sections, in declaration order, so a structured record the case carries (a problem
    list, an account state) is visible to the judges and the withstands gate. A field
    that is absent/empty is skipped; the default ``()`` is byte-identical to before.
    """
    import json as _json

    context = case.get("transcript", "") or ""
    for name in context_fields:
        value = case.get(name)
        if value in (None, "", [], {}):
            continue
        context = f"{context}\n\n{_render_record_section(name, value)}"
    for extra in artifacts[1:]:
        if extra.get("type") != "fhir_document_reference":
            continue
        soap = extra.get("_soap_text")
        if not soap:
            try:
                doc = _json.loads(extra.get("content") or "{}")
                soap = doc["content"][0]["attachment"]["data"]
            except (ValueError, KeyError, IndexError, TypeError):
                soap = None
        if soap:
            context = f"{context}\n\n--- CLINICAL NOTE (documentation of record) ---\n{soap}"
    return context


def _parse(payload: dict[str, Any]) -> BackendVerdict:
    artifact_v = _STAGE_STATUS_NORMALIZE.get(payload.get("verdict", "PASS"), "PASS")
    compliance_v = _GATE_TO_COMPLIANCE.get(payload.get("gate_decision", "allow"), "approve")

    semantic = payload.get("semantic") or {}
    structural = payload.get("structural") or {}

    flags = sorted(
        {
            f.get("code") or f.get("check_name") or ""
            for f in semantic.get("findings") or []
            if f.get("code") or f.get("check_name")
        }
        - {""}
    )

    per_judge: dict[str, JudgeOutput] | None = None
    judge_votes = semantic.get("judge_votes") or []
    if judge_votes:
        per_judge = {}
        for jv in judge_votes:
            role = jv.get("judge_role", "<unknown>")
            vote = jv.get("vote", "PASS")
            verdict_lifted = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}.get(
                vote, "approve"
            )
            per_judge[role] = JudgeOutput(
                judge_name=role,
                verdict=verdict_lifted,
                flags=list(jv.get("findings") or []),
                confidence=float(jv.get("confidence") or 0.0),
            )

    structural_v = _STAGE_STATUS_NORMALIZE.get(structural.get("status", "PASS"), "PASS")
    structural_findings = sorted(
        {
            f.get("check_name") or f.get("code") or ""
            for f in structural.get("findings") or []
            if f.get("check_name") or f.get("code")
        }
        - {""}
    )

    # Rich Finding payloads preserved alongside the flat-code surfaces. The
    # API emits semantic.findings as full Finding dicts (type, severity,
    # detail, field, check_name, code, chunk_id, start_ms, end_ms, speaker);
    # structural.findings as StructuralFinding dicts. Carrying them through
    # lets analysis surface per-finding timeline anchors / span fields that
    # the flat code list discards. Defensive copy so mutations downstream
    # don't tunnel back into the raw payload.
    findings_rich = [dict(f) for f in (semantic.get("findings") or []) if isinstance(f, dict)]
    structural_findings_rich = [
        dict(f) for f in (structural.get("findings") or []) if isinstance(f, dict)
    ]

    return BackendVerdict(
        compliance_verdict=compliance_v,
        artifact_verdict=artifact_v,
        flags=flags,
        per_judge=per_judge,
        structural_verdict=structural_v,
        structural_findings=structural_findings,
        raw={
            "duration_ms": payload.get("duration_ms"),
            "gate_decision": payload.get("gate_decision"),
            "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
            "semantic_status": semantic.get("status"),
            "structural_status": structural.get("status"),
        },
        findings_rich=findings_rich,
        structural_findings_rich=structural_findings_rich,
    )
