# HANDOFF — `bench-salvage` — 2026-06-12 (the generic-CE demarcation program is DONE)

> Written by the monitor on the CE-PACK-6c close. **The generic-CE demarcation program is COMPLETE** — the OSS core council carries no live clinical code; the OSS-core / Pro-pack split is real and verifiable. **Services: the user runs them — `curl`-check, never autostart. LOCAL is SSOT (nothing pushed all program). Foreign/demo files** (`apps/shell/src/app.jsx`, `journeys/*`) — now committed (`ff04b46`); the live_eval_loop highlight cut is the open item in `HANDOFF_bench-salvage_live-demo-recording_2026-06-11.md`.

---

## What just landed

- **Closed phase:** CE-PACK-6c — retire `build_source_message_prompt` + decide `phi_redaction`'s fate (commits `7c41f0c..1efe006`, atop parent `ff04b46`)
- **Critique verdict:** **NON-BLOCKING** [0/2/0] (HARD-GATE fresh-critic `a7febcb0de587d0c3`, worktree-isolated) — `.devloop/sessions/critique-bench-salvage-CE-PACK-6c-2026-06-12.md`
- **Audit verdict:** CLEAN (monitor 7-item)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseCE-PACK-6c-2026-06-12.json`

**What it did:** the last live clinical CODE is out of the frozen core council. `build_source_message_prompt` (the source_message prompt builder) **DELETED** (5th D4-authorized frozen deletion); the source_message stage **rerouted** to the authored evaluator (Fork A — bench-dead re-confirmed, so safe); `evaluate()` now builds no prompt (both branches raise; the source_message branch carries the `CE-PACK-6c` sentinel). `phi_redaction` **kept in core** as a generic privacy mechanism (Fork B — prose genericized, `HIPAA_*` config keys unchanged). The **moat is byte-identical vs `acc4973`** (`_apply_consensus` + `extract_verdict_confidence`); the freeze guard is **non-vacuous both ways** — the critic proved both new markers (`def build_source_message_prompt`, `CE-PACK-6c`) load-bearing and that `_apply_consensus`/`_format_kb_citations` deletions still FAIL. Honest bar (Fork D): **no live clinical CODE** (`grep 'def build_source_message_prompt\|def build_prompt'` → empty), NOT literal grep-empty.

> ⚠️ **Count correction (carry this — same env-inflation as 6b-CLEAN):** the executor handback said 647/2/2; the fresh-critic verified **644 passed / 4 failed / 3 skipped** at HEAD, **0-new vs parent's 639/4/3**. The 4 fails are pre-existing (`test_byoc_provider` unset-Azure-env, `test_uap3_grade` missing gitignored fixture, 2 S-BS-96 observation guards). Cite **0-new (644/4/3)**, not 647/2.

## 🏁 The generic-CE demarcation program — COMPLETE

Four cycles, all closed 2026-06-12: **CE-STANDALONE-1** (the independent non-clinical pack + standalone proof) → **CE-PACK-6b-ROUTE / NEUTRAL-DEFAULT** (authored-path-only product grade + neutral `_core` default) → **CE-PACK-6b-CLEAN** (`build_prompt` + `safety_flags` + `_build_signature` retired) → **CE-PACK-6c** (`build_source_message_prompt` retired). The frozen core council now carries **no live clinical code** — only the domain-agnostic MECHANISM + the 4 pack carve-outs + passive provenance comments. The healthcare realm lives entirely in the `healthcare` pack. **Release-readiness is green on every line:** decoupled · ships-without-healthcare · live-attested · authored-path-only grade · core-council clinical-clean.

## What's next — the user's strategic call (NO autostart)

The program is done; there is no queued next phase. The monitor presents; the user picks:
- **Plugin Phase-1** code cycle — the registry refactor → **HPACK** (the 1st Pro plugin); `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (OQ-1..3 resolved).
- **CHATBIND-2** — the chat-drives-the-3rd-pane line.
- **grounding-floor / KB-VENDOR-1 / TERMINOLOGY-1** — the grounding-moat stream (`grounding-floor-is-the-moat-next`).
- Cleanups: **S-BS-132** (retire the inert source_message machinery), the **owner-gated push**.

## Open seams for `bench-salvage`

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-132 | source_message machinery now fully inert — retire wholesale (constant + `:1085` role-select + `_format_kb_citations` + doc-comments + the stale `else`-raise "source_message-only" tail) in a future NON-frozen cleanup | low | **open** (CE-PACK-6c) |
| S-BS-127 | freeze-guard marker-SUBSTRING residual (inherent to S-BS-124; not a regression) | low | open |
| S-BS-113 | `seed_ontology --check` STALE — **also fold the D2-a `flag_source`/`_provenance.gradeable_note` deleted-path refresh here**; do NOT full-re-seed | low/med | open |
| S-BS-131 | CE-PACK-6c residual | low | **CLOSED (this cycle)** |
| S-BS-129 | core `_build_signature` clinical prose | medium | **CLOSED (6b-CLEAN)** |
| S-BS-126/117/119/118 | fixture-path / corpus-determinism / packs-as-code trust residuals | low | carried-open |

## Load-bearing context the next monitor MUST know

1. **The OSS-core / Pro-pack split is now REAL and verifiable, not aspirational.** `grep -rn 'def build_prompt\|def build_source_message_prompt' lithrim_bench/runtime/council/` → empty; the core council is domain-agnostic mechanism + pack carve-outs. Any future core work must NOT re-introduce a clinical hardcode — `test_6bclean_attestation.py::test_no_live_clinical_code` + `test_residual_clinical_needles_only_in_enumerated_buckets` are the tripwires (a clinical needle in an unlisted core file fails). The honest bar is "no live clinical CODE," NOT grep-empty — the frozen carve-out/provenance comments + `HIPAA_*` config keys are documented passive residual. Don't claim grep-clean.

2. **Executor handbacks inflate the suite count (twice now).** Both 6b-CLEAN (642 vs 639) and 6c (647 vs 644) overstated because the executor env carries Azure vars + the gitignored `out/scribe_v1.jsonl` the bare worktree lacks. The fresh-critic worktree is the count source of truth; judge **0-new vs parent**, not absolute counts, and remember the S-BS-96 observation pair fails only under full-suite module pollution (passes 13/13 in isolation).

3. **The frozen-deletion mechanism is now a proven, reusable pattern** (5 authorized deletions across 6b-CLEAN + 6c). `tests/_seam_freeze.py` authorizes a frozen-file deletion via a per-marker allow-list + the S-BS-124 per-line bar; every new deletion needs a marker, and the critic must prove the marker load-bearing (drop it → guard fails) AND that an unauthorized deletion still fails. If a future cycle ever needs to touch the frozen `compliance_council.py` again, this is the contract. S-BS-127 (marker-substring residual) is the known soft spot.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (First move → the strategic options; Open seams).
3. Read this handoff.
4. `git log --oneline -12`.
5. Wait for the user's strategic call. **No queued next cycle — do NOT autostart anything.**

## References
- This cycle: session `session-bench-salvage-phaseCE-PACK-6c-2026-06-12.json` · critique `critique-bench-salvage-CE-PACK-6c-2026-06-12.md` · driver `.devloop/prompts/bench-salvage_phaseCE-PACK-6c_retire-source-message-prompt-decide-phi-redaction_driver.md`
- Spec: `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` (§4 — 6c DONE; the program closed)
- Memory: `generic-ce-demarcation` (program DONE), `healthcare-realm-as-pack`, `conversational-first-core-plugin-line`, `grounding-floor-is-the-moat-next`
- Prior handoffs: `HANDOFF_bench-salvage_phaseCE-PACK-6c_kickoff_2026-06-12.md`, `HANDOFF_bench-salvage_generic-ce-6b-clean_2026-06-12.md`
