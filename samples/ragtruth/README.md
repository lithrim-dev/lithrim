# RAGTruth queue sample

Five public cases the reviewer works in `make queue`. Each is an LLM response paired with the
source it was generated from and a **human** hallucination annotation, so the reviewer's
grounding checks have something to check against and the reader has something to score the
reviewer with.

## Provenance

- **Corpus:** RAGTruth, Wu et al., *RAGTruth: A Hallucination Corpus for Developing Trustworthy
  Retrieval-Augmented Language Models* (arXiv:2401.00396). Repository:
  github.com/ParticleMedia/RAGTruth. **License: MIT** (Particle Media, 2023).
- **Scale of the source corpus:** 17,790 responses over 2,965 sources; six generating models;
  three tasks (news summarization, MS MARCO question answering, Yelp data-to-text);
  14,289 span-level hallucination labels across 7,664 responses.
- **What ships here:** five responses with their sources and labels, chosen by the rule below,
  plus the committed judge baselines that let the queue replay at $0.
- **Ground truth basis:** `human_annotated`, not by construction. `expected_safety_flags` maps
  the RAGTruth label types onto the neutral `_core` taxonomy (Evident/Subtle Conflict ->
  `SOURCE_CONTRADICTION`; Evident/Subtle Baseless Info -> `UNSUPPORTED_ASSERTION`); the
  annotated spans ride along under `ragtruth.labels` as the evidence for that mapping. These
  cases are a sample corpus, not benchmark gold: the by-construction discipline that governs the
  shipped benchmark packs does not apply to imported human labels, and the file says so.

## Selection rule (`examples/ragtruth/adapter.py`)

Eligible: RAGTruth test split, `quality == good`, source under 3,500 characters, no medical
vocabulary and none of the CE data-surface sweep words (that data lives only on the tree's sanctioned surfaces). Then, shortest source
first and lowest id on ties:

| rule | task | why it is in the queue |
|---|---|---|
| R1 | data-to-text | the `value_grounding` floor finds a value absent from the record and a human span covers it |
| R2 | data-to-text | the floor checks at least three values and finds all present; no human label |
| R3 | news summary | human-labeled baseless information; the response states no values for the floor to check |
| R4 | news summary | the floor finds a value absent from the prose source and a human span covers it: a named lead for a person, not a proof |
| R5 | question answering | the floor checks at least two values, all present; no human label |

The rule, not a person, picked the five. Re-run the script against the upstream files to
reproduce the pick (`python examples/ragtruth/adapter.py --download`).

## What the reviewer can honestly claim on this corpus

Measured offline on the full RAGTruth test split (quality good, non-medical rows; human spans as
gold; 2026-09-06), a value stated in the response but absent from the source is:

| source | precision (strict: value inside a human span) | precision (response carries any human label) | recall on numeric conflicts |
|---|---|---|---|
| structured record (data-to-text) | 0.78 | 0.94 | 0.82 |
| passages (question answering) | 0.68 | 0.74 | 0.53 |
| prose (news summaries) | 0.10 | 0.29 | 0.95 |

So the `value_grounding` floor **injects a block only when the source is a record**, and on
prose it surfaces the missing value as a lead the reviewer routes to a person. The judges' signals on
prose are examined by `source_grounding` (a signal is disproved only on full grounding), which
on paraphrased summaries rarely clears anything. That is the honest shape of this corpus: on
open-ended text the reviewer refuses to pretend, clears what it can prove, and hands a person
the exact value it could not find.

## What the committed queue shows

With the baselines below, `make queue` lands at **cleared 0, flagged 1, held for a person 4**. The
flagged case is the data-to-text description that states a value (`50`) its record never had;
the human label agrees. Two of the held cases are human-clean cases (`ragtruth_9001`,
`ragtruth_12132`) where `value_grounding` confirmed every number the response states while the
Mistral and Llama judges still raised omission claims no deterministic check can test; the line
shows both. The other two held cases are human-labeled summaries the judges also doubted, one
with the exact missing value named as a lead. No case was cleared on a judge's word and none
was passed in silence. A different judge ensemble lands differently (an OpenAI gpt-4o trio
cleared the two human-clean cases outright in a trial capture); the checks and their evidence do
not move.

## Files

- `cases.jsonl`: the five cases (`_core` shape; `transcript` holds the source, `source_kind`
  says whether it is a `record` or `prose`).
- `baseline.<case_id>.json`: the committed judge-ensemble baseline for each case (the raw
  pipeline result of one paid pass; the queue replays it with no model call and runs the
  grounding checks live).

## Baseline provenance

Captured 2026-09-06 on the neutral `_core` trio over Azure AI Foundry, one paid pass per case,
judge cache disabled, every vote checked for a live model call (tokens > 0) and no judge error
before the file was kept:

| role | deployment | confidence |
|---|---|---|
| `risk_judge` (k=5) | `azure/gpt-4.1` | calibrated from token logprobs |
| `policy_judge` (k=1) | `azure/Mistral-Large-3` | `None` (the deployment rejects logprobs; honestly confidence-dark) |
| `faithfulness_judge` (k=3) | `azure/Llama-4-Maverick-17B-128E-Instruct-FP8` | `None` (same) |

Floating model aliases, so provider drift is untracked; a re-capture may vote differently. The
grounding checks are deterministic and run live on every replay, so the floor's part of each
state is reproducible regardless.
