# Spec-Adherence Critique — `bench-salvage` phase `WS-5d`

> Fresh-critic session (HARD GATE). Cold read of the spec + the diff, no prior
> implementation context. Read the spec/driver/diff/tests before the executor's
> session log; log was read last, for cross-check only. The HARD-GATE reason: this
> phase lands `PUT /v1/ontology` — a **write** on the locked v1 BFF API (§10:144).

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-5d` — artifacts pane wired + `PUT /v1/ontology` + S-BS-19
- **Driver bundle:** `bench-salvage-phaseWS-5d-artifacts-wired-driver` (v1)
- **Commits audited:** `38e4071..b065f14` (7 commits: `38e4071` BFF council+PUT · `4363f05` JudgeTab/ConfigTab wired · `73c45f5` corpus tab · `3d847c4` FlagEditor persist · `20474ed` host-mount + prop-lock · `4022657` tests · `b065f14` README)
- **Spec(s) read against:** `docs/specs/SPEC_PRODUCT_SHELL.md` §3(:39-52)/§5(:65-85)/§5b(:87-89)/§6(:95-100)/§8(:131)/§10(:142-146); CLAUDE.md core invariant (labels true by construction)
- **Critique mode:** `fresh-critic`
- **Date:** `2026-06-01`
- **Reviewer:** `critic session-2026-06-01 (fresh)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The HARD-GATE write surface is the headline, and it holds. **`PUT /v1/ontology` is clobber-safe by construction** — the write target is `workdir/<agent>.json` (default `out/bff/ontology/`, which is `.gitignore`d at line 21), *never* `data/ontology/clinical_v1.json`; there is no code path from the PUT to the committed seed. **The validation gate holds in tests, not just prose**: `_validate_ontology` ([app.py:192-212](apps/bff/app.py#L192)) runs the real `ontology.from_dict` round-trip **and** the real `seed_ontology.gradeable_flags_outside_snapshot` snapshot lint (both helpers verified to exist and to key on `gradeable && flag ∉ snapshot`), and `tests/test_ws5_bff.py` exercises accept+round-trip, malformed→422, snapshot-violation→422, and byte-unchanged-seed — all 10 green on re-run. **JudgeTab/ConfigTab are genuinely off the mock**: `artifact.jsx` imports nothing from `data.jsx` (only `icons.jsx` + `bff.js`); JudgeTab takes realized council votes via props, ConfigTab self-fetches `GET /v1/ontology`. **The S-BS-26 honest-close is accurate, not over-claimed** — I independently confirmed `run_eval.py:118` reads `agent.ontology_abspath()` (the committed seed), so a PUT draft does not feed grading, and `journey/*` mounts no input tool-parts, so "S-BS-19 closed for the Shell host only" is true.

The findings are: **(1)** a stale user-visible `read-only ontology` label + docstring in the FlagEditor — the exact "what no test renders" class the WS-5c fresh-critic flagged, here contradicting the phase's own headline feature (the editor now writes); **(2)** the `putOntology` client signature is arg-flipped vs the driver's stated `putOntology(agent, ontology)`; **(3)** an OPEN-QUESTION on whether the working-copy draft *should* feed grading (§3 "the conversation writes the config plane" is currently only half-realized). None blocks. Per the WS-5c precedent, the `:5180` A7 visual-parity smoke remains the one human-eyeball gate build-green + 30 unit tests cannot cover, and it is correctly **OWED to the user**, not auto-PASSed.

---

## 1. Surface fidelity

| Spec/driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| §10:144 — `PUT`/write-ontology DEFERRED to WS-5c/d; locked v1 read surface = `POST /v1/run-eval` · `GET /v1/corpus` · `GET /v1/ontology` · `/health` | `app.py:215` adds `@app.put("/v1/ontology")` **additively**; the four read/health endpoints unchanged | exact (additive) | — |
| §10:144 — the write "would clobber the committed `clinical_v1.json`" was the deferral reason | `app.py:63` `DEFAULT_ONTOLOGY_WORKDIR = out/bff/ontology`; `app.py:229` writes `workdir/<agent>.json`; never `data/ontology/` | exact | — |
| driver D1 A3 — malformed → 4xx; gradeable-flag-outside-snapshot → 4xx | `app.py:204` malformed→`HTTPException(422)`; `app.py:209` snapshot-violation→`HTTPException(422)` | exact (422 ∈ 4xx) | — |
| driver D0 #1 — judge-council data source (decision #1: realized votes vs roster) | `_council_view` ([app.py:141-164](apps/bff/app.py#L141)) folds REALIZED `result.semantic.judge_votes` into `/v1/run-eval`; `configured` roster passed alongside, diagnostic-only | matches decision #1 (fold, realized) | — |
| §5b:89 — `tool-<name>` ↔ component registry; flat `part.output` | `registry.js:81` `h(Component, { ...(part.output||{}), part, ...handlers })`; convention documented `registry.js:57-62` | exact | — |
| driver D1 #3 — add **`putOntology(agent, ontology)`** to bff.js | `bff.js:33` `putOntology(ontology, agent = "ws0_default")` — **arg order flipped** | drift (minor) | NON-BLOCKING |

**Findings:**

- `[NON-BLOCKING]` **`putOntology` arg order differs from the driver's stated signature.** Driver §2 D1 #3 + §3 decision #2 specify `putOntology(agent, ontology)`; the implementation is `putOntology(ontology, agent)` ([bff.js:33](apps/shell/src/genui/../bff.js#L33)). It is **internally consistent** — the sole caller `FlagEditor.persistEdit` passes `putOntology(edited(), agent)` ([FlagEditor.jsx:118](apps/shell/src/genui/FlagEditor.jsx#L118)) and `inputs.test.jsx:54` asserts `mock.calls[0][0]` is the ontology body — so there is no bug, only a deviation from the driver's named symbol. SPEC §10 does not pin the client signature, so this is driver-drift, not spec-drift. Lock the wording or accept the body-first order.
- Otherwise no surface drift: the `PUT` lands additively on the locked v1 surface, the snapshot/`from_dict` gate is wired, the 5-tool registry and flat-spread convention are intact.

---

## 2. Behavioral fidelity

### Behavior 1: `PUT` never clobbers the committed seed (driver A3 / §10:144 deferral reason)

- **Spec assertion:** §10:144 — the write was deferred precisely because "locking an unexercised write that would clobber the committed `clinical_v1.json`" was rejected; driver A3 — "the committed `clinical_v1.json` is byte-unchanged after a PUT."
- **Test:** `tests/test_ws5_bff.py:183` `test_put_ontology_never_clobbers_the_committed_seed` reads `ONTOLOGY_SEED.read_bytes()` before, PUTs an edited body, asserts `ONTOLOGY_SEED.read_bytes() == before`.
- **Implementation:** `put_ontology_endpoint` ([app.py:215-231](apps/bff/app.py#L215)) writes only `workdir/<agent>.json`; `DEFAULT_ONTOLOGY_WORKDIR = out/bff/ontology` ([app.py:63](apps/bff/app.py#L63)); `out/` is `.gitignore`d (line 21).
- **Chain closes?** **YES — and stronger than the test.** Clobber-safety is **structural**: there is no `data/ontology/` write anywhere in `app.py`. The test confirms the byte-equality; the module surface guarantees the property regardless of agent name. `git status data/ontology/ out/` is clean after the test run.

### Behavior 2: the validation gate rejects a snapshot-violating write (CLAUDE.md core invariant / driver A3)

- **Spec assertion:** CLAUDE.md — "a case is admissible only if every flag code is in `KNOWN_TAXONOMY_CODES`… never silently scored"; driver D1 — "a `gradeable` flag outside `taxonomy/taxonomy_snapshot.json` is REJECTED, loudly."
- **Test:** `tests/test_ws5_bff.py:163` appends `{flag: "NOT_IN_SNAPSHOT_CODE", gradeable: True, …}`, asserts `422` + `"NOT_IN_SNAPSHOT_CODE" in res.text`.
- **Implementation:** `_validate_ontology` ([app.py:205](apps/bff/app.py#L205)) calls `seed_ontology.gradeable_flags_outside_snapshot(flags, load_snapshot_codes())`; that helper ([seed_ontology.py:152-161](scripts/seed_ontology.py#L152)) returns `sorted(f["flag"] for f in flags if f.get("gradeable") and f["flag"] not in snapshot_codes)` — non-empty → `422`.
- **Chain closes?** **YES.** I verified both helpers exist and the lint logic keys on exactly `gradeable && code∉snapshot`. The `from_dict` round-trip runs first (`app.py:202`) and the test flag carries all required fields, so it survives `from_dict` and is caught by the lint — the ordering does not short-circuit the gate. Malformed bodies (`{"not":"an ontology"}`) hit `data["flags"]` → `KeyError` → caught at `app.py:203` → `422` (`test_put_ontology_rejects_malformed`).

### Behavior 3: JudgeTab + ConfigTab render real BFF data, off the `data.jsx` mock (driver A1)

- **Spec assertion:** §8:131 — "wire the already-built judge-council view + config/ontology editor… to the BFF"; driver A1 — "neither reads `data.jsx JUDGES`/`CONFIG_YAML` for its live content."
- **Test:** `artifact.test.jsx:36-51` JudgeTab renders the 3 realized votes threaded via props (incl. `confidence:null` → `n/a`, no crash); `:53-74` ConfigTab self-fetches `getOntology` (mocked) and renders domain/flags/severity/contracts.
- **Implementation:** `artifact.jsx:7-9` imports only `icons.jsx` + `{getOntology, getCorpus}` from `bff.js` — **no `data.jsx` import anywhere in the file**. `JudgeTab` ([:144](apps/shell/src/artifact.jsx#L144)) reads `runResult.council`; `ConfigTab` ([:217](apps/shell/src/artifact.jsx#L217)) reads `getOntology(agent)`.
- **Chain closes?** **YES.** The mock is structurally gone from the wired paths (grep of `artifact.jsx` for `JUDGES`/`CONFIG_YAML`/`data.jsx` → none). The mock still silently feeding the tabs was the load-bearing risk; it does not.

**Findings:** All three picked behaviors close. No behavioral drift. (Re-run by critic: `tests/test_ws5_bff.py` 10 passed; `npm run test:run` 30 passed (6 files); `npm run build` clean, 364.51 kB JS / 59.45 kB CSS.)

---

## 3. Out-of-scope intrusion

Driver deliverables: **D0** BFF council source · **D1** `PUT /v1/ontology` + `putOntology` · **D2** wire JudgeTab/ConfigTab · **D3** corpus tab · **D4** FlagEditor persist · **D5** host-mount + prop-lock · **D6** tests + README.

`git diff --name-only 38e4071^..b065f14` = `apps/bff/app.py` + `apps/shell/**` + `tests/test_ws5_bff.py`. The `tests/test_ws5_bff.py` touch is the **sanctioned** D6 #9 exception (the driver's CITATION-DRIFT header + A6 explicitly carve it out as repo-root). **No `lithrim_bench/`, `scripts/`, or `../lithrim-backend` edits; `pyproject.toml` untouched.** I confirmed the snapshot-lint helpers (`gradeable_flags_outside_snapshot`, `load_snapshot_codes`) are used **import-only** — `scripts/seed_ontology.py` is unchanged in the diff.

**Findings:**

- No out-of-scope intrusion. File-boundary scope (A6) holds. The B008 handling (`_ONTOLOGY_BODY = Body(...)` module singleton, [app.py:67](apps/bff/app.py#L67)) avoids widening `ruff.toml` — an in-scope, non-intrusive choice, recorded in the session log.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1 (carried from WS-5c, now RESOLVED): datapoint `part.output` prop convention

- **WS-5c left this OPEN** (VerdictCard `{data}` vs CalibrationChart flat-spread). WS-5d **locks it to flat-spread**: `registry.js:57-62` documents the contract; `VerdictCard.jsx:28-37` was conformed (dropped the `{data}` wrapper, destructures fields directly); `CalibrationChart.jsx:10` already conformed (hence no edit — *correct*, not an omission). `registry.test.jsx:62-72` asserts both render from flat `part.output`. **Resolved as recommended.** Note the diff touches only `VerdictCard.jsx` because CalibrationChart was already flat-spread; the driver's "make BOTH conform" is satisfied (both *do* conform), not half-done.

### Ambiguity 2 (NEW, OPEN-QUESTION): the working-copy draft does not feed grading

- **Spec text:** §3:41 — "the conversation in the center is writing the SQLite config-plane + ontology"; §3 row 1 maps "Pick domain / ontology → writes `Ontology` → renders Ontology config editor."
- **Implementation reality (CONFIRMED):** a `PUT` draft writes `out/bff/ontology/<agent>.json` and `GET` prefers it ([app.py:182-184](apps/bff/app.py#L182)), so the **UI** reflects the edit — but `run_eval.run` reads `agent.ontology_abspath()` = the committed seed ([run_eval.py:118](scripts/run_eval.py#L118)), so **grading is unaffected by the edit**. The executor surfaced this honestly as S-BS-26.
- **Question for spec author:** Is the WS-5d decoupling intended (drafts are inspectable but inert until a later phase wires the working copy into `run_eval`), or does §3's "the conversation writes the config plane" require the draft to feed grading before the journey can be called complete? The phrase "Edit the ontology" must not be read as "edits take effect in grading" — the executor's framing is correct; lock it.
- **Recommended resolution:** **accept the decoupling for WS-5d**, lock S-BS-26 as the owed wiring. The honest-close is faithful.

### Ambiguity 3 (NEW, OPEN-QUESTION): S-BS-19 "closed" scope

- **Spec text:** §3 frames the journey center (the 4-act activation arc, §2.1) as the surface that writes the config plane.
- **Implementation:** input tool-parts mount in the **Shell** `CenterPane` ([panes.jsx:146-150](apps/shell/src/panes.jsx#L146)) but **not** the journey acts (`journey/*` mounts no `renderTool` input parts — confirmed). Plan-review decision #3 + rider #2 approved "Shell host only; journey-act mounting = new seam."
- **Question for spec author:** confirm that closing S-BS-19 for the Shell host while the journey (the §2.1 hero arc) still emits no input tool-parts is the intended close boundary. The session log's "closed for Shell host only, journey-acts owed (S-BS-26)" framing is **accurate** — not over-claimed.
- **Recommended resolution:** **accept** — the boundary was approved at plan-review and is honestly recorded.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 (`putOntology` arg order) | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 (draft↛grading; S-BS-19 scope) |
| — | "what no test renders" (cross-cutting) | 0 | 1 (stale `read-only` label/docstring) | 0 |

**Total BLOCKING: 0.** Cycle MAY close pending only the deferred `:5180` A7 visual-parity smoke (user-run, no-autostart).

---

## The "what no test renders" finding (WS-5c lesson applied)

The WS-5c fresh-critic caught a visible chrome defect (stray `}`) that build-green + tests-green missed. Applying the same lens to WS-5d, the analogous catch is:

- `[NON-BLOCKING]` **Stale `read-only ontology` label + docstring in the FlagEditor — the feature this phase shipped.** The card now has a **"Persist draft"** button that writes via `PUT /v1/ontology` ([FlagEditor.jsx:187-195](apps/shell/src/genui/FlagEditor.jsx#L187)), yet:
  - the user-visible subtitle still reads `{flags.length} flags · read-only ontology` ([FlagEditor.jsx:132](apps/shell/src/genui/FlagEditor.jsx#L132));
  - the module docstring still asserts "Reads the agent's committed ontology via GET `/v1/ontology` (**read-only — no PUT this phase, WS-5d**)" ([FlagEditor.jsx:4-5](apps/shell/src/genui/FlagEditor.jsx#L4)) and "nothing is persisted (no PUT)" ([:12-13](apps/shell/src/genui/FlagEditor.jsx#L12)).

  **No test renders or asserts this subtitle** (`inputs.test.jsx` asserts `/Flags & severity/i` and `/Severity map \(global\)/i`, never the `read-only ontology` chrome). So the contradiction — a card labelled "read-only" that ships a write button, in the demo-wedge hero widget — survives build-clean + 30 green tests, exactly as the WS-5c brace did. **This is a copy/doc defect, not garbage rendering** (the WS-5c brace rendered a literal `}`), so it does not rise to BLOCKING — but it is the one thing the A7 `:5180` smoke would surface, and a ~2-line fix (subtitle + docstring) closes it. Recommend the monitor fix it in the same pass that runs the A7 smoke.

---

## Required actions

**BLOCKING:** none.

**NON-BLOCKING / OPEN-QUESTION (cycle may close):**

1. `[NON-BLOCKING]` Stale `read-only ontology` subtitle ([FlagEditor.jsx:132](apps/shell/src/genui/FlagEditor.jsx#L132)) + stale docstring ([:4-5](apps/shell/src/genui/FlagEditor.jsx#L4), [:12-13](apps/shell/src/genui/FlagEditor.jsx#L12)) contradict the phase's read-write feature. **Disposition:** ~2-line copy/doc fix during the A7 smoke pass; add a render assertion guarding the subtitle (the WS-5c `app.test.jsx` pattern) to close the coverage gap.
2. `[NON-BLOCKING]` `putOntology(ontology, agent)` arg order vs the driver's stated `putOntology(agent, ontology)` ([bff.js:33](apps/shell/src/bff.js#L33)). **Disposition:** internally consistent + no spec pin; accept the body-first order or lock the driver wording.
3. `[OPEN-QUESTION]` Does §3 "the conversation writes the config plane" require the working-copy draft to feed `run_eval` grading (run_eval.py:118 reads the committed seed)? **Disposition:** accept the WS-5d decoupling; lock S-BS-26 as the owed wiring.
4. `[OPEN-QUESTION]` Confirm S-BS-19 "closed for Shell host only" (journey acts still emit no input tool-parts) is the intended close boundary. **Disposition:** accept (plan-review-approved + honestly recorded).
5. `[VERIFICATION OWED]` A7 `:5180` visual-parity smoke (light/dark × Shell/Journey + the 4 wired tabs report/judges/config/corpus), user-run under no-autostart with the BFF up. Correctly NOT auto-PASSed. This is the only gate build+unit-tests cannot cover.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec without reading the executor's session log first (log read last, step 7).
- [x] Read the diff via `git show`/direct file reads against the 7 commits, not via the executor's prose summary; re-ran the build + both test suites independently.
- [x] Each finding cites both spec/driver file:line and implementation file:line.
- [x] Did NOT edit any code, spec, or driver.
- [x] Did NOT confer with monitor or executor before writing the verdict.

Cross-check note: my findings **agree** with the executor's `PROCEED-WITH-CAVEATS` verdict and its two recorded caveats (A7 owed; S-BS-26). I independently confirmed the two load-bearing S-BS-26 claims (`run_eval.py:118` reads the seed; `journey/*` mounts no input parts) — both CONFIRMED, so the honest-close is not over-claimed. The one thing the session log does **not** surface is the stale `read-only` label/docstring (finding above) — the WS-5c "what no test renders" gap, now applied.

---

## Appendix: commits audited

```
b065f14 docs(shell): README status — artifacts wired + PUT-ontology landed (WS-5d)
4022657 test(shell): tab bindings + corpus + FlagEditor persist + prop-shape + host-mount
20474ed feat(shell): mount input tool-parts + lock datapoint prop convention (S-BS-19)
3d847c4 feat(shell): FlagEditor persistence via PUT /v1/ontology
73c45f5 feat(shell): corpus / flywheel artifact view (GET /v1/corpus)
4363f05 feat(shell): wire JudgeTab + ConfigTab off mock to the BFF
38e4071 feat(bff): judge-council view + PUT /v1/ontology (clobber-safe + validated)
```

## Appendix: re-run evidence (critic, this session)

```
git diff --name-only 38e4071^..b065f14
  → apps/bff/app.py · apps/shell/** · tests/test_ws5_bff.py   (no lithrim_bench/ · scripts/ · backend; pyproject untouched)
pytest tests/test_ws5_bff.py -q            → 10 passed
npm run test:run (apps/shell)              → 30 passed (6 files)   [WS-5c was 19/3]
npm run build (apps/shell)                 → clean (364.51 kB JS / 59.45 kB CSS)
git status data/ontology/ out/             → clean (out/ is .gitignore'd line 21)
clobber-safety                             → structural: no data/ontology/ write in app.py
PUT gate helpers                           → seed_ontology.gradeable_flags_outside_snapshot:152 + load_snapshot_codes:139 exist; ontology.from_dict:136
S-BS-26 decoupling                         → run_eval.py:118 reads agent.ontology_abspath() (committed seed), NOT the working copy — CONFIRMED
S-BS-19 boundary                           → journey/* mounts no renderTool input parts — CONFIRMED (Shell-host-only close is accurate)
```
