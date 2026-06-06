# Live from-scratch journey dry-run — 2026-06-06

> Monitor drove the conversational authoring journey live in-browser (Chrome MCP) on
> `:5180`, BYO-Claude, `$0` (replay tools + per-message Claude calls on the local CLI).

## Verdict

The **conversational from-scratch journey works live end-to-end**: talk → in-process
SDK-MCP tools → audited writes → gen-UI cards. Drove **Domain → Judge → Run → Review**
(the Flag leg was offered by the agent, not explicitly driven — same `author_flag`
edit pattern as the proven `author_judge`). The gaps found are polish, not plumbing.

## Legs exercised (live)

| Leg | Tool(s) fired | Result |
|---|---|---|
| Domain | `get_agent` + `get_judge`×3 (parallel) | accurate roster: 3 judges, domain `clinical/1`, tool `presence_check`; agent printed a per-judge lens table + owner↔emit check, and surfaced caveats unprompted (faithfulness_judge 0 derived Qs; all models `(unbound)` → paid run not wired, replay `$0`) |
| Judge | `author_judge` (`PUT /v1/judges`) | **audited write went through** (faithfulness_judge, rationale captured, actor dev-default) + a `tool-judge_editor` card + an audit-summary table |
| Run | `run_eval` (replay) | **REJECT/BLOCK**, run `a57bd49d`, `$0`; honest cost note ("replay over stored outputs … a live run has to go through the cost-confirm modal") + a Sample-verdict card |
| Review | `review_runs` | Sample-verdict card + Audit-trail card (why·when·who·what config-change log) |

## Seams opened

- **S-BS-87 (med) — the `/v1/chat` loop is stateless per message (no cross-turn memory). CONFIRMED in code:** `ChatRequest` is `{message, agent}` only (no history/session); `bff.js chatStream` sends no thread; `agent/loop.py:_real_source` does `client.query(message)` on a fresh `ClaudeSDKClient` (`max_turns=12` *within* one message). So it chains the full Domain→Judge→Flag→Run→Review inside a single rich message, but carries nothing across messages — the agent re-orients from live config each turn and cannot track "what we just changed" (observed live: turn-3 said "no config writes this session," missing the turn-2 audited `author_judge` write). Single-shot journey = fine; multi-turn conversation = not memory-coherent. Fix: thread conversation history into `ChatRequest` + replay to the loop (or persist a session).
- **S-BS-88 (low) — agent-id grounding nit:** mid-Judge-leg the agent said "`default` wasn't found in the config DB" before recovering on `ws0_default`. A loop system-prompt grounding fix (always use the bound agent id).
- **S-BS-89 (low) — "New evaluation" (+) is a non-functional skeleton stub** (`apps/shell/src/panes.jsx:29`): no blank-slate reset, so "from scratch" starts from the default `ws0_default` agent, not an empty one.

## Readiness

The conversational from-scratch journey is **ready to demo live today**. Remaining gaps are
polish: cross-turn memory (S-BS-87), agent-id grounding (S-BS-88), the new-eval stub
(S-BS-89), model-binding for *paid* runs (agent-flagged; replay is `$0`), and conversational
flag *creation* (S-BS-83, `author_flag` edit-only). The 4-act *pitch demo* remains separate —
only Act 2 ("Verify") is live-wired.

---

## Onboarding de-risk probes — 2026-06-06 (`$0`)

Two cheap live probes to retire the biggest unknowns of the ONB workstream
(`SPEC_ONBOARDING_JOURNEY.md`) **before** building.

### Probe B — aha reliability → PASS
Two `$0` replays of `ws0_default` were byte-identical (~5ms each): pre-grounding **BLOCK**
→ composite **reject**, `MEDICATION_NOT_IN_TRANSCRIPT` suppressed by `med-presence-check/v1`
("zidovudine … present verbatim in the transcript"). **The aha is deterministic + free via
a curated replay** → resolves spec OQ-4; the council-non-determinism risk is sidestepped.

### Probe A — teaching quality → STRONG PASS (+2 refinements)
Primed the existing **operator** chat agent as a teacher for a total novice in ONE rich
message (no code). Result: a **frontier-grade guided arc** — defined every term
(Agent/SUT, Eval, Flag, Judge, Grounding) in plain English, grounded in the REAL config +
a real `$0` replay (BLOCK), plain-English flag glosses, step-by-step structure, and a
correct "the insight" explanation (confident AI judge vs deterministic check → the check
overrides → trustworthy verdict). It stayed **honest unprompted**: flagged that it cannot
invent a flag (S-BS-83) and that the replay summary lacked per-judge votes so it described
the override *mechanism* rather than fabricating numbers (the A4 honesty bound, emergent).

**→ De-risks the core bet: the teach-mode PROMPT + curriculum is the main lever, and it
works.** Two refinements surfaced (neither invalidates the spec):
1. **The aha was *explained*, not *shown*.** The chat run-tool result didn't expose the
   suppression detail to the agent, so it couldn't vividly show "judge said NO-MED, but
   it's there → overridden." Phase 3 must surface the grounded suppression payload to the
   teach agent / `tool-reveal` (Probe B confirms the data is in the replay).
2. **It rendered operator cards** (Agent *editor* with "Save agent", Judge editor) + long
   text walls — confirming the Phase-2 teaching-gen-UI gap is real and matters for a novice.

**Net:** Phase 1 (teaching brain) is de-risked as low-risk/high-payoff. The real remaining
work is exactly the spec's phases: Phase 0 (memory, for multi-turn), Phase 2 (teaching
gen-UI, so it's not text walls), Phase 3 (surface the suppression for a *shown* aha).
