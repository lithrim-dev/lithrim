# Ontology flag lifecycle — reference (local) vs gradeable (cross-repo)

> **The one law:** a flag may be **created or deleted locally only if it is a *reference*
> (`gradeable=false`) flag.** A **gradeable** (scoreable) flag's code comes **only** from
> `lithrim-backend` via `scripts/snapshot_taxonomy.py --backend-path …`. Inventing a gradeable
> flag from clean would manufacture a label the contract-of-record has not blessed — exactly
> what this repo exists to prevent (CLAUDE.md *"labels are true by construction"* + *"the
> taxonomy snapshot is the contract"*). FLAG-1 builds the reference surface and makes the
> gradeable refusal explicit and honest.

## The two flag classes (S-BS-10 partition)

| | **Reference flag** | **Gradeable flag** |
|---|---|---|
| `gradeable` | `false` | `true` |
| `tier` | `null` | `TIER_1 / TIER_2 / TIER_3` |
| `owner_roles` | `[]` | a `production_judges`-resident owner |
| In `taxonomy/taxonomy_snapshot.json`? | **No** (out-of-snapshot) | **Yes** (the snapshot's tier union) |
| Scored by the council? | **No** — grounding skip-logs it (`ontology.is_reference`, `grounded.skipped_non_gradeable`) | **Yes** — it can drive a verdict |
| Create / delete | **Local** (this doc, §A) | **Cross-repo** (§B) — never local |

The PUT gate (`_validate_ontology`, `apps/bff/app.py`) enforces this: a `gradeable` flag whose
code is **not** in the snapshot is rejected with **HTTP 422**. A `gradeable=false` reference flag
round-trips freely. That single check is the by-construction guarantee.

## §A — Reference flags: local create + delete (FLAG-1)

A reference flag is *known but out-of-snapshot*: documented in an agent's ontology working copy,
grounding-skip-logged, **never scored**. It is a first-class authoring object.

### Create (`gradeable=false` by construction)
- **Conversationally:** the `create_flag` tool — definitional fields only
  (`flag_code / category / definition / when_to_use / when_NOT_to_use / rationale`). There is
  **no `gradeable` field**; the bound `_create_flag` **hardcodes** `gradeable=false`, `tier=null`,
  `owner_roles=[]`. The agent has no path to a scoreable flag.
- **Via the API / human UI:** `PUT /v1/ontology` with the new flag carrying `gradeable: false`.
- Both persist to the agent-scoped working copy (never the committed seed) and emit an immutable
  audit record (`action=edit`, `target=ontology`; the before→after diff *is* the create evidence).

### Delete (reference-only, orphan-guarded)
- **Conversationally:** the `delete_flag` tool. **Via the API:** `DELETE /v1/ontology/flags/{code}`.
- The reference-only + orphan guards live in the **endpoint** (`delete_flag_endpoint`), so they hold
  for **every** caller (human, API, agent). Delete is refused (**422**) when the flag is:
  1. **gradeable / in-snapshot** — a contract code; removing it desyncs the contract (that is §B,
     a re-snapshot, never a local delete);
  2. **judge-assigned** — a persisted (global) judge lists it in `assigned_flags`; revert that judge
     first;
  3. **case-emitted** — a committed `examples/*.jsonl` case lists it in `expected_safety_flags`
     (a corpus orphan that would break the golden lint).
- Only an **unused reference flag** deletes. The removal emits an immutable audit record
  (`action=delete`, `target=flag`, `before=<the flag>`, `after=null`). It is reversible — re-create
  any time.

## §B — Gradeable flags: the cross-repo re-snapshot procedure (NOT local)

A gradeable flag cannot be created from clean in `lithrim-bench`. Its code must be blessed by the
contract-of-record. The procedure is **architecturally cross-repo**:

1. **`lithrim-backend`** — add the new flag (its tier + owning role) to the council taxonomy
   (`compliance_council.py` and the role lens / council prompt that emits it). The owner must be a
   running `production_judges` role (an inert owner is forbidden — owner↔emit invariant).
2. **Re-snapshot** — refresh the contract:
   ```
   python scripts/snapshot_taxonomy.py --backend-path /path/to/lithrim-backend
   ```
   This rewrites `taxonomy/taxonomy_snapshot.json` (the tier union + `tier1_owners` +
   `production_judges`). **Never hand-edit the snapshot** — the fix is always to re-snapshot.
3. **Role lens** — confirm `LENS_BY_ROLE` (`lithrim_bench/runtime/council/judge_metric.py`) carries
   the owning role so the new code routes to a judge that actually runs.
4. **Re-seed** — rebuild the ontology seed so its gradeable set matches the snapshot:
   ```
   python scripts/seed_ontology.py
   ```
   `gradeable_flags_outside_snapshot` must return `[]` (the lint the PUT gate also runs).

Only after the snapshot carries the code does a `gradeable=true` flag pass `_validate_ontology`.
Until then, any attempt to create or flip a flag to `gradeable=true` from clean returns **422**:

> *a gradeable flag requires a lithrim-backend re-snapshot
> (`scripts/snapshot_taxonomy.py --backend-path …`); it cannot be created from clean locally —
> labels are true by construction.*

This refusal is the honest gate. It is never faked, and the snapshot is never auto-edited by the
BFF.
