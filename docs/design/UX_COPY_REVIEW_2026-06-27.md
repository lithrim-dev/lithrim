# UX copy review — simplify & de-jargon the shell (2026-06-27)

**Brief.** The UI leaks engineer vocabulary into user-facing copy: raw API calls (`POST /v1/...`),
ports (`:8002`), tool/function names (`focus_artifact('report')`), property names
(`role_key_questions`, `kb_bindings`), run-id hex, and raw error/stderr text — plus insider domain
terms (`council`, `roster`, `lens`, `ontology`, `floor`, `oracle`, `corpus`). The conversation is the
product (`SPEC_CONVERSATIONAL_FIRST`), so this register is highly visible.

**Root cause.** No translation layer between internal modeling language and user copy. ~15 insider
terms recur across 11 components + the assistant's system prompt + `app.py` errors. Fix the *map*
once and most rewrites follow.

Evidence: two read-only sweeps (static shell copy: 52 strings / 11 files; agent register: the
`loop.py` system prompt + tool descriptions; `app.py` `HTTPException detail=`).

---

## 0 · The terminology map (approve this first — it drives every rewrite)

| Internal term | Where it leaks | Recommended user-facing word |
|---|---|---|
| council | "the council grades", "council votes", "council's verdict" | **the reviewers** / **review panel** |
| roster | "edit the judges roster", "the roster" | **your reviewers** |
| judge / `*_judge` | `faithfulness_judge`, "a new voice on the council" | **reviewer** — "Faithfulness reviewer" *(decision A — LOCKED 2026-06-27)* |
| verdict | "verdict = BLOCK", "the verdict a tool returns" | **result** *(decision B — LOCKED 2026-06-27)* |
| BLOCK / WARN / PASS | verdict chips, run history | **Flagged / Needs a look / Passed** *(decision B — LOCKED 2026-06-27)* |
| lens | "assign an ontology flag lens", "owned + emitted codes" | **what this reviewer checks for** |
| ontology | "loading ontology…", "the ontology config" | **your checks** / **checklist** |
| flag / `flag_code` | `MEDICATION_NOT_IN_TRANSCRIPT` shown raw | **issue** — render code as Title Case ("Medication not in transcript") |
| verification / grounding contract | "add a grounding contract", "binds a flag to a floor" | **fact-check** (a rule checked against the record) |
| floor / oracle / withstand | "deterministic floor", "an oracle to withstand" | **automated fact-check** / **hard rule** |
| confidence | judge confidence 0–1 | **how sure** (the reviewer is) |
| corpus | "loading correction corpus…", "corpus/flywheel" | **saved cases** / **examples** |
| namespace (KB) | "Namespaces (N bound)" | **knowledge topic** / **section** |
| deployment (Azure) | "type a deployment", "Model deployment" | **model name** |
| re-keying | "reuses the stored key (no re-keying)" | **without re-entering the key** |
| consumer | "models are assigned per consumer" | **per reviewer** |
| logprobs | "⚠ no logprobs — confidence will be dark" | **this model doesn't report a confidence signal** |
| provenance | "full provenance", audit | **history** / **audit trail** |
| `pipeline_run_id` / hex | "Run 09f9689a — verdict = BLOCK" | **drop the hex** → "your latest run" / "this run" |
| `focus_artifact('report')` | assistant text | **"open the report"** (never the function name) |
| `run_eval` / `propose_live_run` / `in_process` / `live` | assistant text, run modes | **"run the evaluation"** / **"grade this case"** |

---

## 1 · Priority 1 — kill API/tool/port/property leakage (must NEVER show to a user)

| File:line | Current | Recommended |
|---|---|---|
| `genui/JudgeEditor.jsx:282` | `POST /v1/judges/{role}/optimize · PAID` | **Improve this reviewer · paid** |
| `genui/JudgeEditor.jsx:334` | `PUT /v1/judges · owner↔emit + snapshot gated (not the seed)` | *(remove — internal note; show nothing or "Save reviewer")* |
| `genui/JudgeEditor.jsx:264` | "the exact `role_key_questions` the bridge will send" | **the exact questions this reviewer will ask** |
| `genui/RunPanel.jsx:182` | `POST /v1/run-eval · replay $0 · live/in-process paid (confirmed)` | **A saved replay is free; a live run is paid** |
| `genui/RunPanel.jsx:25` | `Live :8002` | **Live run** |
| `genui/ProvidersSection.jsx:95` | `https://…azure endpoint (api_base)` | **Azure endpoint URL** |
| `genui/ProvidersSection.jsx:95` | "OpenAI-compatible `api_base`" | **Endpoint URL (OpenAI-compatible)** |
| `genui/KbPicker.jsx:86` | "returns `kb_bindings`" | *(remove — internal)* |
| `genui/ContractBuilder.jsx:184` | "The `verification_contracts` entry this builds." | **The fact-check this adds.** |
| `genui/ContractBuilder.jsx:138` | placeholder `MEDICATION_NOT_IN_TRANSCRIPT` | **e.g. "Medication not in transcript"** |
| `genui/ContractBuilder.jsx:37` | `presence_check`, `snomed_subsumption`, `record_presence` | **plain labels** ("Must be in the record", "Medical-term match", "Was actually recorded") |
| `artifact.jsx:145` | `floor_block` / `floor_inconclusive` | **Blocked by a fact-check** / **Fact-check inconclusive** |
| `genui/AuditView.jsx:23` | `{action} · {target.type}:{target.id}` | **plain sentence** ("Edited the Faithfulness reviewer") |

---

## 2 · Priority 2 — error messages → "what happened + how to fix" (never raw)

Pattern: **what happened · (plain why) · what to do.** Never surface stderr, stack text, status
codes, or Python `repr`.

| File:line | Current | Recommended |
|---|---|---|
| `panes.jsx:408/414/549` | `⚠ {err.message}` (raw) | **Something went wrong: {plain reason}. Try again.** (map known causes; log the raw detail) |
| `artifact.jsx:62` | "Run failed" + raw monospace error | **We couldn't finish that run.** {plain reason} **— try again, or check your model connection.** |
| `genui/RunPanel.jsx:132` | "Run failed: {error}" | same pattern as above |
| `genui/JudgeEditor.jsx:306` | "Optimize failed: {opt.error}" | **Couldn't improve the reviewer — {plain reason}. Try again.** |
| `app.py:907` | `grade subprocess failed (pack=…): {stderr[-1500:]}` | UI: **The evaluation couldn't run. Please try again.** (keep stderr in server logs only) |
| `app.py:1988` | `assigned flags outside taxonomy snapshot (re-snapshot, do not hand-edit): …` | **Some checks aren't in this pack's approved list. Pick from the available checks.** |
| `app.py:1992` | `unknown validator refs (execute-only, choose from …)` | **That fact-check isn't available. Choose one of: …** |
| `app.py:2720` | `refusing to delete {flag}: judge(s) {x} assign it (revert them first)` | **Can't remove this check — {reviewer} still uses it. Remove it there first.** |
| `app.py:2287` | `malformed ontology: {exc}` | **We couldn't read your checklist. Please try again.** |
| `auth.jsx:26` | "That token was rejected — check it and try again." | *(keep — already good)* |

---

## 3 · Priority 3 — the conversational register (highest-impact single change)

The assistant's jargon comes from `apps/bff/agent/loop.py` (`_SYSTEM_PROMPT` + tool descriptions),
which tell the model to cite tool names, run-id hex, and field names, and which model insider terms
("council", "roster", "lens", "oracle to withstand"). The model parrots them.

**Fix = one stanza** added to the system prompt — a "speak to a person" register rule:
- Never print tool/function names, HTTP paths, ports, property names, or run-id hex.
- Translate: council→the reviewers · verdict→result · BLOCK→flagged · lens→what a reviewer checks ·
  ontology→your checks · contract/floor/oracle→fact-check · corpus→saved cases.
- Say "open the report" / "run the evaluation", never `focus_artifact('report')` / `run_eval`.
- Refer to a run as "your latest run", not its hex id.

This is cheaper and higher-leverage than rewriting each generated sentence, and it's testable (a
prompt-contract assertion: the stanza is present; optionally an eval that the assistant's replies
contain no `/v1/`, `focus_artifact`, or 8-hex-id patterns).

---

## 4 · Priority 4 — panel / card jargon (representative; the map covers the rest)

| File:line | Current | Recommended |
|---|---|---|
| `ProviderSettings.jsx:44` | "models are assigned per consumer · keys are write-only (never returned)" | **assign a model to each reviewer · your key is stored securely and never shown again** |
| `AssignModelsSection.jsx:150` | "type a deployment for Azure · reuses the stored key (no re-keying)" | **type your Azure model name · uses your saved key** |
| `AssignModelsSection.jsx:202` | "Chat assistant still needs a model — N of 4 roles assigned" | **The assistant needs a model before you can chat — N of 4 set** |
| `VerdictCard.jsx:46` | "run an eval to see the council's real verdict here" | **run an evaluation to see the reviewers' result here** |
| `VerdictCard.jsx:92` | "Caught by floor rule" | **Caught by a fact-check** |
| `artifact.jsx:204` | "The realized per-judge votes the council cast" | **How each reviewer voted** |
| `artifact.jsx:235` | "Collecting the judges' votes…" | **Gathering the reviewers' results…** |
| `artifact.jsx:94` | "N issue(s) flagged · M false alarm(s) removed by a tool" | **N issues found · M false alarms cleared by a fact-check** |
| `KbPicker.jsx:55/80` | "Namespaces (N bound)" / "(off for structured KBs)" | **Knowledge topics (N selected)** / *(remove the parenthetical)* |
| `RunPanel.jsx:30` | "This is a PAID run (real council calls, ~$0.10–0.20)" | **This is a paid run (real model calls, about $0.10–0.20)** |
| `RunPanel.jsx:188` | "Run a PAID evaluation?" | **Run a paid evaluation?** + consequence line ("This makes real model calls you'll be billed for.") |
| `ContractBuilder.jsx:107` | "BLOCK the verdict — deterministic, no model call." | **Flag the result automatically — no model call.** |
| `JudgeEditor.jsx:204` | "Assign lens (owned + emitted codes)" | **Choose what this reviewer checks for** |
| `JudgeEditor.jsx:250` | "Refinement questions (derived from the ontology)" | **Follow-up questions (from your checklist)** |

---

## Sequencing (devloop drivers, tests-first, staged)

1. **DRIVER_copy_terminology** — **DONE (slice 1, 2026-06-27).** `genui/copy.js` ships
   `verdictLabel()` (BLOCK/WARN/PASS → Flagged/Needs a look/Passed), `roleLabel()`
   (`faithfulness_judge` → "Faithfulness reviewer"), `flagLabel()` (`MEDICATION_NOT_IN_TRANSCRIPT` →
   "Medication not in transcript"). Applied to `VerdictCard.jsx` (title "Result", chip, votes header
   "How each reviewer voted", reviewer names, readable flags, "Caught by a fact-check"). Tests:
   `copy.test.jsx` (helpers + a non-vacuous "no raw codes leak" render assertion); 11 existing tests
   that pinned the old labels updated. Full suite green except the pre-existing `app.test.jsx`.
   **Still to apply the helpers:** `artifact.jsx` (report pane: verdict, votes, flags), run-history,
   `panes.jsx` `verdictShape`/`TOOL_LABELS`, and the other cards (P4).
2. **DRIVER_copy_p1_leakage** — **DONE (2026-06-27).** Stripped `POST/PUT /v1/...`, `:8002`,
   `role_key_questions`, `verification_contracts`, `kb_bindings`, `api_base`, and raw code
   placeholders from user copy across JudgeEditor / RunPanel / Providers / ProviderSettings /
   AssignModels / ContractBuilder / KbPicker / AuditView / artifact / JudgeBuilder.
3. **DRIVER_copy_errors** — **DONE.** The `what + why + fix` pattern across panes / artifact /
   RunPanel / CaseCard / JudgeEditor / FlagEditor; `app.py` now logs the raw detail and returns a
   plain message (no stderr/jargon to the UI). **UX-COPY-ERR-1 (render layer):** a shared
   `copy.js#friendlyError(err)` now sanitizes EVERY raw-error render — it maps known causes
   (network / 5xx / auth / not-found), KEEPS short validation reasons ("… already exists"), and
   strips HTTP envelopes / filesystem paths / JSON / stacks. Applied at all card + pane + report
   error sites (the friendly *heading* pass had left raw `{error}`/`${detail}` dumps below it — e.g.
   the report-tab `POST /v1/run-eval → 404 …/config.sqlite` leak). Tested against that exact string.
4. **DRIVER_copy_register** — **DONE.** `loop.py` carries a "HOW TO SPEAK TO THE USER" stanza (never
   print tool names / paths / ports / run-id hex; translate council→reviewers, verdict→result,
   BLOCK→flagged, lens/ontology/contract→plain) + a prompt-contract test
   (`tests/test_register_stanza.py`, 4/4).

**Executed as a 6-agent parallel fan-out** (one bucket per disjoint file-group) + an orchestrator
pass for the shared `registry.test.jsx` and the cross-cutting `app.chat`/`bff` tests. Shell suite:
**249 pass / 1 pre-existing fail** (`app.test.jsx` ModeSwitch, not copy-related). BFF: ruff clean,
register test green. Staged + proposed (no auto-commit, no push). Naming decisions
(A: judge→**reviewer**; B: verdict→**result**, BLOCK/WARN/PASS→**Flagged/Needs a look/Passed**) LOCKED.
