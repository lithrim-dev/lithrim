---
name: lithrim-research-rerun
description: Reproduce the Lithrim judge-vs-floor research matrix from the public-cut Docker images. Stand up the stack, connect providers, wire the SNOMED floor, then author and grade the arm matrix (single judge, single + CoT, frontier, OpenBio, mixed ensemble, Composo) over the deterministic grounding floor, and score it. Extensible to new arms and new defect families with no engine changes.
---

# Research rerun: the judge-vs-floor matrix from the public cut

This reproduces the paper's experiment (Zenodo 10.5281/zenodo.21270268; OSF 10.17605/OSF.IO/2ZU4H)
from the prebuilt images, structured so new arms and new defect families are one-line additions.
The full grounded plan is `docs/reproduction/RUN_PLAN_PUBLIC_CUT.md`; read it if a step is unclear.
The synthetic-research framing for any Fable-5 reasoning is `docs/reproduction/FABLE5_RESEARCH_CONTEXT_PREAMBLE.md`.

Everything here is skills + config over the already-shipping REST API and the proven `repro/`
scripts. The only part that needs engine code is the Composo per-flag judge (Stage 4.5 of the plan);
the other five arms are config-only.

## Guardrails (do not skip)

- **Never autostart services beyond the explicit Stage 1 step.** If the stack is not up, do Stage 1;
  do not silently restart it later.
- **Paid grades are the user's spend.** Let the USER authorize each cohort. Never grade without a go.
- **One stack, strictly sequential.** `run-eval` grades the GLOBAL active workspace; a mid-cohort
  workspace switch contaminates the target. Finish one arm's cohort before touching another.
- **Token sentinel before every paid cohort.** k=1 arms keep the DSPy cache on, so a re-grade can
  replay for `cost_tokens = 0`. Clear the cache and confirm `cost_tokens > 0` on one case first.
- **Never echo a model key into chat or logs.** Keys live in the gitignored `.provider_env` volume.

## 1. Stack up (public cut, prebuilt images)

Use the `lithrim-docker-up` skill (no-clone prebuilt path). Verify:

```bash
for i in $(seq 1 40); do curl -sf http://localhost:8787/health && break; sleep 3; done
curl -sf -o /dev/null http://localhost:5180            # UI
```

Pin a release tag in `.env` (`LITHRIM_BFF_IMAGE`, `LITHRIM_UI_IMAGE`) and record the image digests
in the run log; `:latest` drift is a reproducibility leak. The `repro/` scripts, corpus, ontologies,
and this skill come from the repo clone the researcher works in; the images serve the BFF/UI/mapper.

## 2. Connect providers (BYOK, once each)

The matrix needs four providers. Prefer the user pasting keys in the UI: session menu then
**Connect AI**, pick the provider, paste, save (the key stays in the volume). Then confirm each
plane with `curl -sf http://localhost:8787/v1/provider/status`.

- `azure` (frontier gpt-5.x + the ensemble gpt members): needs endpoint + api_version + key.
- `anthropic` (ensemble opus + sonnet): key.
- `openai_compatible` (OpenBio + ensemble Llama/Mistral via Featherless): api_base + key.
- `composo` (only for the Composo arm, which is blocked until Stage 4.5): key.

## 3. Wire the SNOMED floor (recommended: do it now)

Use the `lithrim-snomed-setup` skill. It is BYO and licensed: the user supplies a SNOMED release
they are entitled to; you never fetch the terminology. Without it the run still completes, but
terminology checks resolve to DEFER (surfaced as `judge_only` in provenance), so the code-grounded
floor never confirms or overrides. With it, every arm grades over the full is-a floor. Verify one
`subsumed_by` lookup before proceeding.

## 4. Author and bind the arms ($0)

The matrix is declared in `repro/arms.json`; `repro/run_arms.py` authors one workspace per
arm x ontology-arm by reusing `setup_streams.setup_workspace` (identical floor + corpus) and applies
the per-role binds. This is additive; the deposited 5-stream scripts are untouched.

Dry-run first (zero HTTP), then author for real. Point the corpus at the scrubbed v2 set:

The matrix has two classes: **registered** (the 5 published study streams: `arm-single`,
`arm-ensemble`, `arm-specialist-same`, `arm-specialist-mixed`, `arm-scalar-reward` — the faithful
reproduction) and **exploratory** (unregistered cells: frontier, CoT, OpenBio, per-flag Composo).
Filter with `--class registered|exploratory`.

```bash
export LITHRIM_REPRO_BASE=http://localhost:8787
export LITHRIM_REPRO_CORPUS_DIR=repro/corpus_v2
export LITHRIM_REPRO_OUT=./out/public_cut_run
python3 repro/run_arms.py --dry-run                        # inspect the full plan
python3 repro/run_arms.py --class registered              # author + bind the 5 study streams ($0)
python3 repro/run_arms.py --class exploratory             # (optional) author + bind the exploratory cells ($0)
```

Verify: each arm prints `roster pinned`, `readiness ok=True`, and every bind returns `[200]`. A
bind that returns `[400]`/`[422]` means that provider is not connected yet (Stage 2). Nine arms are
authored; `arm-composo-judge` is skipped (blocked, see Stage 4.5). Reproducing the published study
is exactly the five `--class registered` arms; the rest are clearly-labeled extensions.

## 4.5 Composo as a per-flag judge (the one code spike, optional)

`arm-composo-judge` is blocked because the shipped `provider: composo` is a reward wire
(`reward_lm.py`: one criterion to `platform.composo.ai/api/v1/evals/reward`, findings empty), which
is the reward baseline, not a per-flag voter. To run it as a judge, build the adapter in the
UNFROZEN wiring layer only (never `_apply_consensus`), tests-first: verify Composo's live API, then
either iterate the lens codes over the reward endpoint or bind Composo's native criteria API, and
map the result to per-flag findings. Flip `arm-composo-judge` `status` to `ready` in `arms.json`
once its acceptance test is green. Full scoping: `docs/reproduction/RUN_PLAN_PUBLIC_CUT.md` Stage 4.5.

## 5. Grade one arm (paid, user-authorized, sentinel-gated)

For each ready arm, in order. `run_arms.py --grade` refuses to run without `--arm`, so one command
can never fire the whole matrix past a single authorization. One arm grades its two ontology
workspaces (armT and armR); add `--ontology armT` to run a single cohort.

First the token sentinel. The cache clear plus BFF restart is the one place this flow restarts the
stack, so do it only with the user's explicit OK (an unprompted restart is exactly what the
guardrails and CLAUDE.md forbid):

```bash
# only with the user's OK (this restarts the running BFF):
docker compose exec bff rm -rf /root/.dspy_cache && docker compose restart bff
# then re-select the arm workspace, grade ONE case, confirm cost_tokens > 0 in GET /v1/runs
```

Then the cohort, for one arm the user has authorized. `--grade` grades the workspace(s) authored
in Stage 4 and does NOT re-author (no re-ingest), so run Stage 4 first:

```bash
python3 repro/run_arms.py --arm arm-single-frontier-plain --grade            # armT + armR
# single cohort: python3 repro/run_arms.py --arm arm-single-frontier-plain --ontology armT --grade
```

Verify: `GET /v1/runs?agent=ws0_default&limit=5` shows `cost_tokens > 0`, `grade_path=in_process`,
and `model_bindings` naming the model you bound. Do not move to the next arm until this one's cohort
is done. Recommended: set `LITHRIM_BENCH_REQUIRE_DATED_MODELS=1` and bind dated snapshots where the
provider offers them, so `model_bindings` refuses floating aliases (the F11 drift lesson).

## 6. Score ($0 replay)

```bash
python3 repro/run_arms.py --score                      # per-arm $0 scorecard
```

Each scorecard carries exact-flag precision/recall, per-code and per-judge tallies, and the floor
block: `gold_defect_clears` (must be 0, the floor never clears a gold defect) and pre-floor vs
post-floor verdict accuracy. For the full four-block consolidation (floor-flip ledger, reliability,
K-sweep) run the existing `repro/consolidate.py` pattern against the arm workspaces, or read the
endpoints directly (`GET /v1/runs`, `GET /v1/reliability/{agent}`).

## 7. Extend (new arm or new defect family, no engine change)

- **New arm:** add an entry to `repro/arms.json` (unique role names, binds, ontology_arms). Re-run
  Stage 4. That is the whole change.
- **New defect family** (the ranked siblings in `docs/reproduction/UPCODE_SIBLING_DEFECT_FAMILIES.md`;
  miscoding first, its floor oracle already ships): author by-construction cases (each positive with
  a full `injection_recipe`; clean negatives with `injection_recipe: null` and empty flags), lint
  labels-true-by-construction, drop the `.jsonl` into a corpus dir, point `LITHRIM_REPRO_CORPUS_DIR`
  at it, and re-run. A new floor oracle (severity ordinal table, status extractor) is a `kind: tool`
  manifest, still zero engine edits.

## References

- `docs/reproduction/RUN_PLAN_PUBLIC_CUT.md` — the full grounded plan and locked config.
- `docs/reproduction/UPCODE_SIBLING_DEFECT_FAMILIES.md` — ranked next defect families.
- The thesis preamble (maintainer-internal, not in the public clone) — what the research is and why.
- `REPRODUCING.md` — the deposited 5-stream reproduction (the study of record).
