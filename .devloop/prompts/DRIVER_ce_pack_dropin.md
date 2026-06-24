# DRIVER — PACK-DROPIN-1: a pack drop-in volume + pack-aware agent seed + GET /v1/packs

**Goal:** the CE can **drop a pack into a volume/path and load it** — generically, any pack. Empty
drop-in → clean `_core` CE (the clean-by-construction property holds); drop a pack folder → its DATA
is discoverable AND its declared portable agents are seeded so they appear in the rail. This is the
core half of the owner's "drop packs in a volume" requirement (the pack-side portable agent is a
separate pack-repo build that conforms to the `seed_agents` contract this build DEFINES).

## CONTEXT (verified seams)
- Discovery seam (`lithrim_bench/harness/pack.py`): a pack id resolves via entry point →
  `LITHRIM_BENCH_PACKS_DIR` → in-repo `packs/`. `_manifest(pack)` (pack.py:226) reads `pack.json`;
  `pack_ontology_path(pack, check_consistency=False)` (pack.py:402) gives the relocatable ontology
  path. Find the discoverable-packs enumerator near pack.py:139 ("every DISCOVERABLE pack") — if none
  is public, add a small `discoverable_packs() -> list[str]`.
- Seed: `seed_config_db` (`lithrim_bench/harness/config.py:423`) globs `data/config/agents/*.json` →
  `agent_from_dict` (config.py:169) → `save_agent` (config.py:221). Called on first boot (db absent).
- Proven: mounting a pack dir + `LITHRIM_BENCH_PACKS_DIR=<dir>` resolves the pack in-container
  (`_pack_root('healthcare') → /dropin-packs/healthcare`, ontology loads).
- `pack.json` today: `{pack_id, version, tier, domain, ontology, flags_ref, council_roles, floors,
  generators, tools, judges}` — NO `seed_agents` yet.

## THE CONTRACT (this build defines it; the pack-side build conforms)
- **`pack.json` gains an OPTIONAL `"seed_agents": ["agents/<name>.json"]`** — pack-relative paths to
  PORTABLE agent JSONs the pack wants seeded into the config DB.
- Each seed-agent JSON uses LOGICAL refs, NOT host/repo-absolute paths: an `ontology_ref` (e.g.
  `"clinical/1"`) and a `dataset` whose `source`/`baseline` are pack-relative (or mode `in_process`
  for a live grade needing no baseline).
- **The seed RESOLVES refs to the current environment:** for each `seed_agents` entry of each
  discoverable pack, load the JSON, set `ontology_path = pack_ontology_path(pack)` (absolute, valid
  NOW — container or local), resolve a pack-relative `dataset.source`/`baseline` against the pack
  root, then `save_agent`. So a relocated/dropped pack's agent is valid wherever it's dropped.
- Seed-agent NAMES must be pack-distinct (the pack is responsible; e.g. `healthcare_default`). Do NOT
  seed an agent whose name collides with an existing one (skip-with-log, never clobber `ws0_default`).

## DELIVERABLES
1. **Pack-aware seed** — extend `seed_config_db` (or a helper it calls) to, AFTER the core agents,
   enumerate discoverable packs and seed each pack's `seed_agents` per the contract above. Resolve
   `ontology_path` via `pack_ontology_path(pack)`; resolve pack-relative dataset refs against the pack
   root. **Bare-CE (no pack discoverable) seeds ONLY the core agent — unchanged, clean.**
2. **`GET /v1/packs`** (`apps/bff/app.py`) — list discoverable packs `[{id, tier, domain, active}]`
   (active = the workspace's current pack) so the UI can show what loaded + offer them for a workspace.
3. **Drop-in volume (docker-compose.yml)** — add a `/dropin-packs` mount from a gitignored host
   `./packs-dropin` (a DIRECTORY mount, empty by default) and default
   `LITHRIM_BENCH_PACKS_DIR: ${LITHRIM_BENCH_PACKS_DIR:-/dropin-packs}`. Add `./packs-dropin/` to
   `.gitignore` with a tracked `packs-dropin/.gitkeep` + a short README-in-dir ("drop a pack folder
   here, e.g. `healthcare/`, then restart"). Empty drop-in ⇒ clean `_core` CE (verify the discovery
   falls through to in-repo `packs/_core`).
4. **Docs** — a README stanza: "Add a pack — drop its folder into `packs-dropin/` (or set
   `LITHRIM_BENCH_PACKS_DIR`), restart; `GET /v1/packs` shows it. Pro packs are `tier:pro`
   (license-gated; default permit-all)."

## TESTS (RED first) — bare-CE, hermetic
- A — `seed_config_db` with NO discoverable pack seeds ONLY the core agent(s) (clean default unchanged).
- B — with a FAKE drop-in pack on a tmp `LITHRIM_BENCH_PACKS_DIR` (a minimal `pack.json` with
  `seed_agents` + a tiny ontology + a portable agent JSON using `ontology_ref`) → `seed_config_db`
  also seeds that pack's agent, and its `ontology_path` resolves to the tmp pack's ontology (NOT a
  stale `packs/<x>` path). Build the fake pack under tmp_path.
- C — a seed-agent whose name collides with `ws0_default` is skipped (never clobbers the core seed).
- D — `GET /v1/packs` lists `_core` (bare-CE) + the fake pack when discoverable; marks `active`.

## HARD CONSTRAINTS
- Frozen council seam UNTOUCHED (`compliance_council.py`/`_apply_consensus`). NEVER stage
  `apps/shell/src/app.jsx`. Tests in the `debuglithrim` pyenv; full bare-CE MUST stay green (baseline
  **721 passed, 0 failed**). `ruff check .` clean. Scoped commit. DO NOT PUSH.
- Commit message ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Each commit SHA + message + `git show --stat` (no app.jsx). 3. RED→GREEN
evidence + full bare-CE count. 4. The exact `seed_agents` contract you implemented (so the pack-side
build can conform) + any deviation.