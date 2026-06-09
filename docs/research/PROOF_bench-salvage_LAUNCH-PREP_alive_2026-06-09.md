# PROOF CAPSULE — LAUNCH-PREP standalone A-LIVE (2026-06-09)

> **Claim proven:** the Lithrim OSS core runs a **real council eval standalone** — with `lithrim-backend` / `:8002` **stopped**, no Mongo — a human's paid "Run live" routes to the bundled in-process v2 council (BYO key) and returns a real grounded verdict.
> **Honest-Δ:** this is *not* a "verdict == :8002" claim (in_process is ≥-strict). And the run **surfaced a real bug** (a cost-label inversion) — documented + **fixed in the same session**. A manufactured win would be a fail; this is an honest win with a caught defect.
> **Mode:** monitor-driven live (Chrome MCP), paid-authorized by the owner, no autostart.

## The topology (the standalone precondition — verified)
| Check | Value |
|---|---|
| `lithrim-backend` `:8002` | **DOWN** — `curl :8002/health` → connection refused (before + after the run) |
| `LITHRIM_COUNCIL_BACKEND` | **unset** in the BFF process (pid 4263) → the `in_process` default |
| BFF `:8787` / shell `:5180` | UP |

With `:8002` down, a real council verdict can **only** come from the bundled in-process council.

## The run (paid, in_process)
- **Action:** shell **Shell mode** → `ws0_default` selected → **"Run live"** (the PAID ghost button; `live=true`).
- **Resolver:** `_resolve_run_backend({live:true})` + env unset → `(live_http=False, in_process=True)`.
- **Ground truth — the output blob** ([`RUN_launch_prep_alive_2026-06-09.json`](RUN_launch_prep_alive_2026-06-09.json)): `provenance.grade_path: **in_process**`, written at the run timestamp (`2026-06-09T00:01:32Z`).
- **Latency:** ~18s (real LLM calls — a `$0` replay reads a cached file in <1s).
- **Council — 3 real votes** ([`…_audit_…json`](RUN_launch_prep_alive_audit_2026-06-09.json)):
  | Judge | Vote | Confidence |
  |---|---|---|
  | risk_judge | PASS | `0.99932` (a real logprob — not a self-report) |
  | policy_judge | WARN | `null` (Mistral emits no logprobs) |
  | faithfulness_judge | BLOCK | `1.00` (FABRICATED_HISTORY, INCOMPLETE_DOCUMENTATION) |
- **Composite verdict:** **reject / BLOCK**, semantic-stage flip, 2 active findings.

**⇒ v1 runs standalone: a real, grounded council verdict with no lithrim-backend, no `:8002`, no Mongo.** The RELEASE pre-push gate is satisfied.

## The honest defect the A-LIVE caught — S-BS-110 (fixed)
The artifact pane labeled this **paid in_process run "replay · $0"** (Report metrics + Judge-council header). Cause: `apps/shell/src/artifact.jsx` treated **only** `grade_path === "live"` as paid, so LAUNCH-PREP's new `in_process` default fell through to the `$0` label — a **cost-label inversion** that understates spend and contradicts the BYO-key / you-control-cost positioning.

- **Fix** (`0dd5613`): a module-level `gradeTag(grade_path)` — only `"replay"` is `$0`; `"live"` and `"in_process"` are paid (`in-process · paid`). Applied at both render sites.
- **Verification:** a non-vacuous regression test (`artifact.test.jsx` — an `in_process` run renders `in-process · paid`, never `replay · $0`; fails pre-fix) + **76 shell tests green**; a live `$0` replay confirmed the corrected render (the replay path still reads `replay · $0`). The in_process "after" label is unit-test-verified rather than re-screenshotted, to avoid a second paid run (cost-conscious).

## Honest-Δ note
The live in_process run reported **2 active findings (0 grounded-suppressed)**; the captured `$0` replay baseline shows **7 findings (1 grounded-suppressed)**. These are different runs (a fresh live council vs the cached WS-0 baseline) — reported as-is, no reconciliation claimed. The standalone proof rests on `grade_path: in_process` + `:8002` down + real votes, not on matching the baseline finding-set.

## Artifacts
- `docs/research/RUN_launch_prep_alive_2026-06-09.json` — the run blob (source-of-truth, `grade_path: in_process`).
- `docs/research/RUN_launch_prep_alive_audit_2026-06-09.json` — the per-judge audit (3 realized votes).
- Live screenshots captured via Chrome MCP (verdict pane + Judge council + the corrected `$0` replay render).
- **Video:** deferred (owner: "PROOF doc now, video later") — the zyng narrated cut is a re-renderable follow-on. [[proof-capsule-convention]]
