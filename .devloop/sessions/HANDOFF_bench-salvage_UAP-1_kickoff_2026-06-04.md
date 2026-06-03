# HANDOFF — `bench-salvage` → UAP-1 kickoff (2026-06-04)

> **Written by the monitor on session close.** Load-bearing context for the next monitor session that resumes after a break. This session was mostly **monitor-side** (cycle closes + a strategic reframe + a LOCKED spec), not a single executor cycle — so this handoff is the primary bridge.

---

## What just landed (this session, 2026-06-04)

All on `bench-salvage/ws6c-dspy`, **nothing pushed**. Tree clean except local `.claude/` + a stray `KICKOFF_CRITIC_…DSPy-2026-06-02.md`.

1. **WS-6c-DSPy-3b closed** — the DSPy judge loop measured (risk_judge held-out **Δ negative + honest**; gate not loosened). Audit CLEAN + fresh-critic CLEAN. `a94f8b2`. Opened **S-BS-48/49**.
2. **Calibration vertical landed** (the concurrent parallel-session work, preserve-not-bless) — `a6424da..4b46ad4`: `dosage_grounding` floor + `DosageGroundingTool` (6/6) · `SPEC_CALIBRATION_TRAINER` + demo · council `extra=ignore` · the semantic-moat journey rework (Acts 1–4) + `/v1/case` BFF · UX/design critique · semantic-moat research (PAPER_OUTLINE amendment, **§1 unchanged**) · devstack tooling.
3. **`ws7b-kb` merged → `dc1cb7c`** (KB-grounding suppress; additive union; **`tests/verification/` 79 passed**; leverage gate holds). Merge-pending item closed.
4. **WS-7a verify-and-closed** — the journey's Phase-2 Verify is live-wired (it landed in `26e479f`, so this was verify-and-close, not build): D4 test `0b1d2d0` (shell 33/33, build clean) + close `8d72cff`. **A3 deviated** (the journey grew the BFF) → **S-BS-50/51**. **`:5180` smoke OWED** (deprioritized — journey frozen).
5. **STRATEGIC REFRAME + SPEC LOCK** (`213545d..cd60da1`) — see below.

## What's next

- **Next phase:** **UAP-1** — config-plane write-path (`/v1/agent` save/load) + the **draft→grade** loop (S-BS-26b) + the **audit-record + actor foundation** (R0/R1/R3). The no-regret first build of the LOCKED product; sidesteps every open dependency.
- **Driver bundle:** `bench-salvage-phaseUAP-1-config-plane-write-path-driver` (**status: stub**, registered in `prompts/index.json`).
- **First monitor move:** `/devloop-expand-driver bench-salvage UAP-1` (re-grep `config.py`/`ontology.py`/`app.py`/`run_eval.py`, fill deliverables + the AuditRecord/actor design + acceptance + plan-review).
- **Blocked by:** none (OQ-1..5 resolved at lock).

## The reframe (the load-bearing thing to internalize)

**The journey is FROZEN** (a pitch/onboarding demo). The DSPy-judge/calibration track and the shell/product track are **ONE program**: a **complete product whose UI drives the author→process loop** — *create judges → create flags → run processing* — over the WS-1 config plane, with a **first-class why/when/who/what audit trail**. Spec **LOCKED 2026-06-04**: `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` (registered in CLAUDE.md doc-org; memory `unified-authoring-product-frozen-journey`).

**Entity model (LOCKED, §2A/§2B/§12):**
- **Judges** = *formed by ASSIGNING an ontology subset* → the assigned flags' `JudgeQuestion`s become the refinement questions (ontology-as-source; `council_roles/*.txt` retires). Judges **execute** persisted smart-contract validators, **never generate** them.
- **GroundingChecks** = first-class **independent** entities, run per evaluation alongside the judges.
- **Withstands-gate (Ralph-Loop)** = ontology rules + validator outputs are **signals**; a judge's verdict stands only if its reasoning withstands them. **Locus = BOTH** (per-judge critique primary + post-consensus grounding for independent checks). The tool-grounded floor generalized per-judge = the moat.
- **Auditability** = every action (authoring + processing) emits an immutable `AuditRecord {ts, actor{type,id}, action, target, why(typed), before/after, run_id, case_id}`. Two streams: config-change audit (**NET-NEW** — the config plane overwrites today via `save_agent`; needs an append-only log + actor handle) + run-provenance (**EXISTS** — the WS-6d `SqliteProvenanceStore` blob + `corpus.py` corrections; surface as a report). The record shape + actor model land in **UAP-1**.

## Open seams that gate the UAP phases

| ID | Title | Sev | Gates |
|---|---|---|---|
| S-BS-26b | a `PUT /v1/ontology` draft doesn't feed a run (`run_eval` reads the committed seed) | low | **UAP-1 / R3** |
| S-BS-50 | journey hardcodes `BFF_URL` (bypasses `bff.js` `VITE_BFF_URL`) | low | all UAP (route through `bff.js`) |
| S-BS-51 | the §10-locked v1 BFF surface grew unratified (`/v1/case` + council view + `in_process`) | medium | UAP BFF work (ratify §10 as routes are added) |
| S-BS-13/16/41 | floor/KB ship-gates (replay-apply · inject-param validation · `run_eval` no `http_client`) | med | **UAP-3** (before any floor/KB ships from a committed ontology) |
| S-BS-12 | bidirectional snapshot lint (snapshot-code-not-gradeable) | med | UAP flag-author validation |
| S-BS-49 | the exact-accept gate harvests only silent demos → held-out regression | med | **UAP-4** (before optimize is trusted to *improve* a judge) |
| S-BS-48 | bind-compiled-demos-by-default (don't ship the negative-Δ demos) | low | UAP-4 |

(Full seam table + the WS-0..WS-7a history in `STREAM_bench-salvage.md`.)

## Known landmines

1. **Shared dirty branch.** The tree has carried foreign/parallel work all session — **always `git commit -- <your-files>` (never bare-commit)**; verify `git diff <parent> HEAD --stat` (memory `git-commit-pathspec-dirty-index`). The calibration vertical was committed preserve-not-bless (it bypassed devloop; it warrants its own audit before it's *relied on* — the floor's S-BS-16 gate).
2. **`debuglithrim` env reds** are pre-existing (S-BS-39/40: `test_ws5_bff` TestClient break) — not a green gate; don't chase them.
3. **Frozen consensus seam.** All UAP work lives ABOVE `compliance_council._apply_consensus` (byte-frozen — the whole DSPy track's A1). Validators stay deterministic.

## User preferences reinforced this session

- **Spec-then-build.** The user iterated the spec (entity model → audit) and **LOCKED** it before building. Honor the locked decisions; surface, don't silently re-decide.
- **Auditability is non-negotiable** (regulated domain) — the audit *is* the product.
- No autostart; pathspec commits; nothing pushed without explicit say-so.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/streams.json` (bench-salvage `current_phase` now points at UAP-1) + `.devloop/state/STREAM_bench-salvage.md` (the UAP-1..4 arc row + First-move banner + open seams).
3. Read this handoff + the LOCKED spec `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md`.
4. `git log --oneline -20` (the `a6424da..cd60da1` arc).
5. Wait for user input. The first action is `/devloop-expand-driver bench-salvage UAP-1` (do NOT autostart).

## References
- Spec (LOCKED): `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md`
- Memory: `unified-authoring-product-frozen-journey`
- Prior cycle session logs: `session-…WS-6c-DSPy-3b….json`; critiques `critique-…WS-6c-DSPy-3b….md` + `critique-…WS-7a-2026-06-04.md`
- WS-7b-py merge record: `audit-bench-salvage-WS-7b-py-2026-06-03.md` (MERGED @ `dc1cb7c`)
