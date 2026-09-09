# RAGTruth: the reference dataset example

Everything RAGTruth-specific lives here or in the importer manifest
`packs/_core/importers/ragtruth.json`. The engine and the `lithrim` CLI name no dataset.

| File | What it is |
|---|---|
| `adapter.py` | The dataset adapter `lithrim load --adapter` calls: downloads the two upstream files, cuts a per-task slice of the test split, builds the source-disjoint calibration corpus from the train split. Run directly it rebuilds the tracked queue sample `samples/ragtruth/cases.jsonl`. |
| `judge.ragtruth_detector.json` | The reviewer definition `lithrim configure --judge` authors: the paper's Appendix D detection prompt as a single judge with a two-code lens. |
| `arms/paper_prompt.py` | Experiment arm: the paper's prompted baseline, scored with `lithrim score --predictions`. A measured comparison row, not a product verb. |
| `arms/ensemble.py` | Experiment arms E1 (three models, one lens) and E2 (the pack trio, one model). Both measured negative on this two-code task; kept as the record. |
| `arms/finetune_azure.py` | EXPERIMENTAL: an Azure OpenAI fine-tuning client used once for the pilot (submit, poll, bind the deployment as a judge). Not part of the product; Lithrim is not a training platform. |

## The loop on a small cut

With a stack up (`docker compose up` or `make up`) and a provider connected:

```bash
lithrim load      --adapter examples/ragtruth/adapter.py --data-dir out/loop/data --per-task 30
lithrim configure --judge examples/ragtruth/judge.ragtruth_detector.json --model azure/gpt-4.1-2025-04-14
lithrim grade     --judge examples/ragtruth/judge.ragtruth_detector.json --model azure/gpt-4.1-2025-04-14 --confirm-cost
lithrim calibrate --judge examples/ragtruth/judge.ragtruth_detector.json --model azure/gpt-4.1-2025-04-14 --confirm-cost
lithrim regrade   --judge examples/ragtruth/judge.ragtruth_detector.json --model azure/gpt-4.1-2025-04-14 --confirm-cost
lithrim export    --slice out/loop/slice_full.jsonl --split test --out out/loop/export_test.jsonl
lithrim score     --slice out/loop/slice_full.jsonl --grade out/loop/grade_after.json
```

`--per-task 30` is 90 test cases (30 per task) plus 90 calibration cases. The scorecard reports
response-level and span-level precision, recall, and F1 per task, and per code in both
vocabularies (the taxonomy code and RAGTruth's own label terms).

License: RAGTruth is MIT (ParticleMedia/RAGTruth; Wu et al., arXiv:2401.00396). The dataset
files are downloaded into your data dir; nothing from the corpus is tracked here beyond the
five-case sample under `samples/ragtruth/`.
