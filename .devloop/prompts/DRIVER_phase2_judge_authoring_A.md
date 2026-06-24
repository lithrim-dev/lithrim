# DRIVER — PHASE2-A: the audited judge-authoring writer + roster-consistency relaxation (harness)

**Read first:** `docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md` (the discharged §8 gate) ·
`docs/specs/SPEC_COMMUNITY_EDITION.md` §8 · **OWNER SIGNED OFF 2026-06-25** on writing the taxonomy
snapshot via an audited, tier:core-only writer + relaxing one council-consistency check (the same
governance surface `POST /v1/criterion` was signed off for).

**The model to MIRROR:** `lithrim_bench/harness/criterion.py` — the audited snapshot-splice writer
(`splice_gradeable_criterion`, the tier:core gate ~103, the code∈taxonomy gate ~120, `_write_snapshot`
+ `restore_snapshot` atomicity, `NonCorePackError`). The judge writer is its twin.

**FROZEN SEAM — NEVER TOUCH:** `runtime/council/compliance_council.py` `_apply_consensus`. This driver
is HARNESS-LAYER ONLY (`lithrim_bench/harness/`) — NO `apps/`, NO `runtime/council/`, NO `app.jsx`.

## DELIVERABLES
1. **New `lithrim_bench/harness/judge_authoring.py`** — mirror `criterion.py`:
   - `splice_production_judge(pack, role, lens_codes, owned_codes) -> (before: dict, after: dict)`:
     - **tier:core gate** (reuse the `criterion.py` pattern: `_pack._manifest(pack)["tier"] == "core"`,
       else raise the `NonCorePackError` twin).
     - **role-id validation** — a snake/lower judge-id regex; **refuse a collision** with an existing
       `production_judges` entry (raise a clear `ValueError`).
     - **By-construction admissibility gate** (ALL author-time, the heart of the governance promise):
       1. roster ≥ 2 — `len(set(production_judges) | {role}) >= 2`.
       2. lens non-empty — `lens_codes` ≠ ∅.
       3. codes ∈ the active ontology/tiers — every code in `lens_codes ∪ owned_codes` ∈ the pack's
          taxonomy codes (mirror `criterion.py`'s code∈taxonomy check; the snapshot `tiers` union).
       4. **owner↔emit** — every `owned_codes` ⊆ `lens_codes` (no inert owner: an owner must also emit).
     - **Splice** (on the snapshot dict): `after["production_judges"] += [role]`;
       `after["lenses"][role] = sorted(lens_codes)`; for each c in `owned_codes`,
       `after["tier1_owners"].setdefault(c, []).append(role)`. Reuse `criterion`'s `_write_snapshot` +
       `restore_snapshot` for atomic write + rollback; clear any pack caches the writer invalidates
       (`pack.council_roster.cache_clear()` / `_council_known_codes` if present — see #2).
   - `write_role_prompt(pack, role, text)` — write the role-prompt seed into `pack_prompts_path(pack)`
     `council_roles/<role>.txt` (tier:core only; a blank/templated seed is fine — refinement rides
     `assignments`). Satisfies the `judge_assignment.load_role_prompt` FileNotFoundError wall.
2. **Relax the council-roster consistency wall (wall #4)** in `lithrim_bench/harness/pack.py`
   (`assert_judges_known` / `council_roster`, ~458-505): accept the ACTIVE pack's `production_judges`
   as roster-known (a single-function relaxation ABOVE the frozen seam, matching the PACK-2c
   source-of-truth flips — the snapshot already IS the runtime roster authority). It must ADD the
   active-pack roster as acceptable, NOT remove the existing AST-source ∪ DEFAULT_PACK-owners check —
   so `test_healthcare_pack_is_council_consistent` + all existing pack-consistency tests STAY green.

## TESTS (RED first) — `lithrim_bench/harness/tests/test_judge_authoring.py`
Use a TEMP tier:core pack fixture (copy `packs/support_ticket_qa` to tmp_path + point discovery at it
via `LITHRIM_BENCH_PACKS_DIR`, OR mirror however `tests/.../test_criterion*.py` builds its writable
pack). Mock nothing that hides the splice.
- A: `splice_production_judge` adds the role to `production_judges`, `lenses[role]`, and (for owned)
  `tier1_owners[code]` — assert the before/after deltas on the snapshot file.
- B: rejects `owned_codes ⊄ lens_codes` (the inert-owner guard) — raises, snapshot UNCHANGED.
- C: rejects a code ∉ the pack taxonomy — raises, snapshot UNCHANGED.
- D: rejects a non-core (tier:pro) pack — the `NonCorePackError` twin, snapshot UNCHANGED.
- E: rejects a role-id colliding with an existing `production_judges` entry.
- F: ATOMIC — an injected failure after the snapshot write (e.g. patch the prompt-write to raise) leaves
  the snapshot RESTORED (`restore_snapshot`), no partial state.
- G: `write_role_prompt` creates `council_roles/<role>.txt`.
- H (wall-#4): after splicing a new `production_judges` role, `assert_judges_known`/`pack` consistency
  for that pack PASSES for the new role (and a still-unknown role still FAILS — non-vacuous).

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` → green, ≥755 passed / 0 failed (the existing
  pack-consistency tests MUST stay green — the relaxation is additive). `ruff check .` clean.
- `git diff --name-only` = ONLY `lithrim_bench/harness/judge_authoring.py`,
  `lithrim_bench/harness/pack.py`, `lithrim_bench/harness/tests/test_judge_authoring.py`. NO `apps/`,
  NO `runtime/council/`, NO `app.jsx`. Scoped commits (`test…red`, `feat…green`). DO NOT PUSH.
  Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + `git show --stat`. 3. RED→GREEN + full bare-CE count.
4. The `splice_production_judge` signature + the exact admissibility errors it raises (so P2-B's endpoint
maps them to 422) + how you relaxed wall-#4 (so the critic can verify it's additive, not a weakening).
