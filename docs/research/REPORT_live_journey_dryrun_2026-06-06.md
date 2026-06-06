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
