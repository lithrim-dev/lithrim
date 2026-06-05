# HANDOFF — `bench-salvage` phase `UAP-5c` → next (`UAP-5c-2` candidate) kickoff

> **Written by the monitor on cycle close (2026-06-05).** Load-bearing context for
> the next monitor session that takes over after a compaction or after-hours break.
> Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `UAP-5c` — the FULL Domain→Judge→Flag→Run→Review-from-scratch conversational journey (commits `a4e313d..9227b87`, parent `9cac025`, 7 atomic pathspec-only, **NOT pushed**)
- **Critique verdict:** **NON-BLOCKING [0 BLOCKING / 1 NB / 1 OQ]** — HARD-GATE genuinely-fresh-critic, agent `ac63797ec49ec01ac` (`.devloop/sessions/critique-bench-salvage-phaseUAP-5c-2026-06-05.md`)
- **Audit verdict:** **CLEAN** (monitor 7-item, re-verified independently)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseUAP-5c-2026-06-05.json`

The full journey now runs from a blank agent over the proven UAP-5b spine. **3 new in-process SDK-MCP tools**, each a THIN wrapper over a FROZEN op → an EXISTING gen-UI card (no new types): `get_agent` (`$0` Domain read → `tool-agent_editor`), `author_flag` (audited `PUT /v1/ontology`, the Flag leg, **EDIT-ONLY** → `tool-flag_editor`), `review_runs` (`$0` Review read → `tool-audit_log`). **Both carried seams CLOSED:** S-BS-82 (the live `get_judge` break) + S-BS-81 (the A-SAFE allowlist-bounds). Green: default 293p/12s · debuglithrim 143p/3s · Vitest 51p/11f · ruff clean (monitor + critic re-run).

## What's next

- **Next phase:** `UAP-5c-2` (candidate lean) — the pre-authorized D-F SPLIT: complete the tool set
- **Driver bundle:** `bench-salvage-phaseUAP-5c-2-…-driver` (**not yet created** — STUB to author)
- **Driver path:** TBD — run `/devloop-expand-driver bench-salvage UAP-5c-2` to author it from the SPEC + this handoff
- **Blocked by:** none (UAP-5c closed; the spine + the parts-adapter + the audited ops all exist)

> **NEXT-CYCLE FORK is the monitor's choice — not forced.** (1) **UAP-5c-2** — wrap `assemble_agent` (`PUT /v1/agent`, audited WRITE — the heavier Domain-assembly) + `run_eval_pack` (eval-pack batch; **the wrapper MUST hardcode `live=False`** — the batch's per-agent `live` call is paid). Same thin-wrapper pattern; HARD-GATE (it ADDS the first agent-reachable WRITE beyond `author_flag`, so re-prove A-SAFE + extend the allowlist-bounds test). (2) **S-BS-46/49 corpus-deepening** — a clean-negative cohort to counter the S-BS-76 over-fire = the path to a real *optimize WIN* (UAP-4 was an honest LOSS). (3) **S-BS-74 live-correction demo** — engineer a case the authored trio over-fires → the gate corrects LIVE → the visceral S-BS-70 flip (for a pitch).

## Open seams for `bench-salvage` (active/recent)

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-83 | `author_flag` is EDIT-ONLY (conversational flag CREATION needs `owner_roles` authoring + snapshot refresh → human act) | low | `apps/bff/agent/tools.py` `author_flag` + a snapshot/owner-authoring surface | UAP-5c | **open (by-design boundary, critic-endorsed)** |
| S-BS-82 | `get_judge` live break (Query FieldInfo sentinel) | low/med | `app.py` `_build_tool_context._get_judge` | UAP-5b A-LIVE | **CLOSED (UAP-5c)** |
| S-BS-81 | A-SAFE safe-by-allowlist not safe-by-mode | low | `tests/test_uap5c_journey.py` + `loop.py` allowlist | UAP-5b | **CLOSED (UAP-5c)** |
| S-BS-80 | pre-existing TopBar "Run live" fires paid with NO in-DOM modal | low | `apps/shell/src/` TopBar handler | UAP-5b | **open (pre-existing, out of scope)** |
| S-BS-74 | the live CORRECTION needs a case engineered for the authored trio to over-fire (S-BS-70's visceral finale) | med | a by-construction over-fire case | UAP-3b-2 | **open** |
| S-BS-76 | the authored DSPy demos over-fire (UAP-4 honest LOSS root) | med | corpus / calibration | UAP-4 | **open** |
| S-BS-46/49 | corpus-deepening / clean-negative cohort for a real optimize win | med | corpus | (carried) | **open** |
| S-BS-70 | the visceral live verdict-flip (mechanism proven offline + live-SAFE) | med | a base-missed/semantic defect | UAP-5a | **live-corrected-PENDING** |

## Load-bearing context the next monitor MUST know

1. **The A-SAFE invariant got STRICTER, and UAP-5c-2 is where it gets tested.** UAP-5c is the cleanest A-SAFE state the product has had — *no* agent-reachable paid-capable op exists (the D-F split removed both `eval_pack`-`live` and `put_agent`-WRITE from the tool surface). The fresh-critic confirmed this by grepping `apps/bff/agent/` for any paid path and finding **nothing**. **UAP-5c-2 deliberately re-introduces an agent-reachable WRITE (`assemble_agent`) and the paid-capable `eval_pack`** — so its driver MUST (a) hardcode `eval_pack`'s `live=False` in the wrapper, (b) extend the S-BS-81 allowlist-bounds + no-paid-knob tests to the new schemas, and (c) keep every WRITE audited. Treat A-SAFE as the gate-decider again.

2. **The binding-layer landmine (S-BS-82 / the `fastapi-endpoint-as-plain-call-fieldinfo-trap` memory).** Every in-process tool wraps a BFF endpoint by calling it as a *plain function* via a closure in `_build_tool_context`. FastAPI does NOT resolve `Query(...)`/`Header(...)`/`Depends(...)` defaults on a direct call — an omitted param keeps the **FieldInfo object** as its value. This bit `get_judge` live (the offline 8/8 missed it because `TestClient` resolves the default). **Any new wrapper in UAP-5c-2 (`assemble_agent`, `run_eval_pack`) MUST pass every `Query`/`Header` param explicitly**, and its test must drive the BOUND closure (not the TestClient), or it won't catch the regression. This is the kind of bug only the **A-LIVE attestation** catches — which is why A-LIVE is load-bearing, not ceremonial.

3. **A-LIVE ATTESTED (2026-06-05, monitor, Chrome MCP, `$0` BYO-Claude):** the **UAP-5c A-LIVE `:5180`** full-journey ran end-to-end — `get_agent`/`get_judge` (the **S-BS-82 fix VERIFIED LIVE** — the UAP-5b crash is gone) + `author_flag` (the audited `ontology:ws0_default` edit **VERIFIED against the BFF `/v1/audit`**, ts `2026-06-05T15:53:35` — the conversation IS the audit log, server-side) + `run_eval` replay (run `a57bd49d`) + `review_runs` (the §2B audit_log card). A-SAFE held (replay/`$0` only; no paid run). A1–A4 + A-SAFE + A-FIXED all PASS live. **Still OWED:** the older **UAP-5a A8** `:5180` smoke. NOTE for UAP-5c-2: its A-LIVE will exercise the FIRST paid-capable wrapper (`run_eval_pack`) — re-verify the agent stays replay-only live, the same way this UAP-5c A-LIVE confirmed A-SAFE held. The user runs these; the monitor schedules + records the result. The `author_flag` EDIT-ONLY boundary (S-BS-83) is the correct owner↔emit posture (an agent fabricating flag owners is exactly what `CLAUDE.md`'s core invariant forbids) — do NOT "fix" it into agent-driven flag creation without an owner-authoring + snapshot-refresh design.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (the phase table + the open-seams table + the First-move top block).
3. Read this handoff doc.
4. Read the session log: `.devloop/sessions/session-bench-salvage-phaseUAP-5c-2026-06-05.json` + the critique `.devloop/sessions/critique-bench-salvage-phaseUAP-5c-2026-06-05.md`.
5. `git log --oneline -10` on `bench-salvage/ws6c-dspy` to see the commit timeline (nothing pushed).
6. Wait for user input. Don't autonomously start the next cycle — the fork (UAP-5c-2 vs S-BS-46/49 vs S-BS-74) is the monitor's call WITH the user.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md` + `.devloop/state/streams.json` (bench-salvage `current_phase` + `cycle_state_note`)
- This cycle: session `session-bench-salvage-phaseUAP-5c-2026-06-05.json` · critique `critique-bench-salvage-phaseUAP-5c-2026-06-05.md` · driver `prompts/bench-salvage_phaseUAP-5c_full-journey-from-scratch_driver.md`
- Spec (LOCKED): `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §13/R11 + `SPEC_PRODUCT_SHELL.md §10`
- Memory: `fastapi-endpoint-as-plain-call-fieldinfo-trap` · `browser-mcp-confirm-blocks-renderer` (S-BS-69) · `unified-authoring-product-frozen-journey` · `live-reassess-before-driver-lock` · `git-commit-pathspec-dirty-index`
