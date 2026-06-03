# SPEC: The Calibration Trainer — Phase-3 interactive loop

> The build-of-record for the journey's **Phase 3 — Calibration**, the beat the original
> vision calls *"the product."* Lithrim Bench is a **calibration trainer, not a demo**: the
> user takes a deliberately-miscalibrated pack and makes the judges right — tune the council,
> add a tool-grounded floor, re-run, compare — and learns calibration by *doing it*, with
> their own hands, fully local.
>
> **Status:** v1 draft — direction approved by user 2026-06-03 ("re-author now, spec next").
> The shell's Act 3 now *represents* this loop (presentational, see `apps/shell/src/journey/jp3.jsx`);
> this spec pins the **interactive** build behind it.
> **Companion docs:** [`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md) (the 3-pane experience),
> [`SPEC_PRODUCT_SERVICE_TOPOLOGY.md`](SPEC_PRODUCT_SERVICE_TOPOLOGY.md) (services/airgap/BYOK),
> [`../design/JOURNEY_brief.md`](../design/JOURNEY_brief.md) (the GTM journey),
> [`../PAPER_OUTLINE.md`](../PAPER_OUTLINE.md) (the claim the loop must not weaken).

---

## 1. The thesis: calibration is the product

You don't show someone a dashboard and say "see, it works." You hand them a scribe exchange,
let them click verify, show them a result that is **deliberately wrong**, then challenge them
to make the judges smarter. By the time they've added a floor contract, extended the taxonomy,
and watched accuracy improve on re-run, they understand what Lithrim does **because they just
did it**. The experience *is* the value proposition.

What makes Lithrim's calibration different from a prompt-tuning playground (e.g. Composo): the
strongest lever is not rewording a judge prompt — it is **adding a deterministic, tool-grounded
contract that can overrule the judge**. That lever is real today (§2). This spec wires it into
an iterate loop.

## 2. Current state — the engine is mostly real; the loop is not

| Phase-3 mechanic (vision) | State today | Where |
|---|---|---|
| Edit judge prompts | **real** (files; council runs in-process) | `lithrim_bench/runtime/council/council_roles/*.txt` |
| Tool-grounded floor (the hero lever) | **real + tested**: `dosage_grounding` (this cycle), `presence_check` (suppress) | `lithrim_bench/verification/tools.py`, `harness/grounding.py` |
| Record-grounding floor (the moat flip) | **prototype** — runtime-registered for the moat experiment, **not yet committed** | `record_presence` executor (commit in M2) |
| Plain English → Jute conditional | **engine real**, in-product builder parked | `verification/jute_gen.py`, `jute_dspy.py`; see memory `dspy-jute-prompt-builder-deferred` |
| Extend taxonomy codes | **real but snapshot-gated** | `taxonomy/taxonomy_snapshot.json`, ontology flags as data |
| Add knowledge base | **deferred** (`kb_rag` is WS-3b) | corpus = Pinecone `hipaa-compliancev2` |
| Re-run + before/after compare | **metric real, loop not wired**: `0.50→1.00` precision exists | `harness/grade.py:grade_inprocess`, `grounding.ground`, `ontology.severity_map.rescore` |
| Run history / provenance | **real** (WS-6d) | `ProvenanceStore` (blob + projection) |
| Conversational agent orchestrates | **not built** | journey-mode agent is presentational |

**Conclusion:** the substantive pieces exist (council, two real floor executors, the grade path,
the before/after metric, provenance). The product gap is three things: a **miscalibration
baseline**, the **edit→re-run→compare loop wired live**, and the **agent that turns plain English
into a contract**.

## 3. What "miscalibrated" means here (by construction)

The core invariant (`CLAUDE.md`) is **labels are true by construction**. So "miscalibrated" is not
a vibe — it is *measurable*: the council-alone verdict diverges from the by-construction truth on
a defined set. A pack ships with a **miscalibration manifest**: the baseline council run + the per-case
divergence, in **both directions**:

- **too strict** (false-block): `All-real PMH` → council BLOCK `FABRICATED_HISTORY` conf 1.0, truth PASS.
- **too lenient** (false-pass / miss): `Dropped allergy` → council needs-review, truth BLOCK; a dose drift
  the judge rationalizes away, truth BLOCK.

The user's job is to drive divergence → 0. The headline metric is **precision/recall against truth**
on the pack (the journey shows the pair: `0.50 → 1.00`). This is honest because the pack is
by-construction; we are never scoring against another model's opinion.

## 4. The loop (target)

```
   ┌─────────────────────────────────────────────────────────────┐
   │  baseline run (miscalibrated)  ──►  divergence vs TRUTH       │
   │                  ▲                          │                 │
   │                  │                          ▼                 │
   │            re-run (grade)            pick a lever:            │
   │                  ▲                  • edit a judge prompt      │
   │                  │                  • add a floor contract ◄── hero
   │                  │                  • extend taxonomy          │
   │                  │                  • bind a KB                │
   │                  │                          │                 │
   │            compare(before, after) ◄─────────┘                 │
   │            improved? regressed? per-case diff                 │
   └─────────────────────────────────────────────────────────────┘
                         iterate until divergence → 0
```

Every lever is a **config mutation** (the SQLite config plane); every re-run is `grade_inprocess`
(or `grade_replay` offline) over the pack; every compare is a diff of two provenance runs against
truth. No lever is a code change — that is what makes it a *trainer*.

### 4.1 Empirical note — the prompt lever is non-monotonic (first real run, 2026-06-03)

The first real run of this loop (4 live council runs + the `$0` floor, on a by-construction dose
drift via runtime-swapped judge prompts; result + reproducible harness:
[`../research/RUN_calib_progression_2026-06-03.json`](../research/RUN_calib_progression_2026-06-03.json)
/ `.py`) contradicted the tidy "lenient → tighten → done" story — and the contradiction is the point:

| Lever | 20→40 | 20→30 | what happened |
|---|---|---|---|
| Lenient prompt ("routine adjustment — don't flag") | caught | caught | didn't even loosen — base grounding instinct held |
| **"Stricter" prompt** ("be strict about *unsafe* doses") | **MISSED** | **MISSED** | backfired — reframed WRONG_DOSAGE as a *safety* question; 40 & 30 MG read as "within max" → slipped to WARN |
| `dosage_grounding` floor (deterministic, `$0`) | caught | caught | the guarantee |

**Finding (CONFIRMED by the run; caveat — one local run, LLM judges are non-deterministic):** tuning
a judge prompt is **non-monotonic** — a well-intentioned "be stricter" edit silently *narrowed* the
flag's scope and missed the drift entirely. **The deterministic floor was the only lever that
behaved.** This is the honest version of "calibration is the product": the prompt is an *exploratory*
lever (always show the before/after; never assume tightening improves detection); the tool-grounded
floor is the *reliable* one. It sharpens the moat — **you cannot reword your way to grounding.**
Demo consequence: Act 3 ships this real matrix, not a staged monotonic curve.

## 5. Architecture (maps onto the committed topology)

```
Tauri shell (apps/shell)
   │  (local IPC / BFF)
   ▼
Python harness                council (in-process)        etlp :3031          KB
  grade_inprocess  ───────────►  council_roles/*.txt        jute_gen          kb_rag
  grounding.ground ──floor──►   _apply_consensus           (NL→validator)    (WS-3b)
  ontology (flags/severity)      ▲                          ▲                  ▲
   │                             │                          │                  │
   ▼                             └──────────── config plane (SQLite) ──────────┘
  ProvenanceStore (WS-6d)        ontology + contracts + judge prompts + KB bindings
  blob (truth) + projection (run metrics)
```

- **Config plane (SQLite):** the editable surface — ontology flags, severity map, judge prompts,
  verification-contract declarations, KB bindings. A lever edits a row; `load_ontology` reads it.
  (Owner↔emit invariant from WS-6c-AGENTIC applies: no inert owners.)
- **Run + compare:** `grade_inprocess` produces a provenance **blob** (truth-of-record) + a
  **projection** row (verdict/scores/precision/ECE/cost). Compare = diff two projections vs truth.
- **All local / BYOK / airgapped:** the deterministic floor is `$0`; only judge re-runs cost tokens
  (BYOK). The demo path is **replay-first** (`grade_replay`) so a walk-through never bills.

## 6. Milestones (each = a working loop with one more lever)

- **M1 — Miscalibration baseline + manifest (read-only).** Ship the baseline council run for
  `healthcarePackv1` + the per-case divergence vs truth (both directions). Shell renders "here's
  what's wrong." No editing yet. *Exit:* the pack visibly fails on known cases; divergence is a number.
- **M2 — Add-a-floor + re-run + diff (the MVP trainer).** Commit the `record_presence` floor executor
  (alongside the shipped `dosage_grounding`). Wire: enable a floor contract via config → `grade_inprocess`
  re-run → before/after diff vs truth → per-case `↑flipped / held / ↓regressed`. *Exit:* a user enables a
  floor and watches precision improve, offline. **This is the smallest real "trainer, not a demo."**
- **M3 — Edit-a-judge-prompt + re-run.** The prompt lever: editor over `council_roles/*.txt` (config
  plane) → re-run → compare. Guard token cost (BYOK, replay default). **Per §4.1, surface this as an
  *exploratory* lever** — always show the before/after diff and flag non-monotonic regressions; never
  present prompt-tuning as guaranteed improvement (the first real run showed a "stricter" prompt
  *losing* detection).
- **M4 — Plain English → generated contract (the agent). ⭐ NORTH STAR — proven live 2026-06-03.**
  NL conformance rules → our **DSPy `JuteValidatorGenerator`** authors a Jute validator → tested live
  against the by-construction pack via `:3031 /mappings/test-template` → the **bench-gate** (0 FP, 0
  ERR, all defects blocked — NOT the LLM's confidence) accepts or rejects → persist as an etlp mapping
  and apply via id. Demonstrated end to end: DSPy **6/6 · 0 FP/ERR → ACCEPT → mapping id 101**, where
  the raw Copilot was **1/3** (a `confidence='high'` attempt produced 9 errors) and the seeded
  validator FP'd the optional-field control. Evidence: [`../research/RUN_jute_dspy_2026-06-03.md`](../research/RUN_jute_dspy_2026-06-03.md);
  tool: `…/experiments/dspy_council_smoke/jute_dspy_smoke.py` (branch `spike/verification-toolbox`).
  **The refine-on-real-error loop is load-bearing** (the served DSL spec lies about builtins — memory
  `jute-runtime-builtin-gap` — so generation MUST be live-tested). *This is the local north star: the
  agents build toward running this loop live in-product and on the paper thesis.* The remaining
  product work is wiring this generator behind the journey's NL input (the orchestrating agent) and
  promoting the toolbox from the spike branch.
- **M5 — Taxonomy + KB levers.** Extend taxonomy (re-snapshot, never soft-pass — `CLAUDE.md`); bind a KB
  (`kb_rag`, WS-3b). Completes the four levers the journey advertises.

## 7. Auditable experiment log → journey-bot hints

Every experiment in this loop is logged as a structured, **tagged** record (the matrix + a
CONFIRMED/INFERRED/HYPOTHESIS diagnosis), making the whole trainer auditable — and those records are
the journey bot's teaching material. The bot's "what went wrong / how it improved" commentary is
**not authored prose; it is read from the logged runs.**

- **The log (auditable):** each run persists its artifacts + a one-line tagged diagnosis. Today:
  [`../research/RUN_calib_progression_2026-06-03.{json,py}`](../research/RUN_calib_progression_2026-06-03.json)
  (prompt lever non-monotonic) and [`../research/RUN_jute_dspy_2026-06-03.md`](../research/RUN_jute_dspy_2026-06-03.md)
  (generator bench-gate). Product path: the WS-6d `ProvenanceStore` blob + an `experiment_note`
  projection (what was tried, the before/after, the tagged diagnosis, the source run id).
- **The hints (journey bot):** at each beat the bot surfaces the relevant logged notes as asides —
  *"when you tuned the judge prompt, the stricter version missed the drift"* (calib run), *"the raw
  copilot was 1/3 reliable — confidence isn't correctness"* (JUTE run). The shell ships these as
  `BOT_HINTS` keyed by beat; each carries its `src` run id so the user can open the backing
  experiment. **Never a hint without a logged run behind it.**
- **Why it matters:** it turns the trainer into a *taught* experience grounded in real local
  evidence, and makes the paper-thesis experiments and the product demo the *same* artifacts.

## 8. Risks & open questions

1. **Re-run cost.** Live council per re-run is BYOK tokens. Mitigation: `grade_replay` for the guided
   journey; live runs are explicit + metered. The deterministic floor is free, so M2 (the MVP) is `$0`.
2. **Taxonomy snapshot gating.** "Extend taxonomy" must re-snapshot from `lithrim-backend`, not soft-pass
   cases (`CLAUDE.md`). The trainer must surface a re-snapshot step, not silently bless a new code.
3. **`kb_rag` deferred.** The "add knowledge base" lever depends on WS-3b. M5, not earlier.
4. **DSPy plain-English→Jute is parked** until one e2e vertical slice (memory
   `dspy-jute-prompt-builder-deferred`). M4 is the slice that un-parks it — sequence accordingly.
5. **Agent orchestration is the biggest unknown.** M4's NL→contract is the hardest build; M1–M3 deliver a
   real trainer *without* it (levers via direct config edits), so the agent is an accelerator, not a gate.
6. **Don't weaken the paper claim.** Calibration improving precision is a v1-structural / copilot result;
   the semantic-moat (record-grounding flip) is Paper 2 (`PAPER_OUTLINE.md`). The trainer demonstrates both
   but the doc claims must stay scoped.

## 9. Success criteria

A user takes the miscalibrated `healthcarePackv1`, **adds one floor contract** (the record or dosage
grounding) described in plain English, **re-runs**, and sees **precision improve against by-construction
truth** — the whole loop **offline, local, BYOK**. That is the line between a proof and a trainer, and
M2 crosses it.
