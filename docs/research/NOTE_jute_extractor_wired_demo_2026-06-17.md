# NOTE — what it'll take to demo the connector ingest via the JUTE-GENERATED transform (2026-06-17)

> **Why this note.** The published demo (`out/zyng_narrate/lithrim_storyworld_connector_ingest.mp4`) shows the connector ingest via the **deterministic** `_prepare_storyworld_session` + `_to_envelope` path (NARR-6c) — $0, live, 19 cases from 8 real StoryWorld sessions, `source` mapped, PII-redacted. The **JUTE-extractor-GENERATED** path (the model authors a `jute_transform` from the DSL spec + a data sample + the desired shape, live-`:3031`-gated, pinned) is the "eval **anything** on an **arbitrary** shape" capability — NOT what the video shows. This note scopes what it takes to wire it in and demo it. See [[jute-extractor-spec-and-live-gate]].

## DONE (the real bug, fixed + proven)
The extractor signature dropped `dsl_excerpt` (declared 4 InputFields, `forward()` passed a 5th → DSPy silently dropped it), so the model was told to "ground in the DSL excerpt's runtime-reality notes" but never received them. **Fix = add `dsl_excerpt` as an InputField** (`lithrim_bench/verification/jute_extractor.py` `JuteExtractorSignature`), mirroring the proven `jute_dspy.py:321` `JuteValidatorSignature`. **PROVEN:** once grounded, BYO-Claude generated a CORRECT transform (right `source` mapping via `$if/$then/$else`, valid directives, runtime-aware reasoning — it even diagnosed the `$let` scope bug). So the generation LOGIC works; the bug was the dropped field.

## BLOCKERS — what's left, in priority order

1. **The §4.2 `PROVEN_TEMPLATE` is BROKEN on the live `:3031` engine** (count=0 — verified directly on the fixture). Its nested `$let`/`$reduce` body does not inherit outer scope (`resource.id` → null → 0 records). It was **never live-bench-gated** — `test_live_extractor_converges` is skip-guarded (`LITHRIM_NARR_LIVE`), and the non-live tests score against a `FakeExtractorClient` oracle that doesn't replicate engine scope. **→ Author a working generic transform that APPLIES on live `:3031`, and un-skip/run the live gate.** This is the crux.

2. **Generic JUTE join-by-key is engine-scope-blocked.** The natural pattern ("`$map` over `enhanced_scenes`, join `llm_calls` by `e.key`") fails because a nested `$reduce`/`$let` body can't see the outer `$map`'s `e` (or `resource`). **Candidate idioms to test against live `:3031`:**
   - (a) **Iterate `llm_calls`** (which carries `scene_node_id`) + **dynamic-key lookup** into `resource.metadata.enhanced_scenes[c.scene_node_id].clean_text` — IF JUTE supports dynamic key access. (Most promising; avoids the nested-scope join.)
   - (b) A scope-preserving `$let` form, if one exists in the engine.
   - (c) **Per-session unrolled** (hardcode the node names) — works (BYO-Claude produced this) but is NOT generic; it'd require regenerating per session (cost + not a pinned reusable transform).
   Pick the one that applies on live `:3031` with `count==expected, nulls==0`.

3. **Connector must feed the right sample shape.** Today the connector pre-flattens via `_prepare_storyworld_session` then asks JUTE to re-transform the already-flat records (near-identity, pointless). For the generated path, feed the **trimmed full-session** structure `{resource: {id, story_id, mode, language, metadata: {enhanced_scenes, llm_calls}}}` so the §4.2-style transform extracts.

4. **Trim the sample (~10KB, not 162KB).** The full real session is ~162KB (30+ noise fields: `story_text`, `narrative_segments`, illustration jobs…). Feeding it to the `claude` CLI **timed out at 120s**. Trim to the transform-relevant shape (`metadata.enhanced_scenes` clean_text + enhancement_status, `llm_calls` scene_node_id/finish_reason/model, + a few top-level fields) → ~10KB → fast.

5. **The generation LM plumbing.** BYO-Claude ($0) generates correct logic but DSPy-over-`claude -p` has two plumbing limits: (a) the 120s subprocess timeout, (b) a ChatAdapter→JSONAdapter parse mismatch on the CLI's markered (`[[ ## field ## ]]` + ```fences```) output → `AdapterParseError` even on a perfect template. **Either** fix the `ClaudeCliLM`↔DSPy seam (bump timeout + adapter/fence handling, $0/airgapped) **or** use **Azure** for the one-time generation (proven DSPy adapter, no timeout; the transform is pinned + reused, so it's ~1 paid generation). See [[byo-claude-provider-thesis]].

6. **Convergence reliability.** Add a `desired_output_example` InputField (a concrete target record) + seed iteration 0 with the WORKING (live-gated) template so the loop makes minimal edits, not a blank-start re-derivation.

## The end-state demo
A **new/arbitrary** data source — one where you do NOT hand-write a deterministic prep — connected in the shell → the extractor **auto-generates** a `jute_transform` (live-`:3031`-gated, pinned) → applies it → eval-cases, all in-UI. That is the "eval anything" generality. (StoryWorld already has a deterministic prep, so it doesn't *need* generation — the generation's value is precisely the case where there's no prep to write.) A good demo target: a *second* connector/shape (e.g. a different session export, or an FHIR/HL7 bundle) ingested purely via the generated transform.

## Effort + locus
**Medium R&D.** The crux is #1+#2 (a generic transform that applies on live `:3031` + the live-bench-gate); #3–#6 are wiring/plumbing once that's solved. All edits are **above the frozen seam** (moat-clean): `lithrim_bench/verification/jute_extractor.py` (signature + loop + a desired-output field), `apps/bff/app.py` (the connector feeds the trimmed session + seeds the generated transform — a flag/branch alongside the deterministic path), and the live-gate test (un-skip + point at a real session). `jute_extractor` is ingestion-only and absent from every grade-time registry (`tests/test_jute_extractor.py:218`), so none of this touches the council/grounding/spec/tools moat.

## Invariants to keep
- **Live-`:3031`-gate everything** — never fake-oracle-only, and the live gate must actually RUN (a skip-guarded live test = unverified). This is the lesson that hid the §4.2 breakage.
- **Generate-at-authoring → pin → deterministic apply** (don't regenerate per grade). The pinned transform is the reusable artifact.
- **Honest-Δ** — if a generated transform doesn't converge/apply, report it; don't fall back silently or hand-pin a fiction.
