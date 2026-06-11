# Driver — `bench-salvage` phase `CE-PACK-6b-CLEAN`: clinical-clean the core council (the FROZEN endgame)

> **Bundle ID:** `bench-salvage-phaseCE-PACK-6b-CLEAN-clinical-clean-core-council-driver`
> **Version:** v1 · **Authored:** 2026-06-12 · **Last re-verified:** 2026-06-12 (HEAD 4ecbe43, + a 2-agent reassessment)
> **Execution:** a FRESH Claude Code session (paste the kickoff). **HARD GATE — fresh-critic worktree pass required at close.**

**The goal:** `grep -riE 'hipaa|clinical|patient|dosage|allerg|soap|medication' lithrim_bench/runtime/council/` → **empty** (only the domain-agnostic MECHANISM + the 4 pack carve-outs remain). This is the last layer of the generic-CE demarcation (memory `generic-ce-demarcation`; `SPEC_STANDALONE_CORE_VALIDATION.md` §3.3/§4). It RETIRES `build_prompt` (per OQ-1: the authored path is the single prompt source) + genericizes `_build_signature` (S-BS-129, live-evidenced by the CE-STANDALONE-1 smoke).

**⚠️ This is the biggest, most-entangled cycle of the program.** A 2-agent reassessment (2026-06-12) found `build_prompt` is NOT a clean delete — it is the council's `evaluate()` prompt-builder, still reached by the pipeline + the A/B harness; `safety_flags.py` is the healthcare ontology's SEED source; and the freeze guard REJECTS deletions. Read §1.5 (the entanglement map) before planning. **Plan-review is non-negotiable and must be approved before any edit.**

---

## KICKOFF (paste into a FRESH session)

```
You are the EXECUTOR for the .devloop cycle: bench-salvage CE-PACK-6b-CLEAN (clinical-clean-core-council). HARD GATE.

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseCE-PACK-6b-CLEAN_clinical-clean-core-council_driver.md  (this doc — read §1.5 the entanglement map carefully)
  3. docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md (§0 demarcation, §3.3 6b, §4 sequencing)
  4. CLAUDE.md (§"Taxonomy snapshot is the contract" — the frozen-council carve-out discipline)
  5. tests/_seam_freeze.py (READ WHOLE — the guard you must extend to authorize the deletion + the signature edit)
  6. memory generic-ce-demarcation

POST YOUR PLAN-REVIEW (per EXECUTOR.md) BEFORE ANY EDIT — this touches the FROZEN compliance_council.py + judges_dspy.py.
Expect a fresh-critic worktree pass at close. Do not write code until the monitor says "go".

Bundle ID: bench-salvage-phaseCE-PACK-6b-CLEAN-clinical-clean-core-council-driver
```

---

## 1. Pre-flight reading + the entanglement map

### 1.1 `_build_signature` (S-BS-129) — the bounded part
- `lithrim_bench/runtime/council/judges_dspy.py:171-200` `_build_signature()` → the `JudgeSignature`. **Clinical prose (4 strings to neutralize):** `:176` "clinical artifact", `:178` "HIPAA / clinical-safety compliance council", `:189` "provider/patient conversation (ground truth)", `:191` "clinical note / artifact under audit". The I/O fields are ALREADY generic (transcript/artifact/role_key_questions/taxonomy_context → decision/findings/reason). Domain specificity arrives via `role_key_questions` (pack role prompts) + `taxonomy_context` (pack codes) — so the signature should be a **neutral scaffold**.
- Called at `judges_dspy.py:289` `dspy.Predict(_build_signature())` — ONLY when a Judge has no injected predictor (the LIVE path). The $0 authored/predictor path bypasses it (why the CE smoke output was clean but the prose still reached the live LLM).

### 1.2 `build_prompt` — the entangled part
- `compliance_council.py:517-788` `def build_prompt` (~270 lines: HIPAA scaffold + `agent_category` branches + `:752` `get_flag_prompt_section()`). Self-called at **`:2459`** inside `def evaluate(self, context_payload, *, context_kind="transcript", ...)` — the **transcript branch** (`else` of the `context_kind == CONTEXT_KIND_SOURCE_MESSAGE` check at `:2456-2459`). `evaluate()` is the council's public API.

### 1.3 `safety_flags.py` — the SEED source (relocate, don't just delete)
- `lithrim_bench/runtime/council/safety_flags.py` exports `SAFETY_FLAG_DEFINITIONS` (23 clinical flag defs), `SafetyFlagDefinition`, `TAXONOMY_VERSION`, `get_flag_prompt_section()` (+ `FailureType`/maps/`derive_failure_type`).
- `get_flag_prompt_section()` is called ONLY by `build_prompt:752` → dies with it.
- **But `SAFETY_FLAG_DEFINITIONS` + `TAXONOMY_VERSION` + `SafetyFlagDefinition` are LIVE-imported by `scripts/seed_ontology.py:226,231,257`** — the script that SEEDS `packs/healthcare/ontology.json`. So this is **healthcare GENERATION content** (like the PACK-5 generators) → it must **relocate into the healthcare pack**, not be deleted (else `seed_ontology` breaks + the core keeps clinical content).

### 1.4 The freeze guard — it REJECTS deletions
- `tests/_seam_freeze.py`: `assert_council_carveouts_only` (`:211-250`) asserts every changed hunk `tag == "replace"` (`:222`) — a DELETION emits a `"delete"` opcode → **FAILS**. `_COUNCIL_AUTHORIZED_MARKERS`/`_COUNCIL_REQUIRED_CARVEOUTS` + the S-BS-124 per-line hardening. `assert_judges_dspy_consensus_seam_frozen` (`:62-81`) byte-pins judges_dspy EXCEPT `_BYOC1_PROVIDER_SEAM = {build_judge_lm, build_trio}` (`:25`) → editing `_build_signature` FAILS too.

### 1.5 THE ENTANGLEMENT MAP (the callers of `build_prompt` via `evaluate()` — all must stop reaching it before deletion)
| Caller | Site | What it is | Disposition |
|---|---|---|---|
| `compliance_council.evaluate()` | `:2459` | the council's own transcript branch | delete the transcript branch + build_prompt (the deletion) |
| `runtime/pipeline/stages.py` | `:746` `council.evaluate(...)` (council built `:634/636/1001`) | the bench's in-process/pipeline path (CORE) | **reroute to the authored stage** (the 6b-ROUTE treatment for the pipeline) |
| `runtime/council/ab_harness.py` | `:235/247` `council.evaluate(...)` | A/B harness (legacy WS-6c; live mode "deliberately unexercised") | reroute to authored OR retire the build_prompt leg (plan-review) |
| `tests/.../test_consensus.py` | `:311` `council.build_prompt(...)` | unit test of NKA prose in the prompt | rewrite (assert NKA in the role prompt) or delete |
| `tests/.../test_live_smoke.py` | `:97` `council.build_prompt(...)` | smoke: prompt-size proxy | remove the line (not load-bearing) |

> **Citation discipline:** verified at HEAD `4ecbe43` + the 2-agent reassessment (2026-06-12). Re-grep on read.

---

## 2. Deliverables (PHASED — plan-review the order)

**D0 — reassess-confirm (plan-review gate).** Re-grep §1.5; confirm the full caller set of `evaluate()`/`build_prompt` (grep `build_prompt` + `\.evaluate(` repo-wide). Confirm `stages.py` is the only non-test live `evaluate()`-via-transcript caller besides ab_harness. **HALT-and-surface if a caller exists that this driver didn't enumerate.**

**D1 — reroute the pipeline + ab_harness off the default council (NON-frozen, do FIRST).** `runtime/pipeline/stages.py`: where it calls `council.evaluate(context_kind=transcript)`, build + run the AUTHORED semantic stage instead (the 6b-ROUTE pattern: default each judge to `pack_lenses()[role]` → `build_authored_semantic_stage` → the trio + `_apply_consensus`), so `build_prompt` is no longer reached. `ab_harness.py`: reroute its `run_live` leg likewise, or retire the build_prompt arm (it's the legacy "control" arm; plan-review the choice). **After D1, NOTHING reaches `build_prompt` except the 2 unit tests.**

**D2 — relocate the `safety_flags` SEED into the healthcare pack.** Move `SAFETY_FLAG_DEFINITIONS` + `SafetyFlagDefinition` + `TAXONOMY_VERSION` (the seed-bearing exports) into `packs/healthcare/` (mirror the PACK-5 generators relocation — `git mv` or a pack module). Re-point `scripts/seed_ontology.py` to read them from the pack. Keep behavior identical (the regenerated `packs/healthcare/ontology.json` must be byte-identical — verify). Delete `get_flag_prompt_section()` (dies with build_prompt). After this, `runtime/council/safety_flags.py` is either deleted or reduced to NON-clinical residue (the `FailureType` maps — relocate or delete per plan-review).

**D3 — genericize `_build_signature` (FROZEN judges_dspy.py).** Neutralize the 4 clinical strings (§1.1) → a domain-agnostic scaffold ("source conversation", "produced artifact under audit", drop "HIPAA/clinical/patient"). The I/O contract unchanged (byte-stable fields). Authorize via the guard (D5).

**D4 — delete `build_prompt` + the `evaluate()` transcript branch (FROZEN compliance_council.py).** Remove `def build_prompt` (`:517-788`) + the `from .safety_flags import get_flag_prompt_section` (`:27`) + the transcript branch at `:2456-2459` (the `else: prompt = self.build_prompt(...)` — `evaluate()` retains the `source_message` branch). Confirm `_apply_consensus` + the consensus/withstands MECHANISM are byte-untouched.

**D5 — authorize the frozen edits in `tests/_seam_freeze.py`.** (a) The DELETION: add a `_COUNCIL_AUTHORIZED_DELETIONS` mechanism — permit a `"delete"` opcode IFF the deleted block contains an authorized marker (`def build_prompt`), keeping the lower-bound revert-detection + the S-BS-124 per-line hardening for `replace` hunks. (b) The SIGNATURE: authorize the `_build_signature` genericization — add it to the judges_dspy carve-out exclusion set (preferred) OR re-baseline with rationale (plan-review). The guard must stay **non-vacuous** (an UNauthorized deletion/edit still FAILS — prove it).

**D6 — tests.** Rewrite `test_consensus.py:304-314` (assert NKA in the faithfulness role prompt, not via `build_prompt`); remove `test_live_smoke.py:97`'s `build_prompt` line. Add a test that `grep runtime/council/` is clinical-clean (the demarcation bar) + that the genericized signature carries 0 clinical needles. Update any test that asserted the seed lived in `safety_flags`.

**D7 — docs.** `SPEC_STANDALONE_CORE_VALIDATION.md` §4 6b-CLEAN → DONE + the grep-clean attestation; close G2/G2a/G4/S-BS-129. CLAUDE.md note (the core council is clinical-clean; the safety-flag seed lives in the healthcare pack). Update memory pointer in the close handoff.

---

## 3. Plan-review (NON-NEGOTIABLE — approve before any edit)
Post: understanding of the entanglement map · the D1 pipeline-reroute design (does stages.py fully reroute, or is there an evaluate() path that must remain?) · the safety_flags relocation target + the byte-identical ontology proof plan · the `_build_signature` neutral text · the guard authorization design (deletion mechanism + signature carve-out) with a non-vacuity proof · the test rewrites · the commit order · risks. **Wait for "go".** Fresh-critic worktree at close.

## 4. Scope guardrails — NOT in scope
- **The consensus/withstands MECHANISM** — `_apply_consensus`, the gate logic, the oracle. Byte-untouched (the moat). Behavior 0-delta on the authored path is the proof.
- **`build_source_message_prompt` / the source_message branch** of evaluate() — leave it (separate concern; source_message_judge is owner-only/declared-not-running).
- **The 4 existing pack carve-outs** (tiers/owners/lenses/roster) — untouched.
- **The pack content** beyond receiving the relocated safety_flags seed.
- Drive-by refactors / formatting.

## 5. Acceptance
- **A1 (grep-clean):** `grep -riE 'hipaa|clinical|patient|dosage|allerg|soap|medication|consent|escalat' lithrim_bench/runtime/council/` → empty (or only enumerated non-clinical false-positives, documented). The demarcation bar.
- **A2 (build_prompt gone):** `grep -rn 'def build_prompt|build_prompt(' lithrim_bench/runtime/council/` → empty; nothing reaches it (D1 done).
- **A3 (signature generic):** `_build_signature` carries 0 clinical needles; the authored-path tests + a live-optional smoke unaffected (I/O contract byte-stable).
- **A4 (seed relocated, byte-identical):** `scripts/seed_ontology.py` regenerates `packs/healthcare/ontology.json` byte-identical from the pack-resident seed.
- **A5 (guard non-vacuous):** the freeze guard PASSES the authorized deletion + signature edit, and FAILS an unauthorized deletion/edit (prove both, like the PACK-2c critic did).
- **A6 (0-delta + suite):** authored-path behavior 0-delta (consensus/withstands byte-frozen); full suite **0-new vs parent** (debuglithrim; the 2 S-BS-96 guards excepted); ruff clean.
- **A7:** docs updated; S-BS-129 + G2/G2a/G4 closed.

## 6. Commit structure (atomic, pathspec-scoped — foreign files `apps/shell/src/app.jsx` + `journeys/*` + the demo HANDOFF untouched)
1. `refactor(pipeline): reroute stages.py + ab_harness to the authored stage off build_prompt (D1)`
2. `refactor(pack): relocate the safety-flag seed into the healthcare pack; seed_ontology reads it (D2)`
3. `refactor(council): genericize _build_signature — domain-agnostic scaffold (D3, S-BS-129)`
4. `refactor(council): delete build_prompt + the evaluate transcript branch + get_flag_prompt_section (D4)`
5. `test(seam): authorize the build_prompt deletion + the signature edit; non-vacuity proof (D5/D6)`
6. `docs: 6b-CLEAN done — core council is clinical-clean; close S-BS-129/G2/G4 (D7)`
End bodies: `Executed per bench-salvage-phaseCE-PACK-6b-CLEAN-... by session-2026-06-12-N.` + Co-Authored-By.

## 7. Verification
- [ ] A1–A7 PASS · all commits exist, foreign files untouched · the MECHANISM (consensus/withstands) byte-frozen vs `acc4973` (the moat) · tests+ruff clean (record env) · session log written · diagnose-before-edit evidence for every "X is the only caller / behavior 0-delta" claim

## 8. Hardness
- [x] **HARD GATE** — fresh-critic worktree pass required at close (deletes from + edits the FROZEN `compliance_council.py` + `judges_dspy.py`; reroutes the pipeline; relocates the seed). The plan-review + the guard-non-vacuity proof + the byte-identical-ontology proof + behavior-0-delta-on-the-moat are all load-bearing. If the pipeline reroute (D1) can't fully remove the `evaluate()`/build_prompt path, HALT and surface — the cycle may need to split.
