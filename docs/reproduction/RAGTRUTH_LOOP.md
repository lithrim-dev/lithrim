# Reproducing the RAGTruth loop from the published images

The loop is load, configure, grade, calibrate, re-grade, export, with the scorecard read in
both vocabularies (the pack's taxonomy codes and the dataset's own label terms). This page runs
it on a small cut of RAGTruth from the prebuilt Docker images, with one provider key. Nothing
here is RAGTruth-specific in the engine: the dataset enters through
`examples/ragtruth/adapter.py`, the reviewer through
`examples/ragtruth/judge.ragtruth_detector.json`, and the vocabulary through the importer
manifest `packs/_core/importers/ragtruth.json` (see [`../IMPORTERS.md`](../IMPORTERS.md)).
The same loop from the browser, with no terminal, is [`RAGTRUTH_LOOP_UI.md`](RAGTRUTH_LOOP_UI.md).

## 0. What you need

- Docker with Compose v2, and the stack from [`../DEPLOY.md`](../DEPLOY.md) up:
  `docker compose up` on the published `deploy/docker-compose.yml`.
- A provider key for the judge model (Azure OpenAI or OpenAI). Connect it in the UI (session
  menu, **Connect AI**), or set it in `.env` beside the compose file.
- The two RAGTruth dataset files (`response.jsonl`, `source_info.jsonl`; MIT, ParticleMedia/RAGTruth).
  `lithrim load` downloads them into the container's data dir when absent; if the container has no
  outbound network, copy them in first (`docker compose cp response.jsonl bff:/app/out/loop/data/`).

The CLI runs inside the BFF container, where the package, the examples, and the workspace out
dir all live:

```bash
docker compose exec bff lithrim --help
```

## 1. The $0 round first (no key)

The five tracked sample cases replay their committed judge baselines, the grounding checks run
live, and the round is scored against the human spans in both vocabularies:

```bash
docker compose exec bff lithrim replay --cases samples/ragtruth/cases.jsonl
```

From a clone, the same round is `make loop-demo`; CI runs it on every push. This proves the
scorer, the review states, and the vocabulary mapping before anything is spent.

## 2. Load a small cut

```bash
docker compose exec bff lithrim load --adapter examples/ragtruth/adapter.py --per-task 30
```

`--per-task 30` is 90 test-split cases (30 per task: news summaries, QA, data-to-text), one
model-balanced response per source at the corpus's own hallucination rate, plus a 90-case
calibration corpus cut from RAGTruth's train split (source-disjoint by construction). The cut
lands in `out/loop/slice_full.jsonl` and `out/loop/calib.jsonl` on the `lithrim_out` volume and
the test cases are ingested into the active workspace with their human labels.

## 3. Configure the reviewer

```bash
docker compose exec bff lithrim configure \
  --judge examples/ragtruth/judge.ragtruth_detector.json \
  --model azure/gpt-4.1-2025-04-14
```

This authors the `ragtruth_detector` judge (the paper's Appendix D detection prompt with a
two-code lens), pins its model, and sets the roster to that one judge. The model must be a
dated id or an attested deployment (`--model-version`, `--upgrade-policy`); a floating alias is
refused because it cannot anchor a before/after.

## 4. Grade, calibrate, re-grade (paid)

Every paid verb refuses without `--confirm-cost`. On gpt-4.1 the 90-case grade is roughly $1.5
at list price; a calibrate round (a bootstrap compile over the calibration rows plus two held-out
evaluations) is about $2. Set `J=examples/ragtruth/judge.ragtruth_detector.json` and
`M=azure/gpt-4.1-2025-04-14` for brevity:

```bash
docker compose exec bff lithrim grade     --judge $J --model $M --confirm-cost   # the baseline row
docker compose exec bff lithrim calibrate --judge $J --model $M --confirm-cost   # optimize + the gated pin
docker compose exec bff lithrim regrade   --judge $J --model $M --confirm-cost   # the optimized row
```

- `grade` runs as a background job on the BFF (progress lines print as cases finish); an
  interrupted run continues with `--resume-job <id>`. A grade that replayed anything from the
  judge cache is refused as a measurement, and every judge call that failed is reported next to
  the score, never hidden.
- `calibrate` trains only on `split: calibration` rows and pins the compiled demos into the
  workspace only if their held-out score is not below the pinned set's. A losing round says so
  and pins nothing (`--force-pin` overrides, recorded in the output). The UI's Optimize button
  goes through the same gate and shows pinned / not pinned.
- **How held-out is chosen.** The calibration corpus is RAGTruth's train split alone. A
  deterministic, source-disjoint `dev` slice, 30% of each task's sources ordered by the hash of
  the source id, is carved from it; the demos train on the rest and the pin gate scores on
  `dev`. The graded test cut is not in the corpus, so no gate decision reads a test label and
  the after round is the first time the tuned judge meets the test cut. Before 2026-09-10 the
  corpus held out on the test cut itself: in the 450-per-task pilot the gate compared two later
  rounds on those test rows (it refused the contrastive round, 0.68 against the pinned 0.76, and
  the miss-only round was compared there before a hand pin). No reported number changed, since
  the first round's pin had no score to compare against, but those were decisions on test labels.
- Each grade writes `out/loop/grade_<tag>.json` and `out/loop/score_<tag>.txt`.

## 5. Export and score

```bash
docker compose exec bff lithrim export --slice out/loop/slice_full.jsonl --split test \
  --out out/loop/export_test.jsonl
docker compose exec bff lithrim score --slice out/loop/slice_full.jsonl \
  --grade out/loop/grade_after.json
```

`export` writes one row per graded labeled case with the judge's codes and spans, the floor's
dispositions, the human codes and spans, the agreement, and the label-basis tier (floor-proved,
expert-confirmed, judge-only), in both vocabularies. Training formats (`--format paper|chat`) are
written only from the calibration split. `score` re-scores exactly the runs a grade file names.

## 6. Reading the scorecard

The table reports, per task and overall, response-level precision / recall / F1 of
"hallucinated" (verdict after the floor vs the human label "any span") and span-level P / R / F1
by character overlap; then per code, the taxonomy code with the dataset's terms in brackets, and
the verdict rule stated in both vocabularies. On the full 450-case test cut during the pilot
(2026-09), the detector with pinned demos scored 78.8 response F1 / 59.7 span F1 on gpt-4.1; a
30-per-task cut is a smaller sample and its numbers move accordingly.

Honest boundaries measured during the pilot, restated in
[`../CAPABILITY_CARD.md`](../CAPABILITY_CARD.md): recall on news summaries is the weak face; two
ensemble arms measured below the single tuned judge on this two-code task; a fine-tuned small
model matched the prompt on F1 at a fraction of the cost but lost recall; character offsets are
carried as case metadata, not as an engine span type.
