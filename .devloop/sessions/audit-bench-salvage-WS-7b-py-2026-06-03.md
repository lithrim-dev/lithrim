# Audit + close record — `bench-salvage` WS-7b-py (KB-grounding tool, headless parallel executor)

**Verdict:** CLEAN (audited from source). **Status: AUDITED + PRESERVED, MERGE-PENDING.**
**Mode:** background worktree executor (user-authorized hands-off parallel, 2026-06-02→03); the monitor audit IS the gate (no interactive plan-review).
**Work preserved at:** branch **`bench-salvage/ws7b-kb` @ `47b590c`** (decoupled from the ephemeral worktree `agent-a0ec597dbec6ca176`). Base `ce73691`. **NOT merged to `bench-salvage/ws6c-dspy`** — see merge-pending.

## What landed
A **KB-grounding verification tool** that disproves a confident-but-wrong council flag by grounding its claim in the backend KB — the S-BS-7 presence-check generalized from transcript to the `:8002` KB corpus (the Phase-3 "Align" engine; feeds the calibration trainer's Act 3 per `[[calibration-trainer-is-the-product]]`). 7 files, +879/-4: `KbRagTool` (`verification/tools.py`), `KbGrounding` suppress contract (`harness/grounding.py`), additive BFF `GET /v1/kb/{namespace}/search`, tests, session log.

## Gates (monitor-verified)
- **A1 KbRagTool tri-state — PASS (source `tools.py:375-429`).** Grounds only on a corroborated hit clearing `min_score` AND the match predicate; endpoint error → `conforms=None`; suppress-direction (`expect="present"`) miss → `None`. **Never auto-clears.**
- **A2 kb_grounding suppress — PASS (source `grounding.py`).** `check()` suppresses **only** on `conforms is True` (`:259`); `None`/`False`/error leave the flag active. Registered (`_CONTRACT_EXECUTORS{"kb_grounding": KbGrounding}` `:290`); injected `http_client` threaded via `_HTTP_CONTRACT_TYPES` (`:291`). The dangerous BLOCK→PASS direction is correctly conservative — **never clears by silence/error.**
- **A3 leverage gate — PASS (independently re-run).** `import lithrim_bench.harness.grounding` + `verification` leaks **zero** heavy modules (no httpx/onnx/pinecone/pymongo); all deps lazy/method-local; composes over live `:8002 /v1/kb/{namespace}/search`. **No heavy stack salvaged** (the user's governing constraint held).
- **A4/A5** — agent-claimed (additive BFF, 5 routes unchanged; 13 KB tests + 192/1 suite + ruff clean). **Re-verify at merge** (the reconciled code, not the branch).

## Corrections (the headless run's misses — monitor-adjudicated)
1. **Agent's "predates WS-6d" = mislabel.** `ce73691` *includes* WS-6d; it predates the **uncommitted** concurrent `dosage_grounding` work. The agent built against the correct committed base.
2. **The real drift was the monitor's:** the WS-7b brief was grounded against the concurrent calibration session's *uncommitted* `dosage_grounding` edits (cited `_FLOOR_CONTRACT_TYPES{…dosage_grounding}` / `DosageGroundingTool`), which the worktree (off committed `ce73691`) correctly lacked. No harm — the agent built to the true base.
3. **Agent seam mis-numbering.** It filed "S-BS-16"/"S-BS-17" — both already taken (floor-inject validation; shell-demo-content). Corrected to **S-BS-40 / S-BS-41** below.

## Merge-pending (the only remaining step)
**Blocked:** the KB branch edits `grounding.py`/`tools.py`/`verification/__init__.py` — the exact files the concurrent **calibration-trainer session has uncommitted** in the main working tree (`dosage_grounding` floor + `SPEC_CALIBRATION_TRAINER.md` + calib-run artifacts). Merging over uncommitted work that touches the same files is unsafe; the monitor will not stash another session's in-progress edits.
**Unblock = the user commits the calibration work**, then a **3-way reconcile** (≈10 min, mostly additive unions):
- `tools.py`: `KbRagTool` (KB) + `DosageGroundingTool` (calib) — both new classes.
- `grounding.py`: `kb_grounding` suppress (`_CONTRACT_EXECUTORS` + `_HTTP_CONTRACT_TYPES`) + `dosage_grounding` floor (`_FLOOR_CONTRACT_TYPES`) — union the registries.
- `verification/__init__.py`: union the exports.
- `apps/bff/app.py`: additive `/v1/kb` (no concurrent overlap expected).

## Seams opened
- **S-BS-40** (low, pre-existing) — `debuglithrim` venv pairs `starlette 0.27.0` + `httpx 0.28.1`, so `fastapi.testclient.TestClient(app=…)` raises `TypeError` on **every** `tests/test_ws5_bff.py` test (incl. untouched pre-existing). Not WS-7b-py; the env-analogue of S-BS-24/S-BS-39 for the BFF test surface. New BFF KB tests proven by direct-handler call. A spawn-task to align the venv deps was filed by the executor.
- **S-BS-41** (medium, GATE-before-ship) — `run_eval` threads no `http_client` into `ground()`, so a *committed* `kb_grounding` contract would hit **live `:8002` under `--replay`** (the S-BS-13 analog for the suppress path). **Inert today** (no `kb_grounding` declared in the committed `clinical_v1` ontology). Gate: add a replay `http_client` injection + validate before any `kb_grounding` contract ships in a committed ontology. Pairs with S-BS-13/S-BS-16.

## Disposition
The parallel track paid off: a sound, leverage-respecting KB-grounding capability, audited CLEAN, preserved on `bench-salvage/ws7b-kb`. **Cycle closed at the audit; the merge is a tracked mechanical follow-up gated on the calibration commit.** When the user commits the calibration work, merge `bench-salvage/ws7b-kb` + reconcile + re-verify A4/A5 + register the final merge hash.

## MERGED — 2026-06-04 @ `dc1cb7c`

The calibration vertical was committed (`a6424da..4b46ad4`) and `bench-salvage/ws7b-kb @ 47b590c` was merged into `bench-salvage/ws6c-dspy` at **`dc1cb7c`** (3-way, base `ce73691`). The only conflicts were the two predicted additive-union sites — `verification/__init__.py` `__all__` (union `DosageGroundingTool` + `KbRagTool`) and `verification/tools.py` `.spec` imports (union `TOOL_DOSAGE_GROUNDING` + `TOOL_KB_RAG`); `grounding.py` (both registries), `apps/bff/app.py` (`/v1/kb` + `/v1/case`), and the tests auto-merged. **A4/A5 re-verified on the reconciled code:** `tests/verification/` **79 passed** on debuglithrim (incl. `test_kb_grounding` + `test_dosage_floor`); the default-core leverage gate holds — `import lithrim_bench.harness.grounding` pulls no httpx/onnxruntime/pinecone/openai. **S-BS-40** (debuglithrim TestClient env break) still gates `test_ws5_bff` on debuglithrim — pre-existing, not the merge. **S-BS-41** (`run_eval` threads no `http_client` → a committed `kb_grounding` contract hits live `:8002` under `--replay`) stays **open as a GATE** before any `kb_grounding` ships in a committed ontology.
