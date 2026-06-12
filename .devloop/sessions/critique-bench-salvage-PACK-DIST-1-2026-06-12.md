# Spec-Adherence Critique — `bench-salvage` phase `PACK-DIST-1`

> Fresh-critic mode (HARD GATE). Independent reproduction in a clean worktree
> (`/tmp/pdist-critic` @ `3501639`); the moat baseline is `acc4973`; the parent
> baseline is `af25065`. The sibling Pro pack is at the absolute path
> `/Users/aregee/Workspace/github.com/lithrim-pack-healthcare`.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `PACK-DIST-1` — extract the healthcare realm to an externally-loaded pack (release-clean the CE core)
- **Driver bundle:** `bench-salvage-phasePACK-DIST-1-extract-healthcare-to-external-pack`
- **Commits audited:** `9168670..4573088` (7 CE commits) + `3501639` (session log); CE parent baseline `af25065`; moat baseline `acc4973`. Pack repo: `0d61175`, `fca2147`.
- **Specs read against:** `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` (CE-clean contract); `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (OQ-3 separate distribution); the driver A1–A7.
- **Critique mode:** `fresh-critic`
- **Date:** `2026-06-12`
- **Reviewer:** critic session (fresh worktree, no prior implementation context)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

A1 (external load), A2 (CE-clean, non-vacuous), A4 (fail-closed), A5 (moat byte-identity) each independently reproduce; both readings (dev-discovered / bare-CE) hold; A6 is 0-new vs the parent `af25065`; the 4-file passive carve-out is genuinely provenance/docstring prose with zero hidden clinical data. **0 BLOCKING.** Two NON-BLOCKING/OPEN-QUESTION items concern the documented dev-runbook invocation and a pre-existing standalone-test credentials dependency — neither is a product-code defect, a moat delta, tracked clinical content, a silent fallback, or a new failure.

---

## 1. Surface fidelity

The public surface this cycle adds is the **discovery seam** in `lithrim_bench/harness/pack.py` (D1) and the CE-clean proof in `tests/test_pack_dist.py` (D4). Checked against the driver §2/§5 + `SPEC_PLUGIN_ARCHITECTURE` OQ-3.

| Spec / driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| D1: `_pack_root(pack) -> Path`, search order entry-point → `LITHRIM_BENCH_PACKS_DIR` → in-repo `packs/` | `pack.py:109` `_pack_root`; (1) `:116` `importlib.metadata.entry_points(group=…)`, (2) `:124` env dirs, (3) `:130` `PACKS_DIR / pack` | exact | — |
| D1: manifest refs become pack-root-relative (`_resolve_ref`) | `pack.py:143` `_resolve_ref(pack, ref)` | exact | — |
| D1: config key `LITHRIM_BENCH_PACKS_DIR`, `os.pathsep`-joined | `pack.py:60` `_PACKS_DIR_ENV`, `:89-91` split | exact | — |
| A4: absent pack → `FileNotFoundError`, never silent fallback | `pack.py:133-134` `raise FileNotFoundError("pack {pack!r} not found via entry points, …")` | exact | — |
| D1 (non-breaking): in-repo `packs/` resolve unchanged; `DEFAULT_PACK="_core"` | `pack.py:47-48` `PACKS_DIR`, `DEFAULT_PACK="_core"`; in-repo fallback at `:130` | exact | — |

**Findings:** No surface drift detected. The discovery search order, the `LITHRIM_BENCH_PACKS_DIR` key, the pack-root-relative `_resolve_ref`, and the `FileNotFoundError` taxonomy match the driver D1/A4 exactly. The frozen council's carve-out reads (`pack_tiers`/`pack_tier1_owners`/`pack_prompts_path`/`pack_production_judges`) are untouched by this cycle (§3).

---

## 2. Behavioral fidelity

### Behavior 1: A1 — `healthcare` loads from an EXTERNAL location, council binds identically

- **Spec assertion:** driver A1 — "`healthcare` loads from an EXTERNAL location … with the CE repo's `packs/healthcare/` absent."
- **Test:** `tests/test_pack_dist.py:157` `test_a1_council_binds_from_external_pack` — subprocess with `LITHRIM_BENCH_PACKS_DIR=<sibling>`; asserts `root` contains `lithrim-pack-healthcare` and not `lithrim-bench/packs`, `codes==19`, `owners==8`, `roster==["risk_judge","policy_judge","faithfulness_judge"]`.
- **Implementation:** `pack.py:109` `_pack_root` resolves via the external dir; the frozen council's import-time carve-outs read through it.
- **Chain closes? YES.** Reproduced two ways. (a) Manual one-liner, `LITHRIM_BENCH_PACKS_DIR=/Users/…/lithrim-pack-healthcare`, in the bare worktree (`packs/healthcare` confirmed absent → `os.path.isdir(...) == False`): `root=/Users/…/lithrim-pack-healthcare/healthcare`, `codes=19`, `owners=8`, `roster=[risk,policy,faithfulness]`. (b) `test_a1` itself **PASSED** (via a `/tmp/lithrim-pack-healthcare` symlink so `_HAS_SIBLING` resolves; symlink removed after). The FROZEN council binds all clinical data from outside the repo.

### Behavior 2: A2 — the CE tracked tree is clinical-free (non-vacuous)

- **Spec assertion:** driver A2 / `SPEC_STANDALONE_CORE_VALIDATION` §0 — "No `packs/healthcare/`, no clinical corpora, no clinical content beyond the enumerated interface vocabulary."
- **Test:** `tests/test_pack_dist.py:101-148` — `git ls-files packs/healthcare == []`; no `examples/*.jsonl`; only `ws0_default` agent seed (0 clinical strings); data-surface needle sweep clean beyond a 4-file carve-out; sweep non-vacuous (`:134`); carve-out minimal (`:143`).
- **Implementation:** the `git rm` (commit `484d025`) + the dogfood_v1 relocation (`2d32477`).
- **Chain closes? YES.** `test_pack_dist.py` in the bare worktree (env unset): **9 passed, 1 skipped** (A1 skips — sibling not at `/tmp/../`, as the task anticipated). Independent corroboration: I swept the **entire** tracked data surface (`packs` + `examples` + `data/config`, **no** carve-out exclusion) — 32 files, **exactly 4** with any needle hit, and those 4 == `_PASSIVE_CARVE_OUT` exactly. No 5th file hides clinical data. The 4 carve-out files eyeballed (below) are all provenance/docstring prose.

### Behavior 3: A5 — the moat is byte-identical vs `acc4973`

- **Spec assertion:** driver A5 — "`_apply_consensus`/`extract_verdict_confidence` byte-identical vs `acc4973`; … this cycle changes pack DISCOVERY (above the seam), never the council's logic."
- **Test:** `tests/test_pack_dist.py:205` `test_a5_moat_byte_identical_vs_acc4973` (AST `get_source_segment` compare) + `:222` `test_a5_ce_resident_frozen_guards_green` (`assert_compliance_council_carveouts_only` + `assert_judges_dspy_consensus_seam_frozen`).
- **Implementation:** PACK-DIST-1 touches **0 lines** of the frozen files.
- **Chain closes? YES.** `git diff af25065 HEAD --stat` over `compliance_council.py`/`signals.py`/`withstands.py`/`judges_dspy.py`/`judge_metric.py` is **empty** — this cycle's only council-dir edits are to two test files (`runtime/council/tests/conftest.py`, `test_judge_optimize.py`). AST-method hashes are **IDENTICAL** acc4973↔HEAD: `_apply_consensus` `d1b7956e70a8f2ef` (28761B), `extract_verdict_confidence` `ed867bce8be313fd` (1700B) — matching the executor's session-log hashes (their "29109B" byte-count is a measurement artifact; the hash matches). `acc4973..HEAD` for `compliance_council.py` is non-empty but **authorized-carve-outs-only**: PACK-1b tiers, PACK-2b owners, PACK-2 prompts-dir, PACK-2c roster, and the 6b-CLEAN/6c `build_prompt`/`build_source_message_prompt` deletions — all from prior authorized cycles. `test_pack_dist.py` A5 both PASSED.

**Eyeball of the 4 `_PASSIVE_CARVE_OUT` files (task-mandated):**

| File:line | Needle line — verbatim | Verdict |
|---|---|---|
| `packs/_core/ontology.json:3` | `_provenance.note`: "… The prose is **needle-free (no HIPAA/patient/medication/dosage/allergy/clinical/SOAP/escalation/consent/transcript wording)** …" | passive — enumerates the words it excludes |
| `packs/support_ticket_qa/ontology.json:3` | `_provenance.note`: "… non-clinical support-ticket-QA domain … The prose is **needle-free (no HIPAA/patient/…)** …" | passive — same pattern |
| `packs/support_ticket_qa/taxonomy_snapshot.json:4` | `note`: "A genuinely INDEPENDENT **non-clinical** pack — unlike the story_audit pack …" | passive — provenance prose |
| `packs/_plugin_fixture/floors.py:7` | docstring: "… the **clinical** `record_presence` uses — the engine never names it." | passive — docstring prose |

None hide clinical data. The all-needle multi-match on the two ontology notes is precisely because the note *enumerates the excluded vocabulary*.

### Also reproduced (driver A4, A3, A6):

- **A4 fail-closed:** `_pack_root('healthcare')` and `pack_ontology_path('healthcare')` (env unset, undiscoverable) both raise `FileNotFoundError("pack 'healthcare' not found via entry points, LITHRIM_BENCH_PACKS_DIR, or …/packs")`; an absent id likewise. **No silent fallback** to `_core`/in-repo. `test_a4` PASSED.
- **A3 behavior-identical:** A1 binds the same 19 codes / 8 owners / `[risk,policy,faithfulness]` roster from the external pack; the dev-mode consensus suites (`test_consensus`/`test_trio_dspy`/`test_judges_dspy`/`test_pack_layer3`) are green under discovery (A6(a) run).
- **A6(a) dev — 0-new vs parent:** dev suite (`LITHRIM_BENCH_PACK=healthcare` + `LITHRIM_BENCH_PACKS_DIR=<sibling>`) = **3 failed / 592 passed / 56 skipped**. Failures = {`test_byoc_provider::test_build_trio_no_models_is_all_azure_back_compat`, 2× `test_observation_pipeline`}. The parent `af25065` full suite = **4 failed** {byoc, `test_uap3_grade::test_no_assignment…`, 2× observation}. **HEAD failures ⊊ parent failures → 0 new** (HEAD has one fewer). Verified the `byoc` failure is **identical at af25065** (`judges_dspy.py:246: ValueError`, caused by **0** `AZURE_OPENAI_*` vars in the critic env — the documented "executor env over-reports the green bar (Azure vars)" caveat). The 2 `observation_pipeline` failures **pass in isolation** (the documented S-BS-96 full-suite import-ordering flake).
- **A6(b) bare-CE:** env unset → clinical tests SKIP (164 skipped via the root-`conftest.py` RELOCATED/NEEDS_PACK demarcation); `test_standalone_ce` + `test_neutral_default` = **11 passed** with healthcare absent (see Finding 2 re: the offline-key dependency). Core is standalone domain-agnostic.

---

## 3. Out-of-scope intrusion

`git diff af25065 HEAD --stat` (93 files, +888/−4993) maps cleanly to D1–D5:

- **D1** seam: `lithrim_bench/harness/pack.py` (+104).
- **D2** relocation (`git rm`): `packs/healthcare/**`, `examples/*.jsonl` (11 corpora), 7 clinical seeds under `data/config/agents` + `data/config/judge_sets/dogfood_v1.json`. All deletions; the content is now in the sibling repo (`0d61175`, `fca2147`).
- **D3a** fixtures: 4 in-repo packs (`_core`, `_plugin_fixture`, `_tiers_fixture`, `_nondeployable_fixture`, `story_audit`, `support_ticket_qa`) get own `council_roles/*.txt`; `ws0_default.json` genericized to a blank slate.
- **D3b** demarcation: new root `conftest.py`; `tests/conftest.py` + `runtime/council/tests/conftest.py` conditional-pin; `tests/_seam_freeze.py` seam-resolves the 2 clinical guards.
- **D4** proof: `tests/test_pack_dist.py` (+226).
- **D5** docs: `README.md`, `CLAUDE.md`, `SPEC_PLUGIN_ARCHITECTURE.md`.

The session log records 4 plan-review deviations, all APPROVED-AT-PLAN or APPROVED-MID-CYCLE (the CITATION-DRIFT "two fixtures → four", the mandatory `ws0_default` genericization, and the A2-sweep-caught `dogfood_v1` relocation). No drive-by refactors, no dependency bumps, no formatting passes. **No intrusion.** (The session-log byte-count typo on `_apply_consensus` is cosmetic — the hash matches; noted in §2 Behavior 3.)

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the canonical dev-suite invocation (import-ordering hazard) — `OPEN-QUESTION`

- **Driver A6(a) wording:** "dev: `LITHRIM_BENCH_PACKS_DIR=<abs sibling> python -m pytest -q`."
- **What I observed:** that **literal** invocation (PACKS_DIR set, `LITHRIM_BENCH_PACK` *un*set) produced **12 `PackConsistencyError` collection errors** in a fresh worktree — "pack 'healthcare' declares taxonomy codes not in the frozen council `KNOWN_TAXONOMY_CODES` [the 19]". Root cause: `KNOWN_TAXONOMY_CODES` binds at council import from the active pack; with only `PACKS_DIR` set, the active pack is the `_core` default until `tests/conftest.py:25-29` `setdefault`-pins healthcare, and the pin races the council import. Adding `LITHRIM_BENCH_PACK=healthcare` (or pip-installing the pack via its entry point — the executor's method, per the `lithrim_pack_healthcare.egg-info`) resolves it cleanly (**592 passed**).
- **Why it does NOT block:** this is a test-runbook nuance, not a product defect — the product grade path (entry-point discovery, or an explicit pin) works, and the `PackConsistencyError` is the consistency gate behaving **correctly** (refusing to validate healthcare codes against a `_core`-bound `KNOWN` set is fail-closed, not silent mis-grade). All HARD-GATE gates reproduce with the correct invocation.
- **Question for spec author:** lock the canonical dev/CI invocation in the CE-release README / PACK-DIST-2 as either `pip install -e ../lithrim-pack-healthcare` **or** `LITHRIM_BENCH_PACKS_DIR=… LITHRIM_BENCH_PACK=healthcare pytest` (not PACKS_DIR alone).
- **Recommended resolution:** accept; document the invocation. Optionally make `tests/conftest.py` resilient to the ordering (pin before any council import).

### Ambiguity 2: standalone proofs depend on the council conftest's offline key — `NON-BLOCKING`

- **Spec assertion:** `SPEC_STANDALONE_CORE_VALIDATION` §3.2 / §5 — the standalone E2E grades "at `$0` via injected predictors."
- **What I observed:** run as a narrow file subset (without the council subtree conftest, and with no real creds), `tests/test_standalone_ce.py`'s module-scoped `grade_out` fixture **errors** on `openai.OpenAIError: Missing credentials` — `ComplianceCouncil.__init__` (`compliance_council.py:448`) eagerly builds an OpenAI client before the `$0` predictors take over. In the full suite (and dev) the proofs are **green** because `lithrim_bench/runtime/council/tests/conftest.py:16` `setdefault("OPENAI_API_KEY","test-offline-key")` leaks into `os.environ` and the subprocess inherits it. Confirmed: with a dummy `OPENAI_API_KEY`, the standalone subset is **11 passed**.
- **Why it does NOT block:** pre-existing CE-STANDALONE-1 test design (the eager client predates PACK-DIST-1; same behavior at `af25065`), out of this cycle's scope, and green in the measured (full-suite) bar.
- **Recommended resolution:** in PACK-DIST-2 (the clean clinical-test MOVE), have the standalone proofs set their own dummy key for hermeticity rather than depending on the council conftest's leak.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 1 | 1 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions

No BLOCKING findings. NON-BLOCKING / OPEN-QUESTION dispositions:

1. **Finding (OPEN-QUESTION):** the documented `LITHRIM_BENCH_PACKS_DIR=<sibling> pytest` dev invocation (without the `LITHRIM_BENCH_PACK` pin / pip-install) hits a `PackConsistencyError` import-ordering hazard.
   **Proposed disposition:** lock the canonical invocation in the CE-release README + PACK-DIST-2; optionally harden `tests/conftest.py`. Log as a seam if not folded into PACK-DIST-2.
2. **Finding (NON-BLOCKING):** `test_standalone_ce` depends on the council conftest's offline-key leak for its grade subprocess.
   **Proposed disposition:** make the standalone proofs self-supply a dummy key in PACK-DIST-2 (the clinical-test MOVE).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (`SPEC_STANDALONE_CORE_VALIDATION`, `SPEC_PLUGIN_ARCHITECTURE` refs) + driver before the executor's session log
- [x] Reconstructed the diff via `git diff`/`git show`/`git log` against commits, in a fresh worktree at `3501639`
- [x] Each finding cites spec/driver and implementation file:line
- [x] Did NOT edit any code, spec, or driver (only wrote this critique + a transient `/tmp` symlink and a `/tmp/pdist-parent` worktree, both removed)
- [x] Did NOT confer with monitor or executor; read the session log LAST, only to cross-check (the only contradiction — the `_apply_consensus` byte-count — is cosmetic; the hash matches)

---

## Appendix: commits audited

```
3501639 chore(devloop): session log — PACK-DIST-1
4573088 docs(pack-dist): external-pack topology + the CE-release README (D5)
5a66768 test(pack-dist): the CE-clean proof + external-load + fail-closed + moat parity (D4)
2d32477 chore(pack): relocate the dogfood_v1 clinical judge-set out of CE (D2 follow / A2 sweep catch)
484d025 chore(pack): relocate healthcare + clinical corpora/seeds out of the CE repo (D2)
aeb641f test(pack): skip-when-absent demarcation + seam-resolve the clinical seam guards (D3b)
dfefa60 refactor(fixtures): self-contained CE fixture/demo packs; ws0_default → neutral blank slate (D3a)
9168670 feat(pack): external pack discovery — entry points + LITHRIM_BENCH_PACKS_DIR + pack-root-relative refs (D1)
--- pack repo (../lithrim-pack-healthcare) ---
fca2147 chore(pack): add the dogfood_v1 clinical judge-set (relocated from CE, PACK-DIST-1)
0d61175 chore(pack): initial healthcare domain pack — relocated out of the OSS core (PACK-DIST-1)
```

## Appendix: reproduction ledger

```
A2 headline (bare worktree, env unset):  test_pack_dist.py → 9 passed, 1 skipped (A1 skips, sibling not at /tmp/../)
A2 independent sweep:                     32 data-surface files tracked; exactly 4 needle hits == _PASSIVE_CARVE_OUT
A1 one-liner (PACKS_DIR=abs sibling):     root=/Users/…/lithrim-pack-healthcare/healthcare; codes=19 owners=8 roster=[risk,policy,faithfulness]; in-repo packs/healthcare absent=True
A1 test (via /tmp symlink):               test_a1_council_binds_from_external_pack PASSED
A4 fail-closed:                           _pack_root / pack_ontology_path('healthcare', undiscoverable) → FileNotFoundError (no silent fallback)
A5 moat (AST = test method):              _apply_consensus d1b7956e (28761B) acc4973==HEAD; extract_verdict_confidence ed867bce (1700B) acc4973==HEAD
A5 scope:                                 af25065..HEAD touches 0 lines of compliance_council.py/signals.py/withstands.py; acc4973..HEAD = authorized carve-outs only
A6(a) dev (PACK pinned + PACKS_DIR):      3 failed / 592 passed / 56 skipped — all 3 pre-existing (byoc=Azure-creds [identical @ af25065]; 2× observation=S-BS-96 [pass in isolation])
A6(a) parent af25065 full suite:          4 failed — HEAD failures ⊊ parent → 0-new
A6(b) bare-CE (env unset):                clinical SKIP (164); standalone_ce + neutral_default = 11 passed (with offline OPENAI_API_KEY)
```
