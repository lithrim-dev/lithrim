# HANDOFF — bench-salvage — 2026-06-16 (narrative-eval / lithrim-CE wedge)

> **For the FRESH session.** This thread started as `/devloop-resume bench-salvage` (grounding floor) and
> pivoted into a **new product direction**: a domain-agnostic, conversational **narrative-eval wedge** for
> **lithrim CE (OSS)**, proven on the user's **Lenador StoryWorld** project. The hard mechanics are
> de-risked LIVE; the next step is a frontend-driven build.
> **Resume:** `/devloop-resume bench-salvage`, read memory `grounding-floor-is-the-moat-next` +
> `conversational-first-core-plugin-line`, then this doc.

---

## TL;DR — two arcs this thread produced

| Arc | Outcome |
|---|---|
| **A. Grounding floor** (the resume's original target) | De-risked → **`SPEC_GROUNDING_TOOL_LAYER.md`** + **`GROUND-FLOOR-1` driver** authored + committed (`8c45ffc`). **Since SUPERSEDED:** per memory, **TERMINOLOGY-1 landed 2026-06-14** (the `record_presence`→`snomed_subsumption` flip went live, Hermes code-based). Arc A is essentially closed. |
| **B. Narrative-eval / lithrim-CE wedge** (the live new direction) | The whole **JSON→eval-case ingestion via JUTE is PROVEN LIVE**; per-scene grading model established against the user's real data + a human-SME workbook; **decision: build it frontend-first as the OSS wedge.** This is the next build. |

**Branch:** `bench-salvage/ws6c-dspy` (NOT pushed; owner-gated). **Standing prefs unchanged** (no autostart · no push without approval · pathspec-only commits · honest-Δ · BYO-key/$0 first).

---

## Arc A — grounding floor (de-risked, committed, superseded)

- **The 4-axis correction** (evidence-backed): the prior "generate a Jute validator for FABRICATED_HISTORY" plan was wrong on flag / direction / tool-class / root-cause. The real fix was a `record_presence` **suppress** executor. Full detail in memory `grounding-floor-is-the-moat-next`.
- **Hermes SNOMED — LIVE-PROVEN** this thread: imported the real RF2 dump (`~/Workspace/github.com/SnomedCT_InternationalRF2_PRODUCTION_20260501T120000Z.zip`) via `com.eldrix/hermes 1.4.1614` → 2.3 GB `snomed.db` in ~2 min; subsumption + ECL + code-based grounding all work; **fuzzy `search` is unsafe** (ground by code/exact-FSN); Hermes ships a **built-in MCP server** (`com.eldrix.hermes.mcp`, ~27 tools incl. `map-to`/`map-from` SNOMED↔ICD-10) — no wrapper to build. Spike kept at `~/Workspace/github.com/hermes-spike/` (`import.clj`, `query2.clj`, `deps.edn`).
- **Committed `8c45ffc`** (pathspec-only): `docs/specs/SPEC_GROUNDING_TOOL_LAYER.md` + `.devloop/prompts/bench-salvage_phaseGROUND-FLOOR-1_record-presence-floor_driver.md` + the `index.json` bundle.
- **Status now:** TERMINOLOGY-1 superseded GROUND-FLOOR-1's binding live (2026-06-14, separate session). Treat Arc A as done; the live frontier is Arc B.

---

## Arc B — the narrative-eval / lithrim-CE wedge (THE NEXT BUILD)

### B0. The wedge thesis (user decision)
Make the **frontend-driven, conversational eval** the OSS wedge: **"lithrim CE — eval anything."** A developer/writer self-hosts, points it at their own LLM outputs (BYO-key), and grades them conversationally. Demonstrated on **narrative** (the Lenador StoryWorld stories), deployable **at Lenador**. Matches `conversational-first-core-plugin-line` (Core = chat shell + engine + ALL JUTE + BYOK). **Explicitly NOT headless** — the user chose the frontend as the deliverable; the headless proofs already de-risked the mechanics.

### B1. The data sources (both inspected live, read-only)
- **Lenador StoryWorld API** — `http://localhost:8000/api/admin/sessions` (list = metadata) and `…/sessions/{id}` (detail = full content). Auth via an `X-API-Key` header (in the user's curl; **not reproduced here** — set via env/secret). Two LLM-driven stories: **`jinn_of_jebel_hafeet_v3`** (27 sessions) + **`what_mirrors_dont_reflect_v1`** (18); bilingual (en/ar); modes adult/youth/children. The detail carries: `story_text`, `narrative_segments` (canonical), `enhanced_scenes` (the LLM rewrites), `llm_calls` (prompt + response + model + finish_reason, keyed by `scene_node_id`), `answers` (reader choices + `effects` state vector), `metadata` (the keyed copies + provenance).
- **The writer's QA workbook** — `~/Downloads/3 My Story World - Todd Gallicano - Testing (KO).xlsx`. 3 sheets: **"The Jinn of Jebel Hafeet"** (the branching story graph: nodes, baseline + enhanced text, word counts), **"Story Feedback"** (the Writers Brief path/QA matrix: Path ID, route, CP1/CP2, ending, ending-logic, per-bridge Q&A + **Customized Text** columns + Todd's feedback), **"Prompt Testing"**. **This is the human-SME label set** — the anti-circularity anchor.

### B2. The grading model (established)
- **The triad per scene:** *intent/spec* (theme/tone/lesson/mode/language + the chosen branch + the canonical baseline node) → *artifact* (the LLM-enhanced scene `clean_text`) → *provenance* (the prompt's machine-checkable rules + model + finish_reason + source). The enhancement **prompt ships its own contract** ("3–4 sentence preamble, no `[brackets]`, no markdown, don't contradict the authored body, interior POV") — deterministically checkable.
- **Granularity = one eval-case per LLM call = per enhanced scene = per bridge.** A session with 5 calls → 5 cases (~225 across the corpus). **Key finding:** the 5 scene titles map **1:1 to Todd's 5 "Customized Text" columns** (The Ranger / The Exposure / Crash & Consequences / Jinn's Judgement / Ending), joined on the **node**. So per-scene grading aligns the runtime output to the human labels for free.
- **Two grading layers** (same architecture as clinical): a **deterministic floor** (prompt-rule compliance · cliché/repetition overuse · language fidelity · constraint adherence — the "remove weight/chest/tang" kind) + the **LLM judge council** (coherence · mode-appropriateness · tone/theme/lesson fidelity · personalization). The withstands-gate lets the floor correct a hand-wavy judge.

### B3. JUTE extraction — PROVEN LIVE (the de-risk that mattered)
The user's instinct ("use JUTE to extract from the JSON APIs; it walks the tree") was **confirmed live on `:3031`**, after I was wrong twice:
1. **`jute_dspy` generates VALIDATORS, not extractors** (signature/metric are validator-locked) — but its **generate→`test-template`→refine loop + the `:3031` gate are reusable**. A ~50-line **`JuteExtractor` sibling** (new signature + extraction metric) reusing `strip_fences`/`render_dsl_excerpt`/`EtlpJuteClient`/the loop, driven by **BYO-Claude ($0)**, generated a working extractor on **iter 0**, gated live, cross-story (jinn EN + mirrors AR), and generalized to a 3rd arbitrary session. Spike: **`/tmp/jute_extract_spike.py`**.
2. **The full per-scene normalization is PURE JUTE** (no Python fan-out) — `$map` over the node-keyed `metadata.enhanced_scenes` object → an array of per-scene cases, **`$reduce`-find** joining each scene to its `llm_call` by `scene_node_id`. Converged through **5 live runtime quirks** (see below). **The converged template (reusable artifact):**

```yaml
$map: $ resource.metadata.enhanced_scenes
$as: e
$body:
  $let:
    node: $ str(e.key)
  $body:
    $let:
      call:
        $reduce: $ resource.metadata.llm_calls
        $as: [acc, c]
        $start: null
        $body:
          $if: $ c.scene_node_id = node
          $then: $ c
          $else: $ acc
    $body:
      case_id: $ resource.id + "-" + node
      story_id: $ resource.story_id
      mode: $ resource.mode
      language: $ resource.language
      node: $ node
      scene_title: $ e.value.title
      source: $ e.value.source
      model: $ call.model
      finish_reason: $ call.finish_reason
      prompt_chars: $ call.prompt_chars
      response: $ e.value.clean_text
```
→ live result: `compiled: True`, 5 per-scene cases, all fields populated (model `gpt-5.4`, finish_reason `stop`, the real `clean_text`). **Lesson:** hand-authoring JUTE is quirk-laden → this is the case *for* the `jute_dspy` generate-and-gate loop; let it converge the normalizer, don't hand-write it.

### B4. The ensemble council (composable today)
Claude + GPT + Llama is the **existing v2 council** — `build_judge_lm` is already cross-model (`risk_judge`→GPT/COUNCIL, `policy_judge`→Mistral, `faithfulness_judge`→Llama-4-Maverick) + **BYOC** (`provider="claude-cli"` → `ClaudeCliLM`, $0). A narrative panel = assign models to roles; **zero new infra**.

### B5. The load-bearing unlock (the central wedge investment)
Make the config plane + chat authoring **domain-agnostic from the UI**. Today the admissibility gate is bound to the clinical `taxonomy_snapshot` (CLAUDE.md core invariant) — a narrative flag authored via chat gets rejected. The wedge needs **a new domain (narrative) authorable from the UI with its own taxonomy/admissibility**. This is what turns lithrim from "clinical eval" into "eval anything CE," and it generalizes far past stories.

### B6. Proposed build (this is product, not derisk)
- **`SPEC_NARRATIVE_EVAL`** — the narrative domain + the domain-agnostic-config unlock + the chat ingestion tool + the floor executors + the flow. Cross-ref `SPEC_GROUNDING_TOOL_LAYER` + `conversational-first-core-plugin-line`.
- **NARR-1** (load-bearing): domain-agnostic config from the UI + seed the narrative ontology.
- **NARR-2**: chat ingestion tool wrapping the **generated JUTE per-scene extractor** (bench-gated by the `jute_dspy` loop).
- **NARR-3**: the cliché/repetition/constraint **floor executors** + the JudgeEditor *ATTACH VALIDATORS* hook.
- **NARR-4**: the end-to-end **frontend demo** on real Lenador data (Claude/GPT/Llama).

**Reuse (built + proven):** chat shell · `author_judge`/`author_flag` · `run_eval_pack` · `review_runs` · `focus_artifact` · the multi-model council · the JUTE extractor. **Net-new (the wedge):** the domain-agnostic config, the chat ingestion tool, the floor executors.

---

## JUTE runtime quirks discovered (durable — extends `jute-runtime-builtin-gap`)
Caught only by the **live `:3031` gate** (the spec lies):
1. **Top-level `llm_calls[].scene_node_id` is `null`** — the keyed copies live under `metadata.llm_calls` + `metadata.enhanced_scenes` (node-keyed).
2. **`$map` over an object** yields `e.key`/`e.value`; raw `e.key` in a `+` concat stringifies the key **with a leading `:`** (Clojure keyword) → use **`str(e.key)`** which returns it clean.
3. **`substr(s, a, b)` does NOT clamp `b`** — `substr(s,1,99)` throws `StringIndexOutOfBounds` on a short string.
4. **`length`/`size`/`count`/`replace` are unimplemented** (raise at apply time) — confirms the builtin gap.
5. **Inline-indexing a function result** (`splitStr(...).1`) returns `null` — JUTE indexes *bound paths*, not call results.
6. **Cross-array join idiom:** `$reduce` with `$start: null` + `$if c.key = node $then c $else acc` (no `$filter` directive exists).

---

## Key artifacts & where they live
- **Committed (`8c45ffc`, branch `bench-salvage/ws6c-dspy`, NOT pushed):** `docs/specs/SPEC_GROUNDING_TOOL_LAYER.md`, the `GROUND-FLOOR-1` driver, the `index.json` bundle.
- **Spikes (EPHEMERAL `/tmp` — move into the repo if NARR work proceeds):** `/tmp/jute_extract_spike.py` (the `JuteExtractor` sibling), the converged per-scene template (above), `/tmp/lenador_{jinn,mirrors,s3,sessions}*.json` (fetched session data).
- **Hermes spike (kept):** `~/Workspace/github.com/hermes-spike/` (incl. 2.3 GB `snomed.db`; 3.8 GB extracted RF2 dir reclaimable).
- **Salvage sources:** `~/Workspace/github.com/lithrim-backend/lithrim_search_sdk/backend_client.py` (KB pipeline — vendorable) · `~/Workspace/github.com/FHIR-AgentBench/` (FHIR client + MIMIC loaders, GCP-targeted → localize).
- **Memory:** `grounding-floor-is-the-moat-next` (Arc A + TERMINOLOGY-1) · `conversational-first-core-plugin-line` (the OSS/Pro line) · `jute-runtime-builtin-gap` (extend with the 6 quirks above) · `byo-claude-provider-thesis` · `jute-for-data-transformations`.

## Open questions
- Domain-agnostic config: new taxonomy-snapshot per domain vs a CE "freeform" admissibility mode? (NARR-1 decision.)
- Q&A↔scene pairing has a **bridge→scene offset** (Bridge-A Q&A → the Ranger scene, etc., per the workbook) — encode as a lookup in the importer.
- Pack scope for the first demo: the **workbook-labeled paths** (anchored to Todd) vs the full ~225 cases.
- Is narrative-eval a **Core demonstration** or a **public plugin**? (Affects packaging.)

## First move (next session)
1. Read this doc + `conversational-first-core-plugin-line` + `grounding-floor-is-the-moat-next`.
2. Write **`SPEC_NARRATIVE_EVAL`** (same shape as `SPEC_GROUNDING_TOOL_LAYER`) — lead with the **domain-agnostic-config unlock** (NARR-1) + the proven JUTE per-scene normalizer + the floor executors + the frontend flow.
3. Author the **NARR-1** driver. Then NARR-2/3/4.
4. (Optional, $0) move the `/tmp` spikes into the repo as fixtures before they're lost.
