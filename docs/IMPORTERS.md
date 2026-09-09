# Importer manifests: bringing a labeled dataset into a pack

A `kind: importer` manifest declares how a foreign dataset's vocabulary maps onto the active
pack's taxonomy. It is data, not code: the engine never names a dataset, and a second dataset is
a second manifest with zero engine edits. The reference manifest is
`packs/_core/importers/ragtruth.json`; the registry is `lithrim_bench/harness/plugins.py`
(`ImporterManifest`, `importer_plugins`, `importer_vocabulary`).

A pack lists its importers in `pack.json`:

```json
"importers": ["importers/ragtruth.json"]
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | The plugin id (`<dataset>_vocabulary` by convention). |
| `dataset` | yes | The dataset name callers ask for (`importer_vocabulary("ragtruth")`). |
| `label_types` | yes | Dataset label term to taxonomy code. Every code must exist in the pack's `taxonomy_snapshot.json`. A term with no code fails ingest (`LookupError`), never a silent drop. |
| `verdict_rule` | no | The verdict equivalence stated in both vocabularies (the write-up footnote). |
| `metadata_fields` | no | Dataset facets carried as case metadata, never as codes (RAGTruth's Evident/Subtle). |
| `untyped_prediction_class` | no | How an untyped dataset-side prediction is named when scoring. |
| `source_id_path` | no | Dotted path into a case to the dataset source id the response was generated from. The optimizer keeps its train and held-out splits disjoint on this id. |
| `gold_spans_path` | no | Dotted path into a case to the human evidence spans behind its labels. The gold-mismatch correction row carries them; the scorer reads them as gold. |
| `task_path` | no | Dotted path to the dataset task a case belongs to; the scorecard groups by it. Fallback: top-level `task`. |
| `generator_model_path` | no | Dotted path to the model that generated the graded response. Fallback: top-level `model`. |
| `training_classes` | no | Taxonomy code to the class name a training export in the dataset's own format uses (`lithrim export --format paper|chat`). A code with no entry falls back to its first dataset term, lower-cased. |
| `citation`, `license`, `version`, `tier` | no | Provenance. `tier` defaults to the pack's tier. |

## Where the engine reads a case's source id and gold spans

Two engine surfaces need fields a dataset may keep anywhere: the judge optimizer's provenance
manifest (`train_source_ids`, `heldout_source_ids`) and the `gold-mismatch/1` correction row
(`gold_spans`). Both resolve through `case_source_id` / `case_gold_spans` in
`lithrim_bench/harness/plugins.py`:

1. every importer manifest of the active pack is tried at its declared `source_id_path` /
   `gold_spans_path`; a case shaped by that importer resolves there;
2. otherwise the neutral top-level case fields `source_id` and `gold_spans` are read.

So a corpus with no manifest behind it still works: put `source_id` and `gold_spans` at the top
level of each case. Empty values count as absent.

## Adding a second dataset

1. Write `packs/<pack>/importers/<dataset>.json` with at least `id`, `dataset`, `label_types`.
2. Add the ref to the pack's `pack.json` `importers` list.
3. If the cases keep their source id, task, or spans under a nested key, declare the `*_path`
   fields; otherwise emit them top-level (`source_id`, `task`, `model`, `gold_spans`).
4. Cases the importer produces carry `ground_truth_basis: human_annotated` and the mapped codes in
   `expected_safety_flags`; a response with no labels is a first-class clean negative
   (`expected_safety_flags: []`).
5. Write an adapter (below) so `lithrim load` can cut the dataset into cases.

The open/closed test for this is `tests/test_importer_manifest.py`.

## The adapter: how `lithrim load` reads a dataset

The manifest is data. Turning a dataset's own files into cases is code, and that code lives
outside the engine: a Python file (or importable module) the CLI loads with
`--adapter path/to/adapter.py` (`lithrim_bench/cli/adapters.py`). It must define:

| Function | Contract |
|---|---|
| `download(data_dir)` | Optional. Fetch the dataset's files into `data_dir` when absent. |
| `slice_cases(data_dir, *, per_task, split, natural)` | Return eval cases (the pack's case shape) for `split` (`test` or `train`); `train` rows carry `split: calibration`. |
| `calibration_corpus(data_dir, *, per_task, test_cases)` | Return the optimizer corpus: calibration rows from the train side plus the given test cases, source-disjoint. |

The reference adapter is `examples/ragtruth/adapter.py`; the reviewer it pairs with is
`examples/ragtruth/judge.ragtruth_detector.json` (`lithrim configure --judge`). The loop is
described in `examples/ragtruth/README.md`.
