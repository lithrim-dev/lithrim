# Pitch primer — the launch journey, claim by claim, with honest proof

> The pitch artifact for `lithrim_bench_launch_journey.svg`. Every claim is tagged
> **PROVEN-LIVE** (with the run/evidence) or **ROADMAP** (frame as vision). The discipline
> is the point: we sell *verifiable truth, not a promised win* — so the honest ledger **is**
> the wedge against everyone selling "a better judge."
>
> Companion video: `out/zyng_narrate/journey_4phase_narrated.mp4` (the 4-phase re-cut).
> Grounded in this session's live runs + `docs/specs/SPEC_CALIBRATION_TRAINER.md`.

---

## The journey (one line per phase)
1. **First contact** — install (local), journey mode, point at your agent (a scribe), BYOK.
2. **The reveal** — a clean scribe note → verify → a real council + 4 pillars → verdict (first aha).
3. **Calibration (THE PRODUCT)** — the result is *wrong*; you make the judges right; re-run; compare; iterate.
4. **Own it** — load your own traffic (SDK), promote findings to an evalpack, defend it.

## Phase by phase — claim → proof → honest pitch line

### Phase 1 — First contact
- **Claim:** local-first, BYOK, a conversational agent guides every step.
- **Proof — PROVEN-LIVE:** the conversational shell drives the journey on `:5180` over BYO-Claude
  (`ANTHROPIC_API_KEY` unset), `$0`; a novice walked Domain→Judge→Run→Review live this session.
- **Proof — ROADMAP:** the Tauri desktop packaging (still a dev server, not a signed app).
- **Honest pitch line:** *"It runs on your machine, with your key — nothing leaves. You talk to it; it teaches as you go."* (Don't claim "download the app" yet.)

### Phase 2 — The reveal
- **Claim:** verify → a real cross-provider council + 4 pillars → a verdict, and the "aha."
- **Proof — PROVEN-LIVE (run `8a41ef3e`):** a real `:8002` council (gpt-4.1 / Mistral-Large / Llama-4)
  graded a scribe note against faithfulness/safety/structure and returned a verdict.
- **The deeper aha — PROVEN-LIVE:** a judge was **confidently wrong** (declared a medication absent
  that was verbatim in the transcript — it quoted the very line); a **deterministic grounded check
  overruled it.** The moat, observed live.
- **Honest pitch line:** *"A confident, unanimous panel of judges can be completely wrong — we caught
  one live. A source-grounded deterministic check overrules it. That's the aha."*

### Phase 3 — Calibration (THE PRODUCT)
- **Claim:** the result is deliberately miscalibrated; you tune the council, add a grounded floor,
  re-run, and watch accuracy against truth improve — you learn by doing.
- **Proof — PROVEN-LIVE (the strongest beat we have, and it wasn't staged):** our *own* eval drifted —
  a config change had softened the severity weights, so a fabrication-laden note scored `needs_review`
  instead of `reject`. The **calibration check caught it against ground truth (match 0.0)**; we restored
  the weights (with a rationale); **re-ran live (`83ec5086`)**; calibration moved **0.0 → 1.0**. That is
  the Phase-3 loop — miscalibrated → fix → re-run → compare — end to end, *for real*.
- **Proof — PROVEN-LIVE (the moat thesis):** prompt-tweaking is **non-monotonic** — we measured it
  (UAP-4 was an honest loss; stricter/few-shot caught *less*). The reliable lever is the **deterministic,
  tool-grounded floor**, not rewording prompts. This is the Composo wedge, empirically supported.
- **Proof — ROADMAP:** the *polished, by-construction* miscalibrated pack as a designed onboarding
  artifact; the in-UI calibration-trainer loop (we did the loop via API + a real drift, not a UI flow yet).
- **Honest pitch line:** *"You calibrate by grounding, not by guessing. We measured the prompt lever —
  it goes the wrong way. The floor is what makes the verdict true. And the product caught its own drift."*

### Phase 4 — Own it
- **Claim:** load your own conversations (SDK/paper) → promote findings → build a regression evalpack;
  every verdict carries a grounded audit trail. → Pro.
- **Proof — PROVEN-LIVE:** the eval-pack/corpus loop + run-history + the audit trail (why/when/who/what)
  exist and round-trip; we batch-ran a pack and read the audit this session.
- **Proof — ROADMAP:** the SDK ingestion route, multi-user roles, the Pro tier (multi-model council,
  AI mappings, reports).
- **Honest pitch line:** *"Every verdict traces back to the source — an eval you can defend to a
  regulator. Point it at your own traffic and keep the golden cases."*

## The proven-vs-roadmap ledger (keep this straight in any pitch)
| PROVEN-LIVE — show it | ROADMAP — frame as vision |
|---|---|
| Real cross-provider council + verdict (P2) | Tauri desktop app (P1) |
| Grounding overrules a confidently-wrong judge (the moat) | The by-construction miscalibrated pack (P3 onboarding artifact) |
| The calibration loop, run on a *real* drift → 0.0→1.0 (P3) | The in-UI calibration trainer loop (P3) |
| Prompt-tweaking is non-monotonic; grounding is the lever (P3) | The semantic-axis floor + withstands-gate at scale |
| Audit trail + eval-pack + run-history (P4) | SDK ingestion, roles, Pro tier (P4) |

## How to pitch it
Lead with the **proven** column; name the **roadmap** column as roadmap. The honesty *is* the
differentiation: competitors over-promise a smarter judge; you show the judge being wrong, the
deterministic floor catching it, and the eval catching its own drift — all verifiable, all local.
That is a governance claim a buyer can defend, not a benchmark they have to trust.
