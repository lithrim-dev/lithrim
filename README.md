# Lithrim Bench

**A self-hostable evaluation harness for AI agents — with a tool-grounded verification *floor* that can override a confident LLM judge, and an immutable audit trail on every run.**

> **Verifiable truth, not a promised win.** This README tells you exactly what Lithrim Bench does — *and where it doesn't work.* That boundary is the point.

Bring your own model key. Run it on your laptop or in your VPC. **Your data never leaves your machine.**

---

## What it is

Most AI-eval tools end at an LLM-as-judge — a second model scoring the first. But a judge is as fallible as the thing it grades: it can confidently approve a fabricated fact, or confidently flag a correct one. Lithrim Bench adds the layer underneath:

1. **A multi-model council** grades an artifact (a generated note, an HL7/FHIR output, a transcript-derived document) against a set of named flags, with **logprob-calibrated confidence** (a real probability from the model's own tokens — not a self-reported number).
2. **A deterministic, tool-grounded floor** then re-checks the council's findings against ground truth — a record, a schema, a terminology service — and can **override the verdict**: suppress a finding the council got confidently wrong, or block an output the council missed.
3. **An immutable audit record** captures every run — the votes, the floor's decision, and the evidence — so you can see *why*, not just *what*.

The floor is **three-state by design**: a finding is grounded-true, grounded-false, or **inconclusive** — and an inconclusive check is *surfaced, never silently flipped*. The system never manufactures certainty it doesn't have.

---

## Quickstart

**Zero-config demo — no keys, no network, runs in seconds.** See the full loop on a built-in case:

```bash
git clone <repo> && cd lithrim-bench
make demo        # replays a built-in case: council votes → floor flip PASS→BLOCK → audit
```

`make demo` replays a captured council baseline (so no LLM call, $0) and runs the **live deterministic floor** on the neutral built-in `_core` case — so the verdict flip is real and reproducible, not a recording. No key, no network, no domain pack required.

**Run it live on your own case (BYOK):**

```bash
export LITHRIM_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
make up          # local BFF + UI; grade your own artifact, nothing leaves the box
```

You provide the key; Lithrim provides the harness. No accounts, no hosted inference, no telemetry. (Azure is the alternative provider — `LITHRIM_LLM_PROVIDER=azure` + the `AZURE_OPENAI_*` vars; see [`.env.example`](.env.example).)

**Run it in containers — `docker compose up`.** No local Python/Node toolchain needed; a stranger gets the whole stack in two commands:

```bash
docker compose up   # builds + starts BFF (:8787) and UI (:5180)
```

Then open **http://localhost:5180**, connect your own LLM key from the UI (or pass it as env — see below), and grade a case. The BFF auto-seeds the neutral `_core` sample on first boot, so the loop works immediately.

- **BYOK via env** — set keys in your shell or a repo-root `.env` (compose auto-loads `.env`); the `bff` service passes through `OPENAI_API_KEY`, the `AZURE_OPENAI_*` vars, `LITHRIM_LLM_PROVIDER`, `LITHRIM_BFF_TOKEN`, and `LITHRIM_BENCH_PACKS_DIR`. None are required for the offline demo.
- **Chat (conversational assistant)** — the local `claude` CLI can't run in a container, so set `LITHRIM_CHAT_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` to drive the assistant via the Anthropic API. **Grading and the offline demo do not need it.**
- **Clean by construction + persistence** — a fresh `docker compose up` seeds only the neutral `_core` sample; it never inherits a dev `./out/`. Your evaluations + config then persist in a Docker-managed named volume (`lithrim_out`) across `up`/`down`, and `docker compose down -v` resets to the clean seed. A key you connect from the UI applies immediately for the running container; pass it via env (above) to keep it across `down`. Nothing leaves your machine.
- **Offline `$0` smoke** — `make demo` (no keys, no network) still runs on the host exactly as above; it does not require the containers.

> The browser talks to the BFF at `http://localhost:8787` (host-published + CORS-allowed) — *not* the container-internal `bff` hostname. Both ports are published to the host. To point the UI at a different published BFF origin, set `VITE_BFF_URL` before `docker compose up --build`.
>
> **Owner-run smoke (not automated):** after `docker compose up`, verify `curl -sf http://localhost:8787/health` is OK, the UI loads at `:5180`, and a host-side `make demo` REJECTs (flips PASS→BLOCK) with no keys. Agents lint the compose file (`docker compose config`) but don't start the Docker daemon.

**Exposing the server.** Left unset, the BFF is open for local single-user — zero friction. Put it on a network and set `LITHRIM_BFF_TOKEN=<token>` to require a Bearer token on every request: callers pass `Authorization: Bearer <token>` (or `X-API-Key: <token>`); the shell reads it from `VITE_BFF_TOKEN`. `/health` and CORS preflight stay open.

---

## The flagship loop

```
artifact ─▶ multi-model council ─▶ findings + calibrated confidence
                                        │
                                        ▼
                          tool-grounded floor (record / schema / terminology)
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                          ▼
     suppress a wrong finding    block a missed defect    inconclusive → surfaced
                                        │
                                        ▼
                          verdict  +  immutable audit record
```

`make demo` walks exactly this loop on the `_core_fabricated_claim` case: the council returns `PASS`, the deterministic floor catches the fabricated guarantee and flips the verdict to `BLOCK`, and the audit surfaces the `UNSUPPORTED_ASSERTION` / `SOURCE_CONTRADICTION` findings as the *why*.

---

## Architecture

| Layer | What it does |
|---|---|
| **Council** | Multi-model LLM judges, evidence-based consensus, logprob-calibrated confidence. (Frozen, byte-stable core.) |
| **Grounding floor** | `contract_type → executor` (in-process or service-transport); three-state, verdict-overriding, never silently flips. |
| **Packs** | A pack supplies the domain (ontology, flags, prompts, floors). The shipped default is the neutral `_core`; domain packs are pluggable and load from outside the repo. |
| **Plugins** | A unified registry (`kind: contract / provider / tool / pack`) — add a scorer, provider, or connector by manifest. |
| **Audit spine** | Append-only audit records + run provenance (which models, which plugins, what evidence). |

By-construction labeling is the bench's discipline: where it ships labeled cases, the label is *generated*, not annotated — the recipe that injects a defect **is** the label's justification.

### Packs load from OUTSIDE the repo

This repo is the genuinely domain-agnostic OSS core — it ships the engine plus the neutral `_core` pack and a non-clinical sample pack. A **domain** is a *pack*: a `pack.json` bundling an ontology + taxonomy + council role prompts + grounding floors + dataset generators. The core resolves a pack id in order:

1. an installed **entry point** in the `lithrim_bench.packs` group (the pip path);
2. **`LITHRIM_BENCH_PACKS_DIR`** — `os.pathsep`-joined external dirs (the dev / airgap path), pinned active with **`LITHRIM_BENCH_PACK`**;
3. the in-repo `packs/` (the sample packs + fixtures).

With no pack on the path the core stays on the neutral `_core` default and grades fine. To add your own domain, write a pack repo with a `pack.json` + the entry point and point the env var at it — **zero engine edits**.

---

## Connectors (MCP / tools)

The floor and judges can call external services — a terminology server, a schema validator, a retrieval tool — as **connectors**. MCP is the transport standard. A connector is a manifest entry (`transport: service | in_process`) plus an executor; secrets ride env vars, never the manifest. See **[`docs/specs/SPEC_TOOL_CONNECTORS.md`](docs/specs/SPEC_TOOL_CONNECTORS.md)** for the contract and reference connectors (a SNOMED terminology grounder and a web-search retriever).

**Graceful by default:** a connector that isn't configured or reachable resolves to *inconclusive* — the harness still grades, it just tells you what it couldn't verify. You don't need any sidecar to run.

---

## What Lithrim Bench honestly does — and does NOT do

This is the part most tools omit. The floor's power is **bounded**, and we tested the boundary with a blind held-out experiment rather than asserting it:

- **✅ Where the floor generalizes — closed-vocabulary / structured facts.** Dosage arithmetic, code/terminology membership (SNOMED/ICD), schema/FHIR conformance, record presence. The check is set-membership or arithmetic, so it generalizes to unseen cases and can reliably override a judge.
- **❌ Where it does NOT generalize — open-ended discourse.** Detecting an open-ended concept in free text (e.g. "was a refusal documented?") is open NLU. A deterministic/lexical floor here either misses novel phrasings or false-flags paraphrases. **In a blind held-out test, a serious 30-pattern rule scored recall 0.375 / precision 0.75 — it does not generalize.** For that class, an LLM judge (or a human-in-the-loop) is the right tool, not a deterministic floor.

So: **use the floor for grounded, structured claims; use the judge (and a human) for open-ended discourse.** Lithrim Bench is honest about which is which — and surfaces an inconclusive when it can't ground something, instead of guessing.

This is not "a better judge." Judges are commodity. This is **the grounded floor underneath the judge, with an honest map of its own limits.**

---

## Your data & keys stay local

Lithrim Bench is self-hosted. There is no Lithrim-hosted inference, no account, no telemetry.

- **The demo needs nothing** — no key, no network.
- **For a live grade you provide the key** (BYOK): copy [`.env.example`](.env.example) to `.env` and fill in `OPENAI_API_KEY` (or the `AZURE_OPENAI_*` vars). Your real `.env`, `.live_env`, and `.connector_env` are **gitignored** — they never enter the repo, and nothing leaves your machine.

> **Auth is deferred.** A local self-hosted run doesn't need it. Authentication for *exposed* deployments is coming; for now, run it where you trust the network.

---

## Status

This is a **community release** — a working harness and a runnable demo, not a finished product.

- **Stable:** the council, the calibrated-confidence read, the grounding-floor mechanism, the by-construction labeling, the audit spine, the neutral `_core` pack, BYOK (single-provider).
- **Experimental / evolving:** the full connector plane (reference connectors are wired; the SPEC is the design), the conversational UI surface, multi-provider councils.
- **Not included here:** auth (a local self-hosted run doesn't need it — coming for exposed deployments).

We'd rather ship a smaller honest thing than a broad one that over-promises.

---

## Open-core

The engine, the harness, the neutral `_core` pack, the sample packs, and the plugin/connector interface are **all open** (see [`LICENSE`](LICENSE)) — because adoption beats protecting the bits, and the moat was never the cases. The full clinical `healthcare` domain pack is distributed separately (its own repo) and loads through the pack-discovery seam above. Future commercial value (calibration, the SME-calibration loop, larger curated corpora, hosted/VPC, support) is **deferred until there's pull** — and would be *new* value, not a re-closing of what ships open here. The free core is **genuinely useful standalone** — not a crippled teaser.

---

## Research

Lithrim Bench backs the research paper *A Deterministic Structural Floor Under LLM-as-Judge* — the empirical case that an LLM judge cannot be trusted to certify its own safety, and that a deterministic floor grounded in something real measurably corrects it. The locked outline is [`docs/PAPER_OUTLINE.md`](docs/PAPER_OUTLINE.md); the engine spec (the by-construction defect taxonomy) is [`docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md).

---

## Contributing

Issues and PRs welcome. The one rule that mirrors the philosophy: **no manufactured wins** — a benchmark result must be reproducible, a label must be justified by construction, and a claim must say where it *doesn't* hold. Tests are the gate (`make test`), lint is `ruff` (`make lint`).

## License

**Apache-2.0** — see [`LICENSE`](LICENSE).

---

*Lithrim Bench is built on the premise that an AI system cannot be trusted to certify its own safety — the check has to live outside it, be grounded in something real, and be honest about its own blind spots. If you find a place it over-claims, open an issue. That's the contribution we value most.*
