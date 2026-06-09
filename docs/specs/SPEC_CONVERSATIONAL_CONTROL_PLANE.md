# SPEC: The Conversational Control Plane — driving major workflows through chat

> **Status:** MAP / pre-build (2026-06-09). Post-v1 (the launch is the standalone in_process core + the current 8-tool chat surface; this is the next horizon — parked behind the owner-gated push, per the v1-launch CUT). [[conversational-first-core-plugin-line]]
> **Question this answers:** "Can we, through conversation, drive major stuff — demo the seeded packs, swap judge ensembles, mix models?" — and what stands between today and that.
> **Grounded:** every claim below is verified against the running BFF (`:8787`) + `apps/bff/agent/tools.py` + `apps/bff/app.py` on 2026-06-09, not from memory.

## 1. The invariant that shapes everything — A-SAFE

The chat is **author + `$0`-replay + narrate**; the human owns the **paid** trigger. No chat tool carries a `PAID_KEY` (`confirm`/`in_process`/`live`); `run_eval`/`run_eval_pack` hardcode the replay path. This is the **moat** (honest, no runaway spend), **not a limitation to remove.** So "conversationally demo a pack" means: the chat *sets up the config, `$0`-replays, and narrates*; the **real-council run stays the human's "Run live."** The vision is to make that hand-off seamless — never to let the chat spend. Any new tool below is a `$0`, audited config write or a `$0` replay.

## 2. "Major stuff", decomposed into axes (grounded current state)

| # | Axis | What it means | Chat today | Endpoint / tool | Gap |
|---|---|---|---|---|---|
| A | **Replay-demo a pack/case** (`$0`) | run a case, show the verdict from cached results | ⚠️ **`ws0_default` only** | `run_eval`, `run_eval_pack` (replay) | **S-BS-108** — imported cases 500 on replay |
| B | **Real-council demo** (paid) | run the live/in_process council on a pack | ❌ **by design** | human's "Run live" | A-SAFE wall (deliberate) |
| C | **Judge ensemble / roster** | which council roles are active (2- vs 3-judge) | ✅ **yes, `$0`** | `assemble_agent(add_judge, remove_judge)` | S-BS-98 (roster is GLOBAL per-role, not per-agent) |
| D | **Judge lens** | which flags a judge grades (its ontology) | ❌ **UI/API only** | `PUT /v1/judges/{role}` (assign flags) | **no chat tool wraps it** |
| E | **Model-mix** | provider per judge (Azure vs BYO-Claude) | ❌ **UI/API only** | `PUT /v1/judges/{role}` (`model`) | **S-BS-105** + no chat tool |
| F | **Flag authoring** | create/edit safety flags | ⚠️ partial (`create_flag` = non-gradeable only; `author_flag` edits) | `author_flag`, `create_flag` | gradeable-flag create needs a taxonomy re-snapshot |
| G | **Review / narrate** | verdicts, audit, calibration, the pane | ✅ **yes, `$0`** | `get_agent`, `review_runs`, `focus_artifact` | — (works) |

**Seeded inventory (the "packs"):** 5 imported cases across 3 domains — `coding` (1), `scheduling` (1), `scribe` (3: a council-v2 smoke + a clean/violation SOAP pair) — plus `ws0_default`, `s_bs_74_demo`, `uap5a_flip_demo`. A "pack" (`pack_id`) is a **call-time batch of agents**, not a pre-seeded object.

## 3. The honest bottom line

- **Judge ensemble (roster)** → conversationally drivable **now** (`$0`): "drop the policy judge" → a 2-judge ensemble. ✅
- **Demo the packs** → blocked two ways: the **`$0` replay 500s** for the imported packs (S-BS-108, a bug), and the **paid** council demo is the human's button (A-SAFE, by design). Only `ws0_default` replays via chat today.
- **Model-mix + judge lens** → exist at the API (`PUT /v1/judges/{role}`) but **no chat tool reaches them** — they're UI-only.

So the conversation already fully drives the **config plane's roster + flag-edit + review**; the gaps are (a) the imported-replay bug, (b) the missing chat wrappers for judge lens/model, (c) the deliberate paid hand-off.

## 4. The gaps as seams, prioritized

1. **S-BS-108 (the #1 unlock, small):** imported `$0` replay throws `expected str… not NoneType` (replay path-resolution — the dataset/baseline resolves to `None` for imported agents). Fix → the chat `$0`-replays **all** packs. Confirmed still open 2026-06-09.
2. **Conversational judge authoring (new chat tools, A-SAFE-clean):** wrap `PUT /v1/judges/{role}` as a `$0` audited chat tool — **assign a lens** (axis D) and **set the model** (axis E, BYO-Claude/Azure). Mirrors the existing `author_flag`/`assemble_agent` discipline (no `PAID_KEY`; the endpoint holds the guards). This is the biggest *capability* unlock and is fully on-thesis (talk → audited config write).
3. **S-BS-105 (model-mix surface):** the chat tool from #2 + a shell judge/model picker, so the in_process model-mix ladder is drivable (not CLI/SDK-only).
4. **S-BS-98 (per-agent judge store):** today the roster/lens is GLOBAL per-role, so two agents can't hold divergent ensembles. A config-schema refactor; needed only when ensembles must diverge per agent. Bigger.
5. **The paid-run hand-off (keeps A-SAFE):** the chat tees up the config, **`focus_artifact`** the pane, and narrates "click Run live" — optionally an **in-DOM confirm modal** the human accepts (S-BS-69; a native `confirm()` freezes the renderer, [[browser-mcp-confirm-blocks-renderer]]). The chat never holds the trigger.

## 5. The sequence (compose-not-build)

| Phase | Delivers | Composes | A-SAFE |
|---|---|---|---|
| **P0 — the unlock** | chat `$0`-replays all 4 seeded packs + a conversational demo (swap ensemble → replay each) | fix S-BS-108 (replay path-resolution) | unchanged (replay) |
| **P1 — conversational judge authoring** | chat assigns a judge's lens + sets its model (model-mix) | wrap `PUT /v1/judges/{role}` as `$0` audited tools | new tools are `$0` config writes (audited) |
| **P2 — the paid hand-off** | chat sets up → focuses pane → human clicks Run live (the seamless demo) | `focus_artifact` + an in-DOM confirm (S-BS-69) | the human still owns the spend |
| **P3 — per-agent ensembles** | agents hold divergent judge rosters/lenses | S-BS-98 per-agent judge store | config-schema only |

Each phase is independently demonstrable and A-SAFE-bound. P0 alone answers the literal ask ("demo the four packs through conversation"); P1 answers "different judge ensemble / model-mix"; P2 is the polished demo loop.

## 6. What this is NOT (do not weaken)

- **Not lifting A-SAFE.** The chat never spends. Every new tool is `$0`/audited; the paid run is the human's.
- **Not a pre-launch task.** v1 ships the standalone core + the current chat surface first; this is the post-push horizon.
- **Not new infra.** Every phase composes an existing endpoint (`PUT /v1/judges`, `run_eval_pack`, `focus_artifact`) or fixes one bug (S-BS-108). The conversational *control plane* is mostly already built — it just needs three wrappers and one bug fixed.
