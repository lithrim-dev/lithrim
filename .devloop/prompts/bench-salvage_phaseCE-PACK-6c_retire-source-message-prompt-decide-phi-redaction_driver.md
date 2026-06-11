# Driver — `bench-salvage` phase `CE-PACK-6c`: retire `build_source_message_prompt` + decide `phi_redaction`'s fate (the grep-empty finisher)

> **Bundle ID:** `bench-salvage-phaseCE-PACK-6c-retire-source-message-prompt-decide-phi-redaction-driver`
> **Version:** v1 · **Authored:** 2026-06-12 · **Last re-verified against code:** 2026-06-12 (HEAD `ae0854e`; every citation re-grepped this session)
> **Execution:** a FRESH Claude Code session (paste the kickoff). **HARD GATE — fresh-critic worktree pass required at close.**
> **Scope source:** no TASK_PACK/index stub existed (this stream is SPEC-driven — cf. memory `devloop-task-pack-stale-uap-from-spec`). Scope is sourced from `SPEC_STANDALONE_CORE_VALIDATION.md` §4 (the 6c follow-on) + the **authoritative** residual enumeration in `tests/test_6bclean_attestation.py::ENUMERATED_RESIDUAL` + seam **S-BS-131**.

**The goal:** finish what CE-PACK-6b-CLEAN deferred — remove the **last live clinical CODE** from the core council (`build_source_message_prompt`, the source_message prompt builder) and **decide `phi_redaction`'s fate**, so `lithrim_bench/runtime/council/` carries only the domain-agnostic MECHANISM + authorized pack carve-outs + (documented) provenance comments. This closes **S-BS-131** and the generic-CE demarcation program.

**⚠️ Read §1.5 (the diagnostic map) before planning.** This touches the FROZEN `compliance_council.py` AGAIN (delete `build_source_message_prompt` + its `evaluate()` branch — a 5th authorized deletion under the 6b-CLEAN guard mechanism). The MECHANISM (`_apply_consensus`/withstands) stays byte-frozen vs `acc4973`. **Plan-review is non-negotiable and must be approved before any edit. Two forks are load-bearing (A: the source_message disposition; D: the honest grep bar) — do not pre-decide them.**

---

## KICKOFF (paste into a FRESH session)

```
You are the EXECUTOR for the .devloop cycle: bench-salvage CE-PACK-6c (retire build_source_message_prompt + decide phi_redaction). HARD GATE.

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseCE-PACK-6c_retire-source-message-prompt-decide-phi-redaction_driver.md  (this doc — read §1.5 the diagnostic map carefully)
  3. docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md (§0 demarcation, §4 sequencing — the 6c item)
  4. CLAUDE.md (§"Taxonomy snapshot is the contract" — the frozen-council carve-out discipline; the CE-PACK-6b-CLEAN paragraph)
  5. tests/_seam_freeze.py (READ WHOLE — the 6b-CLEAN deletion-authorization mechanism you will EXTEND for the source_message branch)
  6. tests/test_6bclean_attestation.py (the residual enumeration you will TIGHTEN)
  7. memory generic-ce-demarcation + the close handoff HANDOFF_bench-salvage_phaseCE-PACK-6c_kickoff_2026-06-12.md

POST YOUR PLAN-REVIEW (per EXECUTOR.md) BEFORE ANY EDIT — this deletes from the FROZEN compliance_council.py.
Resolve Fork A (source_message disposition) + Fork B (phi_redaction) + Fork D (the honest grep bar) IN the plan-review.
Expect a fresh-critic worktree pass at close. Do not write code until the monitor says "go".

Bundle ID: bench-salvage-phaseCE-PACK-6c-retire-source-message-prompt-decide-phi-redaction-driver
```

---

## 1. Pre-flight reading + the diagnostic map

### 1.1 What CE-PACK-6b-CLEAN left (the starting state — committed `0cec6ac..df08ab3`, closed `ae0854e`)
`build_prompt` + the `evaluate()` transcript branch + core `safety_flags.py` are GONE; `_build_signature` is genericized (S-BS-129 closed). The MECHANISM is byte-frozen vs `acc4973`. The deletion-authorization mechanism EXISTS in `tests/_seam_freeze.py` (the `6b-CLEAN` sentinel + `_COUNCIL_AUTHORIZED_MARKERS` + the per-line bar) — **you extend it, you do not invent it.** `test_6bclean_attestation.py` PINS the residual you are about to clear.

### 1.2 The residual (authoritative — `tests/test_6bclean_attestation.py::ENUMERATED_RESIDUAL`, the NEEDLES set is `hipaa|clinical|patient|dosage|allerg|soap|medication|consent|escalat`)
| Core council file | What carries the needle | Class | 6c disposition |
|---|---|---|---|
| `compliance_council.py` | **`build_source_message_prompt`** (live CODE) + the source_message `evaluate()` branch + retrieval refs **+** PACK-1b/2b carve-out provenance COMMENTS **+** frozen-file comments | CODE + frozen comments | **Fork A** — retire the CODE; the FROZEN carve-out/provenance COMMENTS stay (authorized) |
| `phi_redaction.py` | the PHI-redaction privacy MECHANISM (`sanitize_prompt`/`redact_text`) | live generic CODE | **Fork B** — keep-as-generic (recommended) |
| `settings.py` | `HIPAA_REQUIRE_PHI_REDACTION` / `HIPAA_REQUIRE_ELIGIBLE_LLM_PROVIDER` / `HIPAA_ELIGIBLE_LLM_PROVIDERS` (`:56-58`) | config-key NAMES (load-bearing) | **Fork B** — keep keys (compat); genericize the prose only |
| `judge_metric.py` | withstands-lens provenance COMMENTS naming clinical codes (`:29,58,69,75-77,90-91`) | comments (non-frozen) | **Fork C** — leave or lightly genericize |
| `judge_assignment.py` | one allergy-fabrication provenance comment (`:55`) | comment (non-frozen) | **Fork C** — leave or genericize |
| `judges_dspy.py` | module docstring (`:14`) + a `build_judge_lm` comment (`:249`, BYOC-1 seam) | comments | **LEAVE** (Fork 5 from 6b-CLEAN; do not touch the BYOC-1 seam) |

### 1.3 `build_source_message_prompt` — the LIVE-but-BENCH-DEAD prompt builder (the core target)
- **Def:** `compliance_council.py:762` `def build_source_message_prompt(self, context_payload)`. ~clinical FHIR prompt prose (SAFETY FLAG TAXONOMY source_message subset, `WRONG_DOSAGE`/`MISSING_ALLERGY`/`AllergyIntolerance`/`Patient.*`/`NKDA`).
- **Only live caller:** `compliance_council.py:2183` inside `evaluate()` — `if context_kind == CONTEXT_KIND_SOURCE_MESSAGE: prompt = self.build_source_message_prompt(...)` (`:2182`). NOTE 6b-CLEAN already made the `else`/transcript branch raise the `6b-CLEAN` sentinel; **6c removes the remaining source_message branch** so `evaluate()` builds NO prompt (both branches gone → `evaluate()` is fully dead-for-grading).
- **Also touched in the frozen file by source_message:** `:1085` (`if context_kind == CONTEXT_KIND_SOURCE_MESSAGE:` role-prompt selection → the dormant `source_message_judge` role) + `:257/261` the `CONTEXT_KIND_SOURCE_MESSAGE` constant + `:696/1771` doc-comments referencing the builder.
- **The reachability chain (architecturally live):** `evaluate(source_message)` ← `stages.py:982` (`run_semantic_source_message`, `:968`) ← `stages.py:999-1000` dispatch ← `orchestrator.py:242` (`semantic_routable = context_kind in ("transcript","source_message")`).
- **🟢 THE LOAD-BEARING DIAGNOSTIC (CONFIRMED this session — re-confirm before acting):** source_message is **never exercised by any live bench/product path.** Every grade path hardcodes transcript: `harness/grade.py:73` `"context_kind": "transcript"`, `backends/local_pipeline.py:105` `context_kind="transcript"`, `models.py:242` default `context_kind: ContextKind = "transcript"`. No agent/case/script/BFF sets `source_message`; `data/config/agents/ws0_default.json:9` notes `source_message_judge` is "declared-not-running in v2." → `build_source_message_prompt` is the exact analogue of 6b-CLEAN's dead `gate_mode=True` path: present, routable, but bench-dead. **This is why retire/reroute is SAFE — but the executor must re-confirm it, not take it on faith (diagnose-before-edit).**

### 1.4 `phi_redaction` — a GENERIC privacy mechanism, not domain content
- `compliance_council.py:28` `from .phi_redaction import sanitize_prompt` — called before every external LLM call (PHI/PII redaction). `phi_redaction.py:1` "PHI redaction utilities for external LLM usage"; `:59` `redact_text` (regex redaction). `settings.py:55-58` the `HIPAA_*` policy read by it.
- This is a **domain-agnostic safety capability** (redact PII before sending to an external LLM) — every CE domain benefits. The "HIPAA" naming is clinical framing on a generic mechanism. **Relocating it to the pack would strip the core of PII redaction = WRONG direction.** The honest fate is keep-in-core; the only question is whether to genericize the HIPAA-framed PROSE (and whether the `HIPAA_*` config keys can be renamed without breaking compat — they cannot trivially).

### 1.5 The freeze guard — the EXISTING 6b-CLEAN deletion mechanism (extend, don't reinvent)
- `tests/_seam_freeze.py` already authorizes deletions via `_COUNCIL_AUTHORIZED_MARKERS` (the `6b-CLEAN` sentinel + `def build_prompt` etc.) in `assert_council_carveouts_only`/`assert_compliance_council_carveouts_only`, with the S-BS-124 per-line bar + S-BS-127's known marker-substring residual. **6c adds a `6c`/`source_message` authorized-deletion marker** for `def build_source_message_prompt` + the `:2182-2183` branch removal. The non-vacuity bar is the same: an UNauthorized deletion (e.g. `_apply_consensus`) must still FAIL. `assert_clinical_ontology_seam_frozen` + the moat (`_apply_consensus`/`extract_verdict_confidence`) stay byte-frozen.

> **Citation discipline:** every file:line above re-grepped at HEAD `ae0854e` this session. Re-grep on read — line numbers drift.

---

## 2. Deliverables (resolve the forks in plan-review FIRST)

- **D1 — retire `build_source_message_prompt` + the source_message live path (Fork A).** Per the confirmed bench-dead diagnostic, EITHER (A1, recommended) **reroute** `run_semantic_source_message` (`stages.py:968`) to the authored evaluator (mirror the 6b-CLEAN D1 transcript reroute via `build_authored_evaluator`) so source_message grades via the authored stage, OR (A2) **retire** the source_message stage end-to-end (`run_semantic_source_message` + the `stages.py:999-1000` dispatch + the `orchestrator.py:242` routing). Then DELETE `build_source_message_prompt` (`:762`) + remove the `evaluate()` source_message branch (`:2182-2183`) so `evaluate()` builds no prompt + the `:1085` source_message role-select. FROZEN-file deletion → authorized in D4. **HALT clause:** if the executor finds ANY live source_message caller (a real product/bench path), STOP and surface — the cycle re-scopes.
- **D2 — `phi_redaction` decision (Fork B).** Recommended: KEEP in core as the generic privacy mechanism; genericize the HIPAA-framed PROSE/docstrings (→ "PII/PHI redaction before external LLM calls") **without renaming** the `HIPAA_*` config keys (`settings.py:56-58` — load-bearing; a rename needs back-compat aliases, out of scope). Document the decision. (Alternative paths — rename-with-alias, or relocate — must be justified in plan-review; relocate is NOT recommended.)
- **D3 — provenance COMMENTS (Fork C).** Recommended: LEAVE the FROZEN `compliance_council.py` carve-out/provenance comments (authorized; touching them widens the frozen edit surface) + LEAVE the `judges_dspy.py` docstring/BYOC-1 comment (Fork 5). For the NON-frozen `judge_metric.py` / `judge_assignment.py:55` provenance comments: leave OR lightly genericize (executor's call; either way they do not gate A1 under the re-scoped bar).
- **D4 — freeze-guard authorization (extend 6b-CLEAN).** Add the `6c`/`source_message` authorized-deletion marker(s) to `_seam_freeze.py` so the `build_source_message_prompt` deletion + the `:2182-2183` branch removal PASS; an unauthorized deletion still FAILS. Prove non-vacuity BOTH directions (like the 6b-CLEAN C4 set + the PACK-2c critic).
- **D5 — tighten `test_6bclean_attestation.py`.** Remove the now-cleared buckets from `ENUMERATED_RESIDUAL` (`test_enumerated_buckets_are_not_stale` will FAIL if a file is cleaned but left listed) — so the attestation tightens to the honest post-6c residual (the frozen-file authorized comments + whatever Fork C leaves + the `HIPAA_*` config keys). Add a `test_no_live_clinical_code` assertion (no `build_source_message_prompt`/`build_prompt` def reachable). Rename/extend to a 6c attestation as fits.
- **D6 — docs.** `SPEC_STANDALONE_CORE_VALIDATION.md` §4 → 6c DONE with the HONEST bar (Fork D); CLAUDE.md one-liner; close **S-BS-131**; the close handoff updates memory `generic-ce-demarcation` (program DONE).

## 3. Plan-review checkpoint (REQUIRED before any edit)
Post a plan-review that resolves: **Fork A** (reroute vs retire the source_message stage — with the re-confirmed bench-dead evidence + the full caller list), **Fork B** (phi_redaction keep+genericize vs alternatives), **Fork C** (comment scrub vs leave), **Fork D** (the honest A1 bar — see §5), the exact frozen-file hunks (expect: delete `:762` def, remove `:2182-2183` branch, `:1085` select, + the constant/doc refs), and the D4 guard-marker design + non-vacuity proof plan. The monitor vets Fork A's reachability + the D4 authorization before "go."

## 4. NOT in scope
- The MECHANISM (`_apply_consensus`/withstands/`extract_verdict_confidence`) — byte-frozen vs `acc4973`.
- The 4 pack carve-outs (tiers/owners/lenses/roster) + the authored stage — untouched.
- Renaming the `HIPAA_*` config keys (compat — a separate cycle if ever).
- Scrubbing the FROZEN `compliance_council.py` carve-out/provenance comments (authorized residual).
- The `judges_dspy.py` BYOC-1 seam comment (Fork 5: leave).
- The 9 council test files (they exercise the healthcare pack — a separate, expected bucket).
- Drive-by refactors / formatting. Foreign files (`apps/shell/src/app.jsx`, `journeys/*`, the live-demo HANDOFF) — untouched; pathspec-scoped commits only.

## 5. Acceptance
- **A1 (the HONEST bar — Fork D):** the core council carries **no live clinical CODE** — `grep -rn 'def build_source_message_prompt\|def build_prompt' lithrim_bench/runtime/council/` → empty; `evaluate()` builds no prompt. The remaining `grep -riE '<needles>'` hits are ENUMERATED + attributed to documented buckets (frozen-file authorized provenance comments + `HIPAA_*` config keys + any Fork-C-left comments) and PINNED by the tightened attestation test. **Literal `grep → empty` is NOT the bar** (it would require renaming load-bearing config keys + scrubbing frozen-file authorized comments) — state this honestly in the close; do NOT claim grep-clean.
- **A2 (source_message retired):** `build_source_message_prompt` deleted; no live caller; Fork A applied (reroute/retire) with the bench-dead evidence; source_message either grades via the authored stage or is gone.
- **A3 (phi_redaction decided):** Fork B applied; the privacy mechanism still works (a `sanitize_prompt`/`redact_text` test passes); config keys unbroken.
- **A4 (guard non-vacuous):** the freeze guard PASSES the authorized `build_source_message_prompt` deletion + branch removal and FAILS an unauthorized deletion/edit (prove both).
- **A5 (moat + suite 0-delta):** `_apply_consensus` + `extract_verdict_confidence` byte-identical vs `acc4973`; full suite **0-new vs parent `ae0854e`** (debuglithrim; the 4 pre-existing fails — 2 S-BS-96 observation guards + unset-Azure-env + missing-gitignored-fixture — excepted; judge by 0-new, NOT absolute count, per the 6b-CLEAN count-correction); ruff 0-new.
- **A6 (attestation tightened):** `test_6bclean_attestation.py` `ENUMERATED_RESIDUAL` reduced to the honest post-6c set; `test_enumerated_buckets_are_not_stale` green; a new "no live clinical code" assertion present + non-vacuous.
- **A7:** docs updated; **S-BS-131 closed**; the generic-CE program marked DONE.

## 6. Commit structure (atomic, pathspec-scoped)
1. `refactor(pipeline): reroute/retire the source_message stage off build_source_message_prompt (D1, Fork A)`
2. `refactor(council): delete build_source_message_prompt + the evaluate source_message branch (D1 frozen, D4-authorized)`
3. `refactor(council): genericize phi_redaction prose; keep the generic privacy mechanism in core (D2, Fork B)`
4. `test(seam): authorize the source_message deletion; non-vacuity both directions (D4)`
5. `test(ce): tighten the demarcation attestation to the honest post-6c residual (D5)`
6. `docs: 6c done — no live clinical code in the core council; close S-BS-131 (D6)`
End bodies: `Executed per bench-salvage-phaseCE-PACK-6c-... by session-2026-06-12-N.` + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 7. Verification
- [ ] A1–A7 PASS · all commits exist, foreign files untouched · the MECHANISM byte-frozen vs `acc4973` (the moat) · the source_message bench-dead claim RE-CONFIRMED with evidence · tests+ruff 0-new (record env: `PYENV_VERSION=debuglithrim`) · session log written · diagnose-before-edit evidence for every "only caller / bench-dead / 0-delta" claim.

## 8. Hardness
- [x] **HARD GATE** — fresh-critic worktree pass required at close (deletes from the FROZEN `compliance_council.py`; reroutes/retires a routable stage). The plan-review (Forks A/B/D), the guard-non-vacuity proof, the moat byte-freeze, and the HONEST A1 re-scope are all load-bearing. **HALT clause:** if Fork A finds a LIVE source_message caller, or the deletion can't be fully authorized non-vacuously, STOP and surface — the cycle re-scopes or splits. This is a *purity finisher*, not a release gate — the generic-CE program is already release-ready without it.
