# SPEC: Narrative-Eval — the "eval anything" CE wedge

> One ingest→author→grade loop that proves lithrim **CE is domain-agnostic**: a developer points it
> at their own LLM outputs (BYO-key, $0), drops a JSON dump, and grades it conversationally.
> Demonstrated on **narrative** (the Lenador StoryWorld stories), reused **verbatim** for healthcare.
> The pipeline is one machine; the domain is just a pack + criteria.
> **Status: DRAFT 2026-06-16.** Companion docs:
> [`SPEC_GROUNDING_TOOL_LAYER.md`](SPEC_GROUNDING_TOOL_LAYER.md) (the floor/contract layer),
> [`SPEC_UNIFIED_AUTHORING_PRODUCT.md`](SPEC_UNIFIED_AUTHORING_PRODUCT.md) (the author→process loop + withstands-gate),
> [`SPEC_STANDALONE_CORE_VALIDATION.md`](SPEC_STANDALONE_CORE_VALIDATION.md) (the non-clinical pack precedent),
> [`SPEC_PRODUCT_SERVICE_TOPOLOGY.md`](SPEC_PRODUCT_SERVICE_TOPOLOGY.md) (mapper sidecar).
> Memory: `conversational-first-core-plugin-line`, `byo-ingest-etlp-architecture`,
> `jute-transform-extraction-prior-art`, `jute-runtime-builtin-gap`, `jute-for-data-transformations`.

## 1. The thesis

**CE = "eval anything." One ingest→author→grade loop; swap the domain, not the machine.**

A user drops a JSON dump of their AI system's output. The conversational agent infers the shape, asks
what to extract and what "good" means, generates + live-gates a JUTE extractor behind the scenes,
shows the extracted cases, and — once accepted — grades them with a deterministic floor + an LLM judge
council. **StoryWorld** (LLM-rewritten interactive fiction) is the *accessible* proof that this is
domain-agnostic; **Healthcare** (the clinical pack) is the *deep* vertical. The only things that differ
between them are (1) the pinned JUTE extractor template and (2) the pack's ontology + criteria.

## 2. Current state — what is already true (and one correction)

This wedge is mostly **composition**, not green-field. Verified 2026-06-16 (workflow `wf_8715f73a-0ec`):

- **Admissibility is pack-bound, NOT clinically locked.** `active_snapshot_codes()` resolves the
  taxonomy via `workspace.get_active_workspace().pack` (`harness/admissibility.py:43-57`); the gate
  (`gradeable_flags_outside_snapshot`, `apps/bff/app.py:1229-1240`) checks a case's
  `expected_safety_flags` ⊆ the **active pack's** tier union — never a hardcoded clinical path.
- **The domain-agnostic config plane already exists.** `packs/support_ticket_qa/` is a `tier:core`,
  fully-independent **non-clinical** pack (its own `ontology.json` + `council_roles/` +
  `taxonomy_snapshot.json`, no `packs/healthcare/` reuse) that grades end-to-end via the authored path
  with healthcare unloaded and `:8002` down (`tests/test_standalone_ce.py`). The default pack is the
  neutral `_core`, not healthcare.
- **⚠️ Correction (load-bearing).** The prior assumption — handoff B5 and memory
  `conversational-first-core-plugin-line` both say *"a narrative flag authored via chat gets rejected
  by the clinical taxonomy"* — is **FALSE**, refuted by adversarial grounding. There is **no
  clinical-taxonomy wall**. This shrinks NARR-1 from "build a new config plane" to "author a narrative
  pack + a UI hook." (Update those two records; see Open Questions.)
- **The JUTE per-scene normalizer is proven LIVE** on `:3031` through 5 refine iterations (the 6 runtime
  quirks are in memory `jute-runtime-builtin-gap`). The converged template is in §4.2 — committing it
  here is also its preservation (the `/tmp` original was GC'd).
- **The eval-record schema is a settled contract** (the lithrim-sdk `ExternalResultSubmission` /
  `ActualArtifact` envelope; §4.1). The bench's `grade.py` requires only `artifacts[0].content`.
- **The council + chat surface are reusable.** 16 SDK-MCP tools (`apps/bff/app.py:603-744`,
  `_build_tool_context` `app.py:1595-1910`); `build_judge_lm` is already cross-model
  (Claude/GPT/Llama) + BYOC ($0).

## 3. The one loop

```
   UI (chat shell) ── drop JSON ──▶  StoryWorld session   │   FHIR bundle      (BYO-key, $0)
                                            │
   AUTHOR EXTRACTOR (one-time, LLM)         ▼
     conversational: "what's a case here?" → DSPy generator ⇄ :3031 /mappings/test-template
                                            (generate → live-gate → refine → PIN)
                                            │
   pinned jute_transform ── apply (:3031) ─▶ eval-cases   (StoryWorld: 1 session → 5 per-scene cases)
                                            │
   AUTHOR CRITERIA (pack ontology + judges + floor)  ◀── NARR-1: a narrative pack (small)
                                            │
   GRADE ─▶ deterministic floor  +  multi-model council (Claude/GPT/Llama)  +  withstands-gate
                                            │
   verdicts + provenance (audit) ──▶ review in UI
```

Left of "AUTHOR CRITERIA" is **ingestion** (the net-new `:3031` + DSPy half). Right of it is the
**existing eval engine**. This mirrors the backend's reserved-but-unbuilt `transformer_id`
(normalize) stage and its built `validator_id → etlp_mapping_id` (extract/check) stage — one JUTE
primitive, two faces. lithrim-backend is **reference only**; this builds in the bench (OSS core).

## 4. Data contracts

### 4.1 The eval-case record (unlabeled by construction)
The extractor's output target is the settled SDK envelope — *not* a new shape:
```
{ artifacts: [ { type, content, target_system?, metadata? } ],   # ≥1; content is the graded thing
  context, context_kind,                                          # the prompt/input that produced it
  expected_safety_flags: [], injection_recipe: null }             # ingested data is UNLABELED (HONEST-1)
```
Ingested cases are **unlabeled by construction** (customer output is the SUT input, not gold) — graded
honestly with metrics withheld, never fabricated. Gold labels (e.g. Todd's QA workbook) are layered on
as a separate SME step. For StoryWorld, `prompt → context`, `response → artifacts[0].content`.

### 4.2 The `jute_transform` contract (arbitrary JSON → list of admissible cases)
Input: any domain JSON. Output: a JSON **array** of records matching §4.1. The proven per-scene
normalizer (live on `:3031`, the reference artifact — preserve verbatim):
```yaml
$map: $ resource.metadata.enhanced_scenes
$as: e
$body:
  $let: { node: $ str(e.key) }            # quirk: object-map key is a keyword; str() strips the ':'
  $body:
    $let:
      call:                                # cross-array relational join (no $filter directive exists)
        $reduce: $ resource.metadata.llm_calls
        $as: [acc, c]
        $start: null
        $body: { $if: $ c.scene_node_id = node, $then: $ c, $else: $ acc }
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
      response: $ e.value.clean_text
```
**Boundary (CRITICAL):** a mis-join returns `null`, not an error. The extractor's acceptance metric
therefore carries a hard **structural output-invariant** (zero-null on required fields, `count ==
expected`) gated at generation time *and* at apply time — same burden a verdict-feeding validator
carries (`SPEC_GROUNDING_TOOL_LAYER.md`).

### 4.3 The narrative `taxonomy_snapshot` (seed — authored in NARR-1)
Draft codes, derived from the enhancement prompt's own machine-checkable contract + judge lenses:

| code | layer | check |
|---|---|---|
| `BRACKET_LEAK` | floor (det.) | output contains `[…]` (the marker leaked) |
| `LENGTH_VIOLATION` | judge | preamble not 3–4 sentences (judge lens — not machine-separable from the authored body in the shipped record, S-BS-NARR3-3) |
| `POV_VIOLATION` | floor (det.) | 1st/2nd person in a 3rd-person story |
| `LANGUAGE_DRIFT` | floor (det.) | output language ≠ session language |
| `SILENT_DEGRADATION` | floor (provenance) | `finish_reason != stop` yet silently fell back to baseline while reported `completed` |
| `CLICHE_OVERUSE` / `REPETITION` | floor (det.) | overused tension cliché / reused image vs prior scenes |
| `BODY_CONTRADICTION` | judge | preamble introduces action contradicting the authored body's opening |
| `MODE_INAPPROPRIATE` | judge | not appropriate for adult/youth/children mode |
| `TONE_INFIDELITY` | judge | violates theme/tone/lesson |
| `PERSONALIZATION_MISS` | judge | ignores/contradicts the reader's bridge answers |

## 5. The grading model

Same two-layer architecture as clinical: a **deterministic floor** (the `floor`-layer codes above —
machine-checkable from the prompt's own shipped contract, the anti-circularity anchor) + the **LLM
judge council** (the `judge`-layer codes — coherence, mode/tone/lesson fidelity, personalization). The
**withstands-gate** lets the floor correct a hand-wavy judge. **Day-one proof point:** in the user's
real session, 1 of 5 gpt-5 calls hit `content_filter` and silently fell back to `source: baseline`
while the run reported `completed` → `SILENT_DEGRADATION` caught deterministically. Honest-Δ only.

## 6. Requirements

### P0 — Must Have
- A `packs/narrative/` pack (mirroring `support_ticket_qa`) whose snapshot makes StoryWorld cases admissible — **no engine edits**.
- A `JuteExtractor` (DSPy signature + extraction metric reusing the `jute_dspy` loop) that regenerates the §4.2 template, live-gated on `:3031`, with the zero-null/count invariant.
- A chat **ingest tool** (the 17th SDK-MCP tool): drop JSON → generate jute_transform → present cases → on accept, pin (`persist_or_update`) + upsert the workspace corpus.
- ≥3 narrative floor executors (`BRACKET_LEAK`, `LENGTH_VIOLATION`, `SILENT_DEGRADATION`).
- **Exit:** in the shell, a user drops the pasted Lenador session, gets 5 per-scene cases, and grades them live; `SILENT_DEGRADATION` fires on the content-filtered scene. $0 / BYO-key.

### P1 — Should Have
- The judge-layer council criteria (coherence/mode/tone/personalization) assigned to Claude/GPT/Llama.
- The `bridge→scene` offset lookup (Bridge-A Q&A → the Ranger scene) in the importer.
- Workspace/pack selection surfaced in the chat UI (create/switch to a narrative workspace).

### P2 — Nice to Have
- The healthcare reuse demo: drop a FHIR bundle → the *same* tool → per-artifact clinical cases.
- Join to Todd's QA workbook as the SME gold set (labeled subset → precision/recall, not just verdicts).

## 7. Dependencies
- Live `:3031` (etlp-mapper) — **up** (no autostart; curl first). Ships with CE as a **sidecar**
  (`etlp-mapper-sqlite`, single-file SQLite uberjar) — **deferred until the loop is proven**
  (`SPEC_PRODUCT_SERVICE_TOPOLOGY.md`).
- BYO-key council / BYO-Claude ($0 author) — `build_judge_lm` (already cross-model).
- `jute_dspy.py` loop + `EtlpJuteClient` (`etlp_client.py:48-164`) — present.

## 8. Phased plan (executor cycles)

1. **NARR-1** — the narrative pack + UI hook (*small*, per the §2 correction). Seed `packs/narrative/`
   (`pack.json` + `ontology.json` + `council_roles/` + a hand-authored `taxonomy_snapshot.json` with the
   §4.3 codes); surface workspace/pack selection so a user creates a narrative workspace and drafts
   flags/prompts via the existing `PUT /v1/ontology` (`app.py:1244-1282`) — the snapshot lint already
   resolves any pack's snapshot. **No new config plane, no engine edits.** *Exit:* a StoryWorld case
   with narrative codes passes admissibility and grades to a verdict.
2. **NARR-2** — the JUTE extractor + chat ingest tool (**XFORM-1 folds in here; retire the standalone
   XFORM-1 driver**). Build `JuteExtractorSignature`/extraction-metric/`build_extractor_generator`
   (the rebuild list in the Evidence Appendix), reusing `score_template`/`render_dsl_excerpt`/
   `best_of_n`; add the `ingest_cases` SDK-MCP tool. *Exit:* drop JSON in chat → 5 pinned cases, $0,
   gated live.
3. **NARR-3** — the deterministic floor executors (§4.3 `floor` codes) + the *ATTACH-VALIDATORS* hook
   (`SPEC_GROUNDING_TOOL_LAYER.md`). *Exit:* `SILENT_DEGRADATION`/`BRACKET_LEAK`/`LENGTH_VIOLATION` fire
   deterministically on real data.
4. **NARR-4** — the end-to-end **frontend demo** on real Lenador data with the Claude/GPT/Llama council.
   *Exit:* the visceral two-domain demo (narrative now; FHIR reuse as P2).

## 9. Test plan
- Offline (no `:3031`, no LLM): a mock `EtlpJuteClient` + the pasted session as a fixture; assert the
  §4.2 template yields 5 admissible cases; assert each floor executor on crafted pass/violation pairs
  (`SILENT_DEGRADATION` on `finish_reason=content_filter`, clean on `stop`).
- Live-gated (`LITHRIM_NARR_LIVE=1`): the extractor converges against `:3031`; cross-shape
  (jinn EN + mirrors AR).
- Admissibility: a narrative case under `pack=narrative` grades to a verdict; zero `packs/healthcare/`
  reads (mirror `tests/test_neutral_default.py`).

## 10. Success metrics
- One conversational flow: drop → extract → author criteria → grade, $0, on real StoryWorld data.
- The *same* ingest tool produces a clinical case from a FHIR bundle (domain-agnosticism, demonstrated).
- A caught defect (`SILENT_DEGRADATION`) that is invisible in the finished PDF — honest-Δ.

## 11. Open questions
- **Memory/handoff correction:** update `conversational-first-core-plugin-line` + the
  `narrative-eval-wedge` handoff to drop the "clinical-taxonomy wall" claim (refuted in §2).
- Snapshot authoring: the narrative `taxonomy_snapshot.json` is read-only at grade time (CLAUDE.md core
  invariant) — hand-author for NARR-1, or extend `scripts/snapshot_taxonomy.py` to emit a pack snapshot
  from a UI-drafted ontology? (Affects how "author a domain from the UI" actually closes.)
- Pack scope for the first demo: the workbook-labeled paths (anchored to Todd) vs the full ~225 cases.
- Is narrative-eval a **Core demonstration pack** or a **public plugin**? (Packaging — affects where it ships.)
- RESOLVED 2026-06-16 (S-BS-NARR3-3): LENGTH_VIOLATION is a judge lens, not a deterministic floor — the shipped per-scene record carries only clean_text (no preamble span), so preamble-length is not true-by-construction. The LengthViolationTool is retained, unattached, for a future preamble-span (option a) if real data carries it.

## 12. Evidence appendix
- **Proven artifact:** the §4.2 per-scene template — live `compiled: True`, 5 cases, all fields
  populated (the `/tmp` original GC'd; preserved here). 6 runtime quirks in `jute-runtime-builtin-gap`.
- **Admissibility anchors (CONFIRMED):** `harness/admissibility.py:43-57` (pack-resolved snapshot);
  `apps/bff/app.py:1229-1240` (snapshot lint); `harness/workspace.py` (`Workspace.pack` default `_core`,
  `create_workspace(name, pack=)`); `apps/bff/app.py:353` (`LITHRIM_BENCH_PACK` per-workspace);
  `packs/support_ticket_qa/` + `tests/test_standalone_ce.py` (non-clinical precedent).
- **Reuse anchors (CONFIRMED):** SDK-MCP tools `apps/bff/app.py:603-744` + `_build_tool_context`
  `app.py:1595-1910`; `PUT /v1/ontology` `app.py:1244-1282`; cases via `picklist.load_case`
  (`app.py:109,539-541`) — **no ingest tool yet** (the NARR-2 net-new).
- **JUTE rebuild list (extractor, net-new):** `JuteExtractorSignature` (`extraction_rules`,
  `sample_input`, `prior_template`, `prior_feedback` → `jute_transform`); an extraction metric paralleling
  `score_template` (`jute_dspy.py:130-169`) with the zero-null/count gate; `extraction_feedback_from`;
  `build_extractor_generator` + `best_of_n_extractor`; a `JuteExtractorTool(StructuralJuteTool).verify`
  returning the case list; a `spec.py` `_REQUIRED_REFERENCE_KEYS` entry (`spec.py:44-59`). Reuse
  `render_dsl_excerpt` (`jute_dspy.py:279-302`, exposes the runtime-notes/builtin gap),
  `EtlpJuteClient.test_template`/`apply_mapping`/`persist_or_update` (`etlp_client.py:48-164`).
- **Grounding run:** workflow `wf_8715f73a-0ec` (4 readers + adversarial NARR-1 scope verify →
  `narr1_small_pack_plus_ui`).
