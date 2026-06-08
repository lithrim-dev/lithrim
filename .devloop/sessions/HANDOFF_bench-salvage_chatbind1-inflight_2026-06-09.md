# HANDOFF — bench-salvage (monitor role) — 2026-06-09

> **For the NEW monitor session.** Long multi-cycle session. Three cycles closed (FLAG-1, S-BS-74,
> DOGFOOD-1), the platform **live-attested via UI dogfooding**, and **CHATBIND-1 is in-flight** —
> plan-review APPROVED + the GO relayed; the executor is implementing.
> **Resume:** `/devloop-resume bench-salvage`, then read this, then process the CHATBIND-1 return.

## 🔴 IMMEDIATE STATE — CHATBIND-1 in-flight (go given, executor implementing)
The CHATBIND-1 executor posted a strong plan-review and **the monitor GAVE THE GO** (the paste-ready go block is the last assistant message in the prior transcript; re-relay if needed). The executor is implementing **D1 + D2 only**:
- **D1** — make the chat loop's system prompt **active-agent-aware**: a new `_system_prompt(ctx.default_agent)` that names the active agent + "operate on it by default; 'this case'/'the runs' mean `<active_agent>`." The **only** `loop.py` change is `system_prompt=` at `:112` — the deny-hook / `bypassPermissions` / `setting_sources=[]` / `allowed_tools` / `max_turns` stay **BYTE-IDENTICAL** (A-SAFE).
- **D2** — scope `_review_runs` (`app.py:1295`) to `req_agent` (fetch ~200 < the 500 cap, filter on the `agent` field already on each row, truncate to limit). The frozen `list_runs_endpoint`/`list_all` untouched.
- **DROPPED** (the executor's catch, monitor-confirmed): the driver's deliverable-#2 closure default (`agent or req_agent`) is **unreachable dead code** — `tools.py:194/210` already resolve `args.get(...) or ctx.default_agent` before calling the closure. Do NOT add it.

**Why this matters (the corrected diagnosis):** the chat→BFF→`req_agent` chain was ALREADY wired (`app.jsx:183` → `bff.js:182` → `app.py:1393 _build_tool_context(req.agent)`). The real S-BS-103 bug is (a) the static `_SYSTEM_PROMPT` never names the active agent → the model emits `"ws0_default"` explicitly, and (b) `review_runs` lists ALL runs unscoped. My driver's v1 blamed the shell (wrong); v2 corrected it to the BFF loop; the executor's plan-review refined it further (the prompt is THE fix; the closure default can't fire). The corrected-diagnosis flow worked.

## At CHATBIND-1 close (the new monitor's job)
7-item audit + **HARD-GATE fresh-critic** (cold general-purpose Agent, isolated worktree, same pattern as DOGFOOD-1's `a33d9235c4d470a4d`). The critic must independently confirm: **`loop.py` diff = `system_prompt=` only** (deny-hook + options byte-identical); **no paid knob** (`run_eval_replay` stays `live=in_process=False`; no `PAID_KEYS`); the **`review_runs` agent-scoping is NON-VACUOUS** (seed runs under two agents → only `req_agent`'s returned; fails on current code); the prompt names the active agent (A1); the frozen ops + audit gates untouched. Then close (critique + STREAM seam (close S-BS-103) + streams.json + index + memory + a close commit, pathspec-only). The A-LIVE is a USER-RUN `$0` smoke (select an imported case → chat "show + review this case" → the agent targets it; imported cases lack a baseline so there's no replay verdict — get_agent + review_runs is the demo).

## The arc this session — 3 cycles CLOSED + the platform live-attested
| Cycle | Status |
|---|---|
| **FLAG-1** (flags CRUD) | ✅ CLOSED CLEAN — **all 3 of the 2026-06-07 objectives done** (UX-1 + BYOC-1 + CRUD-from-clean). Deviation: delete = the 11th conv tool. |
| **S-BS-74** (live grounding-flip demo) | ✅ CLOSED PROCEED-WITH-CAVEATS — an **HONEST DOCUMENTED LOSS** (the flip didn't reproduce; the over-fire is context-primed → memory `live-overfire-context-primed`; seam S-BS-100). The honesty IS the proof point. |
| **S-BS-49-WIN** (optimize-win attempt) | 🅿️ **PARKED** — driver authored + registered (combined corpus + selection interleave); the user pivoted away before execution. Resume anytime. |
| **DOGFOOD-1** (import → judge-set ladder → eval-pack CI/CD gate) | ✅ CLOSED PROCEED-WITH-CAVEATS — the generic platform proven end-to-end on real lithrim-backend cases; the `lithrim-bench-pack` gate = the **lithrim-sdk parity, Mongo-free**. fresh-critic `a33d9235` NON-BLOCKING. **A-LIVE attested via UI dogfooding** (below). |
| **CHATBIND-1** (bind chat to active agent) | 🔄 **IN-FLIGHT** (go given). |

**A-LIVE — live UI dogfooding (DOGFOOD-1, monitor-driven via Chrome MCP, paid-authorized, no autostart):** seeded the 5 imported cases into the running BFF (`seed_config_db` → `out/config/bench_config.sqlite`); 2 `Run live` (`:8002`) evals on real imported cases — **NKA clean → approve** (0 findings; the v2 council correctly did NOT false-flag FABRICATED_ALLERGY) + **diabetes violation → reject** (BLOCK, 12 findings, **1 grounding-suppression visible live**). The platform runs real evals on real cases live, grounding floor visibly correcting. **2 screenshots saved to disk** (for the video). The model-mix composition contrast remains owed (in_process-only; the shell can't drive it = S-BS-105 = CLI/SDK-only).

## Git state (NOT pushed — owner-gated)
- Branch `bench-salvage/ws6c-dspy`, **HEAD `6e19e5a`** (the CHATBIND-1 v2 driver). A **large unpushed stack** (everything since the branch diverged — UX-1 through here). Pushing/PR is owner-gated.
- Working tree: `M apps/shell/src/root.jsx` (a concurrent session's deliberate change — LEAVE it) + 3 foreign untracked (`.claude/`, the `KICKOFF_CRITIC_…WS-6c-DSPy…`, `docs/research/REPORT_fhir_agentbench…`).
- **All monitor commits pathspec-only** (`git commit -- <files>`; never bare — the dirty shared tree). [[git-commit-pathspec-dirty-index]]
- Services were up: `:8002` council (healthy), `:8787` BFF, `:5180` shell. **Don't autostart** — `curl /health` first.

## Open seams (current — DOGFOOD-1 dogfooding opened 5)
- **S-BS-103** (med) the chat operates on `ws0_default` not the active agent → **CHATBIND-1 fixes it (in-flight; close it at CHATBIND-1 close).**
- **S-BS-105** (med) the shell UI can't drive the `in_process` model-mix ladder (CLI/SDK-only) — a future shell enhancement (expose `in_process` + a judge-set picker).
- **S-BS-104** (low) the live council over-fires on imported scribe cases + the artifact is free-text-not-JSON (the `imported_demo` cases are second-class).
- **S-BS-101** (low) single-judge roster degenerates at the frozen `min_valid=2` floor · **S-BS-102** (low) `pack_gate` skips orphan outcome rows.
- **S-BS-98** (med) the judge store is GLOBAL per-role not per-agent (the per-agent-judges refactor; S-BS-103-adjacent) · carried: S-BS-91/93/95/96/97/99/100.

## Gated / parked / owed (the fork after CHATBIND-1)
- **OWED — the narrated video walkthrough** (the DOGFOOD-1 proof capsule, elevated): live-captured from the shell (Chrome MCP) + concept slides, via zyng (`record_walkthrough`/`compose_lesson`/`render_presentation`; offline `$0`, ElevenLabs = paid voice). Honest-Δ only. **After CHATBIND-1** (which enables the fully-chat-driven imported-case demo). The user's arc: thesis-slide → live demo → moat → architecture → GTM. Memory `proof-capsule-convention`. NOTE: the zyng MCP flaps connected/disconnected — reconnect-check before producing.
- **GATED on the user resolving SPEC_PLUGIN_ARCHITECTURE OQ-1..3** (esp. **OQ-1 the Core/Pro line**): the **HPACK-1** terminology-floor driver (RECONNED — agent `a52c03ea`; the Hermes SNOMED floor rides the bench-local `structural_codes`, NO cross-repo dep; the one risk is the A-SAFE deny-hook widening for the Hermes MCP, S-BS-90-adjacent) + the **Plugin Phase-1** registry-refactor driver. Can't author HPACK cleanly until OQ-1 decides what's pro. Spec at `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md`.
- **PARKED:** S-BS-49-WIN (optimize-win; driver ready). The S-BS-46/49 corpus-deepening fork. The S-BS-70/S-BS-100 near-miss visceral-flip.

## Standing context for the monitor
- **The user runs the executor sessions** (pastes the kickoff into a fresh session; brings the plan-review + the return back to the monitor). The monitor audits, gives the go, runs the fresh-critic at close, commits the close artifacts (pathspec-only).
- **Prefs:** no autostart (`curl /health`, halt+ask if down); no push without explicit owner approval; LLM-cost-conscious (the user authorizes paid runs explicitly — e.g. they said "you will do the live run" for DOGFOOD-1's UI dogfood); **honest-Δ only** (no manufactured wins — an honest loss/non-result is a PASS, documented); proof capsule = doc + zyng video at every capability A-LIVE.
- **Diagnose-before-edit cuts both ways:** this session's drivers had two diagnosis errors that re-grep / the executor's plan-review caught (S-BS-74's cost-gate drift; CHATBIND-1's wrong shell root-cause). Re-grep every file:line at driver-authoring (Phase-1a); trust the executor's verbatim evidence.
- **Strategy (the through-line):** generic open eval platform (the OSS bench) + premium VERTICAL packs (healthcare) = the moat horizontal players can't touch. The plugin architecture (open-core/pro) is the packaging backbone. The dogfooding proved the platform is genuinely usable on real data (with the 5 gaps it honestly surfaced). Memory `three-objectives-ux-crud-byoc-2026-06`, `launch-journey-platform-derisk`, `gtm-launch-and-journey-thesis`.

## Pointers
- Drivers: `.devloop/prompts/bench-salvage_phaseCHATBIND-1_chat-active-agent-binding_driver.md` (v2, ready, in-flight) · `…phaseDOGFOOD-1…` (closed) · `…phaseS-BS-49-WIN…` (parked) · the HPACK-1 driver is NOT yet authored (reconned only).
- Closes: `critique-bench-salvage-{FLAG-1,S-BS-74,DOGFOOD-1}-2026-06-0{8,9}.md` (DOGFOOD-1's has the **post-close live-dogfooding addendum** — the A-LIVE + S-BS-103/104/105). Session logs alongside.
- Specs: `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (DRAFT, OQ-1..3 open).
- State: `STREAM_bench-salvage.md` (First-move topped with DOGFOOD-1) + `streams.json` (current_phase = DOGFOOD-1 close + CHATBIND-1 next) + `prompts/index.json` (56 bundles; CHATBIND-1 status ready).
- Memory: `live-overfire-context-primed`, `three-objectives-ux-crud-byoc-2026-06`, `git-commit-pathspec-dirty-index`, `proof-capsule-convention`, `byo-claude-provider-thesis`, `conversational-authoring-surface-complete`.
