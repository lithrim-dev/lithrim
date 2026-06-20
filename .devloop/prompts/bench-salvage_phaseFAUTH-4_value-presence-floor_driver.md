# FAUTH-4 / NARR-FLOOR-1 — the `value_presence` completeness floor (the case-10 PASS→BLOCK flip)

**Stream:** bench-salvage · **Phase:** FAUTH-4 · **Gate:** verdict-path (cold critic at close; NOT A-SAFE — no new SDK tool) · **Authored:** 2026-06-20

## Spec
- `docs/specs/SPEC_FLAG_AUTHORING_SELF_SERVE.md` §6 G4 + §7 (the presence/semantic FLOOR executor; OQ-3).
- `docs/specs/SPEC_CLINVERDICT_SELF_SERVE.md:122-124` (**NARR-FLOOR-1** — the precise, testable design + the offline `$0` EXIT).
- Motivation: `docs/research/REPORT_clinverdict_contrast_case10_2026-06-19.md` (the council MISSES the erased vaccine-refusal — Risk-Severity Blindness — and a deterministic floor is what closes it).

## The cut (smallest demonstrable, spec-faithful)
A parametric, pure-stdlib **`value_presence`** floor = the INVERSE of `dosage_grounding`: a required value spoken in a `source_path` (default `transcript`) must be PRESENT in the artifact (`artifacts[0].content`). Absent → inject a BLOCK the council missed; nothing parseable → inconclusive (never flip by silence).

**The deterministic oracle (OQ-3, no LLM):** `re.findall(value_regex, source_text)` extracts the required token(s); each must appear (normalized substring) in the artifact. `conforms=False` on a missing required token → `inject_flag_code`/`inject_severity`; `conforms=None` on no source / no token / empty artifact. The honest limit (stated, not hidden): surface-form matching is brittle vs paraphrase; the SNOMED-coded oracle is the richer swap-in (FAUTH-3b), SAME `FloorExecutor` interface.

## Why this is moat-clean (CONFIRMED by reading the code)
- The `ground()` floor loop (`grounding.py:654-676`) ALREADY does the tri-state (`False`→inject, `None`→stands, `True`→no-op) → **zero loop edits**.
- Tool + executor ship **pack-local** in `packs/narrative/floors.py` (BracketLeakTool template); only the NAME is registered in core `spec.py` (`_KNOWN_TOOLS` + `_REQUIRED_REFERENCE_KEYS` — the one additive line).
- Both `floor_executors()` equality snapshots (`tests/test_plugin_phase1.py:77`, `tests/bff/test_grounding_contract_gate.py:269`) run under pack=healthcare/`_core` → a narrative-pack-local floor does NOT perturb them (CONFIRMED). Making it *core* would break both → decisive for pack-local (= the spec).
- The 4 moat files (`compliance_council.py` / `signals.py` / `withstands.py` / `judge_metric.py`) and `grounding.py` itself stay **byte-frozen**. No new SDK-MCP tool → no A-SAFE widening; tool count stays 20.

## Deliverables
1. `lithrim_bench/verification/spec.py` — additive: `TOOL_VALUE_PRESENCE = "value_presence"`, add to `_KNOWN_TOOLS`, `_REQUIRED_REFERENCE_KEYS[TOOL_VALUE_PRESENCE] = {"value_regex"}` (`source_path` optional, default `transcript`).
2. `packs/narrative/floors.py` — `ValuePresenceTool(VerificationTool)` (reuses core `_dig`/`_norm`) + `_value_presence_reference` + register `value_presence` in `FLOOR_EXECUTORS`.
3. `tests/test_value_presence_floor.py` (NEW, RED-first) — A1 unit tri-state · A2 dotted `source_path` · A3 `_KNOWN_TOOLS` additive (9 prior intact) · A4 in-process `ground()` flip (`@_NEEDS_NARRATIVE_PACK`: violation→BLOCK, clean→PASS, inconclusive→stands) · A5 subprocess grade under pack=narrative (always-runs durable flip proof + zero `packs/healthcare` reads).

## Acceptance (the spec EXIT)
- A `contract_type='value_presence'` entry grades a crafted pair offline/`$0` through `ground()`: source token absent → `conforms=False` → PASS→BLOCK; clean twin → no blocks; no token → `None`. A second inverse floor needs no new code.
- Deterministic Gate 0 supreme: full suite 28==28 (0 net new), the new tests green (A4 skips under healthcare like the NARR-3 A4 — A5 subprocess always runs), MOAT + `grounding.py` 0-diff, tool count 20.

## Scope guardrails (do NOT)
- Do NOT edit the `ground()` floor loop, `grounding.py`, or any of the 4 moat files.
- Do NOT make `value_presence` a CORE floor (would break the two equality snapshots + contradicts SPEC_CLINVERDICT §122).
- Do NOT add a new SDK-MCP tool / touch `apps/bff/agent/*` (authoring is params-only via the shipped surface).
- Do NOT wire the clinical case-10 contract into the EXTERNAL healthcare pack here (DATA follow-on; "HPACK builds in the pack repo").
- Do NOT overclaim: the demonstrable flip is the narrative-pack crafted pair; the clinical live-authoring is a separate, honest follow-on.

## Next
- FAUTH-3b (SNOMED authoring-time terminology, the richer oracle) · FAUTH-5 (KbPicker) · FAUTH-6 (OpenEvidence, last/access-gated).
- The clinical case-10 instance: author `value_presence` into `../lithrim-pack-healthcare` (one `FLOOR_EXECUTORS` re-export + a pinned contract) → the live clinical flip.
