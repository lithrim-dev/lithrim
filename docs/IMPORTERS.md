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
| `gold_spans_path` | no | Dotted path into a case to the human evidence spans behind its labels. The gold-mismatch correction row carries them. |
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
3. If the cases keep their source id or spans under a nested key, declare `source_id_path` and
   `gold_spans_path`; otherwise emit them top-level.
4. Cases the importer produces carry `ground_truth_basis: human_annotated` and the mapped codes in
   `expected_safety_flags`; a response with no labels is a first-class clean negative
   (`expected_safety_flags: []`).

The open/closed test for this is `tests/test_importer_manifest.py`.
