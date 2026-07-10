"""JuteGenValidatorTool — a structural validator the tool GENERATES from a sample.

Instead of selecting a pre-seeded :3031 mapping (StructuralJuteTool), this tool
authors a JUTE conformance validator on demand via the etlp-mapper Copilot
(`POST /mappings/generate`, extend mode from a base validator + a data sample +
a spec description), then applies it via `POST /mappings/test-template` (compile +
apply in-memory, NO DB write).

Determinism (respects the bench's byte-deterministic charter): LLM generation is a
ONE-TIME AUTHORING step. The tool generates once, caches the template, and pins its
content hash; thereafter it applies the PINNED template deterministically. A
generated validator is NOT trustworthy until the by-construction pack accepts it
(clean must PASS, every labeled defect must be caught) — generation is gated by the
bench, not trusted on faith. `confidence` from the Copilot is recorded but is NOT a
substitute for that bench gate.

reference = {
  "service": "http://localhost:3031",
  "artifact_kind": "fhir_patient",
  # apply a PINNED template (deterministic):
  "pinned_template": "<jute yaml>", "pinned_template_sha256": "<hash>",
  # OR author one (generate-once-cached) when no pinned_template:
  "generate": {"description": "<conformance rules / refinement>",
               "base_validator": "fhir-patient-validator",   # fetched as existing_template (extend)
               "expected_output": <opt; else base applied to sample>,
               "source_format": "fhir", "target_platform": "fhir-validation"},
}

conforms: True = sample conforms (no failed checks); False = >=1 failed check;
None = template didn't compile / drift / not configured.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .spec import Claim, VerificationResult, VerificationSpec
from .tools import StructuralJuteTool  # reuse _find_checks


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JuteGenValidatorTool(StructuralJuteTool):
    """Generate-from-sample structural validator. Subclasses StructuralJuteTool only
    to reuse its injectable HTTP plumbing (_acquire/_get/_post) + _find_checks."""

    name = "jute_gen"

    def __init__(
        self,
        *,
        http_client: Any | None = None,
        timeout: float = 90.0,
        template_provider: Any | None = None,
        persist_client: Any | None = None,
    ) -> None:
        super().__init__(http_client=http_client, timeout=timeout)
        self._template_cache: tuple[str, dict] | None = None  # (template, gen_meta)
        # engine="dspy": author the template via this Callable[[], str] (a bench-gated
        # DSPy generator) instead of the etlp Copilot's POST /mappings/generate.
        self._template_provider = template_provider
        # reference.persist: an EtlpJuteClient used to persist the accepted template as a
        # mapping (-> id/title), so it's applicable via the wired StructuralJuteTool.
        self._persist_client = persist_client

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        base = str(ref["service"]).rstrip("/")
        resource = self._to_resource(
            None, base, ref.get("artifact_kind", "fhir_patient"), claim.subject
        )
        client, owns = self._acquire(client_base=base)
        try:
            template, gen_meta = self._resolve_template(client, base, ref)
            manifest: dict = {
                "tool": self.name,
                "deterministic": gen_meta.get("source") == "pinned",
                "service": base,
                "template_source": gen_meta.get("source"),
                "template_sha256": _sha(template),
                "spec_version": spec.version,
                "artifact_kind": ref.get("artifact_kind"),
            }
            manifest.update({k: v for k, v in gen_meta.items() if k != "source"})
            if gen_meta.get("drift"):
                return VerificationResult(
                    conforms=None,
                    evidence={"error": "pinned template hash drifted; refusing", **gen_meta},
                    manifest=manifest,
                )

            applied = self._post(
                client,
                base,
                "/mappings/test-template",
                {"template": template, "sample_input": resource},
            )
            compiled = bool(applied.get("compiled")) if isinstance(applied, dict) else False
            if not compiled:
                manifest["compiled"] = False
                return VerificationResult(
                    conforms=None,
                    evidence={
                        "error": "generated template did not compile",
                        "detail": (applied or {}).get("error"),
                    },
                    manifest=manifest,
                )
            checks = self._find_checks(applied.get("output"))
            failed = [c for c in checks if str(c.get("status", "")).lower() == "fail"]
            conforms = len(failed) == 0
            manifest.update(compiled=True, checks_total=len(checks), failed_count=len(failed))
            evidence = {
                "artifact_kind": ref.get("artifact_kind"),
                "checks_total": len(checks),
                "failed": [
                    {"name": c.get("name"), "field": c.get("field"), "message": c.get("message")}
                    for c in failed
                ],
            }
            return VerificationResult(conforms=conforms, evidence=evidence, manifest=manifest)
        finally:
            if owns:
                client.close()

    def _resolve_template(self, client: Any, base: str, ref: dict) -> tuple[str, dict]:
        if self._template_cache is not None:
            return self._template_cache

        template, meta = self._author_template(client, base, ref)
        # persist-once: the accepted template becomes a live mapping (id/title) so it can be
        # applied deterministically via StructuralJuteTool. Skipped on drift (never persist a
        # pin that no longer matches its hash). Persist failures are recorded, not fatal.
        if ref.get("persist") and self._persist_client is not None and not meta.get("drift"):
            try:
                p = self._persist_client.persist_or_update(
                    ref.get("persist_title", "fhir-us-core-patient-validator-dspy"), template
                )
                meta["persisted_mapping_id"] = p["id"]
                meta["persisted_title"] = p["title"]
                meta["persist_action"] = p["action"]
            except Exception as exc:  # noqa: BLE001
                meta["persist_error"] = f"{type(exc).__name__}: {exc}"
        self._template_cache = (template, meta)
        return self._template_cache

    def _author_template(self, client: Any, base: str, ref: dict) -> tuple[str, dict]:
        pinned = ref.get("pinned_template")
        if pinned:
            meta = {"source": "pinned"}
            want = ref.get("pinned_template_sha256")
            if want and _sha(pinned) != want:
                meta["drift"] = True
                meta["observed_sha256"] = _sha(pinned)
                meta["pinned_sha256"] = want
            return pinned, meta

        gen = ref.get("generate")
        if not gen:
            raise RuntimeError("jute_gen: reference needs either 'pinned_template' or 'generate'")
        return self._generate(client, base, gen)

    def _generate(self, client: Any, base: str, gen: dict) -> tuple[str, dict]:
        # engine="dspy": author via the injected bench-gated DSPy generator, not the Copilot.
        if gen.get("engine") == "dspy":
            if self._template_provider is None:
                raise RuntimeError(
                    "jute_gen: engine='dspy' requires a template_provider "
                    "(Callable[[], str] returning a bench-accepted JUTE template)"
                )
            from .jute_dspy import strip_fences

            template = self._template_provider()
            if not template or not str(template).strip():
                raise RuntimeError("jute_gen: dspy template_provider returned an empty template")
            return strip_fences(str(template)), {"source": "generated", "engine": "dspy"}

        existing = ""
        if gen.get("base_validator"):
            mappings = self._get(client, base, "/mappings")
            m = self._resolve(mappings, {"by": "title", "value": gen["base_validator"]})
            existing = ((m or {}).get("content") or {}).get("yaml", "") if m else ""

        sample = gen.get("sample_input")
        if sample is None:
            raise RuntimeError(
                "jute_gen: generate.sample_input required (a representative resource)"
            )
        expected = gen.get("expected_output")
        if expected is None and existing:
            # exemplar = the base validator's output on the sample (a valid sample->output pair)
            tt = self._post(
                client,
                base,
                "/mappings/test-template",
                {"template": existing, "sample_input": sample},
            )
            expected = tt.get("output") if isinstance(tt, dict) else None
        if expected is None:
            raise RuntimeError(
                "jute_gen: generate.expected_output required when no base_validator to derive it"
            )

        body = {
            "sample_input": sample,
            "expected_output": expected,
            "description": gen["description"],
            "source_format": gen.get("source_format", "fhir"),
            "target_platform": gen.get("target_platform", "fhir-validation"),
        }
        if existing:
            body["existing_template"] = existing
        resp = self._post(client, base, "/mappings/generate", body)
        template = (resp or {}).get("template") if isinstance(resp, dict) else None
        if not template:
            raise RuntimeError(
                f"jute_gen: Copilot returned no template (confidence={(resp or {}).get('confidence')!r})"
            )
        return template, {
            "source": "generated",
            "confidence": resp.get("confidence"),
            "retries_used": resp.get("retries_used"),
            "base_validator": gen.get("base_validator"),
        }
