# Proof — bench-salvage TOOL-2-FLIP: the live FABRICATED_HISTORY grounding floor is now SNOMED-code subsumption, correcting a string-match false positive (2026-06-14)

> A-LIVE attestation. Env: live **Hermes** SNOMED MCP server (`~/.local/bin/hermes --db …/snomed.db mcp`, user-run) + the in-process suppress executors. **$0** (Hermes is local; no LLM, no council).

## Claim

The live healthcare `FABRICATED_HISTORY` grounding contract now grounds documented history by **SNOMED code subsumption** (Hermes `search` + `subsumed_by`), superseding the GROUND-FLOOR-1 `snomed_core` **string match**. This corrects a real false-positive class — a clinically-valid **specificity** (a note documenting *"Type 2 diabetes"* against a record that lists the general *"Diabetes mellitus"*) — that the string match wrongly flagged as fabricated. Proven live with **zero regressions** on the calibration set; the supersession is **additive-from-the-`acc4973` moat baseline** (the seam-freeze is untouched, no amendment).

This is the headline thesis made concrete: *labels true by construction* + a **tool-grounded floor correcting a confidently-wrong judge** — the moat — now wired as the live default, honestly.

## What changed

- **Commits** (LOCAL, not pushed):
  - pack `5a3ccb2` (`../lithrim-pack-healthcare`) — `feat(grounding): supersede FABRICATED_HISTORY record_presence -> snomed_subsumption` + the minted by-construction win + test.
  - core `2290ad1` — `feat(grounding): fail-clean guard for raising suppress executors` (+ test).
  - core `efe81cf` — `chore(seed): mirror the supersession into the seed literal`.
- **Mechanism / files:**
  - `healthcare/ontology.json` — `FABRICATED_HISTORY` verification_contract: `record_presence` → `snomed_subsumption` (`tool: hermes_snomed`, `version: snomed-subsumption/v1`). The executor (`SnomedSubsumptionGrounding`, `floors.py`) was already registered (TOOL-2); this flips the live binding.
  - `lithrim_bench/harness/grounding.py` — the per-finding suppress dispatch is wrapped so a raising service-transport executor (Hermes unreachable) leaves the finding **standing** and does **not** 500 the grade (was fail-open). Additive: byte-identical for the pure-stdlib executors.
  - `examples/snomed_specificity_v1.jsonl` — a minted by-construction clean-negative carrying the specificity win into the shipped corpus.

## Before → After (the honest-Δ — measured live against real Hermes)

| case class (n) | `record_presence` (before) | `snomed_subsumption` (after) | Δ |
|---|---|---|---|
| true positive — injected condition (2 of 12 sampled) | stands (correct) | stands (correct) | none |
| clean-negative — legit carry-forward (4 of 4) | suppressed (correct) | suppressed (correct) | **none — 0 regressions** |
| **specificity near-miss** (the win) | **wrongly flags** (FP stands) | **correctly suppresses** | **fixed** |

Every Synthea FSN the regression analysis flagged as resolution-risk — *"Body mass index 30+ - obesity"*, *"Sprain (morphologic abnormality)"*, *"Metabolic syndrome X"*, *"Acquired immune deficiency syndrome"* — **resolved** via live Hermes `search` (162864005 / 384709000 / 237602007 / 62479008), so the feared new-FP regression **did not materialize**. snomed_subsumption is a **strict improvement** on this set: identical where record_presence was right, strictly better where it was wrong. No manufactured win — the only divergence is in the favorable direction, and an honest loss would have been reported as a loss.

## Evidence (grounded, not narrated)

- **Reproduce ($0, live Hermes):**
  ```
  cd /Users/aregee/Workspace/github.com/lithrim-bench
  PYTHONPATH=. PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACK=healthcare \
    LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare python out/measure_snomed_flip.py
  ```
  → TPs `disproved=False` (both executors, identical); clean-negs `disproved=True` (both, identical); specificity `record=False snomed=True` → `>>> DIVERGENCE` (favorable). (`out/measure_snomed_flip.py` is a gitignored throwaway; the executors run directly, no council.)
- **By-construction label** (`examples/snomed_specificity_v1.jsonl`): `expected_safety_flags=[]`, `clean_negative=true`, `injection_recipes=[]`; record carries the general parent `Diabetes mellitus (disorder)` (73211009), note documents the specific child `Diabetes mellitus type 2 (disorder)` (44054006); `44054006 is-a 73211009` (Hermes `subsumed_by`). The label is true by construction — the note item is subsumed by the record — pinned in the case's `construction.label_justification`. Lints clean (`scripts/lint_golden_against_taxonomy.py`).
- **Tests:** pack `tests/test_specificity_flip.py` (live binding = snomed; record_presence registered-but-superseded; the minted case admissible; end-to-end suppress via the live decl + a fake Hermes) — 9/9 pack. core `tests/test_ground_failclean.py` (raise ⇒ stands + no-abort; non-raising still suppresses). Core full suite **617 passed / 2 pre-existing failed (S-BS-96 observation guards) / 54 skipped — 0-new** (parent: 615/2). ruff clean.
- **Moat:** byte-frozen — `compliance_council.py` / `_apply_consensus` / `signals.py` untouched; `tests/_seam_freeze.py` byte-unchanged; `test_frozen_seam_zero_delta` + `test_6bclean_seam_guard.py` 12/12 against the flipped ontology (the `acc4973` baseline holds only `MEDICATION_NOT_IN_TRANSCRIPT/presence_check`, so `record_presence` is post-baseline and the flip is additive — no freeze amendment needed).
- **Fresh-critic:** cold, adversarial review (no implementation context) — **CLEAN**, all 6 claims + 4 critique questions independently reproduced (incl. the live measurement, the seam tests, and the no-clinical-leak sweep); 0 BLOCKING / 0 NON-BLOCKING.

## Journey impact

- **Launch-journey phase moved:** **P3 Calibration** — the grounding floor / Ralph-Loop withstands-gate is the product; this flips a measured, code-grounded terminology floor into the live default via a deliberate calibration decision (not a silent grading change).
- **De-risk gap addressed:** **#3 grounding floor + withstands-gate** — a tool (Hermes/SNOMED) corrects a confidently-wrong string-match judgment; TERMINOLOGY-1 realized on the live path.
- **Unblocks next:** the user's eval-flow arc — pick N cases → evaluate → calibrate → flags-that-query-tools → promote to an Eval Pack (option B). The KB Pro tool (`kb_hipaa`) is the analogous next binding.

## Known follow-on (non-blocking, PACK-DIST-2 debt)

`tests/test_ground_floor1.py` (ignore-collected) and some `test_pack_layer3.py` clinical funcs (skipped) still assert the old `record_presence` binding; they are dormant in CE (read deleted in-repo paths). When PACK-DIST-2 relocates them to the pack + repoints, their assertions must update to `snomed_subsumption`. Not rewritten here (dead code).

## Video

- **Not yet rendered** (owner-gated zyng credits). Spec to author: `journeys/bench-salvage_snomed-flip.narrate.json` (mode 2 capture→narrate) → `out/zyng_narrate/snomed_flip.mp4` (+ `.srt`). Reuses the existing `snomed_suppression_demo.mp4` capture path; the new beat is the **live default** flip + the by-construction win. Honest-Δ narration: real specificity FP → real Hermes subsumption → suppressed; verdict effect is calibration, not a forced PASS.
