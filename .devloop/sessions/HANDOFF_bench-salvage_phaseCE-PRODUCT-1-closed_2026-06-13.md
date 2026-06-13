# Handoff — `bench-salvage` → next phase (after CE-PRODUCT-1)

> Written at the CE-PRODUCT-1 close, 2026-06-13. The CE (OSS core) is now a usable
> standalone product: a clean healthcare-free shell, the **workspace** as a switchable
> per-tenant domain-setup boundary, and the **install-a-pack → create-agent → load-cases
> → evaluate** loop PROVEN end-to-end. This cycle ran **INLINE** (built directly, no exec
> driver — like WS-5); git history is the authoritative record. The next monitor presents;
> the user picks.

## What just landed — CE-PRODUCT-1 (the CE core made usable)

- **Verdict:** CLOSED — **INLINE** product cycle (no formal driver / no fresh-critic worktree pass; moat-inert by construction). Tested + user-eyeballed live.
- **Commits:** `627fbbe..eaa19d4` (10 commits), parent `5ee6fa4`. Branch `bench-salvage/ws6c-dspy`, **not pushed** (LOCAL SSOT).
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseCE-PRODUCT-1-2026-06-13.json` (retro-registered at reconcile time).
- **Index bundle:** `bench-salvage-phaseCE-PRODUCT-1-ce-core-usable-workspace-pack-loop` (idx 0, newest-first).
- **Memory:** `ce-workspace-multitenancy-program.md` (the authoritative narrative).

**P1** (`627fbbe`) — purged healthcare from the live CE shell (excl. the frozen `/journey` demo) + reset the stale gitignored BFF config DB to the committed `ws0_default` seed (the user's 404 was a stale clinical agent, not a regression).

**P2 — the WORKSPACE primitive = THE multitenancy seam.** A workspace = `out/workspaces/<name>/` holding its own `config.sqlite` (agents/judges/flags/audit) + `collections.sqlite` (runs) + `ontology/` + `out/` + `workspace.json {name,pack,packs_dir,actor,owner,created_at}`; the BFF `get_*` resolvers resolve under the active workspace, so switching repoints every store (`harness/workspace.py`). P2a model + `/v1/workspaces`·`/v1/workspace`; P2b the FE switcher pill; **P2c grade-under-the-pack via subprocess** — the frozen council binds its pack at IMPORT, so a non-`_core` workspace grades in a subprocess bound to `LITHRIM_BENCH_PACK=<ws.pack>` (`_core`+replay stay in-process; `run_eval --emit-json` / `__GRADE_JSON__` the contract); P2c+ fresh workspaces start EMPTY.

**P3 — the pack-loaded loop PROVEN end-to-end.** `discover_packs()` + `GET /v1/packs`; the FE pack-picker; the pack-bound agent template (`pack_ontology_path(check_consistency=False)` — the codes-⊆-KNOWN gate fires for real at GRADE time in the subprocess; the R-GUARD license gate is never skipped) + `GET /v1/packs/{pack}/cases`. **Real grade:** a `healthcare` workspace → a `healthcare_default` agent → graded under healthcare's council via subprocess → verdict **approve**, 3 votes (risk PASS / policy WARN / faithfulness PASS); 145 cases listable. Plus the status bar wired to live `GET /v1/meta` + the last demo numbers neutralized.

**Deployment thesis realized:** TWO primitives — pack=installable unit (PACK-DIST-1 discovery) + workspace=tenant boundary — yield 3 tiers from ONE core (local CE / custom on-prem / Lithrim Cloud); `workspace.json`'s `owner` slot is the persisted AUTH seam (ignored locally → the only local↔cloud diff); the PLUGIN-1 `tier`/`License` gate is the entitlement control point.

## What's next — the user's call (do NOT autostart)

Unchanged from the PACK-DIST-1 close — the options stand:

- **(a) HPACK** — build the 1st Pro plugin IN the pack repo `../lithrim-pack-healthcare`: the SNOMED terminology floor + vector/KB querying + the SNOMED MCP tool + clinical cases + the product narrative. The user's stated goal. Its generic `tool`-kind interface, if needed, is a separate CE cycle in `lithrim-bench` (open/closed — the pack must not require core engine edits). See `HANDOFF_bench-salvage_phaseHPACK_kickoff_2026-06-12.md`, `[[grounding-floor-is-the-moat-next]]`, `[[healthcare-realm-as-pack]]`, TERMINOLOGY-1.
- **(b) PACK-DIST-2** — the deferred CE polish: clean clinical-test MOVE into the pack repo + pack-repo CI/devloop + the history-preserving subtree split + **S-BS-135..139**. The CE-PRODUCT-1 leftovers fold in here (the pack's shipped agents' stale paths; a manifest `corpora` field as the durable corpora link).
- **(c) CHATBIND-2** — chat-drives-the-3rd-pane (also the deferred `frontend` plugin kind).
- **(d)** the owner-gated **push** (LOCAL SSOT — user keeping LOCAL, explicitly fine).

## Open seams (this stream) — UNCHANGED by CE-PRODUCT-1 (0 opened, 0 closed)

- **S-BS-132** (ACCEPTED won't-fix) — frozen-inert source_message machinery.
- **S-BS-135** (low) · **S-BS-136** (medium) · **S-BS-137** (medium) · **S-BS-138** (low) · **S-BS-139** (low) — all PACK-DIST-2-bound.
- Older gate seams still genuinely open (all inert today, GATE-before-a-floor/kb-grounding ships): **S-BS-13**, **S-BS-16**, **S-BS-41**.

**CE-PRODUCT-1 leftovers are memory-only, NOT filed as seams** (deliberate — the cycle ran inline): the optional FE case-picker; the pre-existing `app.test.jsx` ModeSwitch fail.

## Load-bearing context the next monitor MUST know

**Why CE-PRODUCT-1 is moat-safe.** P2c grades a non-`_core` workspace in a SUBPROCESS *precisely because* the frozen council binds its pack at import — the in-process council is never re-bound, `compliance_council.py` is byte-identical, and the R-GUARD license gate is never skipped (the codes-⊆-KNOWN consistency gate fires for real at grade time in the pack-bound subprocess, not in the BFF process which stays on `_core`). This is consistent with the PACK-DIST-1 / PLUGIN-1 moat-frozen-vs-`acc4973` invariant.

**The ledger drift this close fixed.** Before this reconcile, `streams.json` `current_phase` was stale at PLUGIN-1 — it had never even advanced to PACK-DIST-1, and the entire CE-product program was unrecorded. Now `current_phase` leads with CE-PRODUCT-1 (PACK-DIST-1 + PLUGIN-1 demoted into the `===PRIOR===` chain), `previous_phase` = PACK-DIST-1, the index carries the CE-PRODUCT-1 bundle (idx 0), and the STREAM doc's Current-cycle table + First-move both lead with it.

**Standing rules (persist):** LOCAL is SSOT — nothing pushed (owner-gated; user keeps it LOCAL, explicitly fine). Services are user-run — curl-check, never autostart. Commits pathspec-scoped (`git commit -m … -- <files>`, never bare — the shared branch accumulates foreign staged files). HARD GATEs need a fresh-critic worktree pass before close. Honest-Δ — no manufactured wins. **R-GUARD** (binding): never put the license gate on the 4 council inline-import accessors. **HPACK builds in the pack repo, never back in core** (`tests/test_pack_dist.py` A2 is the tripwire).
