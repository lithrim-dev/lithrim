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
