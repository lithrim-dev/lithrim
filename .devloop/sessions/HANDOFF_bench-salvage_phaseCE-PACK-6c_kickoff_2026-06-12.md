# HANDOFF — `bench-salvage` phase CE-PACK-6b-CLEAN → CE-PACK-6c kickoff

> Written by the monitor on cycle close (2026-06-12). The generic-CE demarcation
> program's FROZEN-endgame finale landed. **Services: the user runs them — `curl`-check,
> never autostart. LOCAL is SSOT (nothing pushed all program). Foreign files**
> (`apps/shell/src/app.jsx` M, `journeys/live_eval_loop.*.json` ??, the live-demo HANDOFF ??)
> **are a separate demo track — leave untouched; commit pathspec-scoped ONLY.**

---

## What just landed

- **Closed phase:** CE-PACK-6b-CLEAN — clinical-clean the core council (commits `0cec6ac..df08ab3`, 6 deliverables + session log, atop parent `1073fcc`)
- **Critique verdict:** **NON-BLOCKING** [0/2/0] (HARD-GATE fresh-critic `af17916bd58f71969`, worktree-isolated) — `.devloop/sessions/critique-bench-salvage-CE-PACK-6b-CLEAN-2026-06-12.md`
- **Audit verdict:** CLEAN (monitor 7-item)
- **Session log:** `.devloop/sessions/session-bench-salvage-CE-PACK-6b-CLEAN-2026-06-12.json`

**What it did:** the FROZEN core council shed its last clinical prompt residue — `build_prompt` (~18.8 KB) + the `evaluate()` transcript branch (→ a `6b-CLEAN`-marked `raise`) + the orphaned core `safety_flags.py` **DELETED**; the 23-flag seed **relocated** to `packs/healthcare/safety_flags_seed.py` (D2-a; `seed_ontology` reads it by path, ontology.json byte-identical); `_build_signature` **genericized** (**S-BS-129 / G2 / G2a / G4 CLOSED**). The consensus/withstands **moat is byte-frozen vs `acc4973`** (`_apply_consensus` + `extract_verdict_confidence` byte-identical); the deletion + signature edit are **D5-authorized** in `tests/_seam_freeze.py` with **8 non-vacuity tests** the critic reproduced (all 3 guards bite on real scratch-mutation). **0 new regressions** (corrected suite **639p / 4f [4 pre-existing] / 3s**; ruff −3, 0-new).

> ⚠️ **Count correction (carry this):** the executor handback said 642p/2f; the fresh-critic verified **639p/4f**. The 2 extra failures (`test_byoc_provider` unset-Azure-env + `test_uap3_grade` missing gitignored `out/scribe_v1.jsonl`) are **pre-existing** at parent → still 0 new. Cite 639/4, not 642/2.

**Release-readiness:** active-domain decoupling ✅ · ships-without-healthcare ✅ · live-attested ✅ · authored-path-only live grade ✅ · **core council greps clinical-clean of `build_prompt`/`safety_flags`/`_build_signature` ✅** — but **NOT** grep-empty (see 6c).

## What's next

- **Next phase:** **CE-PACK-6c** (follow-on opened by 6b-CLEAN) — relocate `build_source_message_prompt` (the still-**live** source_message clinical prompt branch, reached via `stages.py:684`) + **decide `phi_redaction`'s fate**; that's what the literal `grep -riE 'hipaa|clinical|…' lithrim_bench/runtime/council/` → empty target needs. Residual is enumerated + PINNED by `tests/test_6bclean_attestation.py` (a needle in an unlisted core council file fails the test).
- **Driver bundle:** **NOT yet authored.** Next monitor action → `/devloop-expand-driver bench-salvage CE-PACK-6c` (then a fresh-critic HARD-GATE again — it edits the FROZEN `compliance_council.py` source_message path).
- **Blocked by:** none. But **lower priority than the user's strategic call** — after 6b-CLEAN the generic-CE program's core-council milestone is MET; the next frontier may instead be the **Plugin Phase-1 code cycle** (registry refactor → HPACK), **CHATBIND-2**, or the **grounding-floor / KB-VENDOR** stream. **Do NOT autostart 6c** — it's a purity finisher, not a gate.

## Open seams for `bench-salvage`

| ID | Title | Severity | Fix loc | Opened/Status |
|---|---|---|---|---|
| S-BS-131 | CE-PACK-6c residual: core council still carries the LIVE `build_source_message_prompt` clinical branch + `phi_redaction` + `settings.HIPAA_*` + provenance/test needles — the grep-empty gap after 6b-CLEAN | low | `compliance_council.py` (source_message) / `phi_redaction.py` | **open** (CE-PACK-6b-CLEAN 2026-06-12) → CE-PACK-6c |
| S-BS-127 | freeze-guard marker-SUBSTRING residual (inherent to the S-BS-124 marker design; not a regression) | low | `tests/_seam_freeze.py` | open |
| S-BS-113 | `seed_ontology --check` STALE (committed ontology vs fresh build: `fidelity.owner_roles` + `_provenance` path strings) — **also fold the `flag_source`/`_provenance.gradeable_note` deleted-path refresh here** when addressed; do NOT full-re-seed (sweeps the `fidelity` owner_roles addition) | low/med | `seed_ontology.py` re-seed | open |
| S-BS-129 | core `_build_signature` clinical prose | medium | — | **CLOSED (this cycle)** |
| S-BS-126/117/119/118 | fixture-path / corpus-determinism / packs-as-code trust residuals | low | various | carried-open |

## Load-bearing context the next monitor MUST know

1. **"Clinical-clean" ≠ "grep-empty" — be precise in any claim.** This cycle removed the THREE named residues (`build_prompt`, `safety_flags`, `_build_signature`). The literal grep is still non-empty because `build_source_message_prompt` is a **live** method (the Lane-2 HIE source_message gate, `stages.py:684` → `compliance_council.py:2182`), plus `phi_redaction.py` / `settings.HIPAA_*` / carve-out & provenance comments / the council test files. All of that is **enumerated + pinned** by `test_6bclean_attestation.py` and deferred to CE-PACK-6c. The SPEC + the attestation docstring both state grep-empty was NOT achieved — keep that honesty in pitch/release language.

2. **The provenance path is intentionally "stale" (D2-a) — do not "fix" it standalone.** `flag_source` still reads `lithrim_bench/runtime/council/safety_flags.py:SAFETY_FLAG_DEFINITIONS` even though that file moved to `packs/healthcare/safety_flags_seed.py`. This was the monitor's Fork-2 ruling: keeping the literal frozen lets `ontology.json` regenerate byte-identical and keeps `assert_clinical_ontology_seam_frozen` byte-frozen (no `_provenance` carve-out = the moat guard isn't weakened). It is comment-guarded as a historical-origin record in both `seed_ontology.py` and the relocated module. The critic flagged the deleted-path refresh as a LOW to fold into the existing **S-BS-113** re-seed, NOT a new seam. If you "honestly" update the path standalone you would trip the frozen-seam guard — don't.

3. **Executor handbacks can overstate the green bar.** This cycle's handback inflated passes (642 vs 639) and undercounted pre-existing failures (2 vs 4) because the executor's env had Azure vars + a gitignored fixture the bare worktree lacks. The fresh-critic worktree is the source of truth for counts. Always re-run + cite the critic's numbers, and remember the persistent **S-BS-96** observation pair fails only under full-suite module pollution (passes in isolation) — judge green by **0-new-at-parent**, not absolute counts (per the gitignored-fixtures / S-BS-119 pattern).

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (Open seams + First move).
3. Read this handoff doc.
4. Read the session log: `.devloop/sessions/session-bench-salvage-CE-PACK-6b-CLEAN-2026-06-12.json`.
5. `git log --oneline -10`.
6. Wait for the user's strategic call. **Do NOT autonomously start CE-PACK-6c** (author its driver only when the user picks it; HARD GATE again).

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- This cycle: session `session-bench-salvage-CE-PACK-6b-CLEAN-2026-06-12.json` · critique `critique-bench-salvage-CE-PACK-6b-CLEAN-2026-06-12.md` · driver `.devloop/prompts/bench-salvage_phaseCE-PACK-6b-CLEAN_clinical-clean-core-council_driver.md`
- Spec: `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` (§3.3 / §4 — 6b-CLEAN DONE, 6c opened)
- Memory: `generic-ce-demarcation` (6b-CLEAN now DONE), `healthcare-realm-as-pack`, `git-commit-pathspec-dirty-index`, `proof-capsule-convention`
- Prior handoff: `.devloop/sessions/HANDOFF_bench-salvage_generic-ce-6b-clean_2026-06-12.md`
