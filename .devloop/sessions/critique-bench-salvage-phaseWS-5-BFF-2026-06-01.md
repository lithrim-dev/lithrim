# Spec-Adherence Critique — `bench-salvage` phase `WS-5-BFF`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-5-BFF`
- **Driver bundle:** `bench-salvage-phaseWS-5-BFF-driver` (v1)
- **Commits audited:** `f19dee4`, `e6e023f`, `b15adc5`, `4549a12` (range `11e0ca7..4549a12`)
- **Spec(s) read against:** `docs/specs/SPEC_PRODUCT_SHELL.md` §5 / §5b / §8 / §10 · `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (sequencing B)
- **Critique mode:** `fresh-critic` (separate session, no prior implementation context)
- **Date:** 2026-06-01
- **Reviewer:** critic session (fresh)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The de-risk vertical is real and the locked surface is faithful where it ships: `POST /v1/run-eval` drives `run_eval.run()` end-to-end, the React `ReportTab` renders the real clinical `composite` (not `data.jsx` mock), and the round-trip smoke is the shell's first behavioral test. The v1 surface this cycle *locks* diverges from the spec's literal §10 four-endpoint naming in two authorized places (write-ontology **deferred**, a `/health` probe **added**) plus a response-envelope reshape — all surfaced and plan-review/mid-cycle approved, none unauthorized. They are recorded here as OPEN-QUESTIONs the spec author should reconcile against §10 at close. Zero BLOCKING findings → cycle MAY close.

---

## 1. Surface fidelity

> The cycle's load-bearing job: lock the **judge-capability API v1** (SPEC §5:85, §10:144).

SPEC §10:144 names the four to lock: **run-eval / get-report / get-corpus / read/write-ontology**. Driver §2:64-69 and §3 decision #2:85 refine: fold report into run-eval; keep `GET /v1/corpus` + `GET/PUT /v1/ontology`.

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| §10:144 `run-eval` | `apps/bff/app.py:94` `POST /v1/run-eval {agent?, live?}` → run dict | ✅ exact | — |
| §10:144 `get-report` (driver §2:65 authorizes folding) | folded into `/v1/run-eval` response (`apps/bff/app.py:114` adds `calibration_check`); **no discrete `GET /v1/report/{run_id}`** | authorized fold; no by-id retrieval | OPEN-QUESTION |
| §10:144 `get-corpus` | `apps/bff/app.py:119` `GET /v1/corpus` → `{rows: [...]}` | ✅ | — |
| §10:144 `read`-ontology | `apps/bff/app.py:125` `GET /v1/ontology {agent?}` | ✅ | — |
| §10:144 `write`-ontology (driver §3:85 rec'd keep `PUT`) | **DEFERRED** to WS-5c/d (`apps/bff/app.py:15`, `:131`) | deferred (approved-at-plan) | OPEN-QUESTION |
| (not in §10) | `apps/bff/app.py:89` `GET /health` **added** | extra symbol | OPEN-QUESTION |
| §5:85 "judge-capability API" | `apps/bff/app.py:80` `FastAPI(title="Lithrim judge-capability API", version="1.0.0")` | ✅ named deliberately | — |

Response envelope of `/v1/run-eval` (the locked datapoint shape): the run record, **minus** `_persisted` (`apps/bff/app.py:113`, internal fs paths stripped — sound), **plus** `calibration_check` (`:114`) and a top-level `grade_path` mirror of `provenance.grade_path` (`:115`).

**Findings:**

- `[OPEN-QUESTION]` **`write`-ontology deferred.** §10:144 names `read/write-ontology` for the v1 lock; impl ships read-only (`apps/bff/app.py:15`, `:125-131`), PUT deferred to WS-5c/d. Approved-at-plan (session log:21-26) with sound reasoning (an unexercised PUT would clobber the committed `data/ontology/clinical_v1.json`). Authorized — but the §10 lock is therefore *not fully satisfied* by this cycle; spec author should ratify "v1 = read-only ontology, write lands WS-5c/d" in §10.
- `[OPEN-QUESTION]` **No `get-report` by id.** Reports are only returned inline at run time; `run_eval.persist` writes to `out/ws0` sqlite/blob (`scripts/run_eval.py:158`) but no endpoint reads them back. Authorized by the driver's fold-rec (§2:65), but §10:144 named `get-report` as a discrete capability — confirm inline-fold satisfies the v1 lock, or that report-by-id is a later phase.
- `[OPEN-QUESTION]` **`GET /health` added** (`apps/bff/app.py:89`) — not in the §10 four. Conventional for a Tauri-sidecar readiness probe (§5:80 sidecar lifecycle), harmless, surfaced in commit/diagnostic_stats. Confirm it belongs in the documented v1 contract.

No *unauthorized* surface drift: every deviation above is either plan-review-approved (session log:14-39) or driver-authorized (§2:65). The three shipping symbols that ARE locked (`run-eval`, `corpus`, `ontology` read) match the spec exactly.

---

## 2. Behavioral fidelity

### Behavior 1: BFF serves a REAL eval-report over the harness (replay)

- **Spec assertion:** §3:49 "Run an eval → drives `scripts/run_eval.py run()` (replay default; live opt-in) → **eval report** (`report.composite` + `calibration_check`)"; driver A1:111.
- **Test:** `tests/test_ws5_bff.py:55-78` — `POST /v1/run-eval {live:False}` asserts `grade_path=="replay"`, `composite.verdict=="reject"`, `stage_verdict=="BLOCK"`, `score==1.0`, `"FABRICATED_HISTORY" in active_findings`, a `MEDICATION_NOT_IN_TRANSCRIPT` grounded suppression, and `calibration_check {verdict_match_rate:1.0, status:PASS, n_cases:1, ece:0.5, caveat~"small N"}`.
- **Implementation:** `apps/bff/app.py:107` `run_eval.run(agent, live=req.live, out_dir=...)` → `:114` folds `calibration_check([record])` (real fn `lithrim_bench/harness/report.py:159`); composite fields are the genuine grounded outcome (`report.py:81-92`).
- **Chain closes?** **YES.** The test asserts the real grounded *outcome* (the S-BS-7 suppression exhibit, the BLOCK verdict), not just envelope shape. Strong chain.

### Behavior 2: Strangler-fig — BFF targets the harness, not Mongo / `../lithrim-backend`

- **Spec assertion:** TOPOLOGY:22-23 "the shell **BFF targets the harness as it already composes over live `:8002`/`:3031`** … The live Mongo backend is scaffolding"; SHELL §84 "Product path is Mongo-free."
- **Test:** `tests/test_ws5_bff.py` is hermetic + replay-only (no network, `pytest.importorskip("fastapi")`); imports only `lithrim_bench.harness` (`:18`). No negative "Mongo-absent" assertion exists (not cheaply testable).
- **Implementation:** `apps/bff/app.py:42-49` imports only `run_eval` + `lithrim_bench.harness.{corpus,config,report}`. No `pymongo`, no `../lithrim-backend` path. Live path routes through `run_eval`'s own `:8002` client (`scripts/run_eval.py:119`), i.e. the harness composes over the live service — it does not import the backend.
- **Chain closes?** **YES** by import-graph (the only Mongo touch would be the harness's own live `:8002` call, which is the sanctioned compose-over-live, not a product coupling). Note: demonstrated structurally, not by an explicit guard test — acceptable, no cheaper proof exists.

### Behavior 3: Replay is the $0 default; live is opt-in, one paid call (trust-wedge)

- **Spec assertion:** §5c:91-93 (LLM-free default / trust wedge); driver §2:64 "replay default", A3:113 "exactly one real council call … Replay stays the default."
- **Test:** `tests/test_ws5_bff.py:60` exercises only `{live:False}` and asserts `grade_path=="replay"`; the request default is `live=False` (`apps/bff/app.py:77`). The live path is **not** automated (A3 is a manual, cost-confirmed run by driver design — A3:113, §7:147 "no autostart").
- **Implementation:** `RunEvalRequest.live=False` default (`apps/bff/app.py:77`); `apps/shell/src/bff.js:24` `runEval({live=false})`; `app.jsx` `doRun(false)` is the primary button, `doRun(true)` the separate "Run live" (`app.jsx` TopBar diff). Live verdict == replay verdict confirmed manually (session log A3:75-77).
- **Chain closes?** **YES** for the replay default (tested + impl). Live is manual-by-design (driver-sanctioned) — the chain is impl + manual smoke, not an automated test, which is faithful to A3.

**Findings:**

- `[NON-BLOCKING]` **The React render (A2) has no automated test.** `artifact.jsx:ReportTab` (the real-data datapoint) is verified only by manual smoke / user screenshot (session log A2:70-72). This is exactly what the driver specifies (A2:112 "manual smoke at :5180"), so it is **not drift** — but the shell's "first behavioral test" (b15adc5) covers the *BFF round trip* only; the React binding remains unguarded by CI. Worth a record so the gap isn't mistaken for covered.

---

## 3. Out-of-scope intrusion

Driver §2 deliverables: (1) `apps/bff/` FastAPI app, (2) `[bff]` extra in `pyproject.toml`, (3) `apps/shell/src/bff.js` client, (4) `artifact.jsx` `ReportTab` wiring, (5) the pytest smoke, (6) README run docs. Driver §7:146 / A5:115 confine the diff to **`apps/bff/` + `apps/shell/` + `pyproject.toml` + the test (+ README)**.

Diffed files mapped to deliverables:

```
apps/bff/app.py            (1) ✅      apps/shell/src/app.jsx     (4, wiring) ✅
apps/bff/README.md         (6) ✅      apps/shell/src/panes.jsx   (4, wiring) ✅
pyproject.toml             (2) ✅      apps/shell/vite.config.js  (3, proxy)  ✅
apps/shell/src/bff.js      (3) ✅      apps/shell/README.md       (6) ✅
apps/shell/src/artifact.jsx(4) ✅      tests/test_ws5_bff.py      (5) ✅
ruff.toml                  ── NOT in the §7/A5 confined set
session-...WS-5-BFF.json   (4549a12 chore — expected session log)
```

**Findings:**

- `[NON-BLOCKING]` **`ruff.toml` is outside the A5-stated confinement.** `ruff.toml:11-15` adds `[lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]`. The driver's A5:115 / §7:146 confined set does **not** list `ruff.toml`. Justified (B008 is a false positive for the `Depends()`-in-default FastAPI idiom) and **approved-mid-cycle, surfaced at the pre-handback halt** (session log:27-32) — not a silent drive-by. Authorized; noted for the record only. (The executor's own A5 evidence at session log:87 silently widened the confined set to include `ruff.toml` — the widening, not the change, is the thing to flag.)

`app.jsx` adds a second "Run live" TopBar button and `panes.jsx` wires the center "Run evaluation" button — both inside `apps/shell/` and in direct service of deliverable 4 / acceptance A2+A3. In scope. No formatting passes, no dep bumps beyond the `[bff]` extra.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the §10 v1 lock vs the as-shipped surface

- **Spec text:** §10:144 "Lock the first endpoints (run-eval, get-report, get-corpus, read/write-ontology) at WS-5 plan-review."
- **Implementation decided:** ship `run-eval` (report folded), `corpus`, `ontology` (read), `/health`; **defer** PUT-ontology; **no** discrete get-report (`apps/bff/app.py:89-131`).
- **Alternatives also spec-compliant:** a discrete `GET /v1/report/{run_id}` over the persisted `out/ws0` store; a locked-but-405 `PUT /v1/ontology` stub.
- **Question for spec author:** Does the v1 lock ratify "read-mostly + report-folded + PUT deferred to WS-5c/d + `/health` added"? §10 is itself an open-questions section, so this is its natural home.
- **Recommended resolution:** update §10 to record the as-locked surface (it's the deliberate, better call); the monitor's own next-step hint already flags "reconcile §10 PUT-ontology deferred."

### Ambiguity 2: S-BS-17 — clinical report inside customer-support chrome (the PROCEED-WITH-CAVEATS driver)

- **Spec/driver text:** driver §3 decision #6:89 "the real `composite` is **clinical** … the Shell chrome is customer-support mock … **Surface; don't silently leave a jarring mix.**"
- **Implementation decided:** accept the split (commit e6e023f, session log verdict). The real clinical `composite` now renders **inside** mock customer-support chrome: `artifact.jsx:199` artifact subtitle `"support-agent-v4 · run #218"`, `app.jsx:14` `acme-support` workspace pill, `app.jsx:51` `κ 0.88`. So a real *reject/BLOCK clinical* report sits under a header that literally reads "support-agent-v4 · run #218".
- **Alternatives also compliant:** reskin Shell-mode chrome to clinical (driver called this "small"); or drive the chrome strings from the run record.
- **Question for spec author:** is the customer-support chrome around a real clinical report acceptable through WS-5d, or should the WS-5-BFF close carry a reskin follow-up?
- **Recommended resolution:** accept-and-track — the executor surfaced it explicitly (not silent), which satisfies decision #6's actual requirement; log as a seam/follow-up for WS-5d when the other tabs go real.

### Ambiguity 3: `calibration_check` folded as an N=1 degenerate diagnostic

- **Spec text:** §3:49 lists `calibration_check` as the eval-report payload; driver A1:111 conflated per-case `calibration` with run-level `calibration_check`.
- **Implementation decided:** `apps/bff/app.py:114` folds `calibration_check([record])` (N=1) and the UI renders it as an explicit "diagnostic · N=1 … not the locked calibration gate (WS-4b)" (`artifact.jsx` calibration section). Approved-at-plan (session log:14-20), mirrors `tests/test_ws4a.py:273-280`.
- **Question for spec author:** none material — the constraint ("render as degenerate diagnostic, NOT the WS-4b gate") is honored in both API docstring (`app.py:102-105`) and UI copy. Recorded for completeness.

**Findings:**

- `[OPEN-QUESTION]` Ambiguity 1 — ratify the as-locked v1 surface in §10 (read-mostly + folded report + `/health`; PUT/write deferred).
- `[OPEN-QUESTION]` Ambiguity 2 — S-BS-17: confirm clinical-in-support-chrome is acceptable through WS-5d or schedule a reskin.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 3 |
| 2 | Behavioral fidelity | 0 | 1 | 0 |
| 3 | Out-of-scope intrusion | 0 | 1 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings; no correction commit required.

NON-BLOCKING / OPEN-QUESTION dispositions:

1. **§10 surface lock vs as-shipped (Q1, Q4-A1).** *Disposition:* spec author updates SPEC_PRODUCT_SHELL §10 at close to record the as-locked v1 surface (run-eval [folded report] + GET corpus + GET ontology + /health; PUT/write-ontology → WS-5c/d). Owner: spec author / monitor at close. Matches the session log's stated close action.
2. **S-BS-17 clinical-in-support chrome (Q4-A2).** *Disposition:* log as a seam for WS-5d (chrome→real when the judge/config/corpus tabs go real); accept for now (surfaced per decision #6). Owner: monitor.
3. **`ruff.toml` outside A5 confinement (Q3).** *Disposition:* accept as-is (approved-mid-cycle, justified FastAPI-idiom lint allowance). Owner: none — record only.
4. **A2 React render has no automated test (Q2).** *Disposition:* accept (driver-sanctioned manual smoke); consider a minimal component test when WS-5c introduces the Vitest/Testing-Library foundation. Owner: monitor (note for WS-5c/d).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (SHELL §5/§5b/§8/§10 + TOPOLOGY) without reading the executor's session log first
- [x] Read the diff via `git show` against each of the 4 commits, not via the executor's prose summary
- [x] Each finding cites both spec file:line and implementation file:line
- [x] Did NOT edit any code, spec, or driver
- [x] Did NOT confer with monitor or executor before writing the verdict

The independently-formed findings did **not** contradict the executor's session log — the two surface deviations (PUT defer, fold) and the `ruff.toml` touch were all already surfaced there as APPROVED deviations, and the S-BS-17 caveat matches the executor's own PROCEED-WITH-CAVEATS rationale. Concordance after an independent pass, not anchoring.

---

## Appendix: commits audited

```
4549a12 chore(ws5-bff): session log — WS-5-BFF de-risk (A1–A5 PASS, PROCEED-WITH-CAVEATS)
b15adc5 test(ws5-bff): BFF round-trip smoke (replay) — the shell's first behavioral test
e6e023f feat(ws5-bff): React bridge + wire the real eval-report into ReportTab
f19dee4 feat(ws5-bff): FastAPI BFF over run_eval + harness (judge-capability API v1)
```

## Appendix: files changed

```
.devloop/sessions/session-...WS-5-BFF-2026-06-01.json | 109 +++++
apps/bff/README.md                                    |  51 ++
apps/bff/app.py                                       | 136 +++++
apps/shell/README.md                                  |  28 +-
apps/shell/src/app.jsx                                |  38 +-
apps/shell/src/artifact.jsx                           | 135 +++--
apps/shell/src/bff.js                                 |  28 +
apps/shell/src/panes.jsx                              |   7 +-
apps/shell/vite.config.js                             |  12 +-
pyproject.toml                                        |   9 +
ruff.toml                                             |   5 +    <-- not in A5 confined set
tests/test_ws5_bff.py                                 | 111 +++++
12 files changed, 622 insertions(+), 47 deletions(-)
```
