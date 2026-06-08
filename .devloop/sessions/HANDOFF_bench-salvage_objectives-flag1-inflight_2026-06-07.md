# HANDOFF — bench-salvage (monitor role) — 2026-06-07

> **For the NEW monitor session.** This session held the monitor role for the user's three 2026-06-07
> product objectives ([[three-objectives-ux-crud-byoc-2026-06]]). Two are CLOSED + the third is one
> cycle (FLAG-1) from done — FLAG-1's plan-review is posted and **awaiting the monitor's "go"**.
> **Resume:** `/devloop-resume bench-salvage`, then relay the FLAG-1 go below.

## The arc — 3 objectives, ~done
| Obj | Cycle | Status |
|---|---|---|
| #3 UX (markdown + chat) | **UX-1** | ✅ CLOSED CLEAN (`c58d7f2..f8bed47` + close `c4d33ab`) |
| #1 Claude native provider | **BYOC-1** | ✅ CLOSED + **A-LIVE attested** (`5c54aaf..c05d8b3`, close `fca336a`/`b74b6ff`; S-BS-92 + S-BS-94 closed; honest capsule shipped) |
| #2 CRUD-from-clean (judges/agents) | **CRUD-1** | ✅ CLOSED CLEAN (`893d7a7..eff4911`, close `a15be6e`; S-BS-98 opened, S-BS-96 sharpened) |
| #2 CRUD-from-clean (flags) | **FLAG-1** | 🔄 **plan-review posted, AWAITING GO** (driver `8f59407` + refresh `0f14a72`) |

After FLAG-1 closes, **all three objectives are done.**

## Git state (NOT pushed — owner-gated)
- Branch `bench-salvage/ws6c-dspy`, HEAD **`0f14a72`** (the FLAG-1 driver citation-refresh).
- Working tree: ONLY `M apps/shell/src/root.jsx` (a **concurrent session's** deliberate shell-as-default change — NOT ours, leave it) + 3 foreign untracked (`.claude/`, `.devloop/sessions/KICKOFF_CRITIC_…WS-6c-DSPy…`, `docs/research/REPORT_fhir_agentbench…`).
- **All monitor commits are pathspec-only.** Never `git commit -a`/bare (the dirty shared tree + the concurrent `root.jsx`). [[git-commit-pathspec-dirty-index]]
- Services were up: `:8787` BFF (`--reload`, debuglithrim), `:5180` shell, `:8002` backend. **Don't autostart** — `curl /health` first.

## 🔴 IMMEDIATE NEXT ACTION — relay the FLAG-1 "go" (executor is in a separate session, blocked on it)
The FLAG-1 executor posted a strong plan-review (reference-flag create/delete local; gradeable refused cross-repo). **Monitor audit verdict: APPROVE.** Paste this go to the executor:

```
GO — FLAG-1 plan-review approved. Proceed, with these confirmations:
1. CITATION-DRIFT (you caught it, you're right): flag-delete does NOT reuse delete_with_audit (that's
   SQL-row-shaped; the ontology is a JSON working copy). Use the AuditRecord shape (action="delete",
   target=flag, before→after) via AuditLog.record + a file-rewrite mirroring put_ontology_endpoint. The
   driver §1's "reuse delete_with_audit directly" is superseded by this.
2. Deviation #2 (audit asymmetry) ACCEPTED: create rides the frozen put_ontology_endpoint → action="edit"
   target=ontology (the before→after diff IS the create evidence; A6-clean). OPTIONAL (if cheap): also emit
   a thin flag-targeted action="create" AuditRecord after the PUT for legibility/symmetry — your call, not required.
3. D-B route-only (DELETE /v1/ontology/flags/{code}, NOT an 11th tool — count stays 10): confirmed.
   D-C docs/ONTOLOGY_FLAG_LIFECYCLE.md: confirmed. D-D owner_roles=[]: confirmed. D-E no create-if-missing
   in author_flag (keep create/edit split): confirmed.
4. LOAD-BEARING (build non-vacuous): A2 the gradeable-from-clean REFUSAL (out-of-snapshot gradeable=true →
   422 with the re-snapshot message; an in-snapshot code stays accepted) — KEEP {offenders} in the message
   (test_ws5_bff asserts the code is in res.text). A-SAFE: create_flag has NO gradeable field + hardcodes
   gradeable=False (reverting the hardcode must FAIL a test). taxonomy_snapshot.json BYTE-UNTOUCHED.
5. The three count/set test bumps (9→10) are sanctioned guardrail maintenance.
HARD-GATE: fresh-critic at close. Canonical pytest -q (debuglithrim + plain) baselining the 2 pre-existing
S-BS-96 failures. Pathspec-only; leave root.jsx. The :5180 smoke (A6): create a reference flag → try to make
it gradeable → see the honest refusal → delete the unused reference flag; screenshot.
```

## At FLAG-1 close (the new monitor's job)
7-item audit + **HARD-GATE fresh critic** (spawn a general-purpose Agent, cold context — same pattern as BYOC-1's `a6b5fbc4bd9b33e42` + CRUD-1's `a989dc135dc2d4d6a`). The critic must independently reproduce: **A2 gradeable-refusal non-vacuous**, **A-SAFE create_flag-can't-make-gradeable non-vacuous**, the **delete orphan-guards** (gradeable/in-snapshot + judge-assigned + case-emitted), **taxonomy_snapshot.json byte-untouched** + golden-lint/`package_case` still pass, frozen-seam 0-delta, scope/pathspec. Then close (critique + STREAM seam table + streams.json + index + memory + a close commit, pathspec-only). No proof capsule unless FLAG-1 surfaces a capability A-LIVE with an honest-Δ (it's CRUD-mechanics — likely none). **Then announce all 3 objectives done.**

## Open seams (current)
- **S-BS-91** (low) post-deny agent UX · **S-BS-93** (low) persistent fake chrome (TopBar/rail-footer/StatusBar) · **S-BS-95** (low) global switch wires only the DSPy judge path · **S-BS-96** (low, **sharpened**) order-non-deterministic observation-isolation test debt (the "2 failures" is an order-dependent floor; fix = subprocess-isolate + deterministic ordering) · **S-BS-97** (low-med) provenance blob doesn't tag the per-judge model · **S-BS-98** (med) **the judge store is GLOBAL (per-role), not per-agent** → a blank-slate agent is roster/Dataset/chat-clean but NOT judge-clean (the user said "noted-for-later"; candidate per-agent-judges refactor — key `(agent, role)`). Closed: S-BS-87/89/90/92/94.
- OQ carried (CRUD-1 critic): guard-precedence cosmetic (ws0_default-also-last → "seed default" msg); session-log diff-stat miscount (corrected in the CRUD-1 critique).

## Standing context for the monitor
- The **user runs the executor sessions** (pastes the kickoff into a fresh session; brings the plan-review + the return back to the monitor). The monitor audits, gives the go, runs the fresh-critic at close, commits the close artifacts (pathspec-only).
- **Prefs:** no autostart; no push without explicit owner approval; LLM-cost-conscious (the user authorizes paid runs explicitly — e.g. the BYOC-1 A-LIVE); honest-Δ only (no manufactured wins); proof capsule = doc + zyng video at every capability A-LIVE.
- **The core invariant (FLAG-1's whole point):** labels are true by construction; the taxonomy snapshot is the contract (codes come only from lithrim-backend via `snapshot_taxonomy.py --backend-path`). FLAG-1 builds reference-flag CRUD locally + **refuses** local gradeable-create honestly.
- Recent closes' critiques + session logs are in `.devloop/sessions/` (UX-1, BYOC-1, CRUD-1). The full per-cycle history + seam table is in `STREAM_bench-salvage.md` (First-move section is topped with the latest).

## Pointers
- Driver: `.devloop/prompts/bench-salvage_phaseFLAG-1_reference-flag-create-delete_driver.md` (§1 has the post-CRUD-1 citation refresh).
- The FLAG-1 invariant deep-trace: agent `ae6ab7f44357c1113` (summarized in the driver §0/§1).
- Memory: `three-objectives-ux-crud-byoc-2026-06`, `byo-claude-provider-thesis`, `git-commit-pathspec-dirty-index`, `proof-capsule-convention`, `unified-authoring-product-frozen-journey`.
