# SPEC: Conversational-First — the conversation IS the product

> **Status: LOCKED 2026-06-19 (owner).** The center conversation is the primary, load-bearing
> surface. The third (artifact) pane is **auxiliary**: closed by default, opened only to drill
> into raw detail. This is a product invariant, not a preference — a demo or an agent that
> operates the chrome (top-bar buttons, pane tabs) to make a point has **failed** the invariant.
> Companion: `SPEC_PRODUCT_SHELL.md`, `SPEC_UNIFIED_AUTHORING_PRODUCT.md` (the author→process
> loop), the CHATBIND program (the chat↔pane binding this re-balances).

## 1. The flaw this fixes

The shell ships with the artifact pane **open by default**, and both the manual run path and the
agent prompt **push the pane open every turn**. The result: the center conversation sits idle
(an empty "What do you want to evaluate?") while work happens by clicking the side panel and the
top-bar Run buttons. The conversation reads as decorative — "a gimmick that's just there for
show." (Owner, 2026-06-19, observed constantly.)

The mental model is **Claude Desktop**: you drive by talking; the assistant answers with
**inline artifacts** in the conversation; a side panel exists only to expand an artifact when you
ask. We were inverted.

## 2. The three rules (invariant)

1. **The pane is CLOSED by default and stays closed.** It opens *only* on an explicit drill-down:
   the human asks for raw/full detail ("open the full transcript", "show the audit log", "open the
   config"), or taps an inline card's **"Open full →"** affordance. Running an eval, selecting a
   case, authoring a judge, or recording a verdict must **never** auto-open the pane.

2. **Everything actionable renders as fully-interactive inline GenUI in the center.** The eval
   result — verdict · per-judge votes · standing findings · the clinician-verdict (dissent) form ·
   calibration — renders and is operable **in the conversation flow**. The human completes the
   whole act (load → grade → dissent → record) without the pane.

3. **The pane holds only raw/full detail that cannot live inline** — the full transcript, the full
   report matrix, the complete audit trail, the ontology config editor, the cohort matrix. These
   are *reference/expand* surfaces reached by an explicit "open full →", not the working surface.

## 3. Implementation contract (the three layers)

| Layer | File anchor | Contract |
|---|---|---|
| **Shell default** | `apps/shell/src/app.jsx` (`open` state; `doRun`; `onSelectCase`) | `open` initializes **false**. `doRun`/`onSelectCase` set the inline result + `runResult`/`activeCase` but do **not** `setOpen(true)`. The pane opens only via the explicit toggle, an inline card's "Open full →" (`onOpenArtifact`), or an agent `open_artifact` directive that is itself gated to explicit drill-down. |
| **Inline GenUI** | `apps/shell/src/genui/*` + `panes.jsx` (`renderTool`) | The inline result card composes verdict + per-judge votes + findings + the **clinician-verdict form** + calibration, all actionable inline. Each inline card carries an "Open full →" that opens the matching pane tab on demand. No eval step requires the pane to complete. |
| **Agent prompt** | `apps/bff/agent/loop.py` (`_SYSTEM_PROMPT` + the per-call stanza) | Lead with inline GenUI cards (`show_case`, `run_eval`→verdict card, the dissent card). Keep the pane **closed**. Call `focus_artifact(<tab>)` **only** when the human explicitly asks to see the full/raw detail (full transcript, full report, audit, config). The prior "pair the inline card with the pane focus" directive is **reversed**. |

## 4. Demo & assistant discipline

- A conversational demo is driven by **typing intents**, full stop. Reaching for the top-bar
  Run buttons or pane tabs to advance the story is the gimmick tell and is **not allowed** in a
  capture or a live walkthrough.
- The pane may appear in a demo **only** as the payoff of an explicit "show me the full X" — the
  drill-down — never as the place the work happens.

## 5. The flagship acceptance scenario (Dr Sharif / ClinVerdict)

A physician runs ClinVerdict's vaccine-refusal case (case 10) on Lithrim, **entirely by
conversation**:

1. *"Evaluate the vaccine-refusal case."* → inline: the case summary, then the council verdict
   (**approve**) + per-judge votes — in the conversation, pane closed.
2. *"I disagree — the council missed that the note erased the patient's vaccine refusal."* → inline:
   the clinician-verdict (dissent) card; the physician marks **fail**, names the fallacy, records
   it — inline, audited, pane still closed.
3. *"Show me the full transcript."* → **now** the pane opens (the drill-down) with the raw source.

If steps 1–2 require the pane, the build has not met this spec.

## 6. Out of scope (for the first cut)

Full per-case parity across all 10 ClinVerdict cases (one flagship case first, then template);
the cohort matrix; restructuring the config-authoring cards (they already render inline — only
their pane-auto-open is removed).
