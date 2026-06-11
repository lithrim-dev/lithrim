# Driver — `bench-salvage` phase `CE-PACK-NEUTRAL-DEFAULT`: a neutral core default pack (ship without healthcare)

> **Bundle ID:** `bench-salvage-phaseCE-PACK-NEUTRAL-DEFAULT-neutral-core-default-pack-driver`
> **Version:** v1 · **Authored:** 2026-06-12 · **Last re-verified:** 2026-06-12 (HEAD b21820e)
> **Execution:** run by a monitor-spawned subagent in the main tree; pathspec-scoped commits; monitor audits at close.

**Release-gating.** Closes **S-BS-130** (+ retires the **S-BS-125** tripwire): today `DEFAULT_PACK="healthcare"` (`pack.py:46`), so `active_pack()` falls back to a Pro pack and `council_roster()` reads `packs/healthcare/` metadata for canonical validation under ANY active pack — i.e. **the core cannot boot without the healthcare pack on disk.** This ships a **neutral `_core` default pack** so the core is genuinely standalone. Non-frozen (no council file).

**MEASURED blast radius (monitor, 2026-06-12):** with a non-healthcare active pack the suite has **15 collection errors** — the suite + engine default deeply assume the clinical pack (floors/generators/taxonomy). The bounding mechanism (below) is a session `conftest` that pins `LITHRIM_BENCH_PACK=healthcare` for the *existing* suite, while the *shipped* default flips to `_core`.

---

## KICKOFF (for reference — this cycle is subagent-executed)

```
EXECUTOR for .devloop cycle: bench-salvage CE-PACK-NEUTRAL-DEFAULT (neutral-core-default-pack).
Read: EXECUTOR.md · this driver · docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md (§G5/CE-PACK-NEUTRAL-DEFAULT) · memory generic-ce-demarcation.
HALT-and-report if D0 shows the conftest bounding does NOT restore the suite (the scope is then larger than estimated).
```

---

## 1. Pre-flight (verified 2026-06-12, HEAD b21820e)

1. `lithrim_bench/harness/pack.py:46` `DEFAULT_PACK = "healthcare"` · `:62-63` `active_pack()` = `env LITHRIM_BENCH_PACK or DEFAULT_PACK` · `:222-242` `council_roster()` reads `pack_tier1_owners(DEFAULT_PACK)` (the S-BS-130 read) · the accessors `pack_tiers/pack_tier1_owners/pack_lenses/pack_production_judges/pack_prompts_path/pack_ontology_path/pack_ontology…`.
2. `packs/support_ticket_qa/` (CE-STANDALONE-1) — the independent-pack template to mirror for `_core` (pack.json + ontology.json + taxonomy_snapshot.json + council_roles/*.txt). `harness/ontology.py:144-178` — the ontology schema.
3. `tests/test_standalone_ce.py:271-287` — A-STANDALONE-4's "permitted = healthcare pack.json + taxonomy_snapshot.json"; after this cycle the run reads `_core` (not healthcare) for canonical roster → **A4 tightens to zero `packs/healthcare/` reads** (update it).
4. The healthcare-default reliance: `tests/verification/test_{dosage_floor,toolbox}.py` (floor tests needing healthcare floors) + the council-grade tests + the many `ONTOLOGY_SEED = packs/healthcare/...` tests — these stay green via the conftest pin.
5. `tests/` — check for an existing `conftest.py` (session scope) to add the pin to, else create one.

---

## 2. Deliverables

**D0 — MEASURE + validate the bounding mechanism (do this FIRST; HALT-gate).**
- Add a session-scoped pin: in `tests/conftest.py`, `os.environ.setdefault("LITHRIM_BENCH_PACK", "healthcare")` at import top (before any council import). Confirm it restores the suite (with `DEFAULT_PACK` still healthcare) — a no-op baseline.
- Then with the pin in place, confirm a subprocess with `LITHRIM_BENCH_PACK` UNSET + `DEFAULT_PACK="_core"` is the ONLY thing that exercises the neutral default.
- **HALT-and-report if** the conftest pin does NOT restore the suite to 0-new (the scope is larger — a per-test sweep — and needs a monitor re-scope decision).

**D1 — `packs/_core/` (a neutral, domain-neutral default pack).**
- `pack.json` — `pack_id:"_core"`, `tier:"core"`, `domain:"generic"`, own ontology/flags_ref/council_roles, `judges` = the deployable roster names `["risk_judge","policy_judge","faithfulness_judge"]` (⊆ `_ROLE_DEPLOYMENT`).
- `ontology.json` — minimal generic flags (a couple of neutral codes, valid per the schema) — enough that the pack loads + `council_known_codes`/consistency gates pass. No clinical content.
- `taxonomy_snapshot.json` — `tiers`/`tier1_owners`/`production_judges`/`lenses` over the neutral codes; **`tier1_owners` must cover the canonical owner roles** so any real pack's owners subset-validate against it (mirror healthcare's owner-role SET, neutral codes). Include `declared_but_not_running` if the roster identity needs `source_message_judge` as an owner-only role (check `council_roster()` semantics — it must still yield the same canonical role identity set so existing packs validate).
- `council_roles/{risk_judge,policy_judge,faithfulness_judge}.txt` — neutral role prompts.
- **No floors/generators** (a content pack, not clinical).

**D2 — flip the default.** `pack.py:46` `DEFAULT_PACK = "_core"`. Update the `:6` + `:62` docstrings ("default `_core`").

**D3 — the healthcare-absent proof `tests/test_neutral_default.py`.** A subprocess with `LITHRIM_BENCH_PACK` UNSET (the shipped default), asserting: `active_pack()=="_core"` · `council_roster()` validates + reads `packs/_core/` (NOT `packs/healthcare/`) for canonical metadata · a generic grade runs (authored path, mock LM, like the standalone test) → a verdict · `sys.addaudithook` proves **zero `packs/healthcare/` reads** (the strict version of A-STANDALONE-4). This is the "ship without healthcare" proof.

**D4 — tighten the standalone A4.** `tests/test_standalone_ce.py` A-STANDALONE-4: with the default now `_core`, the support_ticket_qa run reads `_core` (not healthcare) for the roster → change the assertion to **zero `packs/healthcare/` reads** (the original strict gate, now achievable). Note S-BS-130 closed in the test's header comment.

**D5 — docs.** `SPEC_STANDALONE_CORE_VALIDATION.md` §4 CE-PACK-NEUTRAL-DEFAULT → DONE + the conftest-pin note; G5 → closed. A CLAUDE.md one-line note (the shipped default is the neutral `_core` pack; healthcare is an opt-in pack). Mark S-BS-130 + S-BS-125 resolved.

---

## 3. Plan-review / report
Subagent: post your understanding + the D0 measurement result FIRST. If D0 holds, proceed D1–D5; if not, HALT and report the true blast radius. Surface any place that assumes `DEFAULT_PACK=="healthcare"` beyond the conftest pin.

## 4. Scope guardrails — NOT in scope
- **No core council file** (`compliance_council.py`, `judges_dspy.py`, `safety_flags.py`) — this is `pack.py` + a new pack + a conftest + tests. (The clinical-content removal is 6b.)
- **Don't delete/relocate healthcare** — it stays a fully-working opt-in pack.
- **Don't edit N test files** — the conftest pin is the bounding mechanism. If that's insufficient (D0 HALT), re-scope with the monitor, don't sweep blindly.
- No frozen-council edit; no service autostart; no push.

## 5. Acceptance
- **A1:** `LITHRIM_BENCH_PACK` unset + `DEFAULT_PACK="_core"` → `active_pack()=="_core"`, `council_roster()` green, a generic grade → verdict, **zero `packs/healthcare/` reads** (D3 test).
- **A2:** full suite **0-new vs `b21820e`** (debuglithrim) with the conftest pin (healthcare tests preserved). `ruff` clean on touched files.
- **A3:** `council_roster()` no longer reads `packs/healthcare/` under a non-healthcare active pack — the tightened A-STANDALONE-4 (D4) is green.
- **A4:** `grep -rl 'healthcare' packs/_core/` → empty; healthcare still loads + works when selected (`LITHRIM_BENCH_PACK=healthcare` → its tests green, covered by A2).

## 6. Commits (pathspec-scoped, memory `git-commit-pathspec-dirty-index`)
1. `feat(pack): _core — a neutral domain-generic default pack (CE-PACK-NEUTRAL-DEFAULT D1)`
2. `refactor(pack): DEFAULT_PACK = _core; pin healthcare for the test suite via conftest (D0/D2)`
3. `test(ce): healthcare-absent proof + tighten standalone A4 to zero-healthcare-reads (D3/D4)`
4. `docs: CE-PACK-NEUTRAL-DEFAULT done; close S-BS-130 + S-BS-125 (D5)`
End each body: `Executed per bench-salvage-phaseCE-PACK-NEUTRAL-DEFAULT-... by a monitor-spawned subagent 2026-06-12.` + the Co-Authored-By trailer.

## 7. Verification
- [ ] A1–A4 PASS · commits exist, tree clean for the cycle pathspec (foreign files untouched) · tests+ruff clean (record env) · no core council file touched · session log written · the D0 HALT-gate was honored

## 8. Hardness
- [x] **Routine** (monitor inline critique) — non-frozen. BUT it flips a global default: the **suite-0-new gate (A2) is load-bearing** + the D0 HALT-gate is mandatory. If D0 shows the conftest doesn't bound it, the cycle is bigger → return to the monitor before implementing D1+.
