"""Narrative pack — the deterministic FLOOR executors (NARR-3).

The domain-agnostic grounding engine (``lithrim_bench/harness/grounding.py`` +
``lithrim_bench/verification/``) supplies the generic machinery — the ``ground()``
orchestrator, the floor registry, the ``VerificationTool`` base, and the dispatch in
``_run_floor`` (artifact guard, ``Claim``/``VerificationSpec`` construction,
``tool.verify``). This module is the narrative pack's contribution: three pure-stdlib
floor tools that INJECT a BLOCK the council missed (the FLOOR direction), behind the
pack executor-registration interface (``harness.pack.load_pack_floors`` →
``grounding.floor_executors()`` merges this module's ``FLOOR_EXECUTORS``). It follows
the same pack-floor pattern as the other domain packs' ``floors.py`` modules — pure-
stdlib, no httpx/dspy at import; the lambda tool factories accept-and-ignore the
injected ``http_client``.

The dependency points **pack → core** only (this imports core primitives; the core
loads this LAZILY on first grounding use, by which point all core modules are
imported — so there is no cycle). These floors are ``in_process`` (NOT ``:3031``), so
``SERVICE_CONTRACT_TYPES`` is deliberately absent and ``SUPPRESS_EXECUTORS`` is empty.

What lives here — the ACTIVE floor set is 3 codes (``FLOOR_EXECUTORS``):
  * ``bracket_leak``       — :class:`BracketLeakTool`: a leaked instruction marker.
  * ``silent_degradation`` — :class:`SilentDegradationTool`: a non-``stop`` generation
    silently demoted to the baseline yet shipped as final (the day-one headline; reads
    provenance off the case row via ``claim.source``, NOT the artifact).
  * ``value_presence``     — :class:`ValuePresenceTool` (FAUTH-4 / NARR-FLOOR-1): a value
    spoken in a ``source_path`` (default ``transcript``) is MISSING from the artifact — the
    the omission-completeness floor (the inverse of a presence-grounding check).

``length_violation`` is RETAINED-BUT-UNATTACHED (NARR-4 / S-BS-NARR3-3): the
:class:`LengthViolationTool` class + ``_length_reference`` + the ``TOOL_LENGTH_VIOLATION``
name registration stay, but the executor is NOT in ``FLOOR_EXECUTORS``. The check was
demoted to the ``policy_judge`` lens (it is already a ``policy_judge`` lens code +
question ordinal 2): the shipped per-scene record carries only ``clean_text`` with no
separable preamble span, so counting the whole scene against a 3-4 *preamble* band
false-blocks legitimate enhanced scenes — preamble-length is not true-by-construction
on the shipped record. The tool is kept for a zero-code re-attach if a future record
ever carries a separable preamble span (option a).
"""

from __future__ import annotations

import re
from typing import Any

from lithrim_bench.harness.grounding import FloorExecutor
from lithrim_bench.verification.spec import (
    TOOL_BRACKET_LEAK,
    TOOL_LENGTH_VIOLATION,
    TOOL_SILENT_DEGRADATION,
    Claim,
    VerificationResult,
    VerificationSpec,
)
from lithrim_bench.verification.tools import VerificationTool

# Default instruction-marker shape: an uppercase-led directive inside square brackets,
# e.g. "[READER FEELING: tense]" / "[TONE]". MARKER-TARGETED on purpose — it does NOT
# match any bracket pair, so a legitimate in-prose lowercase bracket ("[it was faded]")
# does not false-BLOCK. SME-pinnable via the optional reference "pattern" key.
_DEFAULT_MARKER = r"\[[A-Z][^\]]*\]"

# Sentence terminators for the length count (drop empties after the split).
_SENTENCE_SPLIT = re.compile(r"[.!?]+")


# --------------------------------------------------------------------------- #
# BracketLeakTool — a leaked instruction marker in the shipped scene
# --------------------------------------------------------------------------- #
class BracketLeakTool(VerificationTool):
    """Floor: the generated scene leaks an instruction MARKER — bracketed directive text
    that is an input to the model and must never reach the reader. ``conforms=False`` on a
    marker match, ``True`` on clean prose, ``None`` on an empty/non-str subject (never
    flips by silence).

    Marker-targeted, NOT any-bracket: the pinned ``pattern`` (default an uppercase-led
    bracketed directive) leaves a legitimate in-prose lowercase bracket alone.

    reference = {"pattern": <optional SME-pinned marker regex>}  # default uppercase-led
    """

    name = TOOL_BRACKET_LEAK

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        pattern = spec.reference.get("pattern", _DEFAULT_MARKER)
        manifest = {
            "tool": self.name,
            "deterministic": True,
            "spec_version": spec.version,
            "locus": spec.locus,
            "pattern": pattern,
        }
        subject = claim.subject
        if not isinstance(subject, str) or not subject.strip():
            return VerificationResult(
                conforms=None,
                evidence={"reason": "empty or non-text subject; nothing to scan"},
                manifest=manifest,
            )
        match = re.search(pattern, subject)
        if match is None:
            return VerificationResult(
                conforms=True,
                evidence={"matched_marker": None},
                manifest=manifest,
            )
        return VerificationResult(
            conforms=False,
            evidence={"matched_marker": match.group(0)},
            manifest=manifest,
        )


# --------------------------------------------------------------------------- #
# LengthViolationTool — the preamble is not the required sentence count
# --------------------------------------------------------------------------- #
class LengthViolationTool(VerificationTool):
    """Floor: the added preamble must be within ``[min_sentences, max_sentences]`` (the
    SME-pinned bounds). ``conforms=False`` outside the band, ``True`` in-range, ``None``
    on empty (never flips by silence).

    reference = {"min_sentences": int, "max_sentences": int}  # required, SME-pinned
    """

    name = TOOL_LENGTH_VIOLATION

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        lo, hi = int(ref["min_sentences"]), int(ref["max_sentences"])
        manifest = {
            "tool": self.name,
            "deterministic": True,
            "spec_version": spec.version,
            "locus": spec.locus,
            "min_sentences": lo,
            "max_sentences": hi,
        }
        subject = claim.subject
        if not isinstance(subject, str) or not subject.strip():
            return VerificationResult(
                conforms=None,
                evidence={"reason": "empty or non-text subject; nothing to count"},
                manifest=manifest,
            )
        n = len([s for s in _SENTENCE_SPLIT.split(subject) if s.strip()])
        conforms = lo <= n <= hi
        return VerificationResult(
            conforms=conforms,
            evidence={"sentence_count": n, "min_sentences": lo, "max_sentences": hi},
            manifest=manifest,
        )


# --------------------------------------------------------------------------- #
# SilentDegradationTool — a non-`stop` generation silently demoted to baseline
# --------------------------------------------------------------------------- #
class SilentDegradationTool(VerificationTool):
    """Floor (the day-one headline): a scene that was content-filtered / truncated (its
    ``finish_reason != "stop"``) AND silently demoted to the baseline generation
    (``source == "baseline"``) yet shipped as a complete, final result. Reads the
    provenance off the CASE ROW via ``claim.source`` (NOT the artifact text).

    ``conforms=False`` iff ``finish_reason != "stop"`` AND ``source == "baseline"`` (a
    silent demotion). ``True`` on a complete generation (``stop``/``enhanced``) or a
    non-``stop`` that was NOT demoted. ``None`` when either provenance field is absent —
    never flip by silence; the floor refuses to manufacture a finding from missing data.

    reference = {}  # the demotion rule is pinned in the tool (no SME reference needed)
    """

    name = TOOL_SILENT_DEGRADATION

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        source = claim.source or {}
        finish_reason = source.get("finish_reason")
        src = source.get("source")
        manifest = {
            "tool": self.name,
            "deterministic": True,
            "spec_version": spec.version,
            "locus": spec.locus,
        }
        if finish_reason is None or src is None:
            return VerificationResult(
                conforms=None,
                evidence={
                    "reason": "provenance absent (finish_reason/source); inconclusive",
                    "finish_reason": finish_reason,
                    "source": src,
                },
                manifest=manifest,
            )
        demoted = finish_reason != "stop" and src == "baseline"
        return VerificationResult(
            conforms=not demoted,
            evidence={"finish_reason": finish_reason, "source": src, "silent_demotion": demoted},
            manifest=manifest,
        )


# --------------------------------------------------------------------------- #
# reference builders — lift each tool's SME-pinned reference out of the decl params
# --------------------------------------------------------------------------- #
def _bracket_reference(params: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {}
    if params.get("pattern"):
        ref["pattern"] = params["pattern"]
    return ref


def _length_reference(params: dict[str, Any]) -> dict[str, Any]:
    return {"min_sentences": params["min_sentences"], "max_sentences": params["max_sentences"]}


def _silent_degradation_reference(params: dict[str, Any]) -> dict[str, Any]:
    return {}


# ── the pack executor-registration interface (PACK-3 D1; FLOOR direction) ───────────
# Module-level declarative dicts: no execution at import, inspectable, import-clean. The
# core merges FLOOR_EXECUTORS into grounding.floor_executors() on first grounding use
# (lazy). These floors are in_process (pure-stdlib) — the lambdas accept-and-ignore the
# injected http_client; no SERVICE_CONTRACT_TYPES (no :3031). Narrative has no suppress
# executors.
SUPPRESS_EXECUTORS: dict[str, Any] = {}
FLOOR_EXECUTORS: dict[str, FloorExecutor] = {
    TOOL_BRACKET_LEAK: FloorExecutor(
        tool_factory=lambda http_client: BracketLeakTool(),
        reference_builder=_bracket_reference,
    ),
    TOOL_SILENT_DEGRADATION: FloorExecutor(
        tool_factory=lambda http_client: SilentDegradationTool(),
        reference_builder=_silent_degradation_reference,
    ),
    # CORE-FLOOR-1: value_presence RELOCATED to core (lithrim_bench/verification/tools.py +
    # grounding._core_floor_executors) — a domain-agnostic completeness floor available to EVERY
    # pack incl. healthcare; narrative still gets it via the core merge in grounding.floor_executors().
    # LENGTH_VIOLATION is NOT attached (NARR-4 / S-BS-NARR3-3): demoted to the policy_judge
    # lens. The LengthViolationTool class + _length_reference + the TOOL_LENGTH_VIOLATION
    # name registration are RETAINED-BUT-UNATTACHED for a zero-code re-attach if a future
    # record ever carries a separable preamble span (option a).
}
