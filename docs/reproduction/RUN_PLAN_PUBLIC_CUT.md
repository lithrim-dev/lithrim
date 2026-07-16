# Clean run plan: public-cut Docker, full arm matrix, SNOMED floor, extensible

Prepared 2026-07-15. Goal: reproduce the paper's experiment matrix (single judge, single + CoT,
frontier, OpenBio, Composo, mixed ensemble) over the deterministic grounding floor, this time
from the prebuilt public-cut Docker images, with Hermes SNOMED wired where possible, structured
so new defect families and cases can be added later without touching the engine.

Grounded against: `deploy/docker-compose.yml`, `REPRODUCING.md`, `repro/{setup_streams,cohort_runner,consolidate}.py`,
`repro/role_binds.json`, `repro/ontology_arm{T,R}.json`, `apps/bff/app.py`,
`lithrim_bench/harness/grounding.py`, `docs/SNOMED_SETUP.md`, `.claude/skills/lithrim-snomed-setup/SKILL.md`.

Standing rules for the operator: never autostart services silently (this plan is the go-ahead);
no paid grade until the token sentinel passes; grades are strictly sequential on one stack
(the active-workspace pointer is global, so a mid-cohort switch contaminates the target).

---

## 0. Topology and the one hazard that dictates the whole run

The public cut is a single stack with **global** active-workspace state. `POST /v1/run-eval`
has no workspace parameter; it grades whichever workspace `POST /v1/workspace` last selected
(`app.py:1241`, `workspace.py:247-265`). Therefore:

- One arm at a time. Setup arm -> bind -> grade the full cohort -> only then move to the next arm.
- No second client touching the same BFF during a cohort.
- The study ran an isolated second stack on :18787 for exactly this reason. For this clean run,
  default to **one public-cut stack, strictly sequential**. If throughput matters later, stand a
  second stack on a different host port and split arms across the two (option B in Stage 6).

Services (all from `deploy/docker-compose.yml`): BFF `:8787`, UI `:5180`, JUTE mapper `:3031`.
No DB service, no Hermes service (both are in-process / BYO). State lives in named volumes
`lithrim_out` (CE state + BYOK keys + pack overlay) and `jute_data`.

---

## Stage 1 — Stand up the public cut from images

No clone. In an empty working dir:

```
mkdir lithrim-run && cd lithrim-run
curl -fsSLO https://raw.githubusercontent.com/lithrim-dev/lithrim/main/deploy/docker-compose.yml
# pin a release instead of :latest for a reproducible run:
echo 'LITHRIM_BFF_IMAGE=ghcr.io/lithrim-dev/lithrim-bff:v0.1.0'  >  .env
echo 'LITHRIM_UI_IMAGE=ghcr.io/lithrim-dev/lithrim-ui:v0.1.0'    >> .env
docker compose up -d
```

Health (BFF start_period ~40s):

```
for i in $(seq 1 40); do curl -sf http://localhost:8787/health && break; sleep 3; done
curl -sf -o /dev/null http://localhost:5180                 # UI
curl -sf http://localhost:3031/jute-dsl-spec.json           # JUTE (optional; core-only: up bff ui)
```

Reset to clean seed at any point: `docker compose down -v` (wipes both volumes). Pin the exact
image digests you ran and record them in the run log; `:latest` drift is a reproducibility leak.

Bundled: neutral `_core` pack, auto-seeded on first `up`. Not bundled (BYO, all gitignored):
the SNOMED release + `hermes.jar`, the external healthcare pack, model API keys.

---

## Stage 2 — Connect providers (BYOK, once per provider)

Keys are entered once per provider through the UI Connect-AI panel or `POST /v1/provider/config`
(`app.py:6724`), read-only probed, then written only to the gitignored `.provider_env` inside the
`lithrim_out` volume. Keys never enter a manifest, the DB, git, logs, or a response body. A later
role bind reuses the stored key (no key in the bind body).

Providers needed for the full matrix (bind targets in Stage 4):

| provider value | plane | used by arms | credential |
|---|---|---|---|
| `azure` | Azure OpenAI (frontier gpt-4.1 / gpt-5.x) | frontier, ensemble | endpoint + api_version + key |
| `anthropic` | Claude (opus-4-8 / sonnet-5) | ensemble | key (per-role-only provider) |
| `openai_compatible` | Featherless (OpenBio, Llama, Mistral) | OpenBio, ensemble | api_base + key |
| `composo` | Composo reward model (scalar reward) | Composo arm | key |

Verify each connected plane with `GET /v1/provider/status` (reports connected planes, never the key).

---

## Stage 3 — Wire the SNOMED / Hermes floor (where possible)

Licensing gate first: obtain a SNOMED CT release you are entitled to (MLDS / UMLS-NLM / NHS TRUD).
The release is never redistributed or baked into any image. If you cannot supply it, skip this
stage: every terminology contract degrades to DEFER and the run still completes, just without the
code-grounded confirm/override on the diagnosis families (surfaced in provenance as `judge_only`,
not hidden). Follow `.claude/skills/lithrim-snomed-setup/SKILL.md`:

1. Fetch `hermes.jar` (wardle/hermes latest; Java 21 to match the container JRE).
2. Build the index host-side: `java -jar hermes.jar --db snomed.db import <release>/ index compact`.
3. Place `hermes.jar`, `snomed.db`, `logback-stderr.xml` in `./snomed/` next to the compose file
   (mounted read-only at `/snomed`); `docker compose up -d`; confirm `docker compose exec bff ls /snomed`.
4. The `hermes_snomed` tool manifest is authored per workspace by `setup_streams.py`
   (`HERMES_MANIFEST`, `setup_streams.py:52-63`) so no manual tool POST is needed for the repro arms;
   for an ad-hoc workspace, `POST /v1/tools` the same manifest.
5. Verify one subsumption: `POST /v1/tools/test` then a real `subsumed_by` lookup (MI `22298006`
   is-a disease `64572001` -> expect `subsumedBy: true`).

The floor is stdio-MCP (a JVM spawned per check, ~1-2s). Fine for these 44-case cohorts; if you
scale to thousands, run Hermes as a long-lived HTTP MCP service instead. The CE battery implements
checks 1-3 + 7 (validity, mislabel, category/semantic-tag, is-a direction). There is no ICD refset
or ECL check in CE. The is-a direction check clears only `record is-a note`; a note that is a
strict descendant of the record (the upcode direction) is never cleared. That asymmetry is the floor.

---

## Stage 4 — The arm matrix

Each arm = one workspace = one judge roster over the identical cloned floor ontology. Authoring
is `repro/setup_streams.py` ($0); binding is `POST /v1/roles/bind` from a declarative map ($0);
grading is `repro/cohort_runner.py` (paid); scoring is `repro/consolidate.py` ($0).

Two orthogonal dials sit outside the per-arm config:

- **Ontology arm** (`LITHRIM_REPRO_ONTOLOGY`): `ontology_armT.json` (transcript-only, default) vs
  `ontology_armR.json` (record-informed; the ONLY diff is `grading_context_fields: [patient_profile]`,
  which folds the record into the judge payload). Run the whole sequence once per arm.
- **Corpus** (`LITHRIM_REPRO_CORPUS_DIR` + `LITHRIM_REPRO_WS_SUFFIX`): `repro/corpus_v2` (scrubbed,
  44 = 22 upcode + 22 clean). Optional +10 physician via `LITHRIM_REPRO_PHYSICIAN_CASES` -> 54.

The matrix has two classes (filter with `run_arms.py --class registered|exploratory`).

**REGISTERED** — the five published study streams (the roster-structure comparison backing Zenodo;
models exactly as `role_binds.json` records them). This is the faithful reproduction.

| arm id | roster | model(s) | K / temp | lens | provider |
|---|---|---|---|---|---|
| `arm-single` | 1 generalist | gpt-4.1 | 8 / 1.0 | FULL | azure |
| `arm-ensemble` | 6 judges | gpt-4.1, gpt-5.4, opus-4-8, sonnet-5, Llama-4-Maverick, Mistral-Large-3 | 1 / 0.0 | FULL | azure + anthropic + openai_compatible |
| `arm-specialist-same` | 3 specialists (risk/policy/faith) | all gpt-4.1 | 1 / 0.0 | RISK/POLICY/FAITH | azure |
| `arm-specialist-mixed` | 3 specialists | risk→opus-4-8, policy→gpt-4.1, faith→gpt-5.4 | 1 / 0.0 | RISK/POLICY/FAITH | anthropic + azure |
| `arm-scalar-reward` | reward model | Composo reward (score→verdict, findings empty) | 1 / 0.0 | FULL | composo |

**EXPLORATORY** — unregistered post-study cells. Never quote as study results.

| arm id | roster | model(s) | K / temp | CoT | provider |
|---|---|---|---|---|---|
| `arm-single-frontier-plain` | 1 generalist | gpt-5.5 | 8 / 1.0 | no | azure |
| `arm-single-frontier-cot` | 1 generalist | gpt-5.5 | 8 / 1.0 | yes | azure |
| `arm-single-openbio-plain` | 1 generalist | OpenBioLLM-70B | 1 / 1.0 | no | openai_compatible |
| `arm-single-openbio-cot` | 1 generalist | OpenBioLLM-70B | 1 / 1.0 | yes | openai_compatible |
| `arm-composo-judge` | `composo_reviewer` | Composo (per-flag) | 1 / 0.0 | no | composo (adapter, Stage 4.5, **blocked**) |

Notes that matter for fidelity:

- **CoT lever.** Carried as prose. Two equivalent seams: append to the judge `role_prompt`
  (what `setup_streams.py` uses), or set the per-judge `criterion` field (appended at grade time,
  `authored_stage.py:229-231`). Use the `criterion` field for CoT so the base prompt stays
  byte-identical across the plain/CoT pair (cleaner control). Memory: CoT is a control-confirmed
  dead lever; keep these arms for completeness, do not expect movement.
- **OpenBio K=1 is forced**, not a choice: Featherless Premium caps concurrency at 4 units and
  n=8 = 32 units is rejected. K=1 is the only viable setting; note this asymmetry vs the frontier
  K=8 arm in the writeup (it is a confound, not a free variable).
- **Composo arm** is a per-flag judge surface (LOCKED decision), which the shipped wire does NOT
  do: `provider: composo` (`reward_lm.py`) POSTs one criterion to `platform.composo.ai/api/v1/evals/reward`
  and returns `{score, explanation}` thresholded to a verdict with findings deliberately EMPTY (a
  reward model types no codes). Running it as a per-flag voter needs the adapter in Stage 4.5. This
  is the one arm that requires code before it can grade; the other five are config only.
- **Dated model ids.** Set `LITHRIM_BENCH_REQUIRE_DATED_MODELS=1` and bind dated snapshots
  (e.g. `gpt-5.5-2026-04-23`) so `model_bindings` provenance refuses floating aliases. The F11
  scalar-vendor drift episode is why this is not optional for a publishable run.

The bind map is `repro/role_binds.json` (`stream_role_binds`). Refine it into an arm-keyed
`repro/arms.json` (see Stage 7) so the whole matrix is declarative and a driver can loop it.

---

## Stage 4.5 — Composo-as-judge adapter (the one pre-req spike)

The `composo-judge` arm cannot run until Composo emits per-flag votes. The shipped `RewardModelLM`
is a single-criterion reward -> verdict judge with empty findings; that is the reward baseline, not
a typing judge. The spike, all in the UNFROZEN wiring layer (`sampling.py` / `reward_lm.py`), never
touching `_apply_consensus` or the consensus/withstands seam:

1. **Verify Composo's live API surface first** (read-only). Confirm whether `platform.composo.ai`
   exposes a per-criterion eval that returns structured pass/fail + reasoning, or only the reward
   endpoint already wired (`/api/v1/evals/reward`). This decides between options A and B and must
   precede any code.
2. **Option A (multi-criterion over the reward endpoint, no new Composo API):** iterate the arm's
   lens codes; for each code send its definition as `evaluation_criteria` to the existing
   `RewardModelLM.evaluate`; threshold each score (`DEFAULT_THRESHOLD` 0.5) into a per-flag finding;
   assemble the findings into one judge vote. Cost = N reward calls per case (N = lens size). This
   deliberately lifts the reward model's empty-findings honesty invariant for THIS role only, so it
   must be a distinct, clearly-named mode (`composo_reviewer`), not a silent change to the baseline
   wire.
3. **Option B (Composo native criteria API, if step 1 finds one):** add a sibling builder to
   `reward_lm.py` that calls the criteria endpoint and maps its structured output to findings. Same
   role, cleaner shape, one call per criterion or per case depending on their API.
4. **Guardrails:** tests-first (RED acceptance test that a Composo vote carries typed findings and
   declines on transport failure), $0 offline transport stub for tests, live-gate one real Composo
   call with a token/response sentinel before the paid cohort, keep the adapter out of the frozen
   seam, secrets stay in `.provider_env`.

Sequencing choice: run the registered study arms and the other exploratory cells first (they need
no code), land the Composo adapter in parallel, and flip `arm-composo-judge` from `blocked` to
`ready` once its acceptance test is green. This keeps the matrix moving without blocking on the
spike. Note the reward-model baseline (`arm-scalar-reward`) is a separate, already-runnable arm and
does not depend on this adapter.

## Stage 5 — Grade one arm (the inner loop, cache-hygiene gated)

For each arm, in order:

1. `python3 repro/setup_streams.py` with the arm's env (`LITHRIM_REPRO_ONTOLOGY`,
   `LITHRIM_REPRO_CORPUS_DIR`, `LITHRIM_REPRO_WS_SUFFIX`, `LITHRIM_REPRO_BASE=http://localhost:8787`).
   `--dry-run` first to print the plan with zero HTTP calls. Authors judges (empty model), tool,
   clones the floor ontology unmodified, ingests the corpus, pins the roster.
2. Bind roles: `POST /v1/roles/bind` per judge from the arm's bind entry (provider + dated model +
   endpoint/api_version; no key in body).
3. **Cache hygiene + token sentinel (blocking gate before any paid cohort).** k=1 arms keep the
   DSPy cache on, so a re-grade can replay cached completions with `cost_tokens = 0`. Clear the disk
   cache and restart, then grade ONE byte-unchanged case and assert `cost_tokens > 0` before the
   cohort:
   ```
   docker compose exec bff rm -rf /root/.dspy_cache && docker compose restart bff
   # re-select the arm workspace, grade one case, confirm cost_tokens > 0 in GET /v1/runs
   ```
   k>1 arms force `config={"n":k,"cache":False}` (`sampling.py:249-257`) so they re-sample anyway,
   but run the sentinel regardless.
4. `python3 repro/cohort_runner.py` (env as above). Grades every case `live=True, in_process=True`
   sequentially. Writes `progress.log`, `cohort_summary.json`, `COHORT_DONE`. Do not switch the
   active workspace until `COHORT_DONE` exists.
5. Spot-check `GET /v1/runs?agent=ws0_default&limit=5`: `cost_tokens > 0`, `model_bindings` shows the
   dated model you bound, `grade_path == "in_process"`.

Repeat Stage 5 for every arm, and re-run the whole set with `LITHRIM_REPRO_ONTOLOGY=ontology_armR.json`
+ a fresh `-R` suffix for the record-informed arm.

---

## Stage 6 — Score and consolidate ($0)

`python3 repro/consolidate.py` per arm (or once with the arm suffix list) writes
`$LITHRIM_REPRO_OUT/consolidated.json` with four blocks per arm:

- **Scorecard** (`$0` replay of persisted provenance): exact-flag `precision`/`recall`, per-code
  `by_flag`, per-reviewer `by_judge`, `majority` tally, `judge_matrix`, and the floor block:
  `cleared/enforced/inconclusive`, `gold_defect_clears` (must be 0 — the floor never clears a gold
  defect), and `verdict_accuracy_pre_floor` vs `verdict_accuracy_post_floor`.
- **Floor-flip ledger** (latest LIVE run per case): `council_block_floor_cleared_flips` (clean-gen
  cases where council BLOCK -> floor PASS, the headline flip) and `upcode_grounded_block`.
- **Reliability**: Fleiss/Cohen kappa, 10-bin ECE + Brier, effective independent votes, floor
  selective-prediction, each with an `insufficient` honesty flag.
- **K-sweep** (single-judge arms): flip-rate / majority-convergence / variance with Wilson CIs over
  K=1..8.

Diff each arm's scorecard against the deposited `data/consolidated_arm{T,R}.json` to confirm the
clean-run reproduces the study within noise. The upcode notice/name/type metrics are derived from
`by_flag` + the typing artifact (`data/typing_report_*.json`), not the generic scorecard.

Option B (throughput, later): a second public-cut stack on `:8797`, arms split across the two,
each stack strictly sequential internally. Never share a stack between two concurrent cohorts.

---

## Stage 7 — Extensibility (add families and cases without engine edits)

The seams already support extension; the SCRUB-1 commits parameterized corpus-dir + workspace-suffix
exactly for this.

Add a new defect family (the ranked siblings: miscoding first, then severity, then status, per
`UPCODE_SIBLING_DEFECT_FAMILIES.md`):

1. Author by-construction cases: each positive carries an `injection_recipe` (defect_type,
   mutated_projection, mutated_field_or_span, pre_value, post_value) that fully justifies the flag;
   clean negatives carry `injection_recipe: null` and `expected_safety_flags: []`.
2. Lint labels-true-by-construction: every flag code in the active taxonomy, every flag owned by a
   running judge. A case that cannot prove its label does not ship.
3. Drop the new `*.jsonl` into a corpus dir; point `LITHRIM_REPRO_CORPUS_DIR` at it, bump
   `expected_cases`, pick a fresh `LITHRIM_REPRO_WS_SUFFIX`. No engine edit.
4. Floor coverage: miscoding reuses the shipped `snomed_battery` (checks 2/3/7) with no new oracle;
   severity and status need new oracles (ordinal staging table; FHIR clinicalStatus + a live-gated
   ConText extractor) authored as `kind: tool` manifests, still zero engine edits.

Refactor for repeatability (the "more structured" ask) — IMPLEMENTED 2026-07-16:
`repro/arms.json` (declarative matrix) + `repro/run_arms.py` (thin driver reusing
`setup_streams.setup_workspace` + `cohort_runner.run_stream`; modes `--dry-run`/`--arm`/`--ontology`/
`--grade`/`--score`) + `.claude/skills/lithrim-research-rerun/SKILL.md` (the orchestration skill,
auto-discovered from a repo clone = packaging path a). Additive: the deposited 5-stream scripts are
untouched and stay byte-reproducible. Adversarially verified (4-lens workflow); fixes applied for a
grade-time mkdir crash, an ensemble role-name collision with the deposited study (renamed to
`ensmix_*`), an unscoped-`--grade` guardrail hole (now refused without `--arm`), and a silent BFF
restart. A new arm is an `arms.json` entry; a new defect family is a new corpus jsonl.

---

## Locked run configuration (2026-07-16)

1. **Matrix** = the faithful superset. REGISTERED = the 5 published study streams (`arm-single`,
   `arm-ensemble`, `arm-specialist-same`, `arm-specialist-mixed`, `arm-scalar-reward`), with the
   exact study models. EXPLORATORY = 4 ready unregistered cells (frontier, CoT, OpenBio) plus
   `arm-composo-judge` (blocked pending the Stage 4.5 adapter). `run_arms.py --class registered`
   runs exactly the study.
2. **Composo** appears twice, distinct: `arm-scalar-reward` is the study's reward-model baseline
   (the shipped `provider: composo` wire, runnable now); `arm-composo-judge` is a per-flag judge
   surface that needs the Stage 4.5 adapter (blocked).
3. **Isolation** = one public-cut stack, strictly sequential. Zero contamination; slower wall-clock.
4. **Scope** = both ontology arms (armT + armR). Registered = 5 arms x 2 = 10 cohorts (~440 grades);
   the full ready set = 9 arms x 2 = 18 cohorts (~792 grades). Plus the 10 physician cases where
   applicable, plus $0 replay scoring.
5. **SNOMED** = wire Hermes now (release available locally). Full code-grounded floor from arm one.

Execution order (when the owner gives the go): Stage 1 stack -> Stage 2 providers -> Stage 3 Hermes
-> Stage 4 `run_arms.py --class registered` (author + bind the study, $0) -> Stage 5/6 grade each
registered arm on the owner's go, then score -> optionally `--class exploratory` for the extensions,
with the Stage 4.5 Composo adapter landing tests-first before `arm-composo-judge` flips to ready.

Not started yet: this is the plan only. No service is up, no grade has run. Awaiting the go to begin
Stage 1, and a separate go before any paid cohort (Stage 5).
