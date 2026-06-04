# HANDOFF — `bench-salvage` → UAP-2 kickoff (2026-06-04)

> **Written by the monitor at UAP-1 close.** Load-bearing context for the next monitor session. UAP-1 (the first build of the LOCKED unified-authoring product) is closed PROCEED-WITH-CAVEATS; UAP-2 is the headline judge-creation gap.
>
> **⏩ UPDATE (session 2 close, 2026-06-04) — read this first:** the UAP-2 driver is now **AUTHORED + READY** (`43d162c`, `.devloop/prompts/bench-salvage_phaseUAP-2_judge-authoring_driver.md`) — the judge-layer citations below were re-grepped and the pack entry backfilled, so the first move is **`/devloop-kickoff bench-salvage UAP-2`** (NOT `/devloop-expand-driver`). Two things landed/baked-in since this handoff was first written: **(a) S-BS-58 FIXED** — UAP-1's A8 `:5180` smoke found that `load_ontology @lru_cache(path)` silently dropped iterative draft edits in the long-running BFF (the core "edit → see it grade" loop); fixed `78929e2` (mtime-keyed) + BFF watch-mode `c2d4495`. The UAP-2 bridge loads draft ontologies, so this fix is load-bearing for it. **(b) DEMONSTRABILITY is first-class** — the JudgeEditor must render the assignment→prompt→questions link **instant + `$0`** (the core "aha", no Azure), with the live verdict-change as the paid finale (user 2026-06-04; memory `judge-creation-must-be-demonstrable`; baked into the driver's A8 + JudgeEditor deliverable).

---

## What just landed (UAP-1, 2026-06-04)

All on `bench-salvage/ws6c-dspy`, **nothing pushed**. Commit range `6bdf975..a7edd25` (7 atomic) + session log `c2e01ae` + the monitor close (this).

- **R1** — `GET/PUT /v1/agent`: assemble + persist an `Agent` to the SQLite config plane from the UI (422 on malformed; writes the config DB only, never the committed seed).
- **R3** — the **draft→grade loop** (closes **S-BS-26(b)**): `run_eval.run(ontology_path=)` threads one resolved source through BOTH committed-seed reads (`run_eval.py:109`+`:142`); the BFF `_resolve_ontology_path` prefers the working copy. A PUT-ed ontology draft now actually grades (A2 = a real `reject→needs_review` flip via `block_at_or_above`, seed byte-unchanged).
- **R0** — the **immutable append-only AuditRecord/actor foundation** (`harness/audit.py`, §2B 9-field shape, INSERT-only `config_audit` table, agent-row+audit-row in one transaction, honest `{system,dev-default}` actor) wired onto every config write + `GET /v1/audit` + `GET /v1/runs/{id}/audit` (sync `PIPELINE_RUNS.get` projection, clean-404 on un-persisted).
- **UI**: `tool-agent_editor` + `tool-audit_log` gen-UI parts, all fetches through `bff.js` (`getAgent/putAgent/getAudit/getRunAudit`).
- **§10 ratified in-cycle** (`a7edd25`) → **S-BS-51 closed**.

**Verdict: PROCEED-WITH-CAVEATS.** Audit CLEAN (7/7, monitor-re-verified) + HARD-GATE genuinely-fresh-critic (agent `a62e561dc12854912`) NON-BLOCKING (0 BLOCKING / 2 NB / 2 OQ). All 5 monitor plan-review notes (N1–N5) folded. Critique: `critique-bench-salvage-phaseUAP-1-2026-06-04.md`.

## The ONE owed gate

**A8 — the `:5180` visual smoke** (user-run, no-autostart). Legs: Agent editor persists + an audit row appears · draft→grade flips a verdict · the audit view renders who/when/what/why. The **run→audit leg needs a persisted (in_process, ~$0.10–0.20) run** — replay persists no blob (**S-BS-52**), and `/v1/run-eval` doesn't surface the `pipeline_run_id` (**S-BS-56**), so the run_id must be fetched from `out/config/bench_collections.sqlite` by hand. When the user attests A8, flip the UAP-1 row + acceptance to PASS and re-mark DONE-clean.

## Monitor correction (do NOT lose this)

The executor hand-back claimed **S-BS-50 closed** — it is **NOT**. S-BS-50 is the *journey's* `BFF_URL` hardcode (`JourneyApp.jsx:18`); the diff touched no journey files (frozen). UAP-1 correctly routed its OWN new code through `bff.js` (A6), but the journey's hardcode persists. **S-BS-50 stays OPEN → WS-5e.** This is recorded in the seam table; don't let the over-claim resurface.

## What's next — UAP-2 (the headline gap)

- **Next phase:** **UAP-2 / R2** — `JudgeEditor` gen-UI widget + `GET/PUT /v1/judges/{role}` + `POST /v1/judges/{role}/optimize` via **ontology-assignment** (OQ-1, decided): a judge is formed by ASSIGNING an ontology subset → the assigned flags' `JudgeQuestion`s become its refinement questions. Judges **execute** persisted validators, never generate them.
- **The load-bearing decision = the prompt↔ontology bridge** (SPEC §3.1.2): the runtime prompt renders from the assignment; `council_roles/*.txt` becomes a render target / retires; UI-authored questions write to the ontology (`questions`). Touches safety-critical prose (cf. S-BS-11) — render carefully + keep the byte-parity guard (the WS-6c-DSPy-2-live `load_role_prompt`/`_load_role_prompts:527` parity).
- **First monitor move:** `/devloop-expand-driver bench-salvage UAP-2` — re-grep `runtime/council/judges_dspy.py` (`Judge`/`build_trio`/`build_judge_lm`), `judge_metric.py` (`LENS_BY_ROLE`/`make_judge_metric`), `ontology.py` (`questions_for(role)`/`owners_of`), `council_roles/*.txt`, `apps/bff/app.py`, `apps/shell/src/genui/registry.js`. There is no UAP-2 task-pack entry yet (the pack predated the reframe; backfill it as for UAP-1 — see memory `devloop-task-pack-stale-uap-from-spec`).
- **Owner↔emit + snapshot are author-time 422 gates** (invariants #1/#4; S-BS-31/S-BS-42). The optimize step (R5) is **UAP-4**, gated on **S-BS-49** — keep it out of UAP-2.

## Open seams that gate the remaining UAP phases

| ID | Title | Sev | Gates |
|---|---|---|---|
| S-BS-50 | journey hardcodes `BFF_URL` (still OPEN — monitor-corrected) | low | all UAP (route the journey through `bff.js`) → WS-5e |
| S-BS-52 | replay runs not auditable (no provenance blob) | med | UAP-3 (run-history + replay-provenance sink) |
| S-BS-55 | run-audit projection attaches stage-shared evidence per-judge | low | UAP-3 |
| S-BS-56 | `/v1/run-eval` doesn't surface `pipeline_run_id` | low | UAP-3 (run-history surfaces ids) |
| S-BS-53 | OQ §2B `why` vs canonical before/after (resolved in code) | low | UAP spec reconcile |
| S-BS-57 | stale `app.py` module docstring | low | fix on next `app.py` touch (UAP-2) |
| S-BS-13/16/41 | floor/KB ship-gates | med | **UAP-3** (before any floor/KB ships from a committed ontology) |
| S-BS-12 | bidirectional snapshot lint | med | UAP-2 flag/judge author validation |
| S-BS-49 | exact-accept gate harvests only silent demos | med | **UAP-4** (before optimize is trusted to improve a judge) |
| S-BS-48 | bind-compiled-demos-by-default (don't ship negative-Δ demos) | low | UAP-4 |

(Full seam table + the WS-0..UAP-1 history in `STREAM_bench-salvage.md`.)

## Known landmines

1. **Shared dirty branch.** The tree carries untracked `.claude/` + a stray `KICKOFF_CRITIC_…` + a parallel `docs/research/REPORT_fhir_agentbench_2026-06-04.md` — **always `git commit -- <files>` (never bare-commit)**; verify `git diff <parent> HEAD --stat` (memory `git-commit-pathspec-dirty-index`).
2. **Frozen consensus seam.** All UAP work lives ABOVE `compliance_council._apply_consensus` (byte-frozen — the whole DSPy track's A1). Validators stay deterministic.
3. **`debuglithrim` env reds** are pre-existing (S-BS-39/40) — not a green gate; don't chase them. The cycle's green bar is: ruff-clean on the changed files, default + debuglithrim suites, Vitest.
4. **Task pack is stale** (memory `devloop-task-pack-stale-uap-from-spec`): author UAP-2 from the LOCKED SPEC + an index stub; backfill the pack entry in the same commit.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/streams.json` + `.devloop/state/STREAM_bench-salvage.md` (the UAP-1 row + the First-move lead + open seams).
3. Read this handoff + the LOCKED spec `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §3.1 (Stage-1 judge creation) + §12 (decisions).
4. If A8 is still owed: request the `:5180` smoke; on attestation, flip UAP-1 A8→PASS.
5. First action: `/devloop-expand-driver bench-salvage UAP-2` (do NOT autostart).

## References
- Spec (LOCKED): `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §3.1 / §4 / §5 R2 / §12
- Session log: `.devloop/sessions/session-bench-salvage-phaseUAP-1-2026-06-04.json`
- Critique: `.devloop/sessions/critique-bench-salvage-phaseUAP-1-2026-06-04.md`
- Prior handoff: `.devloop/sessions/HANDOFF_bench-salvage_UAP-1_kickoff_2026-06-04.md`
- Memory: `unified-authoring-product-frozen-journey` · `devloop-task-pack-stale-uap-from-spec` · `git-commit-pathspec-dirty-index`
