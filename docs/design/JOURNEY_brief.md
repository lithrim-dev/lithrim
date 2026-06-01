# Lithrim — Activation Journey (design brief)

> The canonical **4-phase activation journey**: download → "aha" → calibrate → own it.
> Source-of-truth for (a) Claude Design prompts for the shell screens, (b) the conversational
> "journey mode" agent's script, and (c) [`SPEC_PRODUCT_SHELL.md`](../specs/SPEC_PRODUCT_SHELL.md) §2.
>
> **Provenance:** generated as a Claude Design first-stab flowchart (2026-06-01); brand tokens lifted
> from `../v0-lithrim-landing-page/app/globals.css`. Maps to the GTM calibration-trainer journey.

---

## The journey (4 phases)

**Phase 1 — First contact.** Download Bench + the healthcare pack (Tauri desktop; the paper ships same day). **Journey mode activates** — a conversational agent guides every step. The user selects an agent type (**Scribe**) and configures meta — agent prompt, BYOK LLM key.

**Phase 2 — The reveal (the "aha").** A clean scribe exchange — transcript + audio, **no badges, no verdict**, just the raw interaction. Click **Verify** → four pillar badges animate in (**Faithfulness · Completeness · Safety · Structural**) → verdict + score appear. First aha. Then explore multiple scribe scenarios from the pack.

**Phase 3 — Calibration (the product).** The twist: results are **intentionally miscalibrated** (too lenient OR too strict). The user's task: **make the judges right.** Tweak the **judge council** — edit judge prompts, add knowledge bases, extend taxonomy codes — in plain English, while the agent orchestrates behind the scenes (plain English → structural conditionals via Jute). **Re-run the pack and compare before/after** — improved or regressed? An iterate loop.

**Phase 4 — Own it.** Load your own agent conversations (SDK route or paper methodology — your data, your agents). **Promote findings → build your evalpack** (golden cases + regression suite from real interactions). → **Pro:** multi-model council, AI mappings, eval reports.

> **The load-bearing beat is Phase 3.** "Intentionally miscalibrated → make the judges right" turns calibration from a chore into the engaging core loop — that *is* the product. Phase 2's verify-badges moment and Phase 3's council-tweak + before/after compare are the **hero screens**.

---

## Claude Design prompt (paste-ready)

> Paste into `claude.ai/design`. Produces the key screen per phase in the 3-pane shell. If one-screen-at-a-time works better, lead with Phase 2 and Phase 3 (the hero moments).

**Lithrim — the activation journey (desktop app, 3-pane, Claude-desktop-class)**

Design the onboarding-to-ownership journey for Lithrim, a developer tool that evaluates AI systems and tells teams *when their AI is wrong and why*. A sleek, modern Tauri desktop app: a **3-pane shell** — left = journey/nav rail, center = a conversational guide ("journey mode") with rich inline cards, right = an artifacts/preview pane. Calm, precise, trustworthy; Linear / Claude-desktop polish. The journey is **four acts**, each a deliberate beat the agent narrates while the right pane reveals the matching artifact:

1. **First contact.** Fresh install of Bench + the healthcare pack. The agent welcomes; the user picks an agent type (**Scribe**) and configures meta — agent prompt, BYOK LLM key. Quiet, oriented.
2. **The reveal (the "aha").** Show a clean scribe exchange — transcript + audio, **no badges, no verdict**, just the raw interaction. The user clicks **Verify** → four pillar badges animate in (**Faithfulness · Completeness · Safety · Structural**) → a verdict + score appear. First aha. Then they browse multiple scenarios from the pack.
3. **Calibration — the product.** The twist: results are **intentionally miscalibrated** (too lenient or too strict). The user's job: **make the judges right.** They tweak the **judge council** — edit judge prompts, add knowledge bases, extend taxonomy codes — in plain English, while the agent orchestrates behind the scenes (plain English → structural conditionals via Jute). They **re-run the pack and compare before/after** — improved or regressed? An iterate loop.
4. **Own it.** The user loads their own agent conversations (SDK or methodology — their data, their agents), **promotes findings into their own evalpack** (golden cases + regression suite from real interactions), and unlocks **Pro** (multi-model council, AI mappings, eval reports).

**Brand (match exactly):** bg `#FFFFFF`, ink `#1A2845` navy, primary/accent `#E85C3D` coral (buttons/active/focus rings), surfaces `#F8F9FB` / `#F0F2F5`, muted text `#6B7385`, borders `#E5E7EB`; data colors teal `#3DA98C` · amber `#E89738` · slate `#3F4A66`. Type **Geist** + Geist Mono, ~10px radius, crisp 1px borders, generous whitespace, light theme (dark a plus).

**Deliver:** the key screen for each of the four phases, in the 3-pane shell — center conversation + the right-pane artifact for that beat. Make Phase 2's verify-badges moment and Phase 3's judge-council tweaking + before/after compare the hero screens.

---

## Brand tokens (from `../v0-lithrim-landing-page/app/globals.css`)

| token | value |
|---|---|
| background / ink | `#FFFFFF` / `#1A2845` (deep navy) |
| primary · accent · ring | `#E85C3D` (coral-terracotta) |
| secondary / muted / muted-fg / border | `#F8F9FB` / `#F0F2F5` / `#6B7385` / `#E5E7EB` |
| data (charts) | teal `#3DA98C` · amber `#E89738` · navy `#1A2845` · slate `#3F4A66` |
| type · radius | Geist / Geist Mono · `0.625rem` (~10px) |
| stack | Next + shadcn/ui (Radix) + Tailwind v4 — matches the shell spec |

## References
- [`SPEC_PRODUCT_SHELL.md`](../specs/SPEC_PRODUCT_SHELL.md) §2 (the journey rail) + §3 (journey → primitive mapping)
- [`SPEC_PRODUCT_SERVICE_TOPOLOGY.md`](../specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md)
- Brand source: `../v0-lithrim-landing-page/app/globals.css`
