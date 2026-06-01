"""Vendored compliance council — the validated v2 consensus IP, Mongo-free.

Ported **verbatim** from ``lithrim-backend@493b533`` (WS-6c, bench-salvage).
Only mechanical adaptation was applied (``app.*`` imports → package-relative;
``_ROLE_PROMPTS_DIR`` → the package-local ``council_roles/``). The consensus
arithmetic — tier tables, ownership gating, PHI false-positive suppression,
per-pillar worst-of combine, the v2 llama-veto, and None-confidence tolerance —
is reproduced byte-for-byte. See ``docs/specs/RECOMPOSITION_PLAN_ws6.md`` §5/§6.

Modules
-------
- ``compliance_council`` — ``ComplianceCouncil`` + the ported ``_apply_consensus``
  consensus engine, the tier/owner/pillar tables, ``extract_verdict_confidence``
  (None-tolerant), ``build_prompt``. Requires the ``[council]`` extra
  (``openai`` + ``tenacity``); the OpenAI/Azure client is constructed lazily and
  makes no network call at import time.
- ``safety_flags`` — the second tables file: ``SafetyFlagDefinition``,
  ``FailureType``, ``SAFETY_FLAG_TO_FAILURE_TYPE``, ``FAILURE_TYPE_SEVERITY``,
  ``get_flag_prompt_section``. Pure-pydantic, importable on the offline core
  (no ``openai``). Imported directly by ``scripts/seed_ontology.py`` — this
  ``__init__`` deliberately does NOT eagerly import ``compliance_council`` so
  that path stays openai-free.
- ``llm_provider`` — the salvaged Azure/OpenAI client factory (deployment-id
  substitution reaches Mistral-Large-3 + Llama-4-Maverick).
- ``phi_redaction`` — ``sanitize_prompt`` (PHI redaction before any LLM call).
- ``settings`` — the 16-field council config subset; defaults to v2.

v2 production trio (``COMPLIANCE_COUNCIL_VERSION == "v2"``)
----------------------------------------------------------
``risk_judge`` (gpt-4.1) · ``policy_judge`` (Mistral-Large-3) ·
``faithfulness_judge`` (Llama-4-Maverick). The ``behavior_judge.txt`` and
``source_message_judge.txt`` role prompts are carried for provenance/v1 but are
**NOT** in the v2 trio (``source_message_judge`` is the declared-but-not-running
owner per the taxonomy snapshot). They still appear in ``_TIER1_OWNERS`` by
design — that table is ported verbatim and its non-trio owners are simply
dormant under v2.

The per-judge dict seam (the §6 hybrid boundary)
------------------------------------------------
``ComplianceCouncil._apply_consensus`` consumes a list of per-judge result
dicts shaped as::

    {
        "model": <judge role name>,        # e.g. "risk_judge"
        "decision": "approve"|"needs_review"|"reject",
        "confidence": float | None,        # None for Mistral (no logprobs) — never coerce to 1.0/0.0
        "findings": [{"taxonomy_code": str, "evidence_spans": [{...}]}],
        "errors": [],                      # non-empty ⇒ judge excluded from consensus
    }

This is the stable boundary a future DSPy-rebuilt judge layer (WS-6c-DSPy) must
emit; the ported consensus math wraps DSPy or non-DSPy judges identically. WS-6c
ports the imperative fan-out as-is and only documents this seam — no refactor.
"""
