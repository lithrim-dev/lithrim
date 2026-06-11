# HANDOFF — bench-salvage — 2026-06-12 (the generic-CE program; 6b-CLEAN driver READY)

> **For the next monitor session (`/devloop-resume bench-salvage`).** We are mid-program on the **generic-CE demarcation** (make the OSS Core a domain-agnostic CE; healthcare continues as a pack). Four cycles have landed CLEAN this run; the **last cycle (CE-PACK-6b-CLEAN, the FROZEN endgame) is authored, registered, and READY** — its kickoff just needs handing to a fresh executor session. **Services:** the user runs them; `curl`-check, never autostart. **LOCAL is SSOT** (nothing pushed all program). **Foreign files in the tree** (`apps/shell/src/app.jsx` M + `journeys/live_eval_loop.*.json` ?? + `.devloop/sessions/HANDOFF_bench-salvage_live-demo-recording_2026-06-11.md` ??) are a SEPARATE demo track — leave untouched; commit pathspec-scoped ONLY.

## 🔴 IMMEDIATE NEXT — hand the CE-PACK-6b-CLEAN kickoff to a FRESH executor session
The driver is `.devloop/prompts/bench-salvage_phaseCE-PACK-6b-CLEAN_clinical-clean-core-council_driver.md` (index #73, status `ready`). **HARD GATE** — fresh-SESSION execution (NOT subagent), plan-review BEFORE any edit, **fresh-critic worktree pass at close**. Paste-ready kickoff is in the driver's `## KICKOFF` block.

**Goal:** `grep -riE 'hipaa|clinical|patient|dosage|allerg|soap|medication' lithrim_bench/runtime/council/` → empty. The last clinical residue: genericize `_build_signature` (S-BS-129) + DELETE `build_prompt` + relocate the `safety_flags` SEED into the healthcare pack.

**The entanglement (from a 2-agent reassessment — baked into the driver §1.5):** `build_prompt` is NOT a clean delete — it's the council `evaluate()` prompt-builder, still reached by `runtime/pipeline/stages.py` (the pipeline, CORE) + `ab_harness` + 2 unit tests; `safety_flags.py` is the healthcare ontology SEED source (`seed_ontology.py` imports it); the freeze guard REJECTS `delete` opcodes. So the cycle ALSO reroutes the pipeline off the default council (D1, first), relocates the seed (D2, byte-identical ontology regen), and adds a freeze-guard authorized-deletion mechanism (D5). The MECHANISM (`_apply_consensus`/withstands = the moat) stays byte-frozen.

**When the executor returns its PLAN-REVIEW, the monitor must vet two load-bearing risks before "go":** (1) the **D1 pipeline-reroute design** — can `stages.py` fully stop reaching `evaluate()`/`build_prompt`? (there's an explicit HALT clause if not → the cycle may split); (2) the **D5 guard authorization + non-vacuity proof** (an unauthorized deletion must still FAIL).

## ✅ What landed this run (all CLEAN, all pathspec-scoped, LOCAL only)
The generic-CE program (memory `generic-ce-demarcation`; spec `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md`) corrects the PACK-2c "strangler-fig complete" overclaim (it was DATA-only; the council PROMPT was still in core). Audit + a `$0` experiment proved: the AUTHORED path (`render_role_questions`) = 0 clinical leakage = the generic engine; the legacy `build_prompt`/`safety_flags` = 218 needle hits = clinical-hardcoded. OQ-1 RESOLVED (user): RETIRE build_prompt.

- **CE-STANDALONE-1** ✅ CLOSED (`fe1d170..e2f9b8e`) — a real independent non-clinical pack `packs/support_ticket_qa/` (tier:core) + `tests/test_standalone_ce.py`: grades a non-clinical case via the authored path, healthcare DOMAIN unloaded (A4 audit-hook non-vacuous), `:8002` down, 0 leakage, reject. **Surfaced S-BS-129** (core JudgeSignature clinical prose) **+ S-BS-130** (DEFAULT_PACK=healthcare).
- **CE-PACK-NEUTRAL-DEFAULT** ✅ CLOSED (`0b70d61..60859e6`, subagent-executed) — neutral `packs/_core/` default pack + `DEFAULT_PACK` flip; **the core boots + grades WITHOUT healthcare on disk** (`tests/test_neutral_default.py`: zero healthcare reads; roster identity byte-stable). **CLOSED S-BS-130 + RESOLVED S-BS-125** (tripwire retired → designed invariant).
- **CE-STANDALONE-1 live smoke** ✅ DISCHARGED (~$2 Azure v2 trio) — `support_ticket_qa` LIVE-PROVEN: reject on real LLMs, healthcare unloaded, 0 clinical leakage in the output. Honest-Δ: live judges attributed to DIFFERENT codes than the by-construction label (verdict held, code dispersed). S-BS-129's live impact: NONE observed (still a 6b-CLEAN purity target). `docs/research/RUN_ce_standalone1_live_smoke_2026-06-12.md`.
- **CE-PACK-6b-ROUTE** ✅ CLOSED (`2b1f43d..c6ecd30`, subagent-executed) — the in-process PRODUCT grade is now AUTHORED-PATH-ONLY (no-assignment → full pack-lens default); `build_prompt` is DEAD on the product path (UI-authored prompts = the single live prompt source). NOT deleted (6b-CLEAN does that). No new seams.

**Release-readiness:** active-domain decoupling ✅ · ships-without-healthcare ✅ · live-attested ✅ · authored-path-only live grade ✅ · **core greps clinical-clean ⏳ (6b-CLEAN, the last one).**

## 🧭 Open seams (post-6b-CLEAN context)
- **S-BS-129** (medium) — core `_build_signature` clinical prose → **6b-CLEAN closes it** (genericize). Live-evidenced (no degradation observed, but a purity target).
- **S-BS-127** (low) — freeze-guard marker-substring residual (inherent to S-BS-124; not a regression).
- **S-BS-117 / S-BS-119 / S-BS-128** CLOSED earlier; **S-BS-130 CLOSED**, **S-BS-125 RESOLVED** this run.

## 💤 Owed (no rush)
- The **owner-gated push** of the local stack (user keeping LOCAL — explicitly fine).
- (The CE-STANDALONE-1 live smoke is DISCHARGED — no longer owed.)

## Pointers
- Driver: `.devloop/prompts/bench-salvage_phaseCE-PACK-6b-CLEAN_clinical-clean-core-council_driver.md` (read §1.5 entanglement map).
- Spec: `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` (§0 demarcation, §2 audit findings + gap taxonomy G1-G5, §3 design, §4 sequencing).
- Memory: `generic-ce-demarcation` (the locked direction + the cycle plan), `healthcare-realm-as-pack`, `git-commit-pathspec-dirty-index`, `live-reassess-before-driver-lock`, `proof-capsule-convention`.
- Recent commits: `929c23d` (6b-CLEAN driver) · `4ecbe43` (6b-ROUTE close) · `2742d32` (live smoke) · `99b13c8` (NEUTRAL-DEFAULT close) · `b21820e` (CE-STANDALONE-1 close).
- After 6b-CLEAN the generic-CE program is DONE (the core council greps clinical-clean). The next frontier is then the user's call: Plugin Phase-1 code cycle (registry refactor → HPACK), CHATBIND-2, or the grounding-floor/KB-VENDOR stream.
