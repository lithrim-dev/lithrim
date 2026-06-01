# HANDOFF — `bench-salvage` phase `WS-6a` → phase `WS-6b` kickoff

> Written by the monitor on cycle close. Load-bearing context for the next
> monitor session that takes over WS-6b after a compaction or break.

---

## What just landed

- **Closed phase:** `WS-6a` — backend baseline (curate + commit the pending `../lithrim-backend` WIP). Commits `2f04a40..493b533` (5 atomic, on `mvp-ready`, in **`../lithrim-backend`**, NOT bench).
- **Audit verdict:** **CLEAN** (7/7; independently re-verified: commits real, tree clean, diff maps to deliverables, scope held, no push/tag, 24/24 WIP tests offline, ruff = 3 disclosed nits only).
- **Critique verdict:** **NON-BLOCKING** (inline, user-elected for this HARD-GATE curation cycle) — [.devloop/sessions/critique-bench-salvage-phaseWS-6a-2026-06-01.md](critique-bench-salvage-phaseWS-6a-2026-06-01.md). 0 BLOCKING / 4 NB / 2 OQ.
- **Cycle verdict:** **PROCEED-WITH-CAVEATS** (the one caveat is S-BS-24: the backend suite is red pre-existing, not a regression).
- **Session log:** [.devloop/sessions/session-bench-salvage-phaseWS-6a-2026-06-01.json](session-bench-salvage-phaseWS-6a-2026-06-01.json)

What the 5 commits are: C1 `2f04a40` validator-declared check severity (extends `43b20f6` P0-1); C2 `4b3e4e4` the PIPELINE_GRADING_AUDIT_2026-05-28 D-E/D-J/D-K surface+provenance fixes; C3 `379d1d3` backend docs; C4 `a845809` the `docs/dev-workflow/` .devloop scaffold + migration assessment; C5 `493b533` analysis/migration scripts + `.gitignore` (`out/`, `test-results/`). Two stray bench-doc copies removed; cached-validator timestamp churn restored.

## What's next

- **Next phase:** `WS-6b` — consolidation audit (the strangler-fig audit of the now-clean backend tree, ahead of 6c council-port / 6d persistence swap / 6e ETLP sidecar).
- **Driver bundle:** none yet (no WS-6b bundle in `prompts/index.json`). **Next monitor action: `/devloop-expand-driver bench-salvage WS-6b`.**
- **Blocked by:** nothing structural. WS-6a cleared the precondition (you cannot audit/strangle a dirty tree; the tree is now clean and committed on `mvp-ready`). **But heed S-BS-24** (below) when scoping WS-6b's acceptance.

## Open seams for `bench-salvage` (WS-6a-opened; full table in STREAM)

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-21 | Backend test-rot: 2 collection errors (stale `intent_quality_agent` import; removed `RetrievalMatch`) | low | `tests/test_agent.py:11`, `tests/test_council_evidence_extraction.py:12` | WS-6a | open |
| S-BS-22 | `test_stages_phase_b.py:352` asserts dict but `judge_votes` is a list; fails identically on clean HEAD | medium | `tests/services/pipeline/test_stages_phase_b.py:352` | WS-6a | open |
| S-BS-23 | 3 committed WIP ruff nits preserved as-authored (F401 + 2× I001) | low | `models.py:10`, `stages.py:20`, `test_audit_view_surface_fixes.py:18` | WS-6a | open |
| S-BS-24 | **Backend `-m "not slow"` suite is RED on `mvp-ready`** (52 failed + 2 errors, pre-existing); NOT a green regression gate | **medium** | backend suite (18+ files; see session log) | WS-6a | open |
| S-BS-25 | WS-6a critique Q2: spec-named fix sites not unit-tested (D-E `_judge_votes_from_models` e2e-only; D-K `stages.py` derivation + audit-view rendering) | low/medium | `stages.py:585/806/860`, `pipeline.py:1047` | WS-6a critique | open |

(Standing seams most relevant to the WS-6 consolidation track: **S-BS-7** high, the MED-FP calibration exhibit; **S-BS-11** medium, `build_prompt` not taxonomy-templated; **S-BS-16** medium, floor inject-param validation. See `STREAM_bench-salvage.md` for the full registry S-BS-1..25.)

## Load-bearing context the next monitor MUST know

1. **S-BS-24 is the WS-6b landmine: do NOT assume a green backend suite.** The `-m "not slow"` suite is red on `mvp-ready` (52 failed + 2 errors with Mongo up), and this is **pre-existing**, not WS-6a's doing. WS-6a proved zero regression by stashing the WIP and confirming the failure-set is **identical** clean-HEAD vs WIP. WS-6b should use that same technique (diff the failure-set against the WS-6a baseline) rather than gating on a green run. A dedicated backend test-health cycle (clearing S-BS-21/22/24/25) is the honest prerequisite before the suite can be a regression gate for the council-port (6c).

2. **Concurrency landmine: this stream runs multiple cycles in parallel on shared state files.** WS-6a's close collided with a parallel **WS-5c** close: both touched `STREAM_bench-salvage.md` + `prompts/index.json`. WS-6a had to **wait for WS-5c to commit first** (`e960234`) before editing, and WS-5c had already claimed seam numbers S-BS-19/20 (so WS-6a's seams are S-BS-21..25). Before staging any close, run `git status` in the bench repo and sequence commits: one close commits before the next edits the shared docs. Also remember WS-6a is **cross-repo**: backend commits land in `../lithrim-backend` on `mvp-ready`; the `.devloop` scaffold + session logs live in `lithrim-bench`.

3. **User preferences reinforced this cycle (persist these):** (a) the user **starts services themselves** — Mongo was user-started for the broad suite; never autostart. (b) For a HARD-GATE **curation** cycle, the **diagnose-before-edit D0 manifest is the load-bearing artifact** and an inline critique sufficed (the user elected it; the driver §Hardness permits it). (c) **Attribution correction:** the committed structural-verdict code is `PIPELINE_GRADING_AUDIT_2026-05-28` D-E/D-J/D-K + `43b20f6` P0-1, **NOT** S-P1-15 (the driver's guess) — reconcile the S-P1-15 references in `STREAM_paper-1-copilot.md` (cross-stream, paper-1 monitor). (d) `council_error_rate` (audit fix #8) is **deferred to WS-4b**; WS-6a shipped only the enabling per-run `council_error` flag.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams S-BS-1..25).
3. Read this handoff doc.
4. Read the WS-6a session log + critique (paths above).
5. `git -C ../lithrim-backend log --oneline -8` (the WS-6a commits `2f04a40..493b533` on `mvp-ready`) and `git log --oneline -6` in bench.
6. Read `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (the WS-6 consolidation track / phased breakdown 6b..6e).
7. Wait for user input. Do NOT autonomously start WS-6b; the next action is `/devloop-expand-driver bench-salvage WS-6b`.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-6a-2026-06-01.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-6a-2026-06-01.md`
- Behavioral spec for the committed fixes: `../lithrim-backend/docs/PIPELINE_GRADING_AUDIT_2026-05-28.md` (D-E §3 / D-J §5 / D-K §8)
- Consolidation track: `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-6a_backend-baseline_driver.md`
