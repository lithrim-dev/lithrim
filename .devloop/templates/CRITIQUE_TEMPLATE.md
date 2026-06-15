# Spec-Adherence Critique — `<stream>` phase `<N>`

> **Filled in by the monitor (inline mode) or a fresh critic session
> (fresh-critic mode, for HARD GATEs).** Committed alongside close-out
> artifacts as
> `.devloop/sessions/critique-<stream>-phase<N>-YYYY-MM-DD.md`.

## Metadata

- **Stream:** `<stream-name>`
- **Phase:** `<N>`
- **Driver bundle:** `<bundle-id>`
- **Commits audited:** `<sha-list>`
- **Spec(s) read against:** `<paths + sections>`
- **Critique mode:** `inline` (monitor self-audit) | `fresh-critic` (separate session)
- **Date:** `YYYY-MM-DD`
- **Reviewer:** `monitor session-<id>` | `critic session-<id>`

---

## Verdict

**`<CLEAN | NON-BLOCKING FINDINGS | BLOCKING DRIFT>`**

One sentence: `<the load-bearing summary the monitor reads on closeout>`

---

## 0. Deterministic gate (supreme — runs first)

> Re-run the suite + linters + types from a clean checkout of the audited
> commits. This gate is supreme: any FAIL ⇒ `BLOCKING DRIFT`, halt, do not
> proceed to the 4 questions. The 4 questions (LLM-judge tier) run only
> once this is green and may never overturn it. Respect no-autostart
> (`curl /health` first).

| Check | Command (verbatim) | Result |
|---|---|---|
| Test suite | `<cmd>` | PASS / FAIL `<failing tests>` |
| Linter | `<cmd>` | PASS / FAIL |
| Type check | `<cmd>` | PASS / FAIL |

**Tests-first check:** does `git log` show the `test(...)` commit landing
*before* the implementation it covers? `<YES — RED→GREEN demonstrated / NO — flag>`

**Gate verdict:** `<GREEN — proceed to the 4 questions / RED — BLOCKING, halt here>`

---

## 1. Surface fidelity

> Does the public API (function names, signatures, return shapes, error
> taxonomy, configuration keys, exported namespaces) match the spec exactly?

For each public symbol the spec defines:

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| spec §X.Y `fn(args) -> T` | impl `file.py:42` `fn(args) -> T'` | extra field in `T'` | NON-BLOCKING |
| spec §X.Y error `:foo-error` | impl `file.py:88` emits `:foo-err` | renamed | BLOCKING |
| ... | ... | ... | ... |

**Findings:**

- `[BLOCKING | NON-BLOCKING | OPEN-QUESTION]` `<finding>`
- ...

If no findings: "No surface drift detected. All N public symbols match spec exactly."

---

## 2. Behavioral fidelity

> Pick 3 key spec-claimed behaviors. For each: trace spec assertion →
> test that exercises it → implementation site. Does the chain actually
> demonstrate the behavior?

### Behavior 1: `<short name>`

- **Spec assertion:** `<spec §, verbatim quote>`
- **Test:** `<test file:line, what it asserts>`
- **Implementation:** `<impl file:line, what it does>`
- **Chain closes?** `<YES / PARTIAL / NO>`
- **Note:** `<if PARTIAL or NO, what's missing>`

### Behavior 2: `<short name>`

- **Spec assertion:** ...
- **Test:** ...
- **Implementation:** ...
- **Chain closes?** ...
- **Note:** ...

### Behavior 3: `<short name>`

- **Spec assertion:** ...
- **Test:** ...
- **Implementation:** ...
- **Chain closes?** ...
- **Note:** ...

**Findings:**

- `[BLOCKING | NON-BLOCKING | OPEN-QUESTION]` `<finding>`
- ...

---

## 3. Out-of-scope intrusion

> Read the diff. Anything that isn't in the driver's deliverables list —
> drive-by refactors, formatting passes, "while I was here" edits,
> dependency bumps — is intrusion.

Driver's deliverables list (verbatim from the bundle):

1. `<deliverable>`
2. `<deliverable>`
3. ...

`git diff --stat <base>..HEAD` shows these files changed:

```
file.py                | 120 ++++++++++++++++++
other-file.py          |  45 ++++++++++++++++
README.md              |  12 +-
unrelated-format.md    |   8 +-   <-- not in deliverables list
```

**Findings:**

- `[BLOCKING | NON-BLOCKING | OPEN-QUESTION]` `<finding>`
- ...

If no intrusion: "All diffed files map to deliverables. No intrusion detected."

---

## 4. Spec ambiguity surfaced

> Where did the implementation make a judgment call because the spec
> was silent or ambiguous? List each as an open question for the spec
> author.

### Ambiguity 1: `<short name>`

- **Spec text (or absence):** `<verbatim quote OR "spec is silent on X">`
- **Implementation decided:** `<what the impl did, file:line>`
- **Alternatives that would also be spec-compliant:** `<list>`
- **Question for spec author:** `<the specific question>`
- **Recommended resolution:** `<accept | update spec to require Y | revisit>`

### Ambiguity 2: `<short name>`

...

**Findings:**

- `[OPEN-QUESTION]` `<finding>` (OPEN-QUESTIONs are not BLOCKING by default — they document implicit decisions so the spec author can lock or correct in a separate cycle)

---

## Summary of findings

| # | Gate / Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 0 | Deterministic gate (tests/lint/types) | 0 | — | — |
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 0 |

**Gate 0 RED** → cycle CANNOT close, regardless of the questions below.
**Total BLOCKING: 0** → cycle MAY close.
**Total BLOCKING: ≥ 1** → cycle CANNOT close. Propose correction below.

> Every BLOCKING finding from questions 1–4 must be reducible to a failing
> test (state it in "Required actions"). A fidelity concern that can't be
> expressed as a test is at most an OPEN-QUESTION — the LLM-judge tier does
> not block on judgment alone.

---

## Required actions (if any)

For each BLOCKING finding:

1. **Finding:** `<from above>`
   **Proposed correction:** `<commit X to fix, OR open follow-up cycle Y>`
   **Owner:** `<executor on this cycle | monitor in close-out | spec author>`

For NON-BLOCKING and OPEN-QUESTION findings worth a follow-up but
not blocking closure:

1. **Finding:** `<from above>`
   **Proposed disposition:** `<log as seam S-N | spec update in cycle Z | accept as-is>`

---

## Critic discipline self-check (fresh-critic mode only)

If performed by a fresh critic session (not monitor inline), confirm:

- [ ] Ran Gate 0 (suite + lint + types) from a clean checkout, recorded verbatim, BEFORE the questions
- [ ] Confirmed the `test(...)` commit precedes the implementation it covers
- [ ] Read the spec without reading executor's session log first
- [ ] Read the diff via `git show` against commits, not via executor's summary
- [ ] Each finding cites both spec file:line and implementation file:line
- [ ] Each BLOCKING finding is reducible to a stated failing test
- [ ] Did NOT edit any code, spec, or driver (running tests is not editing)
- [ ] Did NOT confer with monitor or executor before writing the verdict

If any are false, critique is in audit drift. Flag to user.

---

## Appendix: commits audited

```
<git log --oneline of audited range>
```

## Appendix: files changed

```
<git diff --stat of audited range>
```
