# Pack drop-in volume

Drop a **pack folder** here, then restart the stack, to load it into the CE.

```
packs-dropin/
  healthcare/          <- a pack folder (its dir holding pack.json)
    pack.json
    ontology.json
    taxonomy_snapshot.json
    council_roles/
    agents/            <- optional: portable agents the pack seeds
```

- **Empty drop-in → a clean `_core` CE.** With nothing here, pack discovery falls through to the
  in-repo `packs/_core`, so the app boots on the neutral default with no clinical content.
- **Drop a pack folder + restart.** `docker compose` bind-mounts this directory to `/dropin-packs`
  and sets `LITHRIM_BENCH_PACKS_DIR=/dropin-packs`. After a restart the pack is discoverable, shows
  up in `GET /v1/packs`, and any portable agents it declares (`pack.json` → `seed_agents`) are
  seeded into the config DB so they appear in the rail.
- **Pro packs** are `tier: pro` (license-gated via `LITHRIM_BENCH_LICENSE`; the default is
  permit-all, so a Pro pack loads unless you deny it).

The `seed_agents` contract (what a pack declares so its agents seed here):

- `pack.json` may carry an optional `"seed_agents": ["agents/<name>.json"]` — pack-relative paths
  to portable agent JSONs.
- Each agent JSON uses **logical refs**, never host-absolute paths: an `ontology_ref` and a
  `dataset` whose `source`/`baseline` are pack-relative (or `mode: in_process`). The CE resolves
  `ontology_path` to wherever the pack landed and resolves pack-relative dataset refs against the
  pack root — so a dropped pack's agent is valid wherever it's dropped.
- Seed-agent **names must be pack-distinct** (e.g. `healthcare_default`). An agent whose name
  collides with an existing one is **skipped** — a dropped pack never clobbers `ws0_default` or any
  agent you already have.

Anything you drop here is gitignored (only this README + `.gitkeep` are tracked).
