# SPEC: Flow-Video Pipeline — narrated journey videos for any journey

> A reusable, documented pipeline that turns *any* Lithrim journey we drive on `:5180`
> into a narrated flow video — by authoring a journey spec (steps + flowing-prose
> narration) and handing it to **zyng's API** (the video engine). No more hand-rolled
> Playwright+ffmpeg scripts per video; one convention, one engine, any journey.

> **Status:** DRAFT 2026-06-06. Operationalizes the zyng-API direction confirmed this
> session. Supersedes the bespoke scripts `scripts/build_onboarding_narrated.py`
> (a hand-rolled `zyng narrate`) — see §7.

---

## 0. Context — why this exists

Over this session we produced flow videos three ways, each more correct than the last:
a silent Playwright recording (`record_flow.py`), then a hand-rolled narrated build
(`build_onboarding_narrated.py`), and finally the realization that **zyng already is the
"assets + a flow prompt → narrated video" engine** and exposes it as an API (MCP + CLI).
The hand-rolled scripts reinvented zyng's `narrate` / `record_walkthrough`. This spec
makes the zyng-API path the **canonical, reusable pipeline**: for any journey we build,
we author one journey spec in flowing prose and zyng renders the video.

## 1. The Problem

- **We keep hand-rolling.** Each video has meant bespoke Playwright driving + ffmpeg
  muxing — brittle, per-video, not reusable.
- **No standard journey→video path.** Nothing lets us say "here is the flow, here is the
  narration, make the video" for an arbitrary journey (onboarding today; operator
  journey, calibration trainer, pitch cuts tomorrow).
- **Narration was clipped.** Terse beats, not the flowing prose a watchable video wants.

## 2. Solution — the pipeline (journey → zyng → video)

A journey is captured/driven once and rendered by zyng. There are **three modes**; we pick
per journey by how deterministic the flow is:

### 2.1 The three modes

1. **Walkthrough (drive + narrate, one shot)** — best for **deterministic** flows (e.g. the
   offline 4-act journey). We author a `WalkthroughSpec` (ordered `Step`s, each with a
   `say`); zyng's `record_walkthrough` drives `:5180` with Playwright, screen-records, and
   paces each step's dwell to its narration. One call → narrated video.
2. **Capture → narrate** — best for **live-agent** flows (the conversational journeys,
   where the agent's response time is non-deterministic). We capture a silent recording
   once (`record_flow.py`), then author a `RecordingNarrationSpec` (`source` = the silent
   clip, `beats` = flowing-prose narration with offsets) and run `zyng narrate`. The live
   timing is baked into the recording; narration aligns to it. **This is the right mode for
   the onboarding/operator conversational journeys.**
3. **Capture slices → compose** — for **multi-clip** stories: capture several silent slices
   (`slice_ask.mp4`, `slice_teaching.mp4`, `slice_verdict.mp4`), `ingest_bundle` them, and
   author a `CompositionSpec` — an ordered sequence of `{type:"clip", asset_id, audio:
   "own"|"narrate"|"mute"}` interleaved with `{type:"card", slide}` intro/interstitial/outro
   cards. `zyng compose` fits each clip (letterbox, never crop) and concatenates → one
   narrated MP4. This is the literal "slices of silent recordings + cards → video" path.

All three end in a zyng render with the same goodies: ElevenLabs voice, themes, aspect
(16:9 / 9:16 / 1:1), and an **`.srt` caption sidecar**.

### 2.2 The journey spec (the one thing we author per journey)

The spec IS the reusable unit. For a walkthrough:

```jsonc
{ "title": "Onboarding — teach me from zero", "theme": "midnight",
  "voice": "narrator", "aspect": "16:9", "pronunciation": "lithrim",
  "steps": [
    { "do": "goto",  "value": "http://localhost:5180/", "say": "This is Lithrim…" },
    { "do": "click", "selector": "button:has-text('Shell')", "say": null },
    { "do": "fill",  "selector": "textarea[placeholder*='Ask Lithrim']", "value": "<the novice prompt>",
      "say": "They ask in plain English — I don't know anything about evals or healthcare, teach me." },
    { "do": "press", "value": "Meta+Enter", "say": null },
    { "do": "wait",  "ms": 30000, "say": "Lithrim answers by doing — it reads a real agent and shows the judges grading it…" }
  ] }
```

`Step.do ∈ {goto, click, fill, hover, scroll, press, wait}`; `say` is the narration spoken
while the step holds; `hold_ms` auto-scales to the `say` length (the video paces to the
voice). **The agent authors the selectors** (we built the shell — `button:has-text('Shell')`,
`textarea[placeholder*='Ask Lithrim']`, `text=Sample verdict` — no pixel-guessing.)

## 3. Authoring a new journey — the runbook (do this for ANY journey)

1. **Drive it once manually** (Chrome MCP or `record_flow.py`) to learn the real selectors
   and the visual beats, and to decide the mode (deterministic → walkthrough; live-agent →
   capture-then-narrate).
2. **Write the narration as flowing prose** (§4), one passage per visual beat, describing
   what is happening and why it matters — not UI mechanics.
3. **Author the journey spec** for the chosen mode (`WalkthroughSpec` /
   `RecordingNarrationSpec` / `CompositionSpec`). Optionally let `zyng.authoring` generate a
   first draft of the spec from a natural-language flow prompt, then hand-correct selectors.
4. **Render via zyng** (§6) — MCP `record_walkthrough` / `render_presentation`, or the CLI
   `zyng narrate|compose|render`.
5. **Verify** the output: audio track present, captions readable, narration aligned to the
   on-screen beats (extract frames at beat offsets). Iterate by editing only the changed
   narration passage (cached re-synth) and re-rendering.

The journey spec lives with the journey (e.g. `journeys/<name>.json`); the runbook above is
identical for every journey — that is the reuse.

## 4. The narration convention — flowing prose

- **Prose, not bullets.** Each beat is one to three flowing sentences, written to be heard.
- **Describe meaning, not mechanics.** "It reads a real agent and shows the judges grading
  it," never "now it scrolls to the judge card."
- **Thesis-forward + honest.** Land the grounded-correction insight; never claim a feature
  Lithrim doesn't have (the capability-sheet bound from `SPEC_ONBOARDING_JOURNEY` applies).
- **Voice/pronunciation:** `voice="narrator"` (consistent with the existing Lithrim pitch
  videos) unless a journey wants otherwise; `pronunciation="lithrim"` for our terms.

## 5. Worked example — the onboarding journey narration (full prose)

The onboarding flow (`SPEC_ONBOARDING_JOURNEY`), captured silent then narrated (mode 2):

> **Open.** "This is Lithrim. Watch what happens when someone who has never heard of AI
> evaluation simply sits down and talks to it."
>
> **The question.** "They ask in plain English — *I don't know anything about evals, or
> healthcare; just teach me.* No setup, no jargon, no dashboard to configure first."
>
> **Teaching.** "Lithrim answers by doing. It reaches into a real agent — a clinical scribe
> that drafts visit notes — and shows you the panel actually grading it: a few focused AI
> reviewers called judges, each one watching for a single, specific kind of mistake, which
> Lithrim calls a flag."
>
> **The verdict.** "Then it runs a real evaluation and returns a verdict: reject. But here is
> the idea the whole system is built on. An AI judge can be confidently, fluently wrong — so
> when it is, a deterministic check, grounded in the source the judge never read, quietly
> overrules it. That is what turns a plausible opinion into a verdict you can trust."
>
> **Close.** "From *I know nothing* to understanding evals, judges, flags, and grounding —
> in a single conversation. No manual, no training. That is the onboarding."

(Authored from the live on-screen flow; the same passages drive the `beats` of the
`RecordingNarrationSpec`.)

## 6. Interfaces — how we drive zyng

- **MCP (cleanest "through APIs"):** connect `zyng/mcp_server/server.py` to the session →
  call `record_walkthrough(spec)`, `render_presentation(spec)`, `get_spec_guide()`,
  `list_voices()` directly as tools. Recommended standing integration.
- **CLI (works now, no wiring):** `…/zyng/.venv/bin/python -m zyng.cli narrate|compose|render
  <spec.json> --provider elevenlabs`. The EL key loads from `zyng/.env`.

## 7. The reusable runner + what retires

- **Keep** `scripts/record_flow.py` — repurposed as the **silent-slice capturer** that feeds
  modes 2 and 3 (record-only; no narration).
- **Retire** `scripts/build_onboarding_narrated.py` — it hand-rolled `zyng narrate`. Replace
  its job with a `RecordingNarrationSpec` + `zyng narrate`.
- **Add** a thin `scripts/make_flow_video.py` runner (P1): takes a journey spec + a mode,
  invokes zyng (MCP or CLI), writes the video to `out/`. Small, because zyng does the work.

## 8. Data contracts (zyng models we author against)

- `WalkthroughSpec` { title, theme, voice, aspect, pronunciation, steps:[`Step`] };
  `Step` { do, selector?, value?, hold_ms?, say? } (`zyng/walkthrough.py`).
- `RecordingNarrationSpec` { source, beats:[`NarrationBeat`], intro?/outro?:`Slide`, theme,
  voice, aspect, captions, … } (`zyng/models.py:105`).
- `CompositionSpec` — ordered `{type:"clip", asset_id, audio}` / `{type:"card", slide}`
  segments; `frame:<asset_id>@<s>` pulls a still from a clip (`zyng/compose.py`, models:146).
- Assets via `zyng/assets.py:ingest_bundle()`.

## 9. Acceptance — "any journey" criteria

- **A1 — Generality.** A second journey (e.g. the operator Domain→Judge→Run→Review) is
  rendered through the *same* runbook + spec format, no pipeline code changes.
- **A2 — Prose narration.** Narration is flowing prose (§4), spoken by the zyng voice, with
  an `.srt` sidecar.
- **A3 — Sync.** Narration aligns to on-screen beats (frame-checked at beat offsets);
  live-agent latency is absorbed (mode 2/3) without desync.
- **A4 — One engine.** The video is produced by a zyng render call, not bespoke ffmpeg.
- **A5 — Honest.** No narration claims a capability Lithrim lacks (capability-sheet bound).

## 10. Open questions

- **OQ-1 — MCP vs CLI as the default driver.** MCP is cleanest but needs wiring into the
  session config; CLI works today. Recommend wiring the MCP server once, CLI as fallback.
- **OQ-2 — Where journey specs live.** `lithrim-bench/journeys/*.json` (with the product) vs
  `zyng/out_*/` (with the renders). Recommend `lithrim-bench/journeys/`.
- **OQ-3 — LLM-authored specs.** How much to lean on `zyng.authoring` to draft a spec from a
  flow prompt vs hand-authoring selectors. Recommend hand-authored selectors (we wrote the
  shell), LLM-drafted narration prose.
- **OQ-4 — Live re-capture cadence.** Conversational journeys drift as the shell changes;
  define when to re-capture the silent source.

## 11. References

- zyng: `zyng/walkthrough.py` (`record_walkthrough` / `Step`), `zyng/compose.py`
  (`CompositionSpec`), `zyng/narrate.py` (`RecordingNarrationSpec`), `zyng/authoring.py`
  (prompt→spec), `zyng/assets.py` (`ingest_bundle`), `mcp_server/server.py` (the MCP tools),
  `zyng/cli.py` (CLI), `zyng/out_lithrim_demo/build_bench_demo.py` (the proven reference).
- This repo: `scripts/record_flow.py` (slice capturer, keep), `scripts/build_onboarding_narrated.py`
  (retire → `zyng narrate`), `out/onboarding_silent.mp4` (the captured source), `out/onboarding_narrated.mp4`.
- Specs: `docs/specs/SPEC_ONBOARDING_JOURNEY.md` (the first journey this serves).
