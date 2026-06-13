# Handoff — `bench-salvage` → next session (post-TOOL-2 + live demo)

> Written at session close, 2026-06-13. TOOL-2 is closed CLEAN; the SNOMED grounding flip is
> LIVE (real Hermes, not a fake) and recorded; two narrated pitches are published. Next monitor
> picks; the user redirects.

## What just landed (this session, in order)

### Ledger reconciliation + the inline product cycle
- **CE-PRODUCT-1** retro-registered (`6468ee5`) — the 10-commit inline CE-product program (`627fbbe..eaa19d4`) had no formal ledger record; advanced `current_phase`, prepended the index bundle, wrote session log + handoff.

### TOOL-1 — the kind:tool plane
- **`487b7e1`** — fold `kind: tool` into the unified plugin registry (`plugins.tool_plugins()` core static tuple ⊕ `pack.load_pack_tools()` for pack-contributed tools, appended into `provenance_snapshot()`, tier-gated). MCP is the standard; `transport: service`/`in_process`; `implements` carries the sub-kind (`tool.mcp_server`/`api_connector`/`kb_query`/`terminology`/`builtin`). **Open/closed proven** via a fixture tool, **fresh-critic CLEAN** (7/7). Moat byte-frozen.
- **`2ca7690`** — TOOL-1 registered in the ledger (session log + handoff).

### TOOL-2 — the 2 Pro tools + the SNOMED grounding flip
- **CORE `dba90df`** — `verification/mcp_client.py` `McpStdioClient`: stdlib (`subprocess` + JSON-RPC 2.0) MCP-stdio client. Domain-agnostic (the PACK-3 broad-domain sweep enforces it). Injectable transport for hermetic tests. 6 tests.
- **PACK `eb406ca`** (lithrim-pack-healthcare) — `healthcare/tools.json`: `hermes_snomed` (`tool.terminology`; `service.mcp` `hermes --db snomed.db mcp`) + `kb_hipaa` (`tool.kb_query`; `:8002` `hipaa-compliancev2`). Both register **tier: pro**, ABSENT under deny.
- **PACK `6eaffe4`** — the `SnomedSubsumptionGrounding` suppress executor (`floors.py`): resolves PMH items + record conditions to SNOMED codes via Hermes `search`, suppresses `FABRICATED_HISTORY` iff every item is `==` or `subsumed_by` a record concept. 5 by-construction tests, hermetic.
- **CE `9b1b319`** — parity-test pins (snomed_subsumption = contract/pro/service/grounding.suppress).
- **`5b02d47`** — TOOL-2 registered in the ledger. Fresh-critic CLEAN (7/7); moat byte-frozen vs `acc4973`.

### Post-TOOL-2 (this session's later work — INLINE, not a formal phase)
- **`b26b630`** — fix(bff): **non-`_core` packs subprocess on REPLAY too**, not just live/in_process. The `_core`-bound BFF process can't bind a pack's grounding executors; a healthcare replay was 500-ing. Enables the `$0` SNOMED replay demo.
- **`56bca2e`** — gitignore + untrack `.mcp.json` (holds the Zyng API token). *(A prior commit briefly tracked the token; removed from branch via reset-soft + clean re-commit; orphaned in reflog only, never pushed. **Rotate the token** for zero-risk.)*
- **`496359a`** — feat(chat): surface `grounded_adjustments` in the `run_eval` tool result, so the conversational agent can NARRATE which tool suppressed which false positive (it was honestly declining before because the tool only returned the verdict). Still A-SAFE — replay-only.

### Hermes — made runnable (the user delegated)
- `wardle/hermes` cloned to `../hermes`; the published 1.4.1614 *library* jar has no CLI main (`com.eldrix.hermes.cli` ∉ ns set; the spike's `:run` alias was broken). The CLI main `com.eldrix.hermes.cmd.core` (with the `mcp` subcommand) lives in the SOURCE repo.
- **Wrapper:** `~/.local/bin/hermes` = `cd ../hermes && exec clojure -J-Dlogback.configurationFile=../hermes/logback-stderr.xml -M:run "$@"`.
- **Caught a real bug:** Hermes routes logback INFO to STDOUT, corrupting the MCP JSON-RPC stream → `JSONDecodeError: Extra data`. Added `../hermes/logback-stderr.xml` to route logs to STDERR.
- **Live-proven:** `hermes --db /Users/aregee/Workspace/github.com/hermes-spike/snomed.db mcp` → 28 tools; `McpStdioClient` end-to-end against real Hermes (`subsumed_by(44054006, 73211009) = True`); `SnomedSubsumptionGrounding` suppresses the specificity FP, keeps the unrelated case standing.
- **The full live in-process grade reproduced the flip:** real council raised `FABRICATED_HISTORY` → live Hermes suppressed it (`grade_path: in_process`; verdict stays BLOCK because other real findings remain — honest-Δ intact).

### The recordings (managed zyng MCP)
- `~/.local/bin/zyng-mcp` (pipx) wired into `.mcp.json` server `zyng` (managed, cloud-rendered on credits); the old vendored zyng kept as `zyng-local`.
- **Recording #1** — UI flow: `/Users/aregee/zyng-out/snomed_suppression_demo.mp4` · https://app.zyng.work/v1/artifacts/job_9b0814808514511e
- **Recording #2** — conversational pitch: `/Users/aregee/zyng-out/this_is_lithrim.mp4` · https://app.zyng.work/v1/artifacts/job_9d6d6e105df165e8
- Both honest-Δ: real council finding → real live-Hermes suppression → verdict stays BLOCK (other real findings remain).
- Zyng credits: ~2321s remaining (~38 min); `capture_clips` is free, `publish` spends.

## Demo state (still wired — re-run any time)
- Workspace **`demo-clinical`** (healthcare); agent **`snomed-demo`** = case `bench_scribe_v1_inject_condition_1bd0f10dc7b5` + the WS-0 baseline + a **snomed_subsumption-bound ontology** at `out/demo/ontology_snomed.json`. The case's `patient_profile.conditions` has *"Diabetes mellitus (disorder)"* added (the specificity tweak).
- To re-run live: switch the shell to `demo-clinical`, select `snomed-demo`, click **Run live**. Or via chat: select `snomed-demo` and ask Lithrim to evaluate.
- BFF active workspace was restored to `default` at close (so tests stay isolated).

## What's next — the user's strategic call (do NOT autostart)

The natural arc the user laid out (from the TOOL-2 register): **pick N cases → evaluate → calibrate the council → flags-that-query-tools → custom criteria → promote to an Eval Pack.** The tooling is in place; the next phase is the user-facing eval flow.

Other queued options (none autostarted):
- **(a) Calibration / live flip:** flip the live healthcare `FABRICATED_HISTORY` binding from `record_presence` to `snomed_subsumption` (a one-line ontology change — a deliberate calibration decision; per CLAUDE.md "labels true by construction").
- **(b) Eval Pack flow:** pick N cases (the FE case-picker is also a CE-PRODUCT-1 leftover), evaluate the set, promote to an Eval Pack.
- **(c) The KB Pro tool:** the second Pro tool (`kb_hipaa`) is declared but unbound to a live flag — analogous to the SNOMED binding cycle.
- **(d) Pack-repo subtree split + CI** (PACK-DIST-2 cleanups — S-BS-135..139). Low-glamour but unblocking.
- **(e) Test-isolation seam** I filed during the session (chip): BFF tests read the global active-workspace pointer; a leaked active workspace makes them fail. Worth pinning.
- **(f) The owner-gated push** (LOCAL SSOT — user keeping LOCAL, explicitly fine).

## Open seams (this stream) — UNCHANGED by TOOL-2
- **S-BS-132** (ACCEPTED won't-fix) · **S-BS-135..139** (PACK-DIST-2-bound) · **S-BS-13/16/41** (older gate seams, inert).
- TOOL-1 + TOOL-2 + the post-TOOL-2 inline work opened **zero new seams** (one test-isolation chip filed via the session-task channel — non-blocking).

## Load-bearing context the next monitor MUST know

**The moat stays byte-frozen.** `compliance_council.py` 0-diff vs `acc4973` in every cycle window; `_apply_consensus`/`extract_verdict_confidence` AST-identical. R-GUARD honored — never gate the 4 council inline-import accessors.

**The BFF replay routing fix (`b26b630`) widens which tests read the active workspace.** A workspace switch leaked between an interactive demo run and a `pytest` invocation can make BFF tests route to the subprocess instead of the spied in-process `run_eval.run` → 200 instead of the expected 400. The fix is a pinned-workspace fixture (filed as a chip). At session close I restored the active workspace to `default`.

**The conversational chat tool surfaces grounded suppressions (`496359a`).** The agent now narrates "suppressed by `snomed-subsumption/v1`" — but it remains A-SAFE: no PAID knob in any chat tool; the only paid path is the human's **Run live** click + cost modal.

**The token thing.** `.mcp.json` holds the Zyng API token on disk (gitignored). One prior commit on this branch briefly tracked it; removed from branch (reset-soft + clean re-commit), orphaned in reflog only, **never pushed**. The pragmatic fix is to **rotate the token** in app.zyng.work (mint a new one, paste into `.mcp.json`, the old one's worthless). Belt-and-suspenders: `git reflog expire --expire=now --all && git gc --prune=now --aggressive` would scrub the reflog locally, but unnecessary given LOCAL SSOT.

**Standing rules (persist):** LOCAL is SSOT — nothing pushed. Services user-run — curl-check, never autostart. Commits pathspec-scoped (`git commit -m … -- <files>`). HARD GATEs need a fresh-critic worktree pass at close. Honest-Δ — no manufactured wins. Pack repo (`../lithrim-pack-healthcare`) has its own remote — be extra-careful, do NOT push.

## Memories updated this session
- `tool-plane-kind-tool` — TOOL-1 + TOOL-2 + the grounding binding
- `snomed-suppression-live-demo` — the reusable how-to (Hermes wrapper, demo agent, zyng managed)
- The MEMORY.md index carries pointers to both.
