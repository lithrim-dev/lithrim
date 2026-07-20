# Run the prebuilt stack (no clone)

This is the fastest way to a running Lithrim: fetch the published images and start them.
No `git clone`, no local build, no Python or Node toolchain. An empty directory is enough.

If you want the source (to modify it, run the `$0` offline demo, or build from scratch), use the
clone path in [`SETUP.md`](../SETUP.md) instead. Both reach the same UI.

> **Your data never leaves your machine.** You bring the model key; Lithrim is the harness. No
> accounts, no hosted inference, no telemetry.

---

## 0. Prerequisites

- **Docker** (Desktop or Engine) with Compose v2 (`docker compose version` should print a version).
- Ports **5180**, **8787**, and **3031** free on the host.
- **For live grading only:** a model API key (OpenAI or Azure OpenAI). First boot and the built-in
  sample need no key.

---

## 1. Start the stack

```bash
mkdir lithrim && cd lithrim
curl -fsSLO https://raw.githubusercontent.com/lithrim-dev/lithrim/main/deploy/docker-compose.yml
docker compose up
```

The first `up` pulls three public images and starts them. When the pull finishes, open
**http://localhost:5180**.

That is three services:

| Service | URL | What it is |
|---|---|---|
| **UI** | http://localhost:5180 | the app you use |
| **BFF** | http://localhost:8787 | the API the UI talks to |
| **JUTE mapper** | http://localhost:3031 | decodes arbitrary JSON for ingestion (bundled, no config) |

The BFF auto-seeds the neutral `_core` sample on first boot, so the app works immediately with no
key. Sanity check (optional): `curl -sf http://localhost:8787/health` returns OK.

Core-only (skip the mapper): `docker compose up bff ui`.

---

## 2. Grade live: bring your own key (BYOK)

Grading is a paid model call against **your** provider key. Two ways to supply it:

**In the UI (recommended).** Session menu (bottom-left, "Local workspace") then **Connect AI**: pick
your provider, paste your key, save, and assign models under **Assign models**. The key is stored in
the Docker named volume, survives `up`/`down`, and never leaves the box. This is the full happy path
in [`SETUP.md`](../SETUP.md) sections 2 onward.

**Via `.env`.** Compose auto-loads a `.env` file in the same directory as the compose file. Create one:

```bash
cat > .env <<'EOF'
LITHRIM_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
EOF
docker compose up -d
```

For Azure OpenAI, set `LITHRIM_LLM_PROVIDER=azure` and the `AZURE_OPENAI_API_KEY` /
`AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_VERSION` / `AZURE_OPENAI_DEPLOYMENT` vars instead. Every
env var the stack reads is documented in the compose file header and in
[`.env.example`](../.env.example) in the repo.

> The `.env` (and any real key) stays on your machine. Nothing is committed; nothing is uploaded.

---

## 3. Load a case and grade it

The built-in `_core` sample is already loaded. To grade your own data, attach a JSON / JSONL / CSV
file in the composer and follow the mapping preview. If you did not clone the repo, you can still
grab the shipped sample files by URL:

```bash
curl -fsSLO https://raw.githubusercontent.com/lithrim-dev/lithrim/main/samples/quickstart/notes.jsonl
```

Then attach that file in the UI. The end-to-end loop (connect key, set up judges, load cases, grade,
and **read the verdict and audit trail**) is the walkthrough in [`SETUP.md`](../SETUP.md) sections 2
to 6; every step there applies identically to this prebuilt stack.

---

## 4. Pin a release, upgrade, reset

**Pin a version** instead of `latest` (recommended for anything you want reproducible). Set the image
tags in your `.env` or shell before `up`:

```bash
LITHRIM_BFF_IMAGE=ghcr.io/lithrim-dev/lithrim-bff:v0.1.2
LITHRIM_UI_IMAGE=ghcr.io/lithrim-dev/lithrim-ui:v0.1.2
```

Published tags are listed on the GHCR package pages
([lithrim-bff](https://github.com/lithrim-dev/lithrim/pkgs/container/lithrim-bff),
[lithrim-ui](https://github.com/lithrim-dev/lithrim/pkgs/container/lithrim-ui)). Both images are
multi-arch (linux/amd64 + linux/arm64).

| Action | Command |
|---|---|
| Stop, keep state | `docker compose down` |
| Full reset to the clean seed | `docker compose down -v` (wipes evaluations, config, connected keys) |
| Upgrade to the newest images | `docker compose pull && docker compose up` |

State lives in Docker-managed named volumes (`lithrim_out`, `jute_data`): a plain `down`/`up`
persists your evaluations, config, and UI-connected keys; only `down -v` resets to the clean `_core`
seed.

---

## 5. Localhost-only by design (read this before exposing it)

The published UI image bakes its BFF origin (`VITE_BFF_URL=http://localhost:8787`) at **build** time.
So the prebuilt path works only when your browser reaches the BFF at `http://localhost:8787`: same
machine, default ports. The `VITE_BFF_URL` env var in the compose file cannot re-point a prebuilt
bundle (it is kept only for parity with the build-from-source compose).

To serve the UI from any other origin (a remote host, a reverse proxy, a different port), you must
rebuild the UI image from the repo's `Dockerfile.ui` with `--build-arg VITE_BFF_URL=<your BFF origin>`
and add a matching BFF CORS allow-list. That is the clone path, not this one.

For a single-user local deployment (the intended use here), no change is needed.

---

## 6. Optional add-ons

All optional; a stock `up` ignores them. Each is a host directory next to your compose file, created
empty on first `up`:

- **Add a domain pack** (`./packs-dropin`): drop a pack **folder** in and restart. `GET /v1/packs`
  picks it up. See [`packs-dropin/README.md`](../packs-dropin/README.md).
- **SNOMED terminology floor** (`./snomed`): mount `hermes.jar` + a SNOMED database to ground
  terminology checks. SNOMED CT is licensed data: bring your own; nothing is baked into any image.
  Full guide: [`docs/SNOMED_SETUP.md`](SNOMED_SETUP.md).
- **Point at your own JUTE mapper**: override `LITHRIM_JUTE_URL`. See
  [`docs/JUTE_MAPPER_ADDON.md`](JUTE_MAPPER_ADDON.md).
- **Require inbound auth**: set `LITHRIM_BFF_TOKEN=<token>` to require `Authorization: Bearer <token>`
  on every request (`/health` and CORS preflight stay open).

---

## 7. Drive it with an AI agent (optional)

If you use Claude Code or another skills-aware agent, Lithrim ships three Agent Skills that automate
bringing this stack up, running a first grade, and wiring the SNOMED floor. You can install them
without cloning the whole repo. See [`docs/AGENT_SKILLS.md`](AGENT_SKILLS.md).

---

## Troubleshooting

- **`docker compose up` fails to pull / "denied" / "manifest unknown"**: confirm you can reach
  `ghcr.io` and that the tag exists (check the GHCR pages linked in section 4). The images are public;
  no `docker login` is required.
- **Port already in use**: something else holds 5180, 8787, or 3031. Free it, or remap the host port
  in your local copy of the compose file (edit the left side of `host:container`).
- **UI loads but grading says "configure a provider"**: finish section 2 (Connect AI), and confirm
  the key's provider matches the model assigned to your judges.
- **Ingestion seems stuck**: check the mapper: `curl -sf http://localhost:3031/jute-dsl-spec.json`.
- **Start over**: `docker compose down -v` wipes the volumes back to the clean `_core` seed.
