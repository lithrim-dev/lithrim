"""Uniform value objects for the WS-3 verification toolbox.

A `VerificationTool` answers ONE question about a `Claim` against an SME-pinned
`VerificationSpec`: does the artifact CONFORM to the pinned reference on this
claim's locus? The answer is tri-state (`VerificationResult.conforms`), and that
tri-state is the atom of the false-negative guardrail in `router.py`:

    conforms is True  -> violation DISPROVEN  -> the flag MAY be cleared
    conforms is False -> violation CONFIRMED   -> the flag is kept / raised
    conforms is None  -> inconclusive / N/A    -> the flag stays OPEN (never cleared)

A tool never clears a flag by silence. The `spec` is the SME-pinnable reference
(mapping-id+hash / oracle-path / corpus+as-of) authored per question in the
ontology (WS-1); pinning it is what makes a verdict reproducible + auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# claim_type constants
STRUCTURAL_CONFORMANCE = "structural_conformance"
RECORD_PRESENCE = "record_presence"
REFERENCE_CONFORMANCE = "reference_conformance"

# tool names (== VerificationTool.name; == VerificationSpec.tool)
TOOL_IN_ROW = "in_row"
TOOL_STRUCTURAL_JUTE = "structural_jute"
TOOL_RECORD_RAG = "record_rag"
TOOL_KB_RAG = "kb_rag"
TOOL_JUTE_GEN = "jute_gen"
TOOL_DOSAGE_GROUNDING = "dosage_grounding"
# NARR-3 (Option A — minimal core registration): the 3 narrative floor tool-names.
# The CLOSED ``_KNOWN_TOOLS`` set hard-rejects any unknown ``VerificationSpec.tool`` at
# construction, so a pack floor (its EXECUTOR ships in ``packs/<pack>/floors.py``, like
# the clinical ``dosage_grounding``) cannot register a NEW ``contract_type`` without a
# small ADDITIVE core edit here. Option B (a pack-extensible registry) was NOT chosen.
TOOL_BRACKET_LEAK = "bracket_leak"
TOOL_LENGTH_VIOLATION = "length_violation"
TOOL_SILENT_DEGRADATION = "silent_degradation"
# FAUTH-4 / NARR-FLOOR-1: the inverse-direction ``value_presence`` completeness floor —
# a value spoken in a ``source_path`` (default ``transcript``) must appear in the artifact;
# absent → inject a BLOCK the council missed (the case-10 erased-refusal mechanism). The NAME
# is the "one unavoidable additive line" in core (SPEC_CLINICAL_SCRIBE_SELF_SERVE.md:122); the tool
# class + executor ship pack-local (``packs/narrative/floors.py``). After this, authoring is
# params-only and a second inverse floor needs no new code.
TOOL_VALUE_PRESENCE = "value_presence"
# CONCEPT-PRESERVATION: the generalizing successor to value_presence's lexical pin — it consumes
# two ingest-pinned concept lists (a "stated" list vs a "noted" list) and grounds them by code
# (equality or subsumption) via the pack's terminology tool, so a paraphrase still grounds. The
# tool class + executor ship PACK-LOCAL; this NAME + its required-keys row are the one additive
# core line (same minimal-registration pattern as value_presence). Domain-neutral by construction.
TOOL_CONCEPT_PRESERVATION = "concept_preservation"
# CONN-WEBSEARCH-1: the web-search reference connector (community release, §4). It is
# NON-AUTHORITATIVE BY CONSTRUCTION — web results are unverifiable, so its executor ALWAYS
# resolves ``conforms=None`` (inconclusive) and merely ATTACHES retrieved citations/snippets +
# a ``web_support`` assessment as evidence for the SME/withstands-gate to weigh; it can never
# clear or raise a finding. The tool class + executor are generic core; this NAME + its
# required-keys row are the additive registration (the documented minimal pattern). Domain-neutral.
TOOL_WEB_SEARCH = "web_search"
# REPRO-1 R4a/R4b: the BOUNDED-EXTRACTION floors. An LM answers ONE narrow, SME-pinned
# question (temperature 0, K-repeat, majority-gated); the VERDICT is deterministic logic over
# the extracted booleans, conservative (unconfirmed → decline). The manifest is honest
# (``deterministic: False`` + the extraction model + k) — an extraction floor never
# masquerades as a lookup. Core + domain-agnostic: the fact/statement text is UI-authored data.
TOOL_FACT_PRESERVATION = "fact_preservation"
TOOL_SPEAKER_ATTRIBUTION = "speaker_attribution"
_KNOWN_TOOLS = {
    TOOL_IN_ROW,
    TOOL_STRUCTURAL_JUTE,
    TOOL_RECORD_RAG,
    TOOL_KB_RAG,
    TOOL_JUTE_GEN,
    TOOL_DOSAGE_GROUNDING,
    TOOL_BRACKET_LEAK,
    TOOL_LENGTH_VIOLATION,
    TOOL_SILENT_DEGRADATION,
    TOOL_VALUE_PRESENCE,
    TOOL_CONCEPT_PRESERVATION,
    TOOL_WEB_SEARCH,
    TOOL_FACT_PRESERVATION,
    TOOL_SPEAKER_ATTRIBUTION,
}

# per-tool REQUIRED reference keys — the SME-pinnable reference's minimum shape
_REQUIRED_REFERENCE_KEYS: dict[str, set[str]] = {
    TOOL_IN_ROW: {"oracle_path", "extractor", "match"},
    TOOL_STRUCTURAL_JUTE: {"service", "mapping_selector", "artifact_kind"},
    TOOL_RECORD_RAG: {"client", "filters"},
    # kb_rag: namespace into the backend KB index (deployment-configured); index resolved
    # from reference.index / env. Optional: regulation_filter, top_k, rerank, predicate,
    # match_field, expected, min_score, pinned{corpus_version,embedding_model_version,...}.
    TOOL_KB_RAG: {"namespace"},
    # jute_gen: generate-from-sample structural validator via :3031 Copilot. Template
    # comes from reference.pinned_template OR reference.generate{...} (validated at runtime).
    TOOL_JUTE_GEN: {"service", "artifact_kind"},
    # dosage_grounding: deterministic, offline. The pinned dose-extraction regex is the
    # SME-pinnable reference; transcript_path / record_path (the grounding sources) are
    # optional and default to "transcript" / absent.
    TOOL_DOSAGE_GROUNDING: {"dose_regex"},
    # NARR-3 narrative floors (deterministic, offline, in_process). bracket_leak +
    # silent_degradation take no required reference (the marker pattern / the demotion
    # rule are pinned in the tool; an empty set passes the missing-keys check vacuously).
    # length_violation pins the SME's preamble bounds.
    TOOL_BRACKET_LEAK: set(),
    TOOL_LENGTH_VIOLATION: {"min_sentences", "max_sentences"},
    TOOL_SILENT_DEGRADATION: set(),
    # value_presence: the SME pins ``value_regex`` (the required token extractor); ``source_path``
    # is optional (default ``transcript``). The artifact under test is ``artifacts[0].content``.
    TOOL_VALUE_PRESENCE: {"value_regex"},
    # concept_preservation: the SME pins the two concept-list paths (``stated_path`` / ``noted_path``);
    # the terminology ``tool`` is optional (the pack defaults it). The inject coordinates
    # (``inject_flag_code`` / ``inject_severity``) are contract PARAMS read by the floor injector,
    # not reference keys — exactly like dosage_grounding.
    TOOL_CONCEPT_PRESERVATION: {"stated_path", "noted_path"},
    # web_search: the SME pins ``query`` (the claim/query selector); ``service`` / ``api_key`` /
    # ``top_k`` / ``min_score`` / ``match`` are optional (mirrors kb_rag's ``{"namespace"}``).
    # NON-AUTHORITATIVE: it attaches evidence, it never clears or raises a finding.
    TOOL_WEB_SEARCH: {"query"},
    # fact_preservation: the SME pins the FACT that must be preserved (prose — the narrow
    # extraction question). Optional: source_path (default transcript), k, extractor_role.
    TOOL_FACT_PRESERVATION: {"fact"},
    # speaker_attribution: the SME pins the STATEMENT whose attribution is checked. Optional:
    # source_path, k, extractor_role.
    TOOL_SPEAKER_ATTRIBUTION: {"statement"},
}


@dataclass(frozen=True)
class Claim:
    """The unit under verification: a council flag's assertion about a span of an artifact."""

    claim_type: str
    flag_code: str | None  # the council flag this claim adjudicates (None for pure structural)
    subject: Any  # artifact text | extracted items | the value under test
    locus: str = ""  # the named section the flag is ABOUT — claim-scoping
    source: dict = field(default_factory=dict)  # provenance slice of the case row


@dataclass
class VerificationResult:
    """A tool's tri-state answer + human-auditable evidence + the determinism manifest."""

    conforms: bool | None
    evidence: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)

    @property
    def disposition(self) -> str:
        if self.conforms is True:
            return "CONFORMS"
        if self.conforms is False:
            return "VIOLATION"
        return "INCONCLUSIVE"


@dataclass(frozen=True)
class VerificationSpec:
    """SME-pinned reference for one claim type. Authored per question in the ontology.

    `applies_to_flags` is the routing key (which council flags this adjudicates).
    `reference` is the tool-specific pinned reference; its required keys are
    validated against `_REQUIRED_REFERENCE_KEYS` so a malformed spec fails loudly
    at construction rather than silently mis-grounding a verdict.
    """

    tool: str
    applies_to_flags: tuple[str, ...]
    locus: str
    reference: dict
    version: str = "v0"

    def __post_init__(self) -> None:
        if self.tool not in _KNOWN_TOOLS:
            raise ValueError(f"unknown tool {self.tool!r}; known={sorted(_KNOWN_TOOLS)}")
        # normalize applies_to_flags to a tuple (frozen -> use object.__setattr__)
        if not isinstance(self.applies_to_flags, tuple):
            object.__setattr__(self, "applies_to_flags", tuple(self.applies_to_flags))
        if not isinstance(self.reference, dict):
            raise TypeError("reference must be a dict")
        missing = _REQUIRED_REFERENCE_KEYS[self.tool] - set(self.reference)
        if missing:
            raise ValueError(f"{self.tool} spec missing reference keys: {sorted(missing)}")
        if self.tool == TOOL_STRUCTURAL_JUTE:
            sel = self.reference.get("mapping_selector")
            if not (isinstance(sel, dict) and sel.get("by") in {"title", "id"} and "value" in sel):
                raise ValueError(
                    "structural_jute reference.mapping_selector must be "
                    "{'by': 'title'|'id', 'value': ...}"
                )
