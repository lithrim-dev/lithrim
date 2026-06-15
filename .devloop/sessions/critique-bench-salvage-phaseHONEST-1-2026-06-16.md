# Critique — bench-salvage phase HONEST-1 (HARD GATE, fresh critic)

**Cycle:** commits `bdd24c0..b436471` on `bench-salvage/ws6c-dspy` (`bdd24c0` test-red → `6feb103` W1+W2 → `e2dc71b` W3+W4+W5 → `87d800b` log → `b436471` F541 correction)
**Critic:** fresh subagent (`a565a146`), cold read, no implementation context. Edited nothing; non-mutating git only; foreign `stash@{0}` untouched.
**Date:** 2026-06-16

## VERDICT: 0 BLOCKING / 1 NON-BLOCKING / 1 OQ — **CLEAR-TO-CLOSE** (the 1 NB fixed in-cycle at `b436471`)

## Gate 0 — deterministic (SUPREME) — PASS, 0-new
- **pytest** (env exported): **563 passed / 2 failed / 4 skipped** — the only 2 fails are the pre-existing S-BS-96 observation guards (`test_observation_pipeline.py`), which the critic confirmed **pass in isolation** + `runtime/observation/` is byte-identical base↔HEAD. Necessarily pre-existing.
- **vitest:** **124 passed / 1 failed** — the only fail is the pre-existing S-BS-145 (`app.test.jsx` titlebar "Shell" tab role), which **fails identically in isolation**; `app.test.jsx`/`app.jsx` byte-identical base↔HEAD. The 2 vitest "Errors" (`getMeta` rejections in `panes.chat.test.jsx`/`app.chat.test.jsx`) are in untouched files. Pre-existing.
- **0 new failures.** Tests-first: `bdd24c0` precedes the fixes; **non-vacuity proven by controlled revert** (tree restored exactly) — reverting `report.py` → A1/A1b/A2a/A2b/A3 RED; reverting `artifact.jsx` → A4/A5 RED.

## The 4 questions (cold read of driver + diff)
1. **Surface fidelity — MATCH.** W1-W5 + H-D6 present and traced; the 2 non-listed touches (H-D6 `/v1/case` `labeled` via `_case_labeled`; the `run_eval.py` `labeled=` thread) are both logged APPROVED-AT-PLAN. W3 confirmed pass-through (the `:446` fold unchanged; only `/v1/case` gained the flag).
2. **Behavioral fidelity — HONEST both directions.** Unlabeled → `verdict_match_rate:None`, `ece:None`, `status/label_status:"unlabeled"`, factual counts, caveat — **no `0.0/WARN` and no `1.0/PASS` leak**. Labeled path byte-equivalent for all-labeled batches; a labeled **mismatch still yields a genuine `WARN/0.0`** (real failures still surface). The 30 existing `test_ws4a`+`test_ws5_bff` calibration assertions stay green. W2 nulls ECE/bins on `labeled=False`. UI withholds accuracy on unlabeled (DOM has no `WARN`/`· PASS`/`null ·`); CaseTab reads `labeled===false` as unknown-truth.
3. **Out-of-scope intrusion — NONE.** Moat (`compliance_council`/`signals`/`judge_metric`/`judges_dspy`) = **empty diff**; `grade.py composite()` untouched; in `report.py` `def composite` is unchanged (the only `composite` touch is re-indenting the verdict read into the new `if expected:` branch). Scope confined to the 8 files; no `packs/`/`examples/`/`grade.py`/`picklist.py` leak. The replaced clean-negative `artifact.test.jsx` case was kept (label-gated `labeled:true`) + strengthened by the new A5 — not deleted to hide a regression.
4. **Acceptance non-vacuity — CLEAN.** A1-A6 each backed by a test that fails on a controlled revert.

## Honest-Δ — PASS
No fabricated number leaks either direction; the labeled path is unchanged; real mismatches still surface a genuine WARN. The withheld-accuracy state on unlabeled data is the brand thesis made true on the exact surface a BYO user sees first.

## Findings
- **NON-BLOCKING (S-BS-165, FIXED in-cycle `b436471`):** `ruff F541` at `tests/test_ws5_bff.py:142` — an f-string with no placeholder (a new diff line). Trivially fixed (dropped the `f`); touched files now ruff-clean. (The repo-wide `ruff check .` carries 399 pre-existing errors, so wholesale ruff is not a gate; §7 names pytest+vitest. The session-log "ruff clean" claim was a subset — now true.)
- **OPEN-QUESTION (S-BS-166, low):** A3's partial-batch fixture hands the unlabeled rec `ece=0.0`; a production unlabeled rec carries `ece=None` (W2). A3's assertions don't depend on it, but no test exercises the realistic `ece=None`-in-a-partial-batch pooling path. Spec-author call; not a blocker.

## Recommendation
0 BLOCKING (the 1 NB fixed in-cycle) → clear to close. Next phase = BYO-INGEST (Phase 1). Carry S-BS-166 (low).
