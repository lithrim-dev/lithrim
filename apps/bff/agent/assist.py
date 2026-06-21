"""FAUTH-3 (G2): the authoring-time ASSIST — deterministic prose→params suggestions.

Pure, stdlib-only, NO LLM / NO network. The agent uses this to SUGGEST a deterministic
``verification_contract``'s params, pre-filling the ContractBuilder; the human edits + Saves. The
suggestion is a DRAFT — it never auto-writes the ontology and never enters ``ground()`` (the spine
invariant; enforced by ``author_contract_handler`` staying emit-only + the human's Save being the
sole audited write).

``presence_check`` is the FAUTH-3 target: the core, pure-stdlib suppress executor
(``harness/grounding.py`` ``PresenceCheck``, params ``med_source``[req] / ``dosage_regex``[req] /
``token_min_len`` / ``noise_tokens``). The default ``dosage_regex`` / ``token_min_len`` /
``noise_tokens`` are cloned byte-exact from the canonical seeded presence_check
(``tests/fixtures/_core/ontology._core_house.json``) — proven values ``PresenceCheck`` consumes;
``med_source`` defaults to a chart path the agent overrides via ``source_hint`` (lifted from the
prose). SNOMED/code-set suggestion is FAUTH-3b (a net-new authoring-time terminology tool;
ground-by-CODE only) and deliberately NOT here.
"""

from __future__ import annotations

# Cloned byte-exact from the canonical seeded presence_check
# (tests/fixtures/_core/ontology._core_house.json) — the proven values PresenceCheck consumes.
_DOSAGE_REGEX = r"\b\d+(?:\.\d+)?\s*(?:%|x)\b"
_TOKEN_MIN_LEN = 4
_NOISE_TOKENS = ["the", "and", "that"]
# A generic chart-path default the agent overrides with the path it lifts from the prose
# (e.g. "transcript.text", "patient_profile.active_medications").
_DEFAULT_MED_SOURCE = "patient_record.medications"

# Canonical contract_type names (mirror lithrim_bench/verification/spec.py — kept as literals so
# this module stays stdlib-only, the FAUTH-3 invariant). presence_check = SUPPRESS (removes findings);
# value_presence = FLOOR (injects a BLOCK when a required/spoken value is absent).
_PRESENCE_CHECK = "presence_check"
_VALUE_PRESENCE = "value_presence"

# Cloned byte-exact from the proven case-10 value_presence floor (tests/test_governed_flip_case10.py):
# the dissent/refusal surface forms the completeness floor blocks on when the artifact erased them.
# A DRAFT default the human edits per their criterion (the executor default source_path is "transcript").
_VALUE_REGEX = r"don['’]?t want|refus\w*|declin\w*"
_DEFAULT_SOURCE_PATH = "transcript"


def suggest_presence_check_params(flag_code: str, source_hint: str | None = None) -> dict:
    """A deterministic ``presence_check`` param skeleton — the FAUTH-3 prose→params suggestion.

    Returns EXACTLY the ``PresenceCheck`` keys (``med_source``, ``dosage_regex``, ``token_min_len``,
    ``noise_tokens``) with sane, proven defaults — a DRAFT the human edits in the ContractBuilder
    before Saving. Deterministic: same ``(flag_code, source_hint)`` → same dict; no LLM, no network.
    ``source_hint`` is the chart path the agent lifts from the prose; absent → a generic default.
    ``flag_code`` is accepted for API symmetry + future per-flag tuning (the defaults are flag-agnostic
    today)."""
    return {
        "med_source": source_hint or _DEFAULT_MED_SOURCE,
        "dosage_regex": _DOSAGE_REGEX,
        "token_min_len": _TOKEN_MIN_LEN,
        "noise_tokens": list(_NOISE_TOKENS),
    }


def suggest_value_presence_params(flag_code: str, source_hint: str | None = None) -> dict:
    """A deterministic ``value_presence`` (FLOOR) param skeleton — the FAUTH-3 prose→params suggestion
    for the INVERSE direction (S-BS-143).

    ``value_presence`` is a FLOOR executor (``packs/narrative/floors.py`` ``ValuePresenceTool``): a
    required value spoken in ``source_path`` (default ``transcript``) that is MISSING from the artifact
    → inject a BLOCK the council missed (the case-10 erased-refusal mechanism). It INJECTS a finding,
    so unlike the presence_check SUPPRESS direction it can flip council-APPROVE → BLOCK. Returns the
    ValuePresence keys (``spec.py`` required: ``value_regex``; optional ``source_path``) with proven
    defaults — a DRAFT the human edits before Saving. ``source_hint`` (the chart path the value must be
    recorded in) sets ``source_path``; absent → the executor default. Deterministic: same input → same
    output; no LLM, no network."""
    return {
        "value_regex": _VALUE_REGEX,
        "source_path": source_hint or _DEFAULT_SOURCE_PATH,
    }


def suggest_contract_params(
    contract_type: str, flag_code: str, source_hint: str | None = None
) -> dict:
    """Route the prose→params suggestion to the skeleton for the agent-chosen DIRECTION: the FLOOR
    skeleton for ``value_presence``, else the ``presence_check`` SUPPRESS skeleton (the historical
    default — any other/unknown/empty type falls back to it, so callers that pass no type are
    byte-identical to the FAUTH-3 behavior). The LLM picks the direction; this fills the correct KEYS."""
    if contract_type == _VALUE_PRESENCE:
        return suggest_value_presence_params(flag_code, source_hint=source_hint)
    return suggest_presence_check_params(flag_code, source_hint=source_hint)
