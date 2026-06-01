# SPEC: Lithrim Product Shell — Experience & UI Architecture

> The design-of-record for the Lithrim desktop/VPC product shell. A Claude-desktop-class,
> 3-pane, conversational, generative-UI experience over the WS-0→WS-4a eval harness.
> **No code in this doc.** It supersedes the thin stdlib WS-5 plan and is the contract the
> re-scoped `bench-salvage` WS-5 → WS-5e cycles execute against.
>
> **Status:** v1 draft — direction approved by user 2026-06-01; load-bearing decisions
> recommended here, open questions flagged in §10. **HARD-GATE-class program.**
> **Companion docs:** [`docs/LITHRIM_BENCH_PRODUCT_SPEC.md`](../LITHRIM_BENCH_PRODUCT_SPEC.md) (the product/API/pricing surface), the GTM/journey thesis (open-core + VPC + FDE), `.devloop/state/STREAM_bench-salvage.md` (the harness the shell composes over).

---

## 1. The problem

The harness works (WS-0→WS-4a: `grade → ground(suppress + structural floor) → correction corpus → thin eval-pack → calibration check`) but its surface is `CLI + JSONL`. `CLAUDE.md` parks UI at "phase 4" — **this is that phase.** For the product (open-core desktop + VPC, FDE-led, no US-hosted surface), the wedge is the *experience*: a sleek conversational app that walks a user through standing up a calibrated, tool-grounded eval — far more demoable and adoptable than scripts. This spec pins that experience and the architecture that makes it buildable as **both** a standalone desktop app **and** a VPC-hosted surface from one codebase.

## 2. Target experience — a 3-pane, Claude-desktop-class shell

| Pane | Role | What lives here |
|---|---|---|
| **Left — Navigator / journey rail** | the conversation thread + progress through the calibration-trainer journey | thread list, journey checkpoints (domain → judge → oracle → KB → eval → review) |
| **Center — Conversation + generative UI** | the guided dialogue; **generative-UI components render inline** | system guides setup conversationally; inline components for **input** (flag/severity-map editor, verification-contract builder, KB-binding picker) and for **datapoints** (verdict card, calibration sparkline) |
| **Right — Artifacts / Preview pane** | opens like Claude artifacts / Claude Preview Eval; **fullscreenable** | the **large** surfaces: eval report · judge council · ontology config editor · correction-corpus/flywheel view · calibration report |

The user starts conversationally; the system guides them through the **entire journey** (Judge, oracle, KB setup, run, review); rich/large outputs slide into pane 3 as inspectable, fullscreenable artifacts.

## 3. The load-bearing insight: journey → primitive mapping

**The conversation in the center is writing the SQLite config-plane + ontology; the artifacts in pane 3 are the WS-0→WS-4a primitives rendered rich.** The UI is the human surface over the architecture already built — not a new system.

| Journey step (center, conversational) | Writes (config plane / ontology) | Renders as artifact (pane 3) |
|---|---|---|
| Pick domain / ontology | `Ontology` (WS-1 data model) | **Ontology config editor** (flags/tiers/owners/questions/`verification_contracts` + `severity_map`) |
| Configure the judge council | `EvalProfile.{judges, council_config}` | **Judge council** view (roles, votes, calibration) |
| Set up the oracle (the floor) | `verification_contracts` (WS-3a structural floor) | contract list + a **flip preview** (PASS→BLOCK on a violation) |
| Wire the KB | `EvalProfile.kb_bindings` | KB-binding view |
| Run an eval | drives `scripts/run_eval.py run()` (replay default; live opt-in) | **eval report** (`report.composite` + `calibration_check`) |
| Review | reads the corpus | **correction-corpus / flywheel** view (`corpus-row/1`) |

This is the same "Agent=SUT, SQLite=config plane, ontology=domain, verification-contracts=grounding" architecture from the walking-skeleton — surfaced for a human. Setup-the-Judge / oracle / KB **is** authoring the eval-profile + ontology conversationally instead of by hand-editing JSON.

## 4. Stack (recommended)

- **React + Vite** (not Next.js — a desktop shell needs no SSR; Vite is the Tauri-standard frontend).
- **Tauri v2** — the desktop wrapper (Rust shell; small binaries; native installers).
- **Tailwind (v4) + brand theme** — theme tokens / palette as CSS variables, adapted to the Lithrim brand (palette + type — **open question §10**). Brand look is *ours*, not MUI.
- **Component layer: shadcn/ui (Radix primitives + Tailwind)** — copy-in, fully brand-controllable, Tailwind-native. (`../lithrim-ui` is React/**MUI** — BEHAVIOR-REFERENCE-ONLY; do not code-salvage, and we are not adopting MUI.)
- **State: TanStack Query** (server-state from the BFF) + **Zustand** (pane/journey UI state). Lightweight, no Redux.
- **Chat / generative-UI layer: assistant-ui** (purpose-built React chat + tool→component "generative UI", Tailwind-friendly) or the Vercel AI SDK `useChat` message-parts pattern — see §5b.

## 5. Architecture — the load-bearing decision: the React ↔ Python-harness bridge

The harness is Python; the shell is React/Tauri. The bridge is **a local FastAPI backend-for-frontend (BFF) bundled as a Tauri v2 sidecar.**

```
┌─────────────────────────── Tauri v2 app ───────────────────────────┐
│  React/Vite shell (3 panes)  ──HTTP(localhost:PORT)──▶  FastAPI BFF │
│  (shadcn/ui + Tailwind)                                  (sidecar)  │
└────────────────────────────────────────────────────────────┬───────┘
                                                              │ drives
                          lithrim_bench/harness/ + run_eval ──┤
                          composes over live ──────────────────┘
                            :8002 (council/judge + /v1/kb/search) · :3031 (JUTE)
```

- **Sidecar packaging:** PyInstaller-bundle the FastAPI BFF; declare it in `tauri.conf.json` `externalBin` (with the `-$TARGET_TRIPLE` per-arch suffix); Tauri manages its lifecycle (spawn on launch, shut down with the app). Frontend talks to it over `localhost` HTTP. ([Tauri sidecar docs](https://v2.tauri.app/develop/sidecar/), [tauri-fastapi-sidecar template](https://github.com/AlanSynn/vue-tauri-fastapi-sidecar-template), [production desktop-LLM Tauri+FastAPI+PyInstaller writeup](https://aiechoes.substack.com/p/building-production-ready-desktop)).
- **One BFF, two packagings** (this is what makes the GTM work):
  1. **Standalone desktop** — the BFF as a Tauri sidecar; everything local. The no-US-hosted trust wedge: nothing leaves the machine except calls the user configures.
  2. **VPC-hosted** — the *same* FastAPI BFF run as a container (uvicorn) inside the customer's VPC, React served as static assets. No code fork.
- **Strangler-fig (per [`SPEC_PRODUCT_SERVICE_TOPOLOGY.md`](SPEC_PRODUCT_SERVICE_TOPOLOGY.md), sequencing B):** the BFF targets the **harness**, which composes over live `:8002`/`:3031` *today*. The live Mongo `lithrim-backend` is a **dev-time dependency being strangled**, not a product component — the Python-Layer consolidation (port the v2 council Mongo-free + Mongo→SQLite/PG persistence swap) is a **parallel track**, and the BFF re-points from live-`:8002` to in-process as pieces internalize. **The product path is Mongo-free** (SQLite desktop ↔ PG/Aurora VPC, behind a repository interface).
- **The BFF is the "judge-capability API" we flagged earlier** — building the shell forces that API into existence (a real, documented surface over `run_eval`/the harness + `:8002`/`:3031`). That's a side-benefit, not incidental.

### 5b. Generative-UI component protocol

Generative UI = **tool-call → React component** ([Vercel AI SDK generative UI](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces), [assistant-ui tool UI](https://www.assistant-ui.com/docs/guides/tool-ui)). The conversational engine emits a typed "tool" (`tool-<name>`); the shell maps it to a registered React component that either **collects input** (and returns a result into the conversation) or **presents a datapoint**. For Lithrim the "tools" are the config primitives: `tool-flag_editor`, `tool-contract_builder`, `tool-kb_picker`, `tool-verdict_card`, `tool-calibration_chart`. Pattern reference: assistant-ui `makeAssistantToolUI` (register a component for a tool); AI SDK message-`parts` (`part.state === 'output-available'` → render component).

### 5c. The conversational engine — scripted-default (trust-wedge-driven)

**Default = a deterministic scripted journey state-machine, NOT an LLM-driven chat.** Rationale: a fully-LLM-driven conversation needs an LLM to host — which collides head-on with the **no-US-hosted trust wedge** and air-gapped/VPC deployments. A scripted journey + generative-UI components needs **zero LLM** to deliver the whole setup experience (the "conversation" is a guided flow with rich inline components). **LLM-assist is an opt-in layer routed through the customer's own model** (their VPC endpoint / BYO key), never a Lithrim-hosted US model. This keeps the free-core + air-gapped story intact and is the safer default.

## 6. Contracts the shell defines

1. **Plugin / pane architecture** — the shell loads UI "apps" as plugins (a plugin declares an id + which pane(s) it renders into + its routes). One app initially (the eval journey); extensible by registration, not a marketplace.
2. **Generative-UI component protocol** — §5b: a `tool-<name>` ↔ component registry; components return results into the conversation.
3. **Artifacts-pane contract** — an artifact is `{id, type, payload}`; pane 3 renders the registered artifact component for `type` (eval-report / judge-council / ontology-config / corpus / calibration); supports fullscreen.
4. **Conversational engine** — §5c: scripted journey state-machine (default) + optional customer-model LLM-assist.

## 7. Packaging & GTM tie-in

- **Standalone desktop** (Tauri installers, macOS/Windows/Linux) — the open-core free-core surface; runs local, offline-capable; **no US-hosted surface** (trust wedge).
- **VPC-hosted** — same BFF containerized in the customer's VPC; premium license + FDE onboarding.
- **Licensing** — offline-license verification in the shell (per the GTM; install-friction + offline-license are the named execution risks). **Open question §10.**

## 8. Phasing — re-scope `bench-salvage` WS-5 into a program

The thin stdlib WS-5 is **superseded**. New phases (each HARD-GATE-class; thin vertical first, then thicken):

| Phase | Scope |
|---|---|
| **WS-5** | The **real 3-pane shell skeleton** — React/Vite + Tauri v2 + Tailwind/brand + the FastAPI BFF sidecar — with **ONE vertical working end-to-end**: the **eval-report artifact** in pane 3 over the WS-4a vertical (`run_eval.run`, replay default + one live run). Proves the whole stack + the bridge with one real artifact. |
| **WS-5b** | Conversational **journey layer** (scripted state-machine; left rail + center) — the domain→judge→oracle→KB→eval→review flow writing the config-plane. |
| **WS-5c** | **Generative-UI components** — the inline config widgets (flag/severity editor, contract builder, KB picker) + datapoint cards. |
| **WS-5d** | **Artifacts pane thickened** — judge-council view + ontology-config editor + corpus/flywheel view. |
| **WS-5e** | **Packaging** — Tauri installers (desktop) + the VPC-hosted deployment (containerized BFF + static React) + offline-license. |

(Exact split is a recommendation — the user can re-cut. Each phase gets its own driver via `/devloop-expand-driver`.)

## 9. The honest bet

Building a polished product shell now **front-runs the semantic moat** — the product audit found the moat proven on **HL7-structural, not yet scribe-semantic**, and the engine is still a harness. This is a conscious **GTM/demo/fundraise bet**: a conversational eval-config desktop app is the wedge for design-partners and a raise, and building the shell *forces* the BFF/judge-capability API clarity. It is defensible — but it is a **program**, resourced as phases (WS-5→WS-5e) with HARD-GATE closes, not a casual cycle. Hold the bet consciously: the surface is going ahead of full proof of the core.

## 10. Open questions

- **Brand theme source** — do we have brand tokens (palette, type, logo)? WS-5 needs them to theme Tailwind. If not, a quick brand pass (AIDesigner / design skill) precedes WS-5 visuals.
- **LLM-assist provider** — confirm the opt-in conversational-assist routes only through the customer's model / BYO key (never a Lithrim US-hosted model). Default journey stays LLM-free.
- **BFF API surface** — WS-5 defines v1 of it; this is the "judge-capability API." Lock the first endpoints (run-eval, get-report, get-corpus, read/write-ontology) at WS-5 plan-review.
- **Offline-license mechanism** — deferred to WS-5e; named GTM execution risk.
- **`lithrim-ui` mirroring** — which *behaviors* (not code) to mirror; it's MUI/React, reference-only.

## References
- [`docs/LITHRIM_BENCH_PRODUCT_SPEC.md`](../LITHRIM_BENCH_PRODUCT_SPEC.md) — product/API/pricing surface (this spec is its UI layer)
- `.devloop/state/STREAM_bench-salvage.md` — the WS-0→WS-4a harness the shell composes over
- Harness primitives: `lithrim_bench/harness/{ontology,config,grounding,corpus,evalpack,report}.py` + `scripts/run_eval.py`
- Behavior reference (NOT code): `../lithrim-ui/WORKFLOW_UI_IMPLEMENTATION.md`
- Research: [Tauri v2 sidecar](https://v2.tauri.app/develop/sidecar/) · [Tauri+FastAPI sidecar template](https://github.com/AlanSynn/vue-tauri-fastapi-sidecar-template) · [Tauri+FastAPI+PyInstaller desktop-LLM writeup](https://aiechoes.substack.com/p/building-production-ready-desktop) · [Vercel AI SDK generative UI](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces) · [assistant-ui tool UI](https://www.assistant-ui.com/docs/guides/tool-ui)
