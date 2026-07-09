# Setting up Lithrim CE — your first grade in ~15 minutes

This is the hands-on path: stand up the Community Edition with Docker, connect your own model key,
set up a judge, load a few cases, and grade them. For the *why* (the grounding floor, the audit
spine, the architecture), see [`README.md`](README.md).

> **Your data never leaves your machine.** You bring the model key; Lithrim is the harness. No
> accounts, no hosted inference, no telemetry.

---

## 0. Prerequisites

- **Docker** (Desktop or Engine) with Compose.
- **A model API key** for grading — OpenAI (`OPENAI_API_KEY`) or Azure OpenAI (`AZURE_OPENAI_*`).
  You enter it yourself in the UI or via `.env`; the app never asks anyone else for it.
- That's it. No local Python/Node toolchain needed for the container path.

Want to see the loop first with **no key and no network**? From a clone: `pip install -e .` (core
deps only), then `make demo` — it replays a built-in case and runs the live floor (PASS → BLOCK) in ~10s.

---

## 1. Start the stack

```bash
git clone https://github.com/lithrim-dev/lithrim && cd lithrim
docker compose up        # first run builds the images
```

> **Upgrading later:** after a `git pull`, run `docker compose up --build` — a plain `up` reuses
> the previously built images and silently runs the old code.

This brings up three services:

| Service | URL | What it is |
|---|---|---|
| **UI** | http://localhost:5180 | the app you'll use |
| **BFF** | http://localhost:8787 | the API the UI talks to |
| **JUTE mapper** | http://localhost:3031 | decodes arbitrary JSON for ingestion (bundled, no config) |

Open **http://localhost:5180**. The BFF auto-seeds the neutral `_core` sample on first boot, so the
app works immediately. State persists in a Docker volume across `up`/`down`; `docker compose down -v`
resets to the clean seed.

Sanity check (optional): `curl -sf http://localhost:8787/health` should return OK.

---

## 2. Connect your model key

1. Open the **session menu** (bottom-left, your name / "Local workspace") → **Connect AI**.
2. Pick your provider (OpenAI / Azure / …), paste your key, and save. The UI validates it and stores
   it locally for this workspace (in the Docker volume — it survives `up`/`down`, never leaves the box).
3. **Assign the assistant a model** — in the same modal, under **Assign models**, set the
   `chat_assistant` row (in Docker pick OpenAI / Azure / Gemini / OpenAI-compatible; the
   Anthropic/BYO-Claude path needs the host `claude` CLI and is host-run only). Until this is set,
   the chat composer can't answer — the "N of 4 set" line at the top of the modal tracks it.

> Prefer env? Put `OPENAI_API_KEY=…` (or the `AZURE_OPENAI_*` vars) in a repo-root `.env` before
> `docker compose up` — Compose auto-loads it. See [`.env.example`](.env.example).

Grading needs a key; the `_core` offline demo does not.

---

## 3. Create an evaluation

In the left rail under **Evaluations**, click **New evaluation**. This creates an agent (the thing
under evaluation) and starts a short **Setup journey** (Domain → Judges → Ground truth → Run → Review)
that guides the rest. Everything below also happens inline in the center conversation.

---

## 4. Set up the judges

Open the judge editor (the **Judges** step, or ask in chat "set up the judges"). Each judge is a
reviewer assigned a set of **flags** (the issues it may raise) plus the model it runs on.

**Panel vs. single reviewer — take the recommendation.** Under the model assignments you'll see a
**Recommended** line computed from your domain:

- **Panel** (several specialist reviewers) when the work spans multiple failure modes — differentiated
  lenses beat one generalist.
- **Single Generalist** (with a sampling count *k* of 3–8) for a narrow domain with one review lens.

Click **Use this** to apply it. Assign each reviewer a model (the one you connected in step 2).

**Optional — author your own flags.** In chat, describe a check ("add a flag for an unsupported
clinical claim") — it's spliced into the ontology and becomes assignable to a judge, with a full
who/why/what audit record.

---

## 5. Load a few cases — the front door

Click the **📎 attach** button in the composer and pick a **JSON, JSONL, or CSV** file. Try a sample:

- `samples/quickstart/notes.jsonl` — 3 flat records
- `samples/quickstart/notes.csv` — the same as CSV
- `samples/arbitrary/custom_support_trace.json` — a deeply nested custom shape

What happens:

1. Lithrim **decodes** the file and **generates a JUTE template** that maps it into eval cases.
2. A **preview card** appears: the extracted cases (case_id → response / context) and a collapsible
   **"View the generated JUTE template"** so you can verify the mapping. **Nothing is saved yet.**
3. If the mapping is right, click **Approve & load**. If it's off (or the file didn't auto-map),
   use **"Mapping looks wrong?"** / the retry box to describe the fields and re-preview, e.g.:
   > one case per `episodes`; case_id = eid, response = outbound.message.body, context = inbound.text

A case needs **`case_id`**, **`response`** (the AI output being graded), and **`context`** (the source
it's graded against). Any custom agent-trace JSON works — the template is generated, not hardcoded.
See [`samples/README.md`](samples/README.md) for details.

---

## 6. Grade them

In chat, ask **"grade all cases"**. Lithrim opens a cost-confirm dialog (grading is a paid model
call — you authorize the spend), then runs the council on every loaded case and shows a consolidated
**scorecard** inline: per-case verdicts, and — for *labeled* cases — precision / recall / verdict
match. To grade a single case live, use **Run live** in the top bar.

> The sample cases are unlabeled, so the scorecard shows verdicts but not accuracy metrics — that's
> the honest behavior on data with no answer key.

That's the full loop: **setup → key → judges → load → grade.**

---

## Troubleshooting

- **UI loads but grading fails / "configure a provider"** — finish step 2 (Connect AI), and confirm
  the key's provider matches the model assigned to your judges.
- **An upload says "couldn't map this file"** — the generator didn't converge on the shape. Use the
  retry box to name the record collection and the response/context fields (see step 5). Large
  *new-shape* files can also exceed the generation budget — start with a smaller slice.
- **Ingestion seems stuck / mapper errors** — check the JUTE mapper: `curl -sf http://localhost:3031/jute-dsl-spec.json`.
  It's bundled by default; see [`docs/JUTE_MAPPER_ADDON.md`](docs/JUTE_MAPPER_ADDON.md) to point at
  your own mapper.
- **Reset everything** — `docker compose down -v` wipes the volume back to the clean `_core` seed.

---

## Going further

- **Your own domain (a pack)** — drop a pack folder into `packs-dropin/` and restart; `GET /v1/packs`
  picks it up. See [`packs-dropin/README.md`](packs-dropin/README.md) and the README's "Packs load
  from outside the repo".
- **Put it on a network** — set `LITHRIM_BFF_TOKEN=<token>` to require a Bearer token on every request.
- **The grounding floor** (the deterministic layer that can override a confident judge) and the audit
  spine — see [`README.md`](README.md).
