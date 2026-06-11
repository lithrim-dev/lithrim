# HANDOFF — bench-salvage — 2026-06-11 (LIVE product demonstration + zyng recording; composition cut pending)

> **For the next session.** This thread is the **product demonstration + video recording** track (not a devloop code cycle). We drove the REAL product live, proved the two defensible/unique pillars, recorded a complete voiced walkthrough via zyng, and are mid-decision on a **composition highlight cut**. Resume by reading memory `demonstrate-live-not-scripted` + `launch-journey-platform-derisk` + this file. **Services must be up** (the user runs them; `curl`-check, never autostart).

## 🔴 IMMEDIATE NEXT — the composition highlight cut (the user's open ask; awaiting go/tweak)
Build a ~80s highlight from the full demo video using zyng's **CompositionSpec** (one upload → multiple trims + interleaved slide cards → one MP4). **$0** (ffmpeg trims + rendered cards; no re-drive, no live spend). Proposed cut (offsets from `live_eval_loop_voiced.srt`):
```
card  "Lithrim — what a panel of LLM judges can't do"
card  "1 · A deterministic floor overrules a confidently-wrong judge"
clip  out/zyng_narrate/live_eval_loop_voiced.mp4  trim 108–134s  audio=own   ← live BLOCK + grounded suppression
card  "2 · Honest calibration — it won't manufacture a win"
clip  out/zyng_narrate/live_eval_loop_voiced.mp4  trim 262–306s  audio=own   ← held-out Δ + close
```
**Open decision for the user:** build it now / adjust trims+copy / voice the cards too (small ElevenLabs add vs silent text cards). The user has NOT yet said "go" — confirm before rendering.

**HOW to build it (verified locally 2026-06-11):**
- There is **NO `compose` CLI subcommand** → drive `zyng.compose.compose(spec, bundle, out_dir)` programmatically via a short script (run from `cwd=/Users/aregee/Workspace/github.com/zyng`, `.venv/bin/python` — `zyng` imports there).
- `compose.py:110` = `compose()`; `compose.py:145` cuts `ss=seg.trim_start_s, to=seg.trim_end_s` (CONFIRMED it trims). Frame-still refs (`frame:asset@s`) supported (`resolve_frame_refs`, compose.py:51).
- Models (`zyng/models.py`): `CompositionSpec` (:146), `ClipSegment` (:133 — `asset_id, audio, beats, trim_start_s, trim_end_s, embed`), `CardSegment` (:128 — `slide: Slide`), `CLIP_AUDIO={own,narrate,mute}` (:125). `audio="own"` keeps the clip's existing EL voiceover.
- The clip needs an `asset_id` from an `AssetBundle` (`zyng/assets.py`: `AssetBundle`, `Asset(kind="video", has_audio=True, ...)`). Find/confirm the ingest helper (the `def ingest_bundle` wasn't located in the head grep — may need to build `AssetBundle(assets=[Asset(...)])` directly, or read assets.py fully).
- Status caveat (per the user's note): CompositionSpec is built+validated but **deferred behind the data-report launch** — real capability, just not CLI/studio-surfaced.
- The parked alternative the user mentioned (tighten conversational "10–20s" → exact-trim parsing) is a **zyng-engine** change, NOT our demo — leave parked unless asked.

## ✅ What's recorded (out/zyng_narrate/)
- **`live_eval_loop_voiced.mp4`** (~5:10, 16:9, **ElevenLabs voice** + `.srt`) — THE deliverable: the full live loop end-to-end. h264+aac confirmed.
- `live_eval_loop_offline.mp4` (silent validation take + `.srt`) — frame-verified the beats rendered (grounding @~95s, optimize Δ @~245s). Backup / the narrate source.
- `activation_journey_voiced.mp4` (the earlier **scripted 4-act demo**, OpenAI voice) — SUPERSEDED; the user rejected scripted demos in favor of the real-product one.
- Reusable specs: `journeys/live_eval_loop.{walkthrough,narrate}.json` (+ `activation.walkthrough.json`). **All uncommitted** (artifacts; out/ videos are large — don't git the mp4s; the journeys/*.json specs are worth committing if asked).

## 🎯 The demonstration (proven LIVE this session — the two pillars)
Drove the REAL product at `:5180/` (Chrome-MCP on **Brave**, ~$1–1.5 spend, user-authorized) as a user: **author a risk judge** (live BYO-Claude agent + audit trail) → **live in-process council** (paid, in-DOM CostModal) → **BLOCK** verdict + **grounding-floor suppression** → **show_case** planted-label diagnosis → **Optimize calibration-trainer** → honest **held-out Δ**.
1. **Grounding moat:** `risk_judge` fired `MEDICATION_NOT_IN_TRANSCRIPT` (conf 0.74) but its **own evidence span quoted the transcript line where zidovudine IS present, as proof of absence** — a confident self-contradiction. The deterministic `med-presence-check` floor disproved + suppressed it (tool-verified, auditable). Verdict stayed correct (`reject` on the real fabricated PMH; `calibration_check` PASS). **No LLM-judge panel can do this.**
2. **Honest calibration:** the trainer reported **graded 0.80→0.70 (Δ −0.10), precision −0.09** — *"optimize did not improve this judge… the accept-gate is never loosened to manufacture a win."* The anti-manufactured-win moat.

## ⚙️ zyng recording mechanics (LESSONS — critical to not re-learn)
- **MCP (`mcp__zyng__*`) TIMES OUT** ("Connection closed") on long (~4-min) walkthroughs → use the **CLI** for long flows: `cd …/zyng && .venv/bin/python -m zyng.cli {walkthrough|narrate|lesson|render} <spec> --out <dir> --provider <p>`. **CLI provider = `offline|elevenlabs` only** (`openai` is MCP-only).
- **Headless viewport:** WalkthroughSpec defaults 16:9 → **1280×720**, which COLLAPSES the 3-pane shell + hides the chat input → set `"viewport": [1920,1080]`. Also bump the opening `wait` (cold load); even so the **first `fill` flakes** non-deterministically.
- **Robust voiced path (used):** drive ONE `--provider offline` walkthrough (validates + captures `_source_silent.mp4`), **frame-verify**, then `zyng narrate` (RecordingNarrationSpec: `source`=the offline mp4, `beats=[{id,offset_s,text}]` from the `.srt`) `--provider elevenlabs` → overlays voice on the verified footage, **NO re-drive, NO live re-spend, NO re-roll**. (Re-driving live re-spends + re-rolls non-deterministic results — avoid for re-voicing.)
- ElevenLabs key is in `zyng/.env`; the `lithrim` pronunciation dict 400s (cosmetic). Narration is **capability-framed** (honest regardless of the take's exact live numbers).

## 🔌 Live-product driving (Chrome-MCP)
- Browser: **Brave** has the extension, but `list_connected_browsers`/`switch_browser` return empty — connect via **`tabs_context_mcp({createIfEmpty:true})`** (it works). Tab id was `1030124583` (will differ next session).
- Selectors: chat input `textarea[placeholder*='Ask Lithrim']`; send `[data-testid='chat-send']`; clicking a suggestion FILLS the input (doesn't auto-send). Paid gate = **in-DOM `CostModal`** (panes.jsx, driveable — NOT a native `confirm`): `button:has-text('Run live (paid)')`, `button:has-text('Run optimize (paid)')`; the JudgeEditor optimize = `button:has-text('Optimize')`.
- The demo agent: `ws0_default` (the mixed by-construction scribe case `bench_scribe_v1_inject_condition_1bd0f10dc7b5` — injected diabetes/PMH = the planted defect; the med over-fire is the context-primed one the floor catches).

## 🧭 Devloop background (this repo's monitor track — separate from the demo)
PACK-2b CLOSED 2026-06-11 (council OWNER-MAP un-freeze) → with PACK-1b (taxonomy), **the frozen council's clinical DATA is fully pack-resolved**; the relocation arc + clinical-data un-freeze are done. HEAD on `bench-salvage/ws6c-dspy` (close `13a6cb9`), NOT pushed (LOCAL is SSOT). NEXT devloop (if/when): optional **2c** (roster/`LENS_BY_ROLE` un-freeze — frozen-seam, explicit-authorization-gated) or cleanups (S-BS-122 done; docstring-scrub; S-BS-117). See `STREAM_bench-salvage.md` + memory `healthcare-realm-as-pack`. **The owner-gated push of the local stack is still owed** whenever the user wants it off-machine.

## Pointers
- Memory: `demonstrate-live-not-scripted` (the directive + the 2 pillars + the mechanics), `launch-journey-platform-derisk`, `proof-capsule-convention`, `self-asserting-loop-honesty-moat`.
- `docs/specs/SPEC_FLOW_VIDEO_PIPELINE.md` (the recording runbook + the 3 modes). zyng repo: `/Users/aregee/Workspace/github.com/zyng` (compose.py / narrate.py / walkthrough.py / models.py / assets.py / cli.py; `.venv`; `.mcp.json` wires the MCP).
- Standing: no autostart; user-authorized paid runs (okay with demo spend); honesty-only (no manufactured wins); pathspec-only commits if committing.
