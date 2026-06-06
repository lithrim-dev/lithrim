# SPEC: Onboarding / Teaching Journey (ONB · "UAP-6")

> A frontier-lab-grade guided experience that takes a total novice — who knows nothing
> about evals *or* healthcare — from "what is this?" to genuinely understanding what
> Lithrim does, and what an eval / judge / flag / grounding *is*, by talking to the
> system. The system teaches just-in-time, uses generative-UI to take inputs and render
> explanations, contextualizes the user's own background, and stays strictly grounded in
> Lithrim's real capabilities (no feature hallucination).

> **Status:** DRAFT 2026-06-06. New workstream that **extends** the LOCKED
> `SPEC_UNIFIED_AUTHORING_PRODUCT.md` (does not modify its §2A/§2B/§4 invariants). The
> frozen 4-act journey becomes the *storyboard* for this live, adaptive teaching layer.
>
> **Decisions resolved (do not re-litigate):** (1) spec-first; (2) teaching vehicle =
> the built clinical-scribe case as the concrete *spine*, **with** active
> contextualization to the user's stated domain.

---

## 0. Context — why this is a new surface, not a tweak

The conversational authoring loop (UAP-5b/5c/5c-2) is an **operator** assistant: it
assumes you already know what a judge is and helps you build/run one. Verified live this
session (Chrome MCP, `:5180`, `$0` BYO-Claude): the full Domain→Judge→Run→Review loop
works end-to-end over `POST /v1/chat` + 8 in-process SDK-MCP tools, rendering gen-UI
cards (`tool-judge_editor` / `tool-run_panel` / `tool-audit_log`). Evidence:
`docs/research/REPORT_live_journey_dryrun_2026-06-06.md`.

But there is **no top-of-funnel for a novice.** Someone who doesn't know what an eval is
cannot enter. The onboarding journey is the teaching layer that turns the proven
operator loop into something a stranger can learn from in one sitting.

The existing **4-act journey** (`apps/shell/src/journey/`) is a *scripted* version of
exactly this teaching arc (Act 2 already lands the grounded-correction "aha"). This spec
makes that arc **live, adaptive, and conversational** instead of pre-recorded.

---

## 1. The Problem

- **Expertise wall.** Every current surface assumes the vocabulary (eval, judge, flag,
  grounding, council). A novice bounces.
- **No conceptual on-ramp.** There is no path from "I have an AI agent and a vague worry"
  to "I understand how Lithrim checks it."
- **The "aha" is buried.** Lithrim's most convincing moment — a confident AI judge being
  *corrected* by a deterministic floor — is reachable only by operators who already set
  everything up. A novice never sees it.
- **Ungrounded explanation risk.** A naive teaching bot will hallucinate capabilities
  ("Lithrim can auto-fix your agent!"). For a trust-wedge product (`gtm-launch` memory),
  an over-promising onboarding is *worse* than none.

**Why it matters:** this is the entire acquisition funnel. Positioning Lithrim as an
**Execution Integrity Platform** is meaningless to a buyer who can't tell an eval from a
dashboard. The onboarding journey is where the category gets taught.

---

## 2. Solution — a teaching layer over the conversational loop

A **teach-mode** of the conversational shell: same `POST /v1/chat` + gen-UI substrate,
but a different brain (curriculum + teach-mode prompt + grounded capability guardrail)
and a different component palette (teaching cards, not operator cards). The clinical
scribe is the concrete vehicle; the user's own domain is woven in.

### 2.1 The "I know nothing" walkthrough (the target script)

This is the experience to deliver. It is *adaptive* (the agent improvises within the
curriculum + guardrail), not a fixed script — but every run should hit these beats:

1. **"What is this?"** → an **explainer card**: *"Lithrim checks whether an AI is
   actually doing its job — by having focused AI 'judges' grade its output, with a
   deterministic safety net that catches a judge when it's confidently wrong."* + a
   one-line "want the 2-minute tour?" **quick-reply chip**.
2. **Elicit context (lightly).** *"First — what kind of AI are you working on, if any?
   (totally fine to say 'no idea')."* Stored for the rest of the session (see §5).
3. **Offer the guided case.** *"Let me show you with one real example — an AI that writes
   doctors' visit notes from a recorded conversation. You don't need to know medicine;
   I'll point out only what matters."*
4. **Teach `eval` just-in-time** (before running anything): **concept card** — *"An
   **eval** is a repeatable test of whether the AI did its job on real examples."*
5. **Teach `judge` + `flag`** when showing the council: **concept cards** — *"A
   **judge** is an AI reviewer with one narrow job. A **flag** is a specific mistake it
   watches for — e.g. 'invented a medication that was never discussed.'"* Render the real
   roster via the existing `tool-judge_editor` read.
6. **"Your turn."** Show a real artifact (a visit note) + a **"your turn" input prompt**:
   *"Here's what the AI wrote. Does anything look off to you?"* The novice makes a call —
   participation before the reveal.
7. **The reveal / aha** — a **reveal card**: run a `$0` replay, then show that an AI
   judge was **confidently wrong** (e.g. "this medication isn't in the transcript" — but
   it is, verbatim) and the **deterministic grounding flipped the verdict.** This is the
   emotional climax. Attested live this session (run `8a41ef3e`; the presence-check
   suppressed a confident false finding).
8. **Teach `grounding` + `audit`** off the back of the aha: *"That safety net is the
   point — judges can be confidently wrong; a deterministic check overrides them, and
   every decision is logged: who, when, what, why."* Optionally surface the S-BS-86
   teaching moment (a config edit silently softened a verdict; the audit + calibration
   caught it).
9. **Contextualize.** Relate every concept back to the user's stated domain (§5): *"For
   your support bot — same idea: did it invent a refund policy that doesn't exist? That's
   a flag; a judge checks it; grounding verifies against your real policy doc."*
10. **Exit check.** A **concept-recap card** + chips: *"That's the whole idea. Want to
    build one of these for your own agent, or see another example?"* → hands off to the
    operator loop (authoring journey).

### 2.2 Non-goals

- Not a replacement for the operator authoring loop — it *hands off* to it.
- Not domain bootstrapping (bring-your-own-domain authoring) — that is a later workstream;
  here the user's domain is used for *analogy/contextualization*, not to build a new
  ontology live.
- Not a marketing site. It is the in-product first-run experience.

---

## 2A. PREREQUISITE — conversational memory (S-BS-87) is the foundation

**A guided multi-turn teaching conversation is impossible on the current loop.** CONFIRMED
in code this session: `POST /v1/chat` is **stateless per message** — `ChatRequest` is
`{message, agent}` only (no history/session), `bff.js chatStream` sends no thread, and
`agent/loop.py:_real_source` runs `client.query(message)` on a **fresh `ClaudeSDKClient`**
(`max_turns=12` *within* one message). The agent re-orients from live config each turn and
cannot remember what it just taught, what the user said their domain was, or where in the
curriculum they are.

Therefore **Phase 0 of this spec is S-BS-87** (see §7). Everything else (curriculum
progression, contextualization, "where were we") depends on it. This is the single
load-bearing dependency.

---

## 3. The teaching brain

Three net-new pieces, all server-side in the chat loop (`apps/bff/agent/`):

### 3.1 Concept curriculum (a concept-graph, authored data)

A small ordered DAG of concepts the agent teaches just-in-time, not as a lecture:

```
Lithrim (what/why)
  └─ eval (a repeatable test)
       ├─ judge (a narrow AI reviewer)
       │    └─ flag (a specific watched-for mistake)
       ├─ run (executing the eval → a verdict)
       └─ grounding (the deterministic floor that overrides a wrong judge)  ← the aha
            └─ audit (who/when/what/why — every decision logged)
```

Each node carries: a one-sentence plain-English definition, a clinical example, a
contextualization template ("for your <domain>, this is …"), the prerequisite node(s),
and the gen-UI component(s) used to teach it. Stored as authored data (e.g.
`data/onboarding/curriculum_v1.json`), versioned like the ontology.

### 3.2 Teach-mode system prompt (distinct from the operator prompt)

A separate prompt that instructs the agent to: teach one concept at a time, never assume
vocabulary, prefer showing over telling, always check understanding before advancing, use
the curriculum order but follow the user's curiosity, and **emit the teaching gen-UI
components** rather than walls of text. Selected by a `mode: "teach" | "operate"` field
on `ChatRequest` (see §8).

### 3.3 Grounded capability guardrail (no feature hallucination)

A canonical **capability sheet** — the maintained, authoritative description of what
Lithrim *actually does* and an explicit **"do NOT claim"** list (e.g. "does not auto-fix
your agent," "does not train your model"). Injected into the teach-mode prompt. Every
capability claim the agent makes must trace to the sheet. This is the withstands-gate
philosophy applied to *teaching*: a claim stands only if it withstands the capability
sheet. Stored as `data/onboarding/capabilities_v1.json`.

---

## 4. Teaching gen-UI components (NET-NEW types)

Current registry cards (`tool-judge_editor`, `tool-run_panel`, `tool-audit_log`,
`tool-agent_editor`, calibration chart) are **operator** cards. The teaching journey needs
new component types registered in the gen-UI registry (`apps/shell/src/genui/registry.js`,
SPEC_PRODUCT_SHELL §10) and emittable by the loop:

| Type | Purpose | Key props | Agent emits when |
|---|---|---|---|
| `tool-explainer` | Plain-language "what is this" answer | `title`, `body`, `eli5: bool` | answering "what is X" at the top level |
| `tool-concept` | Teach one curriculum node | `concept`, `definition`, `clinical_example`, `your_domain?` | first time a concept becomes relevant |
| `tool-your-turn` | Solicit a novice judgment/input before a reveal | `prompt`, `artifact`, `input_kind: choice\|freeform`, `choices?` | before the aha; any point user participation deepens learning |
| `tool-chips` | Quick-reply options to steer without typing | `chips: [{label, value}]` | offering next steps / pacing checkpoints |
| `tool-reveal` | The grounded-correction "aha" | `judge_claim`, `was_wrong`, `grounding_caught`, `verdict_before`, `verdict_after`, `run_id` | step 7 of §2.1 (after the user's "your turn") |
| `tool-recap` | Concept-recap / exit check | `learned: [concept]`, `next_chips` | end of the arc |

These render in `CenterPane` exactly like the operator cards (the proven render path).
Props must be small and presentational; data comes from the real `$0` reads (e.g.
`tool-reveal` is populated from an actual replay run, never fabricated).

---

## 5. Contextualization (depends on §2A memory)

- **Elicit once** (step 2): the user's domain/role, stored in session memory.
- **Adapt depth:** if the user signals expertise ("I've used Ragas"), the agent skips the
  ELI5 framing and accelerates; if "no idea," it slows and uses more `tool-your-turn`.
- **Relate every concept** back via the curriculum node's contextualization template,
  filled with the user's domain. This is the explicit "contextualise my inputs" ask.
- **Honesty bound:** contextualization is *analogy*, grounded in the capability sheet — it
  must never imply Lithrim already supports the user's domain end-to-end if it doesn't.

---

## 6. The clinical guided case + the aha (the spine)

- Vehicle: the committed clinical-scribe case (`bench_scribe_v1_inject_condition_…`) over
  the v2 cross-provider council (risk=gpt-4.1, policy=Mistral-Large-3,
  faithfulness=Llama-4-Maverick — observed live).
- The aha must be **real and reproducible**, never staged: a `$0` replay surfaces a
  genuine confident-but-wrong judge finding that the deterministic presence-check
  suppresses, flipping the verdict — exactly the mechanism attested live (run `8a41ef3e`).
- **Honesty is the moat** (`self-asserting-loop-honesty-moat` memory): if the live data
  doesn't produce a clean aha on a given run, the agent narrates honestly and falls back
  to the captured exemplar — it never manufactures a flip.
- Optional second beat: the S-BS-86 teaching moment — show that *changing a setting*
  (severity weights) silently turned a BLOCK into needs_review, and the audit + calibration
  caught it. Teaches "why labels-true-by-construction + an audit trail matter."

---

## 7. Phased build (tied to the seams)

| Phase | Scope | Closes / depends |
|---|---|---|
| **Phase 0 — Memory** | Make `/v1/chat` memory-coherent: thread conversation history into `ChatRequest` (or a server session) and replay it to the loop; preserve BYO-Claude + the A-SAFE allowlist + the audited-write path. | **S-BS-87** (hard prerequisite) |
| **Phase 1 — Teaching brain** | `curriculum_v1.json` + `capabilities_v1.json`; teach-mode system prompt; `mode` field on `ChatRequest`; the grounded-capability guardrail. | depends on Phase 0 |
| **Phase 2 — Teaching gen-UI** | Register the 6 net-new component types (§4) + their renderers; loop emits them. | depends on Phase 1 |
| **Phase 3 — Guided case + aha + context** | Wire the clinical spine, the real grounded-correction reveal (`tool-reveal` from a live `$0` replay), and contextualization (§5). | depends on Phases 1–2; uses S-BS-7 grounding |
| **Phase 4 — Frontier polish** | Streaming feel, perceived latency, graceful error recovery, agent-id grounding (**S-BS-88**), a real from-scratch entry (**S-BS-89**). | closes S-BS-88, S-BS-89 |

Each phase is a `.devloop` cycle with its own driver, plan-review, and (for Phases 0/3,
which touch the loop and the grounding) a HARD-GATE fresh-critic.

---

## 8. Data contracts

### `ChatRequest` extension (Phase 0 + 1)
```jsonc
{
  "message": "string",
  "agent": "ws0_default",
  "mode": "teach | operate",          // NEW (Phase 1); default "operate"
  "history": [                          // NEW (Phase 0) — prior turns, replayed to the loop
    { "role": "user | assistant", "content": "…" }
  ]
}
```
(Or a server-side `session_id` if history is persisted server-side — an OQ, see §11.)

### New gen-UI card envelope (Phase 2)
Each teaching card is a tool-result part `{ type: "tool-<name>", … props from §4 }`,
rendered by the registry. `tool-reveal` props are populated **only** from a real run
record (carries `run_id`).

### Authored teaching data (Phase 1)
- `data/onboarding/curriculum_v1.json` — the concept-graph (§3.1).
- `data/onboarding/capabilities_v1.json` — the grounded capability sheet + do-not-claim list (§3.3).

---

## 9. Acceptance criteria ("flawless / frontier-grade")

- **A1 — Zero-knowledge entry.** A tester who has never heard "eval"/"judge"/"flag" can,
  by talking only, reach the aha and correctly explain all four concepts in their own
  words afterward (usability test, n≥3).
- **A2 — Memory coherence.** Across ≥6 turns the agent never loses the user's stated
  domain, never re-asks, and correctly reports "what we just did" (the S-BS-87 failure
  does not recur).
- **A3 — Grounded, no hallucination.** Every capability claim traces to
  `capabilities_v1.json`; an adversarial "can Lithrim do X?" probe for unsupported X is
  declined honestly (fresh-critic checks a do-not-claim list).
- **A4 — Real aha.** The reveal is driven by a live `$0` replay, not a fixture; if the run
  doesn't yield a clean aha it degrades honestly (no manufactured flip).
- **A5 — Contextualization.** Given a stated domain, ≥1 concept is correctly re-framed to
  that domain per session.
- **A6 — gen-UI over text.** The journey uses teaching components (not text walls) for the
  explainer, each concept, the "your turn," and the reveal.
- **A7 — $0 + A-SAFE preserved.** The whole journey is `$0` (BYO-Claude + replay tools);
  no paid run is reachable without the human confirm-gate; the A-SAFE allowlist still
  binds (no new paid-capable tool from the teach loop).
- **A8 — Live attestation.** The full journey runs end-to-end on `:5180` for a fresh
  visitor (the standing live-attestation gate).

---

## 10. Dependencies

- **S-BS-87** (memory) — hard prerequisite (Phase 0).
- The LIVE stack: `:5180` shell, `:8787` BFF (`/v1/chat` + 8 tools), `:8002` council,
  `:3031` mapper — all confirmed up this session.
- BYO-Claude (`claude` CLI present, `ANTHROPIC_API_KEY` unset).
- The clinical domain (`clinical_v1` / `ws0_default`) + the S-BS-7 grounding mechanism for
  the aha. NOTE: keep the *committed* severity calibration (`HIGH≥0.5`); the draft was
  restored this session (S-BS-86) so the guided case blocks correctly.
- gen-UI registry (`apps/shell/src/genui/registry.js`, SPEC_PRODUCT_SHELL §10).

---

## 11. Open questions (for the spec author / first plan-review)

- **OQ-1 — Memory locus.** Client-replayed `history` array (simplest; fits the stateless
  BFF) vs a server-side `session_id` with persisted transcript (enables resume + analytics
  but adds state). Recommend client-replayed `history` for Phase 0; revisit if resume is
  needed.
- **OQ-2 — Teach vs operate switch.** A `mode` flag on `ChatRequest`, a separate
  `/v1/teach` endpoint, or a routing layer? Recommend the `mode` flag (one loop, two
  prompts) to keep the A-SAFE surface single.
- **OQ-3 — Curriculum authority.** Is the curriculum/capability sheet authored data
  (versioned JSON, recommended) or derived from the ontology? Keep it separate authored
  data — teaching scope ≠ grading scope.
- **OQ-4 — Reveal robustness.** The live council is non-deterministic; how many `$0`
  replay attempts before falling back to the captured exemplar for the aha? (A4 honesty
  bound governs.)
- **OQ-5 — Contextualization ceiling.** How far do we analogize to an unsupported domain
  before it risks implying support? Needs an explicit guardrail line in the capability
  sheet.
- **OQ-6 — Entry point.** Does onboarding auto-trigger on first run, or behind a "New /
  Learn" entry (ties to S-BS-89)?

---

## 12. References

- `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` (LOCKED; §13/R11 conversational shell — this extends it)
- `docs/specs/SPEC_CALIBRATION_TRAINER.md` · `docs/specs/SPEC_PRODUCT_SHELL.md` (§10 gen-UI registry) · `docs/design/JOURNEY_brief*`
- `docs/research/REPORT_live_journey_dryrun_2026-06-06.md` (the live dry-run that motivated this)
- `docs/research/RUN_uap5a_a8_live_2026-06-06.json` (the live aha + the S-BS-86 teaching moment)
- Seams: **S-BS-87** (memory, Phase 0), **S-BS-88** (agent-id grounding, Phase 4), **S-BS-89** (from-scratch entry, Phase 4), S-BS-7 (the grounding aha), S-BS-86 (the audit/calibration teaching beat)
- Memory: `self-asserting-loop-honesty-moat` (no manufactured wins), `gtm-launch-and-journey-thesis` (trust wedge), `calibration-trainer-is-the-product`, `judge-creation-must-be-demonstrable`
