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
_KNOWN_TOOLS = {
    TOOL_IN_ROW,
    TOOL_STRUCTURAL_JUTE,
    TOOL_RECORD_RAG,
    TOOL_KB_RAG,
    TOOL_JUTE_GEN,
    TOOL_DOSAGE_GROUNDING,
}

# per-tool REQUIRED reference keys — the SME-pinnable reference's minimum shape
_REQUIRED_REFERENCE_KEYS: dict[str, set[str]] = {
    TOOL_IN_ROW: {"oracle_path", "extractor", "match"},
    TOOL_STRUCTURAL_JUTE: {"service", "mapping_selector", "artifact_kind"},
    TOOL_RECORD_RAG: {"client", "filters"},
    # kb_rag: namespace into the backend KB index (hipaa-compliancev2); index resolved
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
}


@dataclass(frozen=True)
class Claim:
    """The unit under verification: a council flag's assertion about a span of an artifact."""

    claim_type: str
    flag_code: str | None  # the council flag this claim adjudicates (None for pure structural)
    subject: Any  # artifact text | extracted items | the value under test
    locus: str = ""  # the section the flag is ABOUT ("PMH"/"dosage"/...) — claim-scoping
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
