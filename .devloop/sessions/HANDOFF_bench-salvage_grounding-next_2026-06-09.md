# HANDOFF — bench-salvage — 2026-06-09 (conversational journey COMPLETE → grounding next)

> **For the FRESH session.** This session completed the **conversational journey** (all 4 acts of the frozen demo are now demonstrable LIVE through chat) and set up the **grounding floor** as the next, moat-defining work. The user's direction: *"tackle grounding in a fresh session."*
> **Resume:** `/devloop-resume bench-salvage`, read the memory `grounding-floor-is-the-moat-next`, then start the grounding work.

## 🔴 NEXT — the grounding floor (the moat)
The runtime grounding floor is **THIN: 1 of 19 gradeable flags** has a `verification_contract` (`MEDICATION_NOT_IN_TRANSCRIPT → med-presence-check/v1` in `data/ontology/clinical_v1.json`). The other 18 flags have **no independent floor** — the judge's vote stands alone.

- **The motivating case (seen LIVE this session):** the `diabetes_soap_clean_compliant` over-fire — a CLEAN case the council BLOCKed (`FABRICATED_HISTORY`/`HALLUCINATED_DETAIL`, **0 grounded suppressions**). It over-fired *because* those flags have no validator. That's the grounding theory's punch, on a real case.
- **The work:** generate Jute validators (verification contracts) for the flags — esp. `FABRICATED_HISTORY` (a patient-record / transcript grounding check). Machinery EXISTS: `lithrim_bench/verification/` (the WS-3 promote — `jute_gen`/`jute_dspy`/`mutation`/`router`, behind the `[verification]` extra, **live-bench-gated vs `:3031`** — the served JUTE spec lies). [[jute-runtime-builtin-gap]]
- **The UI hook is already wired:** the JudgeEditor card's **ATTACH VALIDATORS** row (`dosage_grounding · structural_jute · kb_rag · jute_gen · record_rag`) — validators attach to a judge as the **withstands-gate**.
- **Do NOT touch optimize.** It's ALREADY grounded (by-construction `recipe=label` corpus, not judge self-report — the anti-circularity FHIR-AgentBench lacks). The FLOOR is the gap, not the calibration target.

Full setup in memory **`grounding-floor-is-the-moat-next`**. Specs: `docs/specs/SPEC_CALIBRATION_TRAINER.md`, `SPEC_CONVERSATIONAL_CONTROL_PLANE.md`.

## What this session shipped (all on `bench-salvage/ws6c-dspy`, NOT pushed)
| Cycle | Commits | What |
|---|---|---|
| **LAUNCH-PREP** (close + A-LIVE) | `84c3c82`..`ec526f4`, `0dd5613` (S-BS-110), `39e64e6` (S-BS-111), `4273982` (S-BS-108), `59608f0` | standalone in_process core; A-LIVE attested; cost-label + truncation + imported-replay fixes |
| **CHATBIND-3** | `238e4fc`, `01b6e50` | Case tab + inline Case Summary card (`show_case`); generic artifact render; FHIR note decoded |
| **CHATBIND-4** | `d57f05d` | consented live-run hand-off (`propose_live_run`); A-LIVE attested (user confirm → `54b46132`) |
| **Calibration (Act 3)** | `a045ace` | `get_judge` surfaces the JudgeEditor Optimize button + a nudge (no new tool) + fixed CHATBIND-3/4 tool-set test debt (12→14) |
| memory/spec | — | `jute-for-data-transformations`, `grounding-floor-is-the-moat-next`, `SPEC_CONVERSATIONAL_CONTROL_PLANE` |

The 4-act journey conversationally: **Act 1** (show_case/author_*) ✅ · **Act 2** (show_case→propose_live_run→confirm→council) ✅ live · **Act 3** (get_judge→Optimize→Δ) ✅ live · **Act 4** (run_eval_pack ✅; data=ingestion deferred; Pro=packaging).

## A-SAFE — held throughout (the sacred invariant)
14 chat tools; the allowlist is EXACTLY the `_TOOL_SPECS` set; **no tool can fire a paid run**. The two paid hand-offs (`propose_live_run`, the JudgeEditor Optimize) emit a `$0` directive/surface a card — the **human's in-DOM CostModal confirm is the only paid path**. Verified non-vacuously (shell + bff) and live (the user's confirm fired `54b46132`, not the agent). Any chat-surface change stays HARD-GATE-class.

## Open seams
- **S-BS-112** (low) the JudgeEditor "ATTACH VALIDATORS" lists validators but most flags have no real contract — the grounding-floor target (the whole point of the next session).
- **S-BS-104** the in_process council over-fires on clean cases (the diabetes case) — the floor is too thin to catch it. The grounding work closes this.
- Carried: S-BS-109 (eval-pack live needs `:8002`), S-BS-98/105 (med), S-BS-96/101/102/106/107/108(ConfigTab)/110/111.

## Standing context
- **Prefs:** no autostart (`curl /health`, halt+ask if down); **no push without explicit owner approval** (the large unpushed stack is owner-gated); LLM-cost-conscious (**optimize is PAID** — the user authorizes it explicitly); **honest-Δ only** (a manufactured win = FAIL); pathspec-only commits (the dirty shared index) [[git-commit-pathspec-dirty-index]]; **shell JSX is hand-compact, NO prettier** [[shell-no-prettier-handcompact-jsx]]; run tests via the explicit `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python` (the `PYENV_VERSION=debuglithrim` drift) [[council-runtime-test-env]].
- **The user runs the executor sessions + the paid/live runs; the monitor audits + commits close artifacts pathspec-only.**

## Pointers
- **Memory:** `grounding-floor-is-the-moat-next` (THE next-session brief), `jute-for-data-transformations`, `conversational-first-core-plugin-line`, `self-asserting-loop-honesty-moat`.
- **Specs:** `SPEC_CALIBRATION_TRAINER.md`, `SPEC_CONVERSATIONAL_CONTROL_PLANE.md`, `SPEC_PLUGIN_ARCHITECTURE.md` (HPACK).
- **Verification core:** `lithrim_bench/verification/` (`jute_gen`/`jute_dspy`/`mutation`/`router`).
- **The over-fire evidence:** `docs/research/RUN_clean_{nka_in_process,compliant_overfire_in_process}_2026-06-09.json`.
