# Handoff — `bench-salvage` → next session (2026-06-15, conversational-UX + shepherd)

> Two phases closed clean this session + a published demo. The conversational surface
> is now staged/gated/workspace-correct (CONV-UX-1) and the agent leads an onboarding
> journey with a live plan + approval gates (SHEPHERD-1). Driven through the "no inline"
> monitor loop: scope → driver → executor → HARD-GATE fresh-critic → monitor A-LIVE re-drive.

## What landed (branch `bench-salvage/ws6c-dspy`, LOCAL — NOT pushed)

- **CONV-UX-1 CLOSED CLEAN** (`cb0a513..96c1517` impl + `adee6fb` close) — fixed the laggy/abrupt/ungated chat: **W0** server-side `_resolve_chat_agent` killed the `ws0_default` 404-cascade; **W1** the dropped `tool_call` events now render a live activity timeline + animated indicator (static "Thinking…" gone); **W2** token-granular streaming (`include_partial_messages`/`StreamEvent`/`ThinkingBlock`, SDK 0.2.90) + soft block fade; **W3** `show_intent` gating + per-turn card dedup (no more off-context cards). Fresh-critic PASS + monitor :5180 re-drive. Moat zero-diff.
- **SHEPHERD-1 CLOSED PROCEED-WITH-CAVEATS** (`95c427e..725b2e7` impl + `634c680` close) — the agent-led onboarding "shepherd" (walking skeleton, operate-mode). **W1** the SETUP JOURNEY rail is now a LIVE config-derived plan (`journey.js deriveSteps`; "0/5" + Domain NOW); **W2** a proactive plan-aware SUPERSET stanza in `_system_prompt` (the agent opens with guidance + leads the next step + degrades to operator posture when complete); **W3** minimal `onConfigSaved`→`refreshJourney` save→advance; **W4** "Start guided setup" + "Next: <step>" entry. Fresh-critic PASS + monitor :5180 re-drive **CONFIRMED the agent leads** (the vision realized at skeleton level). `tools.py` byte-stable, no new GenUI card types, moat zero-diff.
- **Published demo** (Zyng 0.5.0, hardened flow, honest-Δ): `/Users/aregee/zyng-out/lithrim_shepherd_walkthrough.mp4` (44.8s, Presenter voice) · share `https://app.zyng.work/v1/artifacts/job_878cc388a5ee6d0c` · 67 credits (balance 1406.09). The captured live turn is honestly a touch meandering (user reviewed + approved as-is).

## Open seams (none blocking)

- **S-BS-149 (med)** — rail ↔ active-agent sync gap: the rail derives from the shell's blank New-eval `activeAgent` while the chat shepherd resolves its own agent (`_resolve_chat_agent` → eval-1). They disagree on which agent is being set up; also blocks a clean live W3 save→advance demo.
- **S-BS-150 (med)** — shepherd over-eager: chains many proposals per turn vs the stanza's "one step + wait" (prompt-instructed, not mechanically enforced).
- **S-BS-147** (low) — CONV-UX-1: coalesce consecutive duplicate activity-timeline labels.
- **S-BS-148 / S-BS-151** (low) — getMeta-mock test gap (pre-existing) / dead KB step-prompt entry.
- Pre-existing (neither introduced nor fixed): **S-BS-96** (2 observation import-isolation flakes, pass in isolation), **S-BS-145** (app.test.jsx titlebar fail, identical at parent).

## Next moves (do NOT autostart — user steers)

1. **SHEPHERD-1b** (recommended) — close **S-BS-149 + S-BS-150** to make the shepherd coherent + tight end-to-end (bind the rail to the agent the shepherd configures; firmer one-step-and-wait). Small; the difference between "it leads" and "it leads cleanly," and the precondition for a crisper demo capture.
2. **SHEPHERD-2** — the teach-mode CURRICULUM (concept cards / "your turn" / reveal; `SPEC_ONBOARDING_JOURNEY` tutorial layer), deferred from SHEPHERD-1.
3. **EVAL-FLOW** — the run-the-eval use-case the shepherd guides toward (pick N → evaluate → calibrate → Eval Pack).
4. Owner-gated push (LOCAL SSOT — user keeping LOCAL, explicitly fine).

Resume: `/devloop-resume bench-salvage`; state in `streams.json` current_phase + the SHEPHERD-1/CONV-UX-1 session logs + PROOF capsules; memory `[[shepherd-harness-direction]]`.
