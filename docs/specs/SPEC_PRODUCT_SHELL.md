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

### 2.1 The activation journey (4 phases)

The shell's spine is a 4-phase activation arc — canonical brief: [`docs/design/JOURNEY_brief.md`](../design/JOURNEY_brief.md) (this is the GTM calibration-trainer journey):

1. **First contact** — download + journey-mode activates + pick agent type (Scribe) + BYOK config.
2. **The reveal (the "aha")** — a clean exchange → click **Verify** → the four pillar badges (Faithfulness · Completeness · Safety · Structural) + verdict animate in.
3. **Calibration (the product)** — results are *intentionally miscalibrated*; the user's task is to **make the judges right** (tweak the judge council in plain English → Jute structural conditionals; re-run + compare before/after — the iterate loop).
4. **Own it** — load your own conversations, promote findings into your own evalpack, unlock Pro.

Phase 2's verify moment and Phase 3's calibration loop are the **hero screens**. §3 below maps each setup step to the config-plane / ontology primitive it writes.

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

> **CSS/Tailwind sequencing (decision 2026-06-01).** The WS-5 skeleton + the WS-5b journey port ship on the design's **verbatim plain CSS** (pixel-faithful; `apps/shell/src/{styles,journey}.css`). The **Tailwind v4 foundation + `@theme` token bridge + shadcn/ui land at WS-5c** (the first net-new components), mirroring the proven in-family pattern in `../v0-lithrim-landing-page/app/globals.css`, and are adopted **incrementally** — the existing bespoke chrome CSS is **not** rewritten into utilities (high churn / regression risk / low value). Brand consistency holds across both styling systems because both consume one token source (`:root` custom properties ↔ `@theme`).
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

The thin stdlib WS-5 is **superseded**. New phases (each HARD-GATE-class):

> **Amendment 2026-06-01 (front-end-first re-cut).** The original WS-5 row bundled the
> FastAPI BFF + Tauri + one real `run_eval` vertical into the skeleton ("thin vertical
> first"). In practice the shell was built **front-end-surface-first** (a brand-exact 3-pane
> skeleton on representative/mock data — `apps/shell/`), with the bridge sequenced later.
> The WS-5 spec-adherence critique (`.devloop/sessions/critique-bench-salvage-phaseWS-5-2026-06-01.md`)
> flagged this as BLOCKING drift against the old §8 (3 of 5 named components — BFF, Tauri,
> vertical — absent). **Resolution (user, 2026-06-01): re-cut §8 to match the front-end-first
> reality** — WS-5 = the skeleton (the as-built); the displaced "prove the whole stack + the
> bridge" half becomes a new dedicated **WS-5-BFF** phase (still owed, still HARD-GATE, still
> tracked — not dropped); WS-5d shifts from "build" to "wire". The §9 "honest bet" framing is
> unchanged — the surface still goes ahead of full proof of the core; the bridge debt is now
> explicit.

| Phase | Scope |
|---|---|
| **WS-5** ✅ | The real 3-pane shell **skeleton** — React/Vite + brand theme (Tailwind deferred, additive — see §4 + the 2026-06-01 decision) — floating window, 3 resizable panes, journey rail, inline cards (config / verdict / calibration), artifact pane (report / judge-council / config tabs) + fullscreen + light/dark. **Representative/mock data — no BFF, no Tauri yet.** **DONE 2026-06-01** (`apps/shell/`; pixel-faithful Claude Design port, `vite build` clean). |
| **WS-5b** | Conversational **journey layer** (scripted state-machine; left rail + center) — port the 4-phase activation journey (`jp1–jp4`, §2.1) + the domain→judge→oracle→KB→eval→review flow writing the config-plane. |
| **WS-5c** | **Generative-UI components** — the inline config widgets (flag/severity editor, contract builder, KB picker) + datapoint cards (the §5b `tool-<name>` ↔ component registry). **Tailwind v4 foundation + `@theme` token bridge + shadcn/ui are introduced here** (first net-new components; decision 2026-06-01) — adopted incrementally; the existing chrome CSS is **not** rewritten. |
| **WS-5-BFF** (HARD-GATE) ✅ | **DONE 2026-06-01** (`f19dee4..4549a12`; audit CLEAN, fresh-critic NON-BLOCKING). The displaced "prove the whole stack" half: the local **FastAPI BFF** (`apps/bff/`, the judge-capability API v1 — §5/§10) + the React↔Python bridge + **ONE real eval-report vertical** over `run_eval.run` (replay default + one cost-confirmed live run; **live verdict == replay, and the S-BS-7 MED-FP suppression holds on live data**) + the shell's first behavioral test (BFF round-trip smoke). **Tauri sidecar packaging DEFERRED to WS-5e** (the bridge is demonstrable in dev over localhost HTTP; plan-review decision #4). |
| **WS-5d** | **Artifacts pane wired** (re-cut "thickened/build" → **wire**): wire the already-built judge-council view + config/ontology editor (shipped as **mock** in WS-5, `artifact.jsx`) to the BFF + add the corpus/flywheel view. |
| **WS-5e** | **Packaging** — Tauri installers (desktop) + the VPC-hosted deployment (containerized BFF + static React) + offline-license. |

(Exact split is a recommendation — the user can re-cut. Each phase gets its own driver via `/devloop-expand-driver`.)

## 9. The honest bet

Building a polished product shell now **front-runs the semantic moat** — the product audit found the moat proven on **HL7-structural, not yet scribe-semantic**, and the engine is still a harness. This is a conscious **GTM/demo/fundraise bet**: a conversational eval-config desktop app is the wedge for design-partners and a raise, and building the shell *forces* the BFF/judge-capability API clarity. It is defensible — but it is a **program**, resourced as phases (WS-5→WS-5e) with HARD-GATE closes, not a casual cycle. Hold the bet consciously: the surface is going ahead of full proof of the core.

## 10. Open questions

- **Brand theme source** — do we have brand tokens (palette, type, logo)? WS-5 needs them to theme Tailwind. If not, a quick brand pass (AIDesigner / design skill) precedes WS-5 visuals.
- **LLM-assist provider** — confirm the opt-in conversational-assist routes only through the customer's model / BYO key (never a Lithrim US-hosted model). Default journey stays LLM-free.
- **BFF API surface** — **RATIFIED 2026-06-01 (WS-5-BFF; fresh-critic)**, **EXTENDED 2026-06-04 (UAP-1, UAP-2)**. v1 of the "judge-capability API" is locked as: `POST /v1/run-eval` (the eval-report `composite` + a degenerate-N=1 `calibration_check` **folded into the response** — no discrete get-report, since `run_eval.run` has no run-id index), `GET /v1/corpus`, `GET /v1/ontology`, `GET /health`. **`PUT /v1/ontology`** (the clobber-safe working-copy write) ratified at **WS-5d**.
  - **UAP-1 additions (RATIFIED 2026-06-04; SPEC_UNIFIED_AUTHORING_PRODUCT §4):** `GET /v1/agent` + `PUT /v1/agent` (assemble + persist an `Agent` to the config plane — validate-or-422, config-DB-only, never the committed seed); `GET /v1/audit?actor=&target_type=&target_id=&since=` (the config-change audit stream, §2B stream 1); `GET /v1/runs/{id}/audit` (the run-provenance report, §2B stream 2 — a clean 404 for an un-persisted/replay run). Every config write (`PUT /v1/agent`, `PUT /v1/ontology`) is **actor-attributed** (the `X-Actor` header, dev-default fallback) + **audit-logged** (append-only). `POST /v1/run-eval` now resolves the agent's working-copy ontology (R3 draft→grade) and surfaces `ontology_source`.
  - **UAP-2 additions (RATIFIED 2026-06-04; SPEC_UNIFIED_AUTHORING_PRODUCT §4, R2):** `GET /v1/judges?agent=` (list each v2 role + bound model + assignable lens + derived questions + validator refs); `GET /v1/judges/{role}?agent=&assigned_flags=` (one judge's config + the **rendered `role_key_questions`** the prompt↔ontology bridge will send — `base_prompt` is the unassigned seed render, `rendered_prompt` is the effective assignment; the `assigned_flags` CSV drives a live **$0** before/after preview, no model call); `PUT /v1/judges/{role}` (assign a flag lens + bind a model + attach validator refs — **422** on owner↔emit [authority = `LENS_BY_ROLE`/`_TIER1_OWNERS`, *not* the ontology's `owner_roles`], snapshot, or unknown-validator violation; actor-attributed + audit-logged with `target.type="judge"`; config-DB-only, never the seed; validators are **execute-only refs**, never authored/generated here). **`POST /v1/judges/{role}/optimize` is NOT in this surface** — it is UAP-4 (gated S-BS-49).
  - **UAP-3 additions (RATIFIED 2026-06-04; SPEC_UNIFIED_AUTHORING_PRODUCT §5, R4/R6):** `GET /v1/runs?limit=` (run-history — persisted runs newest-first, each row `{run_id, verdict, gate_decision, verdict_flipped_by_stage, agent, ts}` — the `verdict_flipped_by_stage` field reconciled in at UAP-3 close to match the shipped `_run_summary` projection, S-BS-67 — every `run_id` round-trips to `GET /v1/runs/{id}/audit`); `POST /v1/eval-pack/run {pack_id, agents[], live?}` (batch a pack via `evalpack.build_pack` → the frozen pack + the run ids; replay `$0` default, `live` paid; replay/live only — `build_pack` has no in_process param this cycle); and `POST /v1/run-eval` now **surfaces `pipeline_run_id`** (the addressable run id; S-BS-56). Run-provenance is persisted for **all three** grade paths now — replay + live + in_process (S-BS-52) — so the `$0` replay default appears in run-history and is auditable; the prior "replay runs are not audited" 404 copy is retired (an unknown/never-run id is still a clean 404). The in-process grade is built with the agent's **authored judge assignments** (S-BS-63), so an authored judge re-votes with its authored lens (live `:8002` per-judge assignment-injection stays WS-2-backend-gated).
  - **S-BS-51 reconciliation:** the WS-7a journey additions (`GET /v1/case`, the `council` view on `/v1/run-eval`, the `in_process` field) are **ratified here** as part of closing the unratified-growth pattern — the surface grows through §10, not around it.
  - This as-locked shape is the contract of record; it supersedes the earlier "run-eval / get-report / get-corpus / read-write-ontology" sketch.
- **Offline-license mechanism** — deferred to WS-5e; named GTM execution risk.
- **`lithrim-ui` mirroring** — which *behaviors* (not code) to mirror; it's MUI/React, reference-only.

## References
- [`docs/LITHRIM_BENCH_PRODUCT_SPEC.md`](../LITHRIM_BENCH_PRODUCT_SPEC.md) — product/API/pricing surface (this spec is its UI layer)
- `.devloop/state/STREAM_bench-salvage.md` — the WS-0→WS-4a harness the shell composes over
- Harness primitives: `lithrim_bench/harness/{ontology,config,grounding,corpus,evalpack,report}.py` + `scripts/run_eval.py`
- Behavior reference (NOT code): `../lithrim-ui/WORKFLOW_UI_IMPLEMENTATION.md`
- Research: [Tauri v2 sidecar](https://v2.tauri.app/develop/sidecar/) · [Tauri+FastAPI sidecar template](https://github.com/AlanSynn/vue-tauri-fastapi-sidecar-template) · [Tauri+FastAPI+PyInstaller desktop-LLM writeup](https://aiechoes.substack.com/p/building-production-ready-desktop) · [Vercel AI SDK generative UI](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces) · [assistant-ui tool UI](https://www.assistant-ui.com/docs/guides/tool-ui)
