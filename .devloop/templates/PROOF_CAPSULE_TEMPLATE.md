# Proof Capsule — template + convention

> A **proof capsule** is produced at **every A-LIVE attestation** (every live `:5180`/`:8787`/
> `:8002`/`:3031` proof run at a cycle close). It is **two artifacts**: a **proof doc** (the
> durable, auditable written record) + a **narrated video** (the visceral journey artifact). The
> capsule answers: *what changed · what it did to the verdict/behaviour · how it moved our launch
> journey.*
>
> **Convention LOCKED 2026-06-06 (user).** Enforcement (3 places): this template; the monitor
> close-out ritual (`MONITOR.md` Phase 3); the per-cycle driver **D6** (wired into ONB-0 first).
> Memory: `proof-capsule-convention`. Video engine: `docs/specs/SPEC_FLOW_VIDEO_PIPELINE.md` + the
> zyng MCP (`mcp__zyng__*`).

## When it fires
**Every A-LIVE attestation.** If the live test FAILED or surfaced something honestly (a
non-convergence, an over-fire, a loss), the capsule documents THAT — never a manufactured win
(`self-asserting-loop-honesty-moat`). **The honest-Δ IS the proof.**

## The two artifacts
1. **Proof doc** → `docs/research/PROOF_<stream>_<phase>_<YYYY-MM-DD>.md` (skeleton below). Cites the
   evidence blob (`docs/research/RUN_*.json`), the audit record, and the run-id — it *grounds*, it
   doesn't narrate.
2. **Narrated video** → a journey spec `journeys/<stream>_<phase>.narrate.json` (**mode 2
   capture→narrate**, `SPEC_FLOW_VIDEO_PIPELINE` §2.1 — the right mode for live-agent journeys)
   rendered via zyng to `out/zyng_narrate/<name>.mp4` (+ `.srt`). Offline ($0 silent) preview during
   dev; `provider=elevenlabs`, `voice="narrator"`, `pronunciation="lithrim"` for the shipped/pitch cut.

## Proof doc skeleton
```markdown
# Proof — <stream> <phase>: <one-line claim> (<YYYY-MM-DD>)

> A-LIVE attestation. Env: :5180 shell / :8787 BFF / :8002 council / :3031 mapper (as used). $<cost>.

## Claim
<the one thing this proves — e.g. "the chat loop now remembers across turns; S-BS-87 closed">

## What changed
- Commits: <hashes> (branch; pushed?)
- Mechanism / files: <the load-bearing change, 1-3 bullets>

## Before → After
| dimension | before | after |
|---|---|---|
| <behaviour / verdict / metric> | <…> | <…> |
<the delta that IS the proof; an honest loss is reported AS a loss>

## Evidence (grounded, not narrated)
- Run id(s): <…> · audit record(s): <…> · blob: docs/research/RUN_<…>.json
- Reproduce: <the exact $0 replay / command>

## Journey impact
- Launch-journey phase moved: <P1 Install · P2 Verify · P3 Calibration · P4 Scale>
- De-risk gap addressed: <#1 SME-authorable bounded context · #2 governance audit · #3 grounding floor>
- Unblocks next: <…>

## Video
- Spec: journeys/<stream>_<phase>.narrate.json · render: out/zyng_narrate/<name>.mp4 (+ .srt)
- Narration: flowing prose, thesis-forward + honest (capability-sheet bound).
```

## Video runbook (mode 2 — capture→narrate; `SPEC_FLOW_VIDEO_PIPELINE` §2.1/§3/§8)
1. **Capture once, silent:** drive the live attestation (`scripts/record_flow.py` or Chrome MCP) →
   `out/<name>_silent.mp4`. (Live-agent latency is baked into the recording; narration aligns to it.)
2. **Author the spec** `journeys/<stream>_<phase>.narrate.json` (a `RecordingNarrationSpec`):
   `source` = the silent clip; `beats` = one flowing-prose passage per visual beat (what's happening
   + why it matters, **not** UI mechanics); `voice:"narrator"`, `theme:"midnight"`, `aspect:"16:9"`,
   `pronunciation:"lithrim"`, captions on.
3. **Render via zyng** — MCP `mcp__zyng__record_walkthrough` (deterministic flows) / the narrate
   path; CLI fallback `…/zyng/.venv/bin/python -m zyng.cli narrate <spec.json> --provider elevenlabs`.
4. **Verify** (`SPEC_FLOW_VIDEO_PIPELINE` §9): audio present, `.srt` readable, narration aligned to
   on-screen beats (frame-check at offsets); honest (no capability the product lacks). Iterate by
   editing only the changed narration passage (cached re-synth) and re-rendering.

## References
- `docs/specs/SPEC_FLOW_VIDEO_PIPELINE.md` (the reusable journey→video pipeline + data contracts) ·
  `docs/specs/SPEC_ONBOARDING_JOURNEY.md` (the capability-sheet honesty bound)
- zyng MCP: `mcp__zyng__{record_walkthrough,render_presentation,compose_lesson,get_spec_guide,list_voices}`
  · `.mcp.json` → `../zyng/.venv/bin/python mcp_server/server.py` · voices {narrator,founder,agent},
  themes {midnight,dawn,mono}, packs {lithrim,medical}
- Memory: `proof-capsule-convention` · `self-asserting-loop-honesty-moat` · `launch-journey-platform-derisk`
