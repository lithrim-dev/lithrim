# Spec-Adherence Critique — `bench-salvage` phase `UAP-5a`

> Fresh-critic mode (separate session, HARD GATE). Committed as
> `.devloop/sessions/critique-bench-salvage-phaseUAP-5a-2026-06-04.md`.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `UAP-5a` (the in-UI authoring loop: mount the JudgeEditor [S-BS-62] + legible authored audit [S-BS-66] + a by-construction live-flip demo case)
- **Driver bundle:** `bench-salvage-phaseUAP-5a-authoring-loop-driver`
- **Commits audited:** `d7be919 1c6a629 e3b0591 0669743 2faf8d3 e2c48a6` (parent `9213fd6`)
- **Spec(s) read against:** `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A/§2B/§4/§5; the driver §2/§4/§5; `CLAUDE.md` (admissibility #1–#4, diagnose-before-edit)
- **Critique mode:** `fresh-critic`
- **Date:** `2026-06-04`
- **Reviewer:** `critic session (cold read)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

One sentence: A4 (the live verdict-flip) honestly FAILED and is correctly surfaced as S-BS-70 with the user pre-authorizing the honesty-over-manufacture choice; everything else (the frozen-seam byte-0-delta, the legible-audit D2 projection, the by-construction demo case's admissibility, scope discipline) checks out under independent verification — there is **no BLOCKING issue**, and the cycle is safe to close as PROCEED-WITH-CAVEATS.

---

## Independently verified (commands I ran myself, not trusting the session log)

| Check | Result | Verdict |
|---|---|---|
| **A3 frozen-seam 0-delta** (`git diff 9213fd6..HEAD` over `compliance_council.py` + `judges_dspy.py` + `judge_metric.py` + `council_roles/` + `clinical_v1.json` + `ws0_default.json` \| `wc -l`) | **`0`** | PASS (load-bearing) |
| **CLAUDE.md lint** (`lint_golden_against_taxonomy.py --golden examples/uap5a_flip_demo.jsonl`) | `[OK] TIER_1 WRONG_DOSAGE x1` … `OK: every code resolves … every Tier-1 flag paired with a reject verdict` | PASS |
| **Owner residency (#4)** | `WRONG_DOSAGE` owners `[behavior_judge, risk_judge, source_message_judge]`; production-resident = **`risk_judge`** (the declared owner); NOT a `source_message_judge`-only case | PASS |
| **Offline uap5a tests** (`test_uap5a_projection.py`, `test_uap5a_flip_demo.py`, $0 injected predictors) | `3 passed` | PASS |
| **D1 Vitest** (`panes.test.jsx`, `JudgeEditor.test.jsx`) | `5 passed (2 files)` | PASS |
| **Default-deps import-clean** (`import lithrim_bench`; dspy/openai/fastapi in sys.modules?) | `LEAKED: none` | PASS |
| **Offline suite** (`pytest tests/ -q` under debuglithrim) | `264 passed, 0 failed` (matches session log "264p/0f") | PASS |
| **Pathspec discipline** (`git status --porcelain`) | `.claude/`, `KICKOFF_CRITIC_…`, `REPORT_fhir_agentbench…` still **untracked**; the monitor-edited driver `.md` shows ` M` (unstaged) — none swept into commits | PASS |
| **Demo case is the injector's genuine output** (read `injectors/wrong_dosage.py`) | `_swap = soap.replace(pre_dose, post_dose, 1)` → first-occurrence-only swap yields `"…450MG Oral Tablet 300 MG daily"`; the odd double-dose is the deterministic injector output, **not** hand-tampering | PASS |
| **ruff on changed Python** | new files clean; `stages.py` 127→128 errors (**+1 `UP006`** at `stages.py:564 _synth_reason(…, finding_codes: List[str])`) — all pre-existing-class typing debt; file is non-clean at baseline | NON-BLOCKING nit |

---

## 1. Surface fidelity

| Spec/driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| Driver A.1 — mount `tool-judge_editor` in `CenterPane`, mirror `tool-agent_editor`, thread `onResult` into config-plane state | `panes.jsx:172` `renderTool({type:"tool-judge_editor", output:{role,agent}}, {onResult: captureSetup("judge")})` — identical pattern to `:162` agent editor | YES | — |
| Spec §2A — judge = ASSIGNED ontology → refinement questions; execute-not-generate | demo flips on the `=== AUTHORED REFINEMENT (ontology assignment) ===` marker that `render_role_questions` appends *only* when a flag is assigned; no validator generated anywhere | YES | — |
| Spec §4 / `JudgeVote` shape (`models.py:28`) | `_judge_votes_from_models` populates `judge_role`/`vote`/`confidence`/`reason`/`model`/`findings` | YES, with one caveat ↓ | — |
| `models.py:42` `model: str  # LLM model id … (NOT the role name)` | D2 fallback `model=model_lookup.get(role) or m.get("model")` puts the **role name** here on the authored path (seam dict's `model` IS `self.role`, `judges_dspy.py:287`) | DEVIATES from the field's own doc-comment | **NON-BLOCKING** |
| Driver E.7 / §10 — "only if BFF surface changes (it should NOT)" | no `apps/bff/` file in the diff; `SPEC_PRODUCT_SHELL.md` gets a single "**UAP-5a — NO BFF surface change**" note | YES | — |
| BFF surface (`/v1/judges`, `/v1/run-eval`, `/v1/runs/{id}/audit`) reused unchanged | confirmed: zero BFF files in `git diff --name-only` | YES | — |

**Findings:**

- `[NON-BLOCKING]` **`JudgeVote.model` semantic stretch.** `models.py:42` documents `model` as "LLM model id, e.g. 'gpt-4.1' (NOT the role name)". The D2 fix deliberately falls `model` back to the role name on the authored/injected path (because the FROZEN DSPy seam dict carries no Azure deployment id — `judges_dspy.py:286-292` returns `{"model": self.role, …}`). This makes the audit *legible* (the §2B goal) but the value contradicts the field's stated contract. The executor disclosed this openly as **S-BS-71** (low) with a clean additive fix (attach a real `{role: deployment}` lookup off the non-frozen `authored_stage.py`). Not blocking — it neither corrupts a label nor touches the frozen seam — but the field's doc-comment should be reconciled (or the fix landed) so the contract and the behavior agree.

---

## 2. Behavioral fidelity

### Behavior 1: S-BS-62 — a user can author a judge in the UI ($0 preview)

- **Spec assertion:** Driver A1 — "`tool-judge_editor` renders in `CenterPane`; the `$0` assignment→prompt→questions preview works in-UI (no model call)."
- **Test:** `panes.test.jsx` "mounts the JudgeEditor with the $0 prompt preview (S-BS-62)" — asserts `Judge · risk_judge` renders, the "the exact role_key_questions" preview copy is present, and a "Save judge" button exists. **Ran it: 5/5 Vitest green.**
- **Implementation:** `panes.jsx:167-174` mounts the tool-part in the conversation flow with `onResult: captureSetup("judge")` (the same config-plane capture closure the agent/flag/contract editors use).
- **Chain closes?** **YES** (offline). The `$0` preview itself is the WS-5c/UAP-2 `getJudge` path (out of this diff but exercised by the existing JudgeEditor test).
- **Note:** The `:5180` *visual* smoke (A1's A8-class gate) is **OWED** — user-run, correctly flagged in the session log and not claimed as done.

### Behavior 2: S-BS-66 — the authored per-judge audit is LEGIBLE

- **Spec assertion:** §2B — "every action … emits an immutable AuditRecord (why/when/who/what)"; driver A2 — "council.votes + `/v1/runs/{id}/audit` carry **non-empty** role/decision/model/findings."
- **Test:** `test_uap5a_projection.py::test_injected_path_projects_non_empty_model_reason_and_roster` — asserts `all(v["model"] for v in votes)`, `risk["model"]=="risk_judge"`, `risk["reason"]` non-empty and contains `WRONG_DOSAGE`, `policy_judge["reason"]==""` (clean approve stays empty), roster `== list(V2_ROLES)`. **Ran it: green.**
- **Implementation:** `stages.py:564 _synth_reason` + `:611-619` (model fallback + reason synthesis) + `:861-868` (roster projection off the seam `model` fields, replacing `["injected"]`).
- **Chain closes?** **YES** offline; the **live** half is the executor's paid attestation (rid `8f5bbcda`), which I could not re-run (cost-gate). The code path is sound and the offline regression pins the exact shape, so the live claim is plausible and internally consistent.
- **Note:** see D2-honesty below — the synthesized `reason` is an honest reconstruction, not a fabrication.

### Behavior 3: A4 — an authored judge changes the verdict (the flip)

- **Spec assertion:** Driver A4 — "the demo case grades **non-reject unassigned** and **reject when the flag is authored** … on the **real in_process trio** (cost-confirmed), AND reproduced **offline/$0**."
- **Test:** `test_uap5a_flip_demo.py::test_demo_case_flips_non_reject_to_reject_on_assignment` — unassigned → all approve → verdict ≠ reject; assigned `{risk_judge:[WRONG_DOSAGE]}` → risk_judge BLOCK → composite reject. **Ran it: green (offline).**
- **Implementation:** the flip rides the assignment marker (`render_role_questions` appends the refinement section iff a flag is assigned); the Tier-1 one-strike floor in the FROZEN `_apply_consensus` drives the composite.
- **Chain closes?** **OFFLINE: YES. LIVE: NO (FAIL).** On the real paid trio both unassigned AND assigned returned BLOCK — the base risk_judge already catches the 1.5× drift ("zidovudine 450MG, but transcript confirms 300MG"), so there is no miss to flip. Correctly recorded as **A4 FAIL → S-BS-70**.
- **Note:** see A4-integrity below.

**Findings:**

- `[NON-BLOCKING]` **A4 live-flip FAILED — but honestly.** The phase's headline product promise ("author a judge → watch the verdict change") is **not demonstrated live**. This is a genuine shortfall against the driver's A4 and the `judge-creation-must-be-demonstrable` bar, but it is surfaced truthfully (not gamed) and the user pre-authorized honesty-over-manufacture. It does not block *closure* (PROCEED-WITH-CAVEATS is the right verdict), but the monitor must carry S-BS-70 forward as the unfinished core of the visceral demo. See the "A4-integrity" judgment.
- `[OPEN-QUESTION]` **Stale premise left in shipped artifacts.** The committed demo-agent `note` (`uap5a_flip_demo.json:9`) and the generator docstring (`generate_uap5a_flip_demo.py:5-8`) assert as fact that "the base risk_judge **under-fires** (calibration gap)" — the very premise the live run **refuted**. The session log and the `SPEC_PRODUCT_SHELL.md` note correct this, but the shipped data-file/script prose still states the disproven claim. Recommend reconciling the demo-agent note + generator docstring to read "intended/hypothesized base-miss; live run showed the base trio catches it (S-BS-70)" so a future reader of the artifact isn't misled.

---

## 3. Out-of-scope intrusion

Driver §2 deliverables (verbatim): A.1 `panes.jsx` mount · B.2 `stages.py` projection · C.3 demo case + demo agent (`examples/…`, `data/config/agents/<demo>.json`) · C.4 cost-gated verify · D.5 `JudgeEditor.test.jsx`/panes mount test · D.6 `tests/test_uap5a_*.py` · E.7 `SPEC_PRODUCT_SHELL.md §10` note.

`git diff --stat 9213fd6..HEAD` (10 files):

```
apps/shell/src/panes.jsx                         |  9 ++   ← A.1
apps/shell/src/panes.test.jsx                    | 11 ++   ← D.5
lithrim_bench/runtime/pipeline/stages.py         | 37 +++  ← B.2
data/config/agents/uap5a_flip_demo.json          | 23 ++   ← C.3
examples/uap5a_flip_demo.jsonl                   |  1 +    ← C.3
scripts/generate_uap5a_flip_demo.py              | 109 +++ ← NOT in §2 file list
tests/test_uap5a_flip_demo.py                    | 111 ++  ← D.6b
tests/test_uap5a_projection.py                   | 88 ++   ← D.6a
docs/specs/SPEC_PRODUCT_SHELL.md                 |  1 +    ← E.7
session-…UAP-5a-2026-06-04.json                  | 147 ++  ← close artifact
```

**Findings:**

- `[NON-BLOCKING]` **`scripts/generate_uap5a_flip_demo.py` is justified, not intrusion.** It is not in the driver's literal file list but is squarely **within D3 intent** and is the *correct* by-construction discipline: rather than hand-writing the JSONL (the exact anti-pattern CLAUDE.md forbids — "Do not append to `examples/*.jsonl` without the lint passing"; "the recipe **is** the label justification"), the executor wrote a deterministic generator that runs the real `WrongDosageInjector` + `package_case` (which enforces D1/D3) so the label is true by construction and reproducible. Logged as an APPROVED-MID-CYCLE deviation. **Keep it.**
- **No forbidden-scope leakage.** I grepped the full diff for `withstands`/`ralph-loop`/`signals`/`groundingcheck`/`optimize`/`calibrat`/`LLMClient`/`ClaudeCliClient`/`ClaudeSDK`/`SSE`/`EventSource`/`/v1/author`/`⌘K`/`cmdk`/`command-palette`. **Every hit is in prose** (session-log narrative, docstrings, the spec note describing what was deferred) — **zero out-of-scope code**. R10 author-assist, R11 chat/SSE/⌘K, the §2A withstands-gate, and optimize/calibration are all absent from the implementation. The "calibration near-miss" wording is the demo-case framing, not the UAP-4 optimize feature.
- **No drive-by refactor/format/dep bump.** The +1 `UP006` in `stages.py` is *consistent with the file's existing convention* (97 pre-existing of the same class); the executor explicitly did **not** modernize the file's typing (which would have been the drive-by). Correct restraint.

All diffed files map to deliverables (the generator as justified D3 support). No intrusion.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: `reason` synthesis vs leave-empty (driver D2 left this as a plan-review decision)

- **Spec text:** §2B types the judge-raise `why` as `{taxonomy_code, decision, reasoning, evidence_spans[], confidence}` but does not say what to do when the per-judge seam carries **no** `reasoning`/`summary`. Driver B.2 explicitly defers: "synthesize from findings/evidence_spans … vs leave `reason` empty."
- **Implementation decided:** synthesize `f"{decision} — {codes}"` **only when grounded findings exist**; clean approve → `""` (`stages.py:564-575`).
- **Alternatives also spec-compliant:** leave `reason` empty and rely on `findings` alone.
- **Question for spec author:** is a reconstructed-from-(decision+grounded-codes) `reason` an acceptable §2B "why", or must `why.reasoning` carry *only* model-emitted prose (and therefore stay empty on the DSPy path until the seam surfaces `reason`)?
- **Recommended resolution:** **accept.** It is honest (built solely from data the judge emitted; empty when there's nothing to justify) and strictly improves audit legibility. Lock it in §2B as "reconstructed-when-absent is permitted, provided it is derived only from emitted decision+grounded findings."

### Ambiguity 2: `JudgeVote.model` semantics on a seam that has no deployment id

- **Spec text (absence):** §4 lists `model` binding as part of a judge but does not specify what `JudgeVote.model` must hold when the per-judge seam (FROZEN) exposes no Azure deployment string.
- **Implementation decided:** fall back to the role name (`stages.py:615`), contradicting `models.py:42`'s "(NOT the role name)" comment.
- **Alternatives also spec-compliant:** leave `model=""`; or thread a `{role: deployment}` lookup off `authored_stage` (the S-BS-71 fix).
- **Question for spec author:** should the authored-path audit show the *deployment id* (requires the S-BS-71 follow-up) or is the role-name fallback acceptable as the legible interim?
- **Recommended resolution:** **accept interim + land S-BS-71**; update the `models.py:42` doc-comment to acknowledge the authored-path fallback so the contract matches behavior.

### Ambiguity 3: D1 scope — CenterPane-only vs also a ⌘K entry

- **Spec/driver text:** driver A.1/§3.4 left "CenterPane mount only vs also a ⌘K entry" as a plan-review decision; full chat = UAP-5b.
- **Implementation decided:** CenterPane mount only (no ⌘K).
- **Recommended resolution:** **accept** — explicitly permitted as "the minimum"; ⌘K is a deferrable entry-point, not a behavior gap.

**Findings:**

- `[OPEN-QUESTION]` reason-synthesis acceptability under §2B (Ambiguity 1) — recommend accept + lock.
- `[OPEN-QUESTION]` authored-path `model` semantics + the `models.py:42` contract-comment mismatch (Ambiguity 2) — recommend accept interim + land S-BS-71 + fix the comment.

---

## Specific judgments demanded by the kickoff

### D2-honesty (audit-projection integrity, §2B)

**HONEST.** The synthesized `reason` (`stages.py:564 _synth_reason`) returns `f"{decision} — {', '.join(finding_codes)}"` **only when `finding_codes` is non-empty**, else `""`. The `finding_codes` come from `_validate_findings` (`judges_dspy.py:131-149`), which admits **only in-`KNOWN_TAXONOMY_CODES`, evidence-grounded** findings — so "reject — WRONG_DOSAGE" is a faithful restatement of what the judge actually emitted (decision + its grounded codes), never invented prose. **A clean approve carries no findings → `reason` stays empty** (test-pinned: `policy_judge["reason"]==""`). The `model` fallback surfaces the seam's own `model` field, which on the DSPy path **is** `self.role` (`judges_dspy.py:287`) — it recovers *which judge voted*, not a fabricated deployment. This is a reconstruction from emitted data, not a fabricated rationale. The only blemish is that `model`'s value contradicts its doc-comment (S-BS-71), which is disclosed and non-blocking.

### A4-integrity (the headline caveat)

- **(a) Is the demo case a REAL by-construction defect?** **YES.** Transcript says "300 MG"; artifact PLAN says "450MG" — a genuine 1.5× `WrongDosageInjector(factor=1.5)` drift. The recipe is complete (`defect_type/mutated_projection/mutated_field_or_span/pre_value/post_value/params`), lint is green (`[OK] TIER_1 WRONG_DOSAGE`), the Tier-1↔reject pairing holds, and the owner (`risk_judge`) is production-resident. The case was produced by the **unmodified injector** (the first-occurrence `replace(…, 1)` explains the in-artifact double-dose) — not hand-gamed. Label warranted.
- **(b) Is the offline-flip-via-injected-predictors a LEGITIMATE mechanism-proof?** **YES, but it proves a narrower claim than "the judge changes its mind."** What it honestly proves: *the assignment reaches the judge's prompt (the marker appears iff assigned) and a resulting BLOCK propagates through the Tier-1 floor to flip the composite* — i.e. the orchestration is consequential at $0. It does **not** prove a real LLM under-fires unassigned and fires assigned; the predictor is a stand-in for "a judge that fires iff it sees the refinement." The test docstring states exactly this and labels the live run as the real attestation. Not a fake pass — it is a correctly-scoped *plumbing* proof, clearly distinguished from the empirical claim.
- **(c) Is A4-FAIL→S-BS-70 PRINCIPLED, or does it paper over a missed core purpose?** **PRINCIPLED — and it does NOT paper over the gap; it names it.** The honest reading: the phase delivered the *machinery* (mounted editor, legible audit, an admissible by-construction case, a verified offline flip mechanism) but **not** the visceral live payoff, because the chosen defect (a base-owned Tier-1 dosage drift) is one the base trio already catches — so there was no miss to flip. The executor refused to manufacture a flip (which would have violated labels-true-by-construction), surfaced the failure as CONFIRMED with live evidence (both runs BLOCK), and opened S-BS-70 with the correct prescription (a defect the base trio genuinely misses — a non-v2-base-owned code or a subtle semantic defect). This is the right call. The cost: the "watch the verdict change" demo — the paid finale that `judge-creation-must-be-demonstrable` says is the product's emotional core — is still **owed**. Closure is appropriate; the monitor must not let S-BS-70 be treated as cosmetic.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 (`JudgeVote.model` vs doc-comment) | 0 |
| 2 | Behavioral fidelity | 0 | 1 (A4 live-flip FAIL → S-BS-70) | 1 (stale "base under-fires" premise in shipped artifacts) |
| 3 | Out-of-scope intrusion | 0 | 1 (generator script — justified, keep) | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 (reason-synthesis; authored-path `model`) |
| — | ruff +1 `UP006` on `stages.py` | 0 | 1 | 0 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions

No BLOCKING findings. For NON-BLOCKING / OPEN-QUESTION worth a follow-up:

1. **A4 live-flip not reproduced (S-BS-70).** Disposition: **accept as the cycle caveat; carry S-BS-70 as a first-class follow-up** — it holds the product's visceral demo. Owner: a future demo/UAP-5a-assist cycle. Do not down-grade to cosmetic.
2. **`JudgeVote.model` shows the role name (S-BS-71) vs `models.py:42` "(NOT the role name)".** Disposition: land the additive `{role: deployment}` lookup off `authored_stage.py`; meanwhile update the `models.py:42` doc-comment so the contract matches the fallback. Owner: S-BS-71.
3. **Stale "base under-fires (calibration gap)" premise in `uap5a_flip_demo.json:9` + `generate_uap5a_flip_demo.py` docstring.** Disposition: reword to "hypothesized base-miss; live run showed the base trio catches it (S-BS-70)" so the shipped artifact doesn't assert the refuted claim. Owner: monitor in close-out or the S-BS-70 cycle.
4. **+1 `UP006` (`List[str]`) in `stages.py:564`.** Disposition: accept (consistent with the file's pervasive convention; the file is 128-error baseline; `ruff format` — the CLAUDE.md-named lint — does not flag it). Optional: a separate file-wide typing-modernization pass, explicitly out of this cycle's scope.
5. **OPEN-QUESTIONs (reason-synthesis acceptability; authored-path `model` semantics).** Disposition: spec author lock in §2B/§4 in a doc cycle.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec + driver + CLAUDE.md before reading the executor's session log (read the session log LAST)
- [x] Read the diff via `git diff`/`git show` against commits, and re-ran the tests/lint myself — did not rely on the executor's summary
- [x] Each finding cites both spec/driver and implementation file:line
- [x] Did NOT edit any code, spec, test, seed, or driver (only wrote this critique file)
- [x] Did NOT confer with monitor or executor before writing the verdict
- [x] Made NO paid LLM calls / no live council / no `--live` (only $0 offline injected-predictor tests + lint + Vitest)

---

## Appendix: commits audited

```
e2c48a6 docs(bench-salvage): UAP-5a executor session log (PROCEED-WITH-CAVEATS)
2faf8d3 docs(spec): note S-BS-62/66 closed + the demo agent/case (no §10 surface change)
0669743 test(uap-5a): S-BS-66 legible projection + the demo live-flip (offline/$0)
e3b0591 feat(injectors+examples): by-construction live-flip demo case + agent (UAP-5a A4)
1c6a629 feat(shell): mount tool-judge_editor in CenterPane (S-BS-62)
d7be919 fix(stages): legible per-judge projection on the authored in_process path (S-BS-66)
```

## Appendix: files changed

```
apps/shell/src/panes.jsx                           |   9 ++
apps/shell/src/panes.test.jsx                      |  11 ++
data/config/agents/uap5a_flip_demo.json            |  23 ++++
docs/specs/SPEC_PRODUCT_SHELL.md                   |   1 +
examples/uap5a_flip_demo.jsonl                     |   1 +
lithrim_bench/runtime/pipeline/stages.py           |  37 +++++-
scripts/generate_uap5a_flip_demo.py                | 109 +++++++++++++++
tests/test_uap5a_flip_demo.py                      | 111 ++++++++++++++++
tests/test_uap5a_projection.py                     |  88 ++++++++++++
.devloop/sessions/session-…UAP-5a-2026-06-04.json  | 147 +++++++++++++++++++++
```
