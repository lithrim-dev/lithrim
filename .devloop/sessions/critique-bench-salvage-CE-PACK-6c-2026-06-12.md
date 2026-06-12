# Spec-Adherence Critique — `bench-salvage` phase CE-PACK-6c

> Fresh-critic mode (HARD GATE). Worktree-isolated, adversarial-by-reproduction. The FINALE of the generic-CE demarcation program.

## Metadata

- **Stream:** bench-salvage
- **Phase:** CE-PACK-6c — retire `build_source_message_prompt` + decide `phi_redaction`'s fate (the last live clinical code)
- **Driver bundle:** `bench-salvage-phaseCE-PACK-6c-retire-source-message-prompt-decide-phi-redaction-driver`
- **Commits audited:** `7c41f0c..1efe006` (6 deliverables + session log) atop parent `ff04b46`; moat baseline `acc4973`
- **Spec(s) read against:** `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` §0/§4; `tests/test_6bclean_attestation.py` (the residual contract); `tests/_seam_freeze.py`
- **Critique mode:** `fresh-critic` (separate worktree-isolated session)
- **Date:** 2026-06-12
- **Reviewer:** critic session `a7febcb0de587d0c3` (opus, `isolation: worktree`)

---

## Verdict

**NON-BLOCKING FINDINGS — [0 BLOCKING / 2 NON-BLOCKING / 0 OPEN-QUESTION]**

The last live clinical CODE (`build_source_message_prompt`) is out of the frozen core council with the **moat byte-identical vs `acc4973`**, the freeze guard **reproduced non-vacuous in both directions** (both new markers proven load-bearing), the source_message stage correctly rerouted (zero live callers, bench-dead re-confirmed), `phi_redaction` kept as a working generic privacy mechanism, and the attestation honest (no grep-empty overclaim). The 2 NB are bookkeeping — an env-inflated suite count (corrected to 644/4/3, 0-new) and a cosmetic byte-count convention drift in the docs.

---

## 1. Surface fidelity

| Plan ruling | Implementation | Match? | Severity |
|---|---|---|---|
| Fork A: reroute source_message → authored | `stages.run_semantic_source_message:969` `if council_evaluate is None: council_evaluate = _default_authored_evaluator()` (mirror of the transcript reroute) | exact | — |
| D1 frozen: delete `build_source_message_prompt`; source_message branch → `CE-PACK-6c` raise | `compliance_council.py` diff = 1 ins / 109 del, 2 hunks (def deletion + the marked raise); transcript `else` 6b raise byte-unchanged | exact | — |
| `:1085` role-select = LEAVE (ruled) | untouched (shifted to `:977`, byte-identical to parent) | exact | — |
| Fork B: keep `phi_redaction` in core; genericize prose; keep `HIPAA_*` keys | prose-only diff; `settings.py` not in cycle diff; mechanism works | exact | — |
| D4: extend the guard with `def build_source_message_prompt` + `CE-PACK-6c` markers | both added; both proven load-bearing | exact | — |

**Findings:** No surface drift. Foreign/demo files (`apps/shell/src/app.jsx`, `journeys/*`) untouched; Fork C (`judge_metric`/`judge_assignment`/`judges_dspy`) untouched.

---

## 2. Behavioral fidelity

### Behavior 1: the moat is byte-frozen
- **Spec:** the consensus/withstands MECHANISM is byte-frozen vs `acc4973`.
- **Verification:** full-body extraction HEAD vs `git show acc4973:…`.
- **Result:** `_apply_consensus` + `extract_verdict_confidence` **byte-identical** (HEAD == acc4973). **Chain closes? YES.** *(Absolute byte figures differ by extraction convention — see NB-2 — but the identity holds.)*

### Behavior 2: the freeze guard is non-vacuous in BOTH directions
- **Spec:** driver D4 — an unauthorized deletion must still FAIL; the new markers must be load-bearing.
- **Test:** `test_6bclean_seam_guard.py` (11/11) + scratch-mutation.
- **Result:** delete `_apply_consensus` → raises; delete `_format_kb_citations` (unauthorized) → raises; marker-less raise → raises; **drop either new marker → the legit edit becomes unauthorized → guard FAILS** (both load-bearing). **Chain closes? YES.**

### Behavior 3: the reroute is correct and `build_source_message_prompt` has no live caller
- **Spec:** Fork A / C1 — only the source_message path reroutes; `evaluate()` builds no prompt; bench-dead.
- **Result:** zero live `build_source_message_prompt(` call-sites; both `evaluate()` branches raise; nothing in `lithrim_bench/`/`data/`/`tests/` sets `context_kind=source_message`; `test_6bclean_reroute.py` 3/3. **Chain closes? YES.**

**Findings:** No behavioral drift.

---

## 3. Out-of-scope intrusion

`git diff ff04b46 HEAD --stat` = 11 files, all mapping to D1–D6 + tests: `stages.py`/`compliance_council.py`/`phi_redaction.py` (D1/D2), `_seam_freeze.py`/`test_6bclean_seam_guard.py` (D4), `test_6bclean_reroute.py` (D1 test), `test_6bclean_attestation.py` (D5), `SPEC`/`CLAUDE.md`/`STREAM` (D6), session log.

**Findings:** No intrusion. Every commit pathspec-scoped; foreign/demo files untouched.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the honest grep bar (Fork D)
- **Decided:** A1 = "no live clinical CODE" (`grep 'def build_source_message_prompt|def build_prompt'` → empty), NOT literal grep-empty — the FROZEN carve-out/provenance comments + `HIPAA_*` config keys are passive residual, enumerated + pinned by `test_6bclean_attestation.py`.
- **Resolution:** ACCEPTED at plan-review. Non-vacuous (`test_no_live_clinical_code` fails on a scratch fake def; `test_enumerated_buckets_are_not_stale` confirms `phi_redaction.py` retains a needle → correctly still listed). SPEC/STREAM/CLAUDE.md explicitly disclaim grep-empty.

### Ambiguity 2: `:1085` role-select (driver D1 listed it for removal)
- **Decided:** LEAVE — confirmed dead-after-raise, no clinical needle in its CODE, removal would inject guard-noise on frozen functional lines.
- **Resolution:** monitor-ruled at plan-review. → S-BS-132 (retire the inert source_message machinery wholesale in a future non-frozen cleanup).

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 2 | 0 |

**Total BLOCKING: 0** → cycle MAY close.

### NON-BLOCKING dispositions
1. **Suite-count overstatement (recurring env inflation).** Executor handback claimed **647/2/2**; bare-worktree truth is **644 passed / 4 failed / 3 skipped** at HEAD, **0-new vs parent `ff04b46` (639/4/3)**. The 4 fails are PRE-EXISTING (reproduced at parent): `test_byoc_provider` (unset Azure env), `test_uap3_grade` (missing gitignored `out/scribe_v1.jsonl`), 2 S-BS-96 observation guards (pass 13/13 in isolation). **Disposition:** close cites **0-new vs parent (644/4/3)**, not 647/2. ruff 0-new on all 7 touched files.
2. **Cosmetic byte-count drift (LOW).** STREAM/SPEC cite `_apply_consensus` 28767 B / `extract_verdict_confidence` 1703 B; a full-body extraction yields 29113 / 1700 — a function-boundary convention artifact. **Byte-IDENTITY to `acc4973` is the verified fact and holds.** Harmless; the close states the identity claim, not the absolute number.

---

## Critic discipline self-check (fresh-critic mode)
- [x] Verified the diff via `git show`/`git diff` against commits, not the executor's summary
- [x] Re-ran the suite + ruff independently in an isolated worktree; ground-truthed the count against parent
- [x] Reproduced guard non-vacuity by scratch-mutation, both directions (restored each)
- [x] Did NOT edit any code/spec/driver in the user's tree
- [x] Did NOT confer before writing the verdict

## Appendix: commits audited
```
1efe006 chore(devloop): session log — CE-PACK-6c (6 commits, CLEAN)
022831f docs: 6c done — no live clinical code in the core council; close S-BS-131 (D6)
c486fe8 test(ce): tighten the demarcation attestation to the honest post-6c residual (D5)
556b88b test(seam): non-vacuity for the source_message deletion authorization, both directions (D4)
47ac8f9 refactor(council): genericize phi_redaction prose; keep the generic privacy mechanism in core (D2, Fork B)
2b209f1 refactor(council): delete build_source_message_prompt + raise on the evaluate source_message branch; authorize in the freeze guard (D1 frozen, D4)
7c41f0c refactor(pipeline): reroute the source_message stage off build_source_message_prompt (D1, Fork A)
```

## Appendix: suite observed
`644 passed / 4 failed / 3 skipped` (debuglithrim full run, HEAD `1efe006`); parent `ff04b46` = `639/4/3` → **0-new**. The +5 passed at HEAD are this cycle's new non-vacuity/reroute tests (`test_6bclean_seam_guard` +new, `test_6bclean_reroute` inverted, `test_no_live_clinical_code`).
