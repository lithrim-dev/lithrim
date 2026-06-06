# HANDOFF — `bench-salvage`: pitch + de-risk arc (2026-06-06)

> Written by the monitor at the close of a strategy/pitch/de-risk session (monitor↔founder,
> not an executor cycle). Load-bearing context for the next session to **resume the de-risk
> discussion + start executing it.** Pairs with the auto-memory
> `launch-journey-platform-derisk` (loaded into every new session).

---

## What this session did (the arc)
1. **Cleared the owed UAP-5a A8** `:5180` smoke — attested LIVE (commit `0a0c87e`).
2. **S-BS-86 found + fixed** — the active draft ontology under-blocked (`HIGH=0.45 < 0.5`), so a
   fabrication-laden note scored `needs_review` not `reject`. The **calibration check caught it
   (match 0.0)**; restored the weights (audited, with a rationale); **re-ran live → `reject`,
   calibration `0.0→1.0`**. This is the Phase-3 calibration loop, lived for real. Opened
   **S-BS-87/88/89** from a live conversational-journey dry-run.
3. **Locked `SPEC_ONBOARDING_JOURNEY`**; wrote **`SPEC_FLOW_VIDEO_PIPELINE`** (a reusable,
   zyng-API narrated-journey-video pipeline); produced 2 narrated recordings.
4. **Synthesized the strategic arc** from `~/Documents/lithrim_bench_launch_journey.svg`:
   `docs/strategy/PITCH_journey_proof.md` (claim↔proof, proven-live vs roadmap) +
   `docs/strategy/PLATFORM_THESIS_bounded_context.md` (the de-risk roadmap).
5. **Confirmed the zyng MCP** is configured (`.mcp.json`) + functional; needs a session reconnect.

## The direction we're moving toward (de-risking)
**Lithrim = the SME↔Engineering shared bounded context (the ontology) as a governed-AI control
plane** — governance/policy · domain · ops · calibration converge on one versioned, executable,
auditable, calibratable artifact. **Healthcare-first.** The de-risk roadmap
(`PLATFORM_THESIS_bounded_context.md` §4-5):
- **#1 SME-authorable bounded context** (criteria *minting*, not just editing) → S-BS-83, S-BS-87, `SPEC_ONBOARDING_JOURNEY`
- **#2 governance-grade audit** (no blank-rationale policy edits; immutable/exportable) → S-BS-86b
- **#3 grounding floor + withstands-gate under every judge** → S-BS-74
- then scale: multi-domain bootstrapping · SME↔Eng RBAC + SDK · Tauri/VPC packaging
- **Do #1-3 → the platform is de-risked AS A GOVERNANCE CLAIM.**

## NEXT MOVE
**De-risk #1, Phase 0 = S-BS-87 (conversational memory)** — already specced
(`SPEC_ONBOARDING_JOURNEY` Phase 0) + probe-de-risked this session (teaching brain works; the aha
is deterministic). Expand the driver: `/devloop-expand-driver bench-salvage <phase>`.

## Open seams (active, by de-risk priority)
| ID | Title | Sev | De-risk # |
|---|---|---|---|
| S-BS-87 | `/v1/chat` stateless per message (no cross-turn memory) | med | #1 (Phase 0) |
| S-BS-83 | `author_flag` edit-only (no conversational criteria *minting*) | low | #1 |
| S-BS-86b | UI permits blocking-critical edits with a BLANK rationale | low→gov | #2 |
| S-BS-74 | the live withstands-correction / visceral flip (the moat) | med | #3 |
| S-BS-88 / S-BS-89 | agent-id grounding nit · New-eval `+` stub | low | scale/polish |
| S-BS-46/49/76/70 | corpus / optimize / over-fire / visceral-flip (carried) | med | — |

## Artifacts (this session)
- **Specs:** `docs/specs/SPEC_ONBOARDING_JOURNEY.md` (LOCKED), `SPEC_FLOW_VIDEO_PIPELINE.md`.
- **Strategy:** `docs/strategy/PITCH_journey_proof.md`, `PLATFORM_THESIS_bounded_context.md`.
- **Journey specs (reusable):** `journeys/onboarding.narrate.json`, `journeys/journey_4phase.narrate.json`.
- **Pipeline:** `scripts/record_flow.py` (silent-slice capturer). `scripts/build_onboarding_narrated.py` = retired (hand-rolled `zyng narrate`).
- **Recordings (gitignored `out/`):** `out/zyng_narrate/onboarding_narrated_zyng.mp4`, `journey_4phase_narrated.mp4` (+ `.srt`).
- **Evidence:** `docs/research/RUN_uap5a_a8_live_2026-06-06.json`, `REPORT_live_journey_dryrun_2026-06-06.md`.

## zyng MCP (the video engine, "through APIs")
Configured in `lithrim-bench/.mcp.json` (command = `zyng/.venv/bin/python mcp_server/server.py`);
server imports clean, `[mcp]` extra present, 4 tools (`get_spec_guide`/`list_voices`/
`render_presentation`/`record_walkthrough`), config auto-loads the EL key from `zyng/.env`.
**Not loaded in the session it was added to — needs a session RECONNECT + project-MCP approval** to
appear as `mcp__zyng__*`. The CLI / `zyng.narrate()` path gives identical output (not blocked).

## How to resume
1. Read the auto-memory `launch-journey-platform-derisk` + this handoff.
2. Read `docs/strategy/PLATFORM_THESIS_bounded_context.md` (the de-risk roadmap) + `PITCH_journey_proof.md`.
3. Watch `out/zyng_narrate/journey_4phase_narrated.mp4` (the canonical journey, narrated) for the product picture.
4. To execute: `/devloop-expand-driver bench-salvage <de-risk-#1 / S-BS-87 Phase-0>`.
5. Everything is on branch `bench-salvage/ws6c-dspy`, **NOT pushed**.

## References
Specs above · `SPEC_CALIBRATION_TRAINER.md` (Phase 3 = the product) · `SPEC_UNIFIED_AUTHORING_PRODUCT.md` (LOCKED) · memories `launch-journey-platform-derisk`, `calibration-trainer-is-the-product`, `self-asserting-loop-honesty-moat`, `eval-services-venture-thesis`, `gtm-launch-and-journey-thesis`.
