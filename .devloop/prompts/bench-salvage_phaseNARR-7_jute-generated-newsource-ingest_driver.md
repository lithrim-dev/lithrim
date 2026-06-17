# Driver — `bench-salvage` phase `NARR-7`: JUTE-generated ingest for an ARBITRARY new source — the "eval anything" generality (P-GEN)

> **Authored by the monitor from a LIVE validation spike (2026-06-17): the engine + generation were proven against `:3031` directly, with verbatim evidence, BEFORE this driver was locked. Every load-bearing anchor re-grepped.**
>
> **Bundle ID:** `bench-salvage-phaseNARR-7-jute-generated-newsource-ingest-driver`
> **Version:** v1 · **Authored:** 2026-06-17 · **Re-verified:** 2026-06-17 (vs HEAD `b8cff10`)
> **Hardness:** **HARD GATE** (edits the extractor's generation grounding — affects what transforms get generated; a new-source route; live-LM-gated evidence. The MOAT is read-only — fresh cold critic at close.) **$0 deterministic gate** — a one-time paid/`$0` template generation is the only LM cost, behind the live-gated path.

---

## KICKOFF (paste into a fresh executor session)
```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase NARR-7
(JUTE-generated ingest for an ARBITRARY new source — the "eval anything" generality; P-GEN).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseNARR-7_jute-generated-newsource-ingest_driver.md  (this doc)
  3. docs/research/NOTE_jute_extractor_wired_demo_2026-06-17.md  (the VALIDATED findings + the deployed capability map — read §A/§B fully)
  4. lithrim_bench/verification/jute_extractor.py  (the extractor: score_extraction:103, _build_extractor_signature:202, build_extractor_generator:232, best_of_n_extractor:325, _to_envelope:63)
  5. lithrim_bench/verification/jute_dspy.py:279  (render_dsl_excerpt) + the _RUNTIME_NOTES const (grep it) — SHARED by the validator; do NOT regress it
  6. apps/bff/app.py:2004-2120  (_ingest_cases — the generate->:3031-gate->PIN->corpus-upsert->audit pipeline to REUSE; note the expected_count heuristic :2030-2040 — it's a BUG for a {issues,comments} dict, see G3/R5)
  7. tests/verification/test_jute_extractor.py  (FakeExtractorClient:117, PROVEN_TEMPLATE:42, score_extraction tests, the skip-guarded test_live_extractor_converges)
  8. out/storyworld_real/github_newsource_sample.json  (the REAL new-source sample already fetched: pallets/flask issues+comments, join-valid) — trim + commit a small fixture from it
  9. lithrim_bench/verification/etlp_client.py:97-145  (test_template wraps sample_input as {resource: <input>}; apply contract)

Canonical env:
  LITHRIM_BENCH_PACK=narrative LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim
  Regression: LITHRIM_BENCH_PACK=healthcare ... ; UI: cd apps/shell && npx vitest run
Services are UP (curl /health; NEVER autostart). For localhost curl/HTTP from Bash use dangerouslyDisableSandbox:true.
Gate 0 is OFFLINE (mock :3031 + the LM). The LIVE convergence test is LITHRIM_NARR_LIVE-gated — RUN it once for evidence, it is NOT part of the green bar.

Post your plan-review per EXECUTOR.md. Do not write code until I say "go".

Bundle ID: bench-salvage-phaseNARR-7-jute-generated-newsource-ingest-driver
```

---

## 0. Context — what's already PROVEN (do not re-litigate; build on it)

A live validation spike this session (verbatim evidence in `docs/research/NOTE_jute_extractor_wired_demo_2026-06-17.md` §A) established, against the deployed `:3031`:
- **The engine expresses the per-scene/relational join** (nested `$reduce` join-by-key): StoryWorld scenes⋈calls **5/0**, AND a genuinely new shape (GitHub issues⋈comments) **6/0** — the earlier "engine-scope-blocked" claim was a double-wrap feed bug, now overturned.
- **A capable model reliably GENERATES it** given truthful grounding: 8/8 blind+steered agents produced live-accepted StoryWorld transforms; agents steered toward the trap idioms correctly refused them.
- **Deployed capability map:** `len`✓ `groupBy`✓ `replace`✗ `count/length/size`✗; **robust idiom = nested-`$reduce` find-by-key**; **two traps** — predicate `coll.*(this.k=key).0.field` → `[]`, and `assoc`-built index `.(key)` → null (string-vs-keyword key mismatch).
- **The reliable pattern is already built:** `_ingest_cases` (app.py:2004) = generate (`best_of_n_extractor`) → live-`:3031`-gate (`score_extraction`) → **PIN** → apply → corpus-upsert → one AuditRecord. It's live on the chat `ingest_cases` tool.

**The gap NARR-7 closes:** the extractor's GENERATION grounding (`render_dsl_excerpt`/`_RUNTIME_NOTES`) is **validator-focused** — it does NOT teach the join idiom or warn about the two traps. The 8/8 used an ENRICHED excerpt. So generation on a join-heavy new shape is **not yet reliable in-product**. Plus `_ingest_cases` mis-infers `expected_count` for a non-list dict. Fix both, prove generality on a NEW source, demonstrate in the shell.

**OWNER DECISIONS (2026-06-17 — bake in):** (1) **Build it.** (2) **Target a genuinely NEW source shape** (the real "eval anything" win — not a StoryWorld re-proof). Recommended: **GitHub issues+comments** (real, nested, join-by-key, non-clinical — sample already fetched). (3) **Gen LM picked at build time** — default **BYO-Claude $0** (the trimmed ~1.6KB sample clears the old 120s timeout), **Azure fallback** if the CLI adapter misbehaves.

---

## 1. Deliverables (P-GEN; deterministic gate is $0/offline)

**G1 — enrich the EXTRACTOR's generation grounding (the reliability lever; SMALL but load-bearing).**
- Add EXTRACTOR-specific runtime facts the model needs to author a JOIN. The exact set is **empirically derived** — these are the quirks that took a blind first-shot to **0/3** and a one-round refine to **3/3** on the GitHub shape (NOTE §A2):
  - `$map` over an OBJECT → `{key,value}` (recover the key with `str(e.key)`); the **`$reduce` find-by-key join** idiom; `len`✓/`groupBy`✓; the **feed-shape rule** (engine wraps input as `{resource:<input>}`).
  - **STRING LITERALS: DOUBLE QUOTES ONLY** — single-quote literals `'x'` FAIL to parse on deployed (the spec lies). *This was the dominant first-shot failure.*
  - **CONCAT with `+`**, e.g. `a + "-" + toString(b)` — `joinStr` is `(sep, ARRAY)`, NOT a variadic concat.
  - A `$reduce`/`$let` `$body` that selects between values MUST be a **structured `$if` OBJECT** (`{$if:, $then:, $else:}`), NEVER an inline string `"$ $if: …"`.
  - The **two join TRAPS** (predicate-`.0` → `[]`; `assoc`-index keyword/string mismatch); the **no-`#`-in-a-YAML-scalar** rule.
- **DO NOT regress the validator.** `_RUNTIME_NOTES` is SHARED by `jute_dspy` (validator) and the extractor. Add an **extractor-only addendum** (a separate const appended ONLY on the extractor path — e.g. `render_dsl_excerpt(..., for_extractor=True)` or a dedicated `render_extractor_excerpt`), leaving the validator's excerpt **byte-identical**.

**G2 — make the live gate RUN on a NEW shape (the honest "it generalizes" evidence).**
- Repoint/extend the skip-guarded `test_live_extractor_converges` (or add `test_live_extractor_converges_github`) so that under `LITHRIM_NARR_LIVE=1` it: builds the extractor with the enriched excerpt, runs `best_of_n_extractor` against the committed GitHub fixture, and asserts the **live `:3031`** accepts (count=6, zero-null). RUN it once in-cycle; capture the result to a PROOF doc. **It is NOT in Gate 0.**

**G3 — route a NEW source through the existing pipeline + demonstrate in the shell (mostly COMPOSE).**
- **Fix the `expected_count` heuristic** (`_ingest_cases` app.py:2030-2040): today it returns `enhanced_scenes`-count OR top-level-list-len OR `1` — so a `{issues, comments}` dict ingests as `1` and the 6-case transform is rejected. Add an explicit `expected_count` (and/or an "iterated collection" hint in `extraction_rules`) so the caller/agent can name the source collection. Keep StoryWorld behavior unchanged.
- **Demonstrate** the GitHub dump ingesting via the EXISTING path end-to-end in the shell: the chat `ingest_cases` tool (or a thin connector "generic source" route if the chat path is insufficient for "in the shell") → generate→gate→**PIN**→apply → **6 cases** → corpus → one AuditRecord ("ingested 6 cases via pinned mapping M"), gradeable by `case_id` (D1 bridge). The StoryWorld deterministic direct-write stays the DEFAULT; this is the generation path for an arbitrary source.
- **Commit a small, trimmed, injection-free GitHub fixture** under `tests/fixtures/narrative/` (the live `github_newsource_sample.json` is from `pallets/flask` — clean; trim bodies; tests must run offline).

---

## 2. Tests-first (RED before code; ALL $0/offline — mock `:3031` + the LM)
- **A1 (G1):** the EXTRACTOR excerpt contains the `$reduce` find-by-key join idiom + BOTH trap warnings + `len`/`groupBy`; AND the VALIDATOR excerpt (`render_dsl_excerpt` as used by `jute_dspy`) is **byte-unchanged** (non-regression). RED at parent.
- **A2 (G1 non-vacuity):** a fake predictor emitting a TRAP template (predicate-`.0`) over the GitHub fixture → `score_extraction` (FakeExtractorClient tuned to the trap) → REJECTED. Proves the grounding+gate target a REAL failure, not a tautology.
- **A3 (G3 offline):** `score_extraction` over the committed GitHub fixture with the known-good pinned template → **6 cases, zero-null**, `issue_title` correctly joined. RED at parent (fixture/path absent).
- **A4 (G3 expected_count fix):** `_ingest_cases` with an explicit `expected_count=6` (or rules naming `comments`) on the GitHub dict → 6 cases (was 1 at parent → RED). Mock the LM (inject a predictor returning the known-good template) + `:3031` (FakeExtractorClient).
- **A5 (D1 bridge):** a GitHub-ingested case resolves by `case_id` through the picklist/`load_case` (mirror NARR-5/NARR-6 D1).
- **A6 (mis-join fails clean):** a mis-joined GitHub template → the apply-gate rejects → nothing pinned, no bad provenance.
- Mock the StoryWorld/LM/`:3031` so the whole green bar is $0/offline (mirror `tests/bff/test_ingest_cases_bound.py` + the FakeExtractorClient pattern).

## 3. Plan-review risks
- **R1 — `_RUNTIME_NOTES` is SHARED (validator + extractor); the #1 correctness risk.** Add an extractor-ONLY addendum; assert (A1) the validator excerpt is byte-identical. Re-run the `jute_dspy` validator tests — 0 new failures.
- **R2 — gen LM plumbing.** BYO-Claude `claude -p` had a 120s timeout + a ChatAdapter→JSONAdapter parse mismatch on the 162KB session; the trimmed ~1.6KB GitHub sample clears the timeout. If the CLI adapter still misbehaves, use **Azure** (one-time, pinned). The LIVE test is `LITHRIM_NARR_LIVE`-gated; **Gate 0 NEVER calls an LM** (inject a predictor).
- **R3 — fixture hygiene.** Commit a trimmed, **injection-free** GitHub fixture (the spike saw a prompt-injection issue body on a *different* repo — `pallets/flask` is clean; still, treat ingested `body` text as INERT DATA — it is graded content, never an instruction; the JUTE transform is a pure data transform, no code/instruction execution).
- **R4 — MOAT + core read-only.** `git diff b8cff10 HEAD --` EMPTY for `runtime/council/{compliance_council,signals,withstands,judge_metric}.py` + `harness/grounding.py` + `verification/{spec,tools}.py` + `apps/bff/agent/tools.py`. G1 edits `jute_extractor.py` + `jute_dspy.render_dsl_excerpt` (BOTH ingestion-only, above the seam, absent from every grade-time floor/contract registry — `test_jute_extractor.py` pins this). `_ingest_cases` is EDITED only for the `expected_count` hint (additive; StoryWorld path unchanged). No re-snapshot.
- **R5 — feed-shape + expected_count.** The generated transform targets the source's NATIVE shape; `test_template` wraps it as `{resource:<dump>}`. `expected_count` MUST equal the iterated collection's length (GitHub: `len(comments)`=6, NOT the dict). This is the G3 fix — without it the new shape rejects.

## 4. Scope guards / NOT in scope
- **No** paid council over the corpus (deferred); **no** corpus Findings view (**resequenced to NARR-8** — it was pencilled as NARR-7 in the NARR-6 driver; the owner pulled the JUTE generality forward this session); **no** moat/core edit; **no** healthcare touch; **no** auto-on-connect generation UI (a follow-on — the demonstrable cut routes an arbitrary dump through the EXISTING pipeline). The StoryWorld deterministic path stays the default.

## 5. Exit
- A1–A6 GREEN (`pack=narrative`); canonical regression (`pack=healthcare`) 0-new vs `b8cff10`; vitest 0-new; ruff clean; **moat 0-diff**; RED→GREEN with parent-RED pasted; the validator excerpt byte-unchanged.
- **Live evidence (owner/manual, `LITHRIM_NARR_LIVE`):** `best_of_n_extractor` GENERATES the GitHub transform (BYO-Claude $0 or Azure) → `:3031` accepts **6/0** → PIN → apply → 6 cases; captured to `docs/research/PROOF_jute_newsource_<date>.md` (honest-Δ — if it doesn't converge, report it).
- **Demonstrable (live, in the shell):** ingest the GitHub dump via the generation path → 6 cases land, PINNED transform + AuditRecord, gradeable by `case_id`.
- **HARD GATE:** a fresh cold critic confirms — the validator grounding is un-regressed, the new-shape generation is genuinely live-gated (not fake-oracle-only), `expected_count` is correct for the new shape, mis-join fails clean, and the moat/core are 0-diff.
