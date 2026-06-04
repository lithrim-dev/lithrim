# HANDOFF — `bench-salvage` → UAP-3 kickoff (2026-06-04)

> **Written by the monitor at UAP-2 close.** UAP-2 (judge authoring via ontology-assignment) is closed PROCEED-WITH-CAVEATS. UAP-3 is the processing/run-history phase; UAP-5a (authoring-assist) may pull forward for a $0 demonstrability win.

---

## What just landed (UAP-2, 2026-06-04)

All on `bench-salvage/ws6c-dspy`, **nothing pushed**. Build `86fa1d3..3e89ad5` (executor, 7 atomic) + the close commit (this) on top of the concurrent UAP-5a/5b roadmap commit `111ac3c`.

- **The prompt↔ontology bridge (R2 headline):** `judge_assignment.py render_role_questions` is **LAYERED** — the `council_roles/<role>.txt` seed base + an authored-refinement section composed from the assigned flags; `build_trio(ontology=, assignments=)` threads it into the in-process council so an authored judge re-votes with its authored lens (no WS-2 `:8002`). **A4 byte-parity proven for all 3 roles against the LIVE council loader** ⇒ **S-BS-11 safety prose preserved**; `faithfulness_judge` (0 ontology questions) keeps its full 164-line base.
- **`GET/PUT /v1/judges`** + `harness/judges.py` doc-shim store (shared `audit.upsert_with_audit` txn; `config.save_agent` refactored onto it; `target.type=judge` audit row). **Owner↔emit 422 keys off `LENS_BY_ROLE`**, not the stale ontology `owner_roles` (CITATION-DRIFT → S-BS-59); in-snapshot/gradeable (inv #1/#4); no inert-owner authoring.
- **`JudgeEditor` gen-UI** (`tool-judge_editor`, KNOWN_TOOLS→8) — the **$0 assignment→prompt→questions preview** (demonstrability), all via `bff.js`.
- **§10 ratified.** **A5 frozen 0-delta** (monitor + fresh-critic re-verified): `compliance_council` + `clinical_v1.json` + `data/config/agents` + `council_roles/*.txt` + the per-judge seam dict.

**Verdict: PROCEED-WITH-CAVEATS.** Monitor 7-item audit CLEAN + HARD-GATE genuinely-fresh-critic (agent `a8c77571d1a911d6d`) NON-BLOCKING (0 BLOCKING / 3 NB / 2 OQ; both OQs monitor-resolved — suites reproduced, SPEC §13 edit confirmed foreign). Suites monitor-re-ran ($0): default 277/12 · council 94/3 · BFF 30 · Vitest 40. Critique: `critique-bench-salvage-phaseUAP-2-2026-06-04.md`.

## The owed gate

**A8 — the batched UAP-1 + UAP-2 `:5180` visual smoke** (user-run, no-autostart). UAP-2 legs: the JudgeEditor renders the assignment→prompt→questions link **instant + $0** (demonstrability) · an authored judge re-votes with its authored lens (the paid verdict-change finale; ~$0.10–0.20 in_process). When attested, flip both UAP-1 and UAP-2 A8→PASS.

## Concurrent-edit note (do NOT lose this)

A parallel session is doing **roadmap planning** in this same repo — it committed the **UAP-5a/5b conversational-driver surface** (`111ac3c`: SPEC §13 + R10/R11, additive/surface-only, does NOT alter the lock or §2A/§2B/§4/R0–R5) mid-close. Per user election the UAP-2 close **waited** for that commit, then landed on a clean tree (pathspec-only, no clobber). Expect the arc to read **UAP-1..5** and two `status: stub` index bundles (UAP-5a/5b). The `git-commit-pathspec-dirty-index` landmine is LIVE — concurrent sessions leave foreign edits in shared `.devloop/` state + the SPEC. **Always `git status` + pathspec-commit; if a shared state file is dirty by another session, coordinate/wait before writing it.**

## What's next — UAP-3 (processing + run-history)

- **Next phase:** **UAP-3 / R4+R6** — `RunPanel`/processing surface + eval-pack + run-history. First move: `/devloop-expand-driver bench-salvage UAP-3` (no UAP-3 bundle yet — author from SPEC §5 R4/R6; re-grep `scripts/run_eval.py`, `apps/bff/app.py` `/v1/run-eval`, the `SqliteProvenanceStore`, `apps/shell/src/genui`). Backfill the pack entry (memory `devloop-task-pack-stale-uap-from-spec`).
- **UAP-5a (authoring-assist, R10) MAY pull forward** after UAP-2 for a cheap demonstrability win (reuse the zyng `../zyng/zyng/authoring.py` `LLMClient`/`ClaudeCliClient`; rides the UAP-2 judge/flag endpoints; index stub ready). UAP-5b stays after UAP-3b.

## Open seams that gate the remaining UAP phases

| ID | Title | Sev | Gates |
|---|---|---|---|
| S-BS-52 | replay runs not auditable (no provenance blob) | med | **UAP-3** (run-history + replay-provenance sink) |
| S-BS-55 | run-audit projection attaches stage-shared evidence per-judge | low | UAP-3 |
| S-BS-56 | `/v1/run-eval` doesn't surface `pipeline_run_id` | low | **UAP-3** (run-history surfaces ids; also the A8 run→audit leg) |
| S-BS-13/16/41 | floor/KB ship-gates | med | **UAP-3** (before any floor/KB ships from a committed ontology) |
| S-BS-59 | ontology `owner_roles` stale vs v2 `_TIER1_OWNERS` (re-snapshot deferred) | med | a re-snapshot pass; ties to WS-2 Q4.1 flag-source-authority |
| S-BS-60 | question-text write-back deferred (§12.2) | low | a later R (assignment-first held in UAP-2) |
| S-BS-50 | journey hardcodes `BFF_URL` (still OPEN) | low | WS-5e (journey frozen) |
| S-BS-49 | exact-accept gate harvests only silent demos | med | **UAP-4** (before optimize is trusted) |

(Full seam table + the WS-0..UAP-2 history in `STREAM_bench-salvage.md`.)

## Known landmines

1. **Shared dirty branch + concurrent sessions** (see above). Untracked foreign: `.claude/` + `KICKOFF_CRITIC_…` + `docs/research/REPORT_fhir_agentbench_2026-06-04.md`. **Pathspec-only commits**; verify `git diff <parent> HEAD --stat`.
2. **Frozen consensus seam.** All UAP work lives ABOVE `compliance_council._apply_consensus` + the per-judge seam dict (byte-frozen — the DSPy track's A1).
3. **`debuglithrim` env reds** are pre-existing (S-BS-39/40) — not a green gate. Green bar = ruff-clean on changed files + default + debuglithrim suites + Vitest.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/streams.json` + `.devloop/state/STREAM_bench-salvage.md` (the UAP-2 row + the First-move lead + open seams).
3. Read this handoff + the LOCKED spec `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §5 R4/R6 (UAP-3) — and §13/R10 if pulling UAP-5a forward.
4. If A8 is still owed: request the batched UAP-1 + UAP-2 `:5180` smoke; on attestation, flip both A8→PASS.
5. First action: `/devloop-expand-driver bench-salvage UAP-3` (do NOT autostart).

## References
- Spec (LOCKED): `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §5 R4/R6 / §13 R10/R11
- Session log: `.devloop/sessions/session-bench-salvage-phaseUAP-2-2026-06-04.json`
- Critique: `.devloop/sessions/critique-bench-salvage-phaseUAP-2-2026-06-04.md`
- Prior handoff: `.devloop/sessions/HANDOFF_bench-salvage_phaseUAP-2_kickoff_2026-06-04.md`
- Memory: `unified-authoring-product-frozen-journey` · `judge-creation-must-be-demonstrable` · `git-commit-pathspec-dirty-index` · `devloop-task-pack-stale-uap-from-spec`
