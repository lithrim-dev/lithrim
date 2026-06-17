# PROOF — JUTE-generated ingest GENERALIZES to an arbitrary NEW source (2026-06-17)

> **NARR-7 / P-GEN, G2 live evidence.** Honest-Δ: the result below is the verbatim live run —
> no manufactured win. The generate → live-`:3031`-gate → refine loop authored a working JUTE
> transform for a genuinely NEW data shape (GitHub issues⋈comments) it had never seen, from the
> enriched (`for_extractor`) grounding alone, and the live engine accepted it.

## Claim under test

For a well-specified arbitrary source with truthful runtime grounding + a live structural gate,
the bench's `best_of_n_extractor` GENERATES a JUTE `jute_transform` that the deployed `:3031`
engine accepts (count = the iterated-collection length, zero-null on the required keys) — proving
the "eval anything" generality on a shape that is NOT a StoryWorld re-proof and NOT clinical.

## Setup (verbatim)

- **Source shape:** `pallets/flask` GitHub dump — 2 issues + 6 comments, join-by-key
  (`comments[].issue_number` ⋈ `issues[].number`). Committed clean/injection-free fixture:
  `tests/fixtures/narrative/github_newsource_sample.json` (bodies are INERT graded DATA).
- **Engine:** live `:3031` (`/jute-dsl-spec.json` → 200; `/mappings/test-template` the gate).
- **Generation LM:** BYO-Claude `$0` (the local `claude` CLI as a tool-less `dspy.BaseLM`,
  `lithrim_bench/runtime/council/byo_claude_lm.py`). Trimmed ~1.6KB sample clears the old 120s
  timeout. Total wall time ~20s.
- **Grounding:** `render_dsl_excerpt(..., for_extractor=True)` — the NARR-7 G1 extractor-only
  addendum (the `$reduce` find-by-key JOIN idiom, both join traps, DOUBLE-quote literals, `+`
  concat, structured `$if`, `len`/`groupBy`, the `{resource:<input>}` feed-shape).
- **Command:** `LITHRIM_NARR_LIVE=1 ... pytest
  tests/verification/test_jute_extractor_newsource.py::test_live_extractor_converges_github`
  → `1 passed in 19.93s`.

## Result — CONFIRMED (live, verbatim)

The generate → gate → refine convergence (the honest mechanism, NOT a first-shot):

```json
[
 {"iter": 0, "accepted": false, "graded": 0.0, "count": 6, "nulls": 6},
 {"iter": 1, "accepted": true,  "graded": 1.0, "count": 6, "nulls": 0}
]
```

- **iter 0:** the join mis-fired — 6 records, but all 6 null on a required key (graded 0.0). The
  live gate caught it; the structural feedback named the mis-join.
- **iter 1:** corrected — count=6, zero-null, ACCEPTED (graded 1.0). The apply-time re-gate
  confirmed `count=6 nulls=0 accepted=True`.

The transform the model authored (verbatim) — note the grounded idioms: `$map` over the iterated
collection, the nested `$reduce` find-by-key join, double-quoted `"gh-"`, `+` concat with
`toString`, a STRUCTURED `$if` object (NOT an inline string):

```yaml
$map: $ resource.comments
$as: c
$body:
  case_id: $ "gh-" + toString(c.id)
  issue_number: $ c.issue_number
  issue_title:
    $reduce: $ resource.issues
    $as: [acc, x]
    $start: null
    $body:
      $if: $ x.number = c.issue_number
      $then: $ x.title
      $else: $ acc
  author: $ c.author
  source: $ resource.source
  response: $ c.body
```

Sample enveloped case (`_to_envelope`, §4.1 shape — UNLABELED by construction):

```json
{
 "case_id": "gh-87403507",
 "artifacts": [{"type": "narrative_scene",
   "content": "What is the output, and what did you expect?",
   "metadata": {"model": null, "finish_reason": null, "source": "github"}}],
 "context_kind": "narrative_scene",
 "expected_safety_flags": [],
 "injection_recipe": null,
 "source": "github"
}
```

## What this does and does NOT prove

- **Does:** the loop generalizes — the *same* extractor mechanism that handled StoryWorld
  scenes⋈calls authored a working transform for a never-seen GitHub issues⋈comments shape, with
  the live engine as the decider (not the model's confidence). The single refine round is the
  mechanism, exactly as the 2026-06-17 spike predicted (0/3 first-shot → 3/3 after one refine).
- **Does NOT:** prove first-shot reliability (it took one refine), nor more than one new shape /
  one model tier. The defensible claim is the gated-loop one: *truthful grounding + generate →
  live-gate → refine converged on a genuinely new source*.

## Trust-model note

The extractor is INGESTION-ONLY — never a grade-time floor contract (pinned by
`tests/verification/test_jute_extractor.py::test_extractor_is_not_a_grade_time_floor_contract`).
The MOAT (council / grounding / spec / tools / agent) is byte-frozen vs `d0beed8`.
