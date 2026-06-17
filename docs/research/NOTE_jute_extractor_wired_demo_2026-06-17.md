# NOTE — JUTE-generated ingest: VALIDATED + incorporation plan (2026-06-17)

> **Supersedes the earlier draft of this note.** That draft listed two headline blockers —
> "§4.2 template broken on live `:3031`" and "generic join-by-key engine-scope-blocked." **Both
> were WRONG** — a story-shaped self-diagnosis caused by feeding a double-wrapped sample. Re-tested
> against the live engine with verbatim evidence below; corrected in memory
> [[jute-extractor-spec-and-live-gate]]. The honest finding: **JUTE can reliably express this
> transform, and a capable model can reliably generate it.**

## A. VALIDATION (the "be double-sure" gate) — PASSED, with live evidence

**A1 — the engine applies the transform (CONFIRMED live).** The §4.2 per-scene normalizer, including
the **nested `$reduce` join-by-key** that reads the outer `$let`'s `node` (`$if c.scene_node_id =
node`), applies cleanly on `:3031`: **5 records, 0 nulls, `model`/`finish_reason` correctly joined**
from `llm_calls`. Nested scope DOES inherit — confirmed in the engine source
(`jute.clj` `src/jute/core.cljc`: `$map`/`$reduce`/`$let` each `assoc` the bound var INTO the existing
scope and thread it through `$body`).

**The old "count=0" was a feed-shape bug, not the engine.** `test_template` wraps `sample_input` as
`{resource: <input>}`. Feed the **bare inner resource** → `resource.metadata.*` matches → 5/0. Feed the
**whole fixture** (`{resource:{…}}`) → double-wrap → `resource.id`→null → count 0. The "`resource.id`→null"
I'd blamed on "scope doesn't inherit" was the double-wrap symptom.

**A2 — a model GENERATES it, and the GATED LOOP (not first-shot) is what makes it reliable (MEASURED).**
- **First-shot WITH a repo anchor (StoryWorld): 8/8.** 8 blind fresh-context agents each produced a
  live-accepted transform (7 rediscovered the pinned template, 1 novel-but-correct); agents steered toward
  the trap idioms correctly refused them. *Misleadingly easy* — the proven template was in the repo to copy.
- **First-shot on a GENUINELY NOVEL shape from grounding alone (GitHub issues⋈comments): 0/3.** The join
  *logic* was right (all 3 used the correct `$reduce`-find, avoided the traps) but they tripped on **deployed
  runtime quirks not in their grounding**: single-quote string literals (parse error), `joinStr` misused as a
  variadic concat, and `$if` inlined as a string instead of a structured object. **The live gate caught all 3.**
- **After ONE refine round (feed each its live `:3031` error + sharpened grounding): 3/3, count=6, 0 nulls,**
  correct join. This is `best_of_n_extractor`'s mechanism.
- **Conclusion:** generation reliability = **truthful (quirk-complete) grounding + generate → live-gate → refine**,
  NOT raw first-shot. The model gets the *structure* right; the loop fixes the deployed-engine quirks.

**A3 — deployed `:3031` capability map (probed live; deployed build ≠ the `jute.clj` source).**
| builtin / idiom | deployed | note |
|---|---|---|
| `len` (=count) | ✅ | the actual count fn — "count"/"length"/"size" names absent |
| `groupBy(keyfn, coll)` | ✅ | clean keyed-index primitive |
| `replace` | ❌ | **in source (line 120) but FAILS on deployed** — the live-gate's whole point |
| single-quote string literal `'x'` | ❌ | **parse error on deployed** though the served spec documents it — use DOUBLE quotes only (this caused the GitHub first-shot 0/3) |
| `joinStr(sep, array)` | ✅ (as `(sep, array)`) | NOT a variadic concat — for string concat use the `+` operator (`a + "-" + b`) |
| nested-`$reduce` join (iterate scenes) | ✅ | **robust** — row-count = scene-count; the pinned idiom |
| dynamic-path `enhanced_scenes.(c.scene_node_id)` | ✅ | clean, but row-count = #llm_calls |
| predicate `coll.*(this.x=key).0.field` | ⚠️ TRAP | after a predicate, `.0` maps INTO each match → `[]` |
| manual `assoc`-index then `.(key)` | ⚠️ TRAP | `assoc` makes STRING keys; dynamic `.(…)` looks up as KEYWORD → null |

**Honest caveats (what 8/8 does and doesn't prove):** one data shape (scenes⋈calls), one model tier
(Claude Opus), and **generation reliability is grounding-dependent** — with the OLD wrong notes or no
runtime grounding, a model would reach for `replace`/predicate idioms and fail. The defensible claim:
*"for a well-specified shape with truthful runtime grounding + a live gate, generation converged 8/8;
the limiting factor is grounding quality and feed-shape, not model capability."*

## B. HOW TO RELIABLY INCORPORATE IT (the pattern)

**generate-at-authoring → live-`:3031`-gate → PIN → deterministic apply.** Never regenerate per pull.
1. **Truthful grounding** — the corrected `_RUNTIME_NOTES` (add `len`✓/`groupBy`✓, the join idiom, the two
   traps, and the "feed the bare resource" rule). This is the single biggest reliability lever.
2. **best-of-N generate + refine loop** — already built (`build_extractor_generator` / `best_of_n_extractor`).
3. **Hard structural live gate** — `score_extraction`: output is an array, `count == scene-count`, ZERO null on
   `case_id`+`response`. The engine is the decider, not the model's confidence.
4. **PIN** the accepted template (+ provenance: source shape, sample id, gate result) and **apply deterministically**
   per pull. One-time generation ⇒ cost is trivial.
5. **LM for the one-time gen:** Azure (proven DSPy adapter, no timeout) OR BYO-Claude $0 — the latter now viable since
   the trimmed bare resource is ~2.6KB (the 120s timeout was the 162KB full session). [[byo-claude-provider-thesis]]
6. **Trust-model separation preserved** — `jute_extractor` is INGESTION-ONLY; never registered in any grade-time
   floor/contract executor (`tests/test_jute_extractor.py` pins this). Generated-ingest ≠ verdict-grounding.

## C. WIRE INTO THE SHELL (plan)

- The generated transform targets the **source's NATIVE shape** (raw StoryWorld session: `enhanced_scenes`/`llm_calls`
  at TOP level), so there's **no hand-written prep** — that's the "eval anything" point. (The pinned §4.2 template
  targets the metadata-wrapped fixture shape; for the raw connector feed, generate/pin against `resource.enhanced_scenes`.)
- Connector setup: on first connect, fetch one real session → **generate → gate → pin** the transform (store template +
  provenance). Per "Pull a batch": **apply the pinned transform** (bare-resource feed) to each fetched session → cases.
- The NARR-6c **deterministic direct-write stays as the default/fallback** for StoryWorld; the JUTE-generated path is the
  capability for a **new/arbitrary source with no prep**. Honest-Δ: the visceral demo is a *different* shape ingested with
  zero hand-written code, not StoryWorld (which already has prep).

## D. REMAINING WORK (small, all above the frozen seam — moat-clean)
1. Correct `_RUNTIME_NOTES` (add `len`/`groupBy` + the join idiom + the two traps + feed-shape rule). Tests-first.
2. Un-skip + actually RUN the live-convergence gate (`test_live_extractor_converges`) — the skip-guard is what let the
   wrong note stand.
3. Connector: feed the bare native session shape + a setup-time generate/gate/pin step (a flag/branch alongside the
   deterministic path). `apps/bff/app.py` connector endpoints; `jute_extractor.py` (loop/grounding only).
4. Pick the one-time-gen LM (Azure vs BYO-Claude) + the demo target (a genuinely new source vs StoryWorld re-proof).

## Invariants to keep
- **Live-`:3031`-gate everything** (deployed ≠ spec AND ≠ source) and make the gate RUN (skip-guarded = unverified).
- **Generate-at-authoring → PIN → deterministic apply** (don't regenerate per grade).
- **Honest-Δ** — if a generated transform doesn't apply, report it; never fall back silently or hand-pin a fiction.
