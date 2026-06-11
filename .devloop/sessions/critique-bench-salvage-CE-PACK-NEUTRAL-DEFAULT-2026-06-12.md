# Inline critique — bench-salvage CE-PACK-NEUTRAL-DEFAULT (neutral core default pack)

**Date:** 2026-06-12 · **Mode:** inline (Routine, non-frozen; subagent-executed) · **Verdict:** CLEAN
**Commits:** 0b70d61 (D1 `_core` pack) · 2014daf (D2 flip + conftest pin) · 375f20a (D3/D4 tests) · 60859e6 (D5 docs) — on `d463979`.
**Cold-read basis:** the driver §2/§5 + `git diff d463979 HEAD` + monitor re-runs (roster-identity check, the healthcare-absent proof, the full suite).

## 7-item audit — CLEAN
4 commits exist · scope = exactly `pack.py` + `packs/_core/` + `tests/conftest.py` + 2 tests + a fixture + 2 docs (no core council file — grep-confirmed) · monitor re-ran the suite (627 passed, 0-new vs baseline; the 2 fails = pre-existing S-BS-96 guards) + ruff clean · foreign files (`app.jsx`, `journeys/*`, the demo HANDOFF) untouched throughout · the D0 HALT-gate was honored (the conftest pin measured to bound the flip; proceeded) · session log present.

## The 4 questions
- **Q1 Surface fidelity — PASS.** `DEFAULT_PACK="_core"` (pack.py:46) + docstrings updated; `packs/_core/` satisfies the pack contract (loads, gates pass) with neutral content; `tests/conftest.py` pins `LITHRIM_BENCH_PACK=healthcare` for the legacy suite.
- **Q2 Behavioral fidelity — the load-bearing one, PASS.**
  1. **Roster identity stable** (the correctness property): monitor independently ran `council_roster()` under env-unset (`_core`) vs `healthcare` → **identical** `{behavior,faithfulness,policy,risk,source_message}_judge`. So existing packs still subset-validate against the canonical roster under the new default. The subagent correctly sourced the owner-only `source_message_judge` from `_core`'s `tier1_owners` over neutral codes (the AST `CouncilModel` leg, frozen, supplies the other 4).
  2. **Ships without healthcare** (the goal): `tests/test_neutral_default.py` (5 green) — env-unset → `active_pack()=="_core"`, a generic case grades to `reject`, and `sys.addaudithook` records **zero `packs/healthcare/` reads**. The S-BS-130 "core can't boot without healthcare" is genuinely closed.
  3. **A-STANDALONE-4 tightened** — now asserts zero healthcare reads (was: permitted the 2 roster-metadata files); green.
- **Q3 Out-of-scope intrusion — NONE.** No core council edit; healthcare untouched (still a fully-working opt-in pack, covered green by the pinned suite). The A4 prose fix (`_core` snapshot metadata reworded off the word "healthcare") is in-scope (needed for the zero-leak grep) + disclosed.
- **Q4 Judgment calls — surfaced.** The conftest-pin bounding (validated at D0); sourcing `source_message_judge` from `_core` to hold roster identity; the prose fix. All documented in the report + session log.

## Findings / disposition
- **No undiscovered coupling** — the subagent needed no core edit; the falsification surface stayed clean (unlike CE-STANDALONE-1, which surfaced S-BS-129/130). Good sign the demarcation is converging.
- **S-BS-130 — CLOSED.** `DEFAULT_PACK="_core"`; `council_roster()` reads `packs/_core/`; the core boots + grades with healthcare absent (proven non-vacuously by the audit-hook test).
- **S-BS-125 — RESOLVED (tripwire retired).** The canonical-roster source is now a PURPOSE-BUILT neutral pack (`_core`) that declares the deployable-capability universe — the correct design for "validate the active pack against the core's universe," not an accidental Pro pack. The `council_roster`(canonical) vs `council_known_codes`(active) split is now principled (core universe vs active pack); `_core.production_judges == _ROLE_DEPLOYMENT` keys, so the old tripwire condition is now a designed invariant. (The `council_known_codes` self-check vacuity remains a documented intentional no-op, unchanged.)
- **Citation-drift (benign):** driver cites HEAD `b21820e`; actual parent is `d463979` (the driver-authoring commit), byte-identical code state — used `b21820e` as the code baseline as intended.

## Owed
- Live smoke (CE-STANDALONE-1, still owed) unaffected. No new owed items.

**Disposition:** CLEAN. The core now **ships standalone without the healthcare pack** — the release-gating S-BS-130 is closed, S-BS-125 retired, roster identity provably stable, suite 0-new. Two cycles remain for the *clinical-clean core* (6b-ROUTE → 6b-CLEAN incl. the S-BS-129 signature).
