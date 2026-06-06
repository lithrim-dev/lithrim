# Journeys

Narrated walk-through videos of the Lithrim workspace, recorded with **Zyng** — the agentic Loom.
No manual screen-recording: Zyng drives the running app with Playwright and narrates the flow.

## Record one

1. Start the app: `make up` (UI on `:5180`).
2. **From a Claude session here** — the `zyng` MCP server is registered (`.mcp.json`), so just ask:
   > "Record a walk-through of the activation journey at http://localhost:5180."

   Claude authors the steps from the UI it knows and calls the `record_walkthrough` tool. As you
   build new screens or journeys, ask it to record whatever you want.
3. **Or from the CLI:**
   ```bash
   zyng walkthrough journeys/activation.walkthrough.json \
     --provider elevenlabs --mode voiced --out out/
   ```

## Lessons — mix clips + slides + data (for educating end consumers)

A **lesson** stitches short walk-through clips together with explainer cards and data charts into
one narrated video. Ask Claude *"compose a lesson teaching X"* (it calls the `compose_lesson` tool),
or run the CLI:

```bash
zyng lesson journeys/grading.lesson.json --provider elevenlabs --out out/
```

Each segment is one of `walkthrough` (a short app clip), `card` (title/bullets/statement/closing),
or `data` (inline rows or a data file → a chart). See `grading.lesson.json` for a worked example
(title card → a `:5180` clip → the grading-panel chart → a closing card).

## Specs here
- `grading.lesson.json` — a composite **lesson** (clips + cards + a data chart).
- `activation.walkthrough.json` — the 4-step activation journey (a single walk-through: `url` + `steps`).
- `onboarding.narrate.json` — the older format (narration beats over a pre-existing recording).

Voice needs `ELEVENLABS_API_KEY`; use `--mode silent` / `--provider offline` for a key-less,
captioned silent capture. Full schema: `zyng/docs/WALKTHROUGH.md`.
