# Lithrim — v1 Release (OSS core)

The **conversational, tool-grounded clinical-AI eval platform**, releasable as a
self-contained OSS core. This doc is the release scope + the **owner-executed**
push/PR/tag checklist. The executor PREPARES this; **the owner runs the push** — nothing
here pushes, tags, or publishes.

---

## What ships in v1 (OSS core)

- **The engine** — Synthea-derived, by-construction-labeled clinical artifact cases
  (`lithrim_bench/`, the `taxonomy_snapshot.json` contract).
- **The conversational platform** — the 3-pane shell (`apps/shell`) + the BFF
  (`apps/bff`) + the chat agent loop (author judges/flags + read/replay; `$0`,
  A-SAFE deny-by-default gate).
- **The multi-provider v2 council** — the vendored, Mongo-free in-process council
  (`lithrim_bench/runtime/council`), Azure-default with a BYO-Claude provider.
- **The grounding floor (the moat)** — the post-hoc verification contracts that can flip
  a confidently-wrong judge (`med-presence-check/v1`, the withstands-gate).
- **The audit trail** — every authoring + run action → an immutable who/when/what/why
  record; run provenance blobs persisted to local SQLite (no Mongo).
- **The CI/CD gate** — `lithrim-bench-pack` (reliability ≥ threshold AND
  never_events == 0; exit 0/1) — the Mongo-free lithrim-sdk parity.
- **A clinical sample agent + cases** — runnable from a clean clone.

## The framing (the trust wedge)

- **BYO-key** — the user brings their own Azure or Claude key; Lithrim ships no keys.
- **Airgapped-capable** — the OSS core runs **standalone**: no `lithrim-backend`, no
  `:8002`, no Mongo. `LITHRIM_COUNCIL_BACKEND` defaults to the bundled in-process
  council (`http`/`:8002` is opt-in for a `lithrim-backend` deployment).
- **No us-hosted surface** — no trial-expiry, no hosted endpoint the user's PHI flows
  through. The moat is the flywheel/corpus/SME-loop/brand, not the (open) bits.

## NOT in v1 (parked post-v1, specs written)

SCENARIO-1 / FHIR / StoryWorld (`SPEC_EVAL_SCENARIOS`) · IMPORT-1 (data ingestion) ·
the provider-picker / Claude-council UI (S-BS-105) · the plugin refactor
(`SPEC_PLUGIN_ARCHITECTURE`). These do not block v1.

---

## Pre-push verification (the executor ran these; the owner re-confirms)

- [ ] Quickstart followed clean from a clean clone ([`QUICKSTART.md`](QUICKSTART.md)) —
      `$0` replay works with no key; the paid run needs the BYO key.
- [ ] **Standalone A-LIVE** — on `:5180` with `lithrim-backend` STOPPED, a run completes
      via the in-process council (BYO key) → the correct verdict. (No `:8002`.)
- [ ] Full suite green under `debuglithrim` (the credential-gated council tests need a
      BYO key — documented, not a regression).
- [ ] `ruff` clean; the shell builds.
- [ ] The seam-triage table (below) shows no HARD launch-blocker.

## Push checklist (OWNER executes — not the executor)

1. [ ] Review the branch diff: `git log main..bench-salvage/ws6c-dspy --stat`.
2. [ ] Confirm no foreign/untracked files are bundled (`git status` clean except
       intended).
3. [ ] Open the PR `bench-salvage/ws6c-dspy → main`; paste the release notes (below).
4. [ ] Land the PR.
5. [ ] Tag `v1.0.0` on the merge commit: `git tag -a v1.0.0 -m "Lithrim v1 (OSS core)"`.
6. [ ] `git push origin v1.0.0`.
7. [ ] (If publishing) attach the release notes to the GitHub release.

---

## Draft release notes — Lithrim v1.0.0 (OSS core)

> **Lithrim v1 — a conversational, tool-grounded clinical-AI eval platform.**
>
> Author LLM judges and safety flags in chat, run them against by-construction-labeled
> clinical cases, and watch a **deterministic grounding floor** correct a confidently-wrong
> judge — with a full who/when/what/why audit trail.
>
> **Self-contained & airgapped-capable.** Runs standalone with a **BYO Azure or Claude
> key** — no hosted backend, no Mongo, no PHI leaving your machine. The `$0` replay needs
> no key at all.
>
> **In this release:**
> - The 3-pane conversational shell + the in-process multi-provider v2 council.
> - The grounding floor / withstands-gate (the moat): tool-grounded verification that can
>   flip a judge's verdict.
> - By-construction-labeled clinical case generation (the engine).
> - An immutable authoring + run audit trail (local SQLite).
> - A CI/CD eval gate (`lithrim-bench-pack`).
>
> **Get started:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md).
>
> License: Apache-2.0.

---

## Seam triage (launch-blocking?)

_(Filled in the green-bar commit — see below.)_
