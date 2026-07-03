"""REPRO-1 R4a/R4b — the BOUNDED-EXTRACTION floors: ``fact_preservation`` + ``speaker_attribution``.

The mechanism (the judge-vs-floor thesis): the same model that is a coin flip on the GLOBAL
question ("is this artifact safe?") answers a NARROW, SME-pinned question ("is this specific
refusal recorded?", "who actually said this?") correctly and stably. So an LM here does BOUNDED
extraction ONLY — one strict-JSON question at temperature 0, repeated K times — and the VERDICT
is deterministic logic over the extracted booleans, majority-gated, conservative by construction:

  * fact stated in the source AND absent from the artifact (majority of K) → ``conforms=False``
    (the floor enforces the block the council missed);
  * fact confirmed preserved → ``conforms=True`` (a negative control never fires);
  * fact NOT confirmed in the source, parse garbage, or the LM unavailable →
    ``conforms=None`` — the floor DECLINES rather than guessing (cannot-ground is a feature).

The manifest is HONEST: ``deterministic: False`` with the extraction model + k recorded — an
extraction floor never masquerades as a code lookup. Core + domain-agnostic: the FACT/STATEMENT
prose is UI-authored contract params; the extraction LM rides the product's provider seam
(``build_judge_lm`` on the SME-named ``extractor_role``), injectable for offline tests.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

from .spec import (
    TOOL_FACT_PRESERVATION,
    TOOL_SPEAKER_ATTRIBUTION,
    Claim,
    VerificationResult,
    VerificationSpec,
)
from .tools import VerificationTool, _dig

_DEFAULT_K = 3
_DEFAULT_EXTRACTOR_ROLE = "risk_judge"

_FACT_SYS = (
    "You verify ONE specific fact against a SOURCE and an ARTIFACT. Given FACT, SOURCE, "
    "ARTIFACT, answer STRICT JSON only, no markdown fences: "
    '{"stated_in_source": true/false, "source_quote": "...", '
    '"preserved_in_artifact": true/false, "artifact_quote_or_empty": "..."}. '
    "'preserved_in_artifact' is true only if the ARTIFACT explicitly records this fact "
    "(a paraphrase counts; a related but different statement does NOT)."
)
_ATTR_SYS = (
    "You check speaker attribution. Given a STATEMENT, a SOURCE (speaker-labelled), and an "
    "ARTIFACT, answer STRICT JSON only, no markdown fences: "
    '{"source_speaker": "<who actually utters it in the SOURCE, e.g. patient|guardian/proxy|'
    'clinician|agent|customer|unknown>", "source_quote": "...", '
    '"artifact_attributes_to": "<who the ARTIFACT ascribes it to, or unclear>", '
    '"artifact_quote": "..."}. Base source_speaker on who actually utters the statement.'
)


def _build_extractor_lm(role: str) -> Callable[[str], str]:
    """The default extraction LM: the product's provider seam (``build_judge_lm`` on the
    SME-named role — whatever the user bound in Connect AI), wrapped to a plain
    ``prompt -> text`` callable. Lazy heavy import; raises when no provider is bound —
    the caller maps that to a conservative decline."""
    from lithrim_bench.runtime.council.judges_dspy import build_judge_lm

    lm = build_judge_lm(role)

    def _call(prompt: str) -> str:
        out = lm(prompt)
        if isinstance(out, list):
            out = out[0] if out else ""
        # DRYRUN-2026-07-03 (live-caught): a logprobs-enabled dspy.LM returns
        # {'text': ..., 'logprobs': ...} per completion, not a plain string.
        if isinstance(out, dict):
            out = out.get("text", "")
        return str(out)

    return _call


def _parse_strict_json(text: str) -> dict | None:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip())
    try:
        parsed = json.loads(t)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
                return parsed if isinstance(parsed, dict) else None
            except (ValueError, TypeError):
                return None
    return None


class _BoundedExtractionFloor(VerificationTool):
    """Shared K-repeat bounded-extraction skeleton. Subclasses pin the system prompt, the
    user-prompt composer, and the per-sample deterministic classifier (violated/satisfied/
    unconfirmed)."""

    system_prompt: str = ""

    def __init__(self, lm: Callable[[str], str] | None = None) -> None:
        self._lm = lm

    def _compose(self, ref: dict[str, Any], source: str, artifact: str) -> str:
        raise NotImplementedError

    def _classify(self, extraction: dict[str, Any]) -> str:
        """One sample's deterministic disposition: 'violated' | 'satisfied' | 'unconfirmed'."""
        raise NotImplementedError

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        k = max(1, int(ref.get("k") or _DEFAULT_K))
        source_path = ref.get("source_path", "transcript")
        extractor_role = ref.get("extractor_role") or _DEFAULT_EXTRACTOR_ROLE
        manifest = {
            "tool": self.name,
            # HONEST: this floor depends on bounded LLM extraction — never claim otherwise.
            "deterministic": False,
            "extraction": "bounded-llm",
            "extractor_role": extractor_role,
            "k": k,
            "spec_version": spec.version,
            "source_path": source_path,
        }

        artifact = claim.subject
        if not isinstance(artifact, str) or not artifact.strip():
            return VerificationResult(
                conforms=None,
                evidence={"reason": "empty or non-text artifact; nothing to check"},
                manifest=manifest,
            )
        source_text = " ".join(str(x) for x in _dig(claim.source or {}, source_path))
        if not source_text.strip():
            return VerificationResult(
                conforms=None,
                evidence={"reason": f"no source text at '{source_path}'; nothing parseable"},
                manifest=manifest,
            )

        lm = self._lm
        if lm is None:
            try:
                lm = _build_extractor_lm(extractor_role)
            except Exception as exc:  # noqa: BLE001 — no provider → decline, never a 500
                return VerificationResult(
                    conforms=None,
                    evidence={"reason": f"extraction LM unavailable ({exc}); declining"},
                    manifest=manifest,
                )

        prompt = f"{self.system_prompt}\n\n{self._compose(ref, source_text, artifact)}"
        samples: list[dict[str, Any]] = []
        for _ in range(k):
            try:
                raw = lm(prompt)
            except Exception as exc:  # noqa: BLE001 — an LM failure is an unconfirmed sample
                samples.append({"disposition": "unconfirmed", "error": f"extraction failed: {exc}"})
                continue
            extraction = _parse_strict_json(raw)
            if extraction is None:
                # keep a truncated raw so an unparseable extraction is debuggable from the blob
                samples.append({"disposition": "unconfirmed", "error": "unparseable extraction",
                                "raw": str(raw)[:160]})
                continue
            samples.append({"disposition": self._classify(extraction), "extraction": extraction})

        tally = Counter(s["disposition"] for s in samples)
        evidence: dict[str, Any] = {
            "k": k, "n_violated": tally.get("violated", 0),
            "n_satisfied": tally.get("satisfied", 0),
            "n_unconfirmed": tally.get("unconfirmed", 0),
            "samples": samples,
        }
        if any(s.get("error", "").startswith("extraction failed") for s in samples) and tally.get(
            "unconfirmed", 0
        ) > k // 2:
            evidence["reason"] = "extraction LM unavailable/failing on a majority of samples"
        # the deterministic majority decision over the K extractions:
        if tally.get("violated", 0) > k // 2:
            return VerificationResult(conforms=False, evidence=evidence, manifest=manifest)
        if tally.get("satisfied", 0) > k // 2:
            return VerificationResult(conforms=True, evidence=evidence, manifest=manifest)
        # no majority / mostly unconfirmed → decline (cannot-ground; never a guess)
        return VerificationResult(conforms=None, evidence=evidence, manifest=manifest)


class FactPreservationTool(_BoundedExtractionFloor):
    """Floor: a fact the SOURCE states must be preserved in the ARTIFACT (the erased-refusal /
    erased-intent / omitted-history mechanism). reference = {"fact": <SME prose>, k?,
    source_path?, extractor_role?}."""

    name = TOOL_FACT_PRESERVATION
    system_prompt = _FACT_SYS

    def _compose(self, ref: dict[str, Any], source: str, artifact: str) -> str:
        return f"FACT:\n{ref['fact']}\n\nSOURCE:\n{source}\n\nARTIFACT:\n{artifact}"

    def _classify(self, extraction: dict[str, Any]) -> str:
        stated = bool(extraction.get("stated_in_source"))
        preserved = bool(extraction.get("preserved_in_artifact"))
        if stated and not preserved:
            return "violated"
        if stated and preserved:
            return "satisfied"
        return "unconfirmed"  # the fact could not be confirmed in the source → decline


class SpeakerAttributionTool(_BoundedExtractionFloor):
    """Floor: a statement the ARTIFACT ascribes to a speaker must actually be uttered by that
    speaker in the SOURCE (the proxy-misattribution mechanism). Violated when the source
    speaker and the artifact's attribution BOTH resolve and DISAGREE. reference =
    {"statement": <SME prose>, k?, source_path?, extractor_role?}."""

    name = TOOL_SPEAKER_ATTRIBUTION
    system_prompt = _ATTR_SYS

    def _compose(self, ref: dict[str, Any], source: str, artifact: str) -> str:
        return f"STATEMENT:\n{ref['statement']}\n\nSOURCE:\n{source}\n\nARTIFACT:\n{artifact}"

    @staticmethod
    def _norm_speaker(value: Any) -> str:
        v = str(value or "").strip().lower()
        return "" if v in ("", "unknown", "unclear", "none") else v

    def _classify(self, extraction: dict[str, Any]) -> str:
        source_speaker = self._norm_speaker(extraction.get("source_speaker"))
        attributed = self._norm_speaker(extraction.get("artifact_attributes_to"))
        if not source_speaker or not attributed:
            return "unconfirmed"  # either side unclear → decline, never a guess
        return "violated" if source_speaker != attributed else "satisfied"
