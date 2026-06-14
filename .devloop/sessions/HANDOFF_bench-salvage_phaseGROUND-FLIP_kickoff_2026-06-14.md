# Handoff — `bench-salvage` → next session (post-GROUND-FLIP)

> Written at phase close, 2026-06-14. **GROUND-FLIP is CLOSED CLEAN (via adjudication).** The live
> FABRICATED_HISTORY grounding binding is now `snomed_subsumption`, the conversational grounding/KB
> tools are live, and the close passed a two-run HARD-GATE fresh-critic. The Journey-Pitch video on
> the LATEST shell is the deliverable still in flight.

## What landed (this cycle: `d4dd519..HEAD`, LOCAL, not pushed)

**The flip (the calibration decision TOOL-2 queued):**
- pack `5a3ccb2` — `healthcare/ontology.json` FABRICATED_HISTORY `record_presence → snomed_subsumption`
  (`snomed-subsumption/v1`) + `examples/snomed_specificity_v1.jsonl` (by-construction clean-negative,
  expected verdict=approve) + `tests/test_specificity_flip.py` (hermetic binding+suppress proof).
- core `2290ad1` fail-clean guard for raising suppress executors; `efe81cf` seed mirror; `9e68d5c`
  the PROOF-capsule doc.

**The conversational grounding/KB surface:**
- `b05457e` **add_grounding_contract** (15th tool — the journey step-5 "add grounding" move; audited $0
  write via the frozen endpoint). `e3090c5` **kb_context** (16th — `KbRagTool.search`, read-only KB
  retrieval, NEVER changes a verdict). `04ad329` the `.live_env` kb:read loader (→ a server-startup
  event in `79484a2`). `cbba04b` namespace normalize, `700f27a` flag alias.
- `a929db7` the **honesty guardrail** — caught + fixed a real manufactured-win narration (the run_eval
  chat tool was dropping string findings → telling the agent "active: none" on a reject).

**Journey BFF preconditions:** `9576daf` (active-workspace pack snapshot for the 3 config-write gates —
a pre-existing PACK-DIST-1 500) · `6fc6bbf` (eval-pack batch → pack-bound subprocess).

**The HARD-GATE fix `79484a2`:** the 11 net-new regressions + 1 core domain-leak run 1 found —
tool-count `14→16`, the 2 stale `_stub_ctx` ToolContext stubs, the evalpack.py:123 clinical leak, the
FastAPI Depends sentinel in the eval-pack route (+ a non-_core subprocess-path regression test), the
`.live_env` import-leak (→ startup event), and the 2 BFF fixtures made hermetic vs `out/workspaces/.active`.

## The close — what the HARD-GATE found (honest record)

- **Run 1 → DIRTY:** 11 net-new test regressions + 1 core domain-leak. All real, all above the frozen
  seam, all fixed in `79484a2`.
- **Run 2 → DIRTY on ONE stale criterion only:** my own moat critic's CHECK 2 ("`git diff acc4973 HEAD`
  on the moat files must be empty") — a wrong anchor. The council files legitimately diverged from
  `acc4973` via the authorized PACK-*/6b-CLEAN/6c refactors (all PREDATE this cycle). **Independently
  verified:** `git diff d4dd519..HEAD -- '*compliance_council.py' '*signals.py' '*safety_flags*'` = **0
  lines**; seam-guard + attestation = **17/17** (the CLAUDE.md mechanism anchor). Critics 2/3/4 CLEAN.
  Adjudicated CLEAN (the gate's own synth recommended it); the gate-script criterion was re-pointed to
  the mechanism anchor (closes the stale-criterion seam).
- **Canonical suite:** `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare
  LITHRIM_BENCH_PACK=healthcare pytest -q` → **619 passed / 54 skipped / 2 failed** (the 2 = pre-existing
  S-BS-96 observation pair) → **0 net-new**. ruff clean. Moat untouched.

## DELIVERABLE IN FLIGHT — the Journey-Pitch video on the LATEST shell

The first render (`~/zyng-out/lithrim_journey_pitch.mp4`, 2:46) reused **stale June-11 footage** — the
user flagged it ("this is not the latest shell"). The current `:5180` shell is materially evolved (a
6-step SETUP JOURNEY in the rail, `snomed-demo`, the Case/Report/Judge-council/Config/Corpus pane).

- **User-approved cut:** the **FULL 6-step setup journey** (Domain → Judges → Ground truth → Knowledge
  base → Run → Review), driven LIVE.
- **Plan (stated to the user):** `zyng capture_clips` (free, headless Playwright on the real DOM —
  selectors already read: chips ref_11/12/13, tabs ref_21-25, Run eval ref_5, chat textbox ref_15,
  workspace switcher ref_1) → a SILENT cut for the user to approve → THEN paid `mcp__zyng__publish`
  (real voice; ~2143s credit remaining). Honest-Δ only.
- **Live stack is up:** `:5180` shell, `:8787` BFF, `:8002` backend, `:3031` JUTE. `out/workspaces/.active`
  is on `demo-clinical` for the demo (the suite is now hermetic to it).
- **Caveat for the pitch's "it flips" moment:** on `snomed-demo` the verdict honestly STAYS BLOCK
  (FABRICATED_HISTORY suppressed but other real findings remain). A clean reject→approve VERDICT flip
  needs a curated single-FP case — demo curation, not an engine gap.

## Open seams (this stream)

- **S-BS-140 (low):** the observation-pipeline import-isolation pair fails in the full run + passes in
  isolation at BOTH baseline and HEAD (S-BS-96 class) — an import-order fix is owed.
- **S-BS-141 (low):** `_grade_via_subprocess` 500s when a non-_core workspace's pack is undiscoverable
  in bare CE; harden to fail-clean. (Only reproduces with a non-default `.active` + the pack absent.)
- Carried: S-BS-132 (won't-fix), S-BS-135..139 (PACK-DIST-2-bound).

## Next moves (do NOT autostart — user steers)

1. **Finish the Journey-Pitch video** (the in-flight deliverable above).
2. The broader arc: pick N cases → evaluate → calibrate → promote an Eval Pack.
3. S-BS-140 / S-BS-141 hardening.
4. The owner-gated push (LOCAL SSOT — user keeping LOCAL, explicitly fine).
