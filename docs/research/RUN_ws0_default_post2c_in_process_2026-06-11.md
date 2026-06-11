# RUN — `ws0_default` PAID in-process council, post-1b/2b/2c (the owed before/after)

**Date:** 2026-06-11 · **Type:** A-LIVE PAID (in-process v2 Azure council, BYO-key) · **Cost:** ~1 case × 3 judges
**Command:** `PYENV_VERSION=debuglithrim python scripts/run_eval.py --agent ws0_default --in-process`
**Purpose:** the belt-and-suspenders LIVE confirmation owed since PACK-1 — that the pack-resolved council (after the 1b taxonomy + 2b owner-map + 2c roster/lens un-freeze) reaches the same VERDICT on `ws0_default` as the documented baseline. Offline A2 already proved the resolved data byte-identical (deterministic 0-delta); this confirms it end-to-end with real Azure judge calls.

## Result

| | BEFORE (baseline fixture `tests/fixtures/ws0/baseline.…json`) | AFTER (this run) |
|---|---|---|
| **Verdict** | **BLOCK** | **reject (stage BLOCK, was BLOCK)** |
| Planted defect | `FABRICATED_HISTORY` (2 judges) | `FABRICATED_HISTORY` ✅ |
| Other findings | `MEDICATION_NOT_IN_TRANSCRIPT`(2) · `FABRICATED_CONSENT`(1, KB-grounded) · `INCOMPLETE_DOCUMENTATION`(1) | `INCOMPLETE_DOCUMENTATION` · `HALLUCINATED_DETAIL` |
| Composite | — | 0.5 (ECE 0.5 over 2 non-null conf; small-N, indicative only) |

Raw output: `out/ws0/bench_scribe_v1_inject_condition_1bd0f10dc7b5.json` (gitignored).

## Honest verdict: PASS (verdict-level), with attributed secondary dispersion

- **Load-bearing claim HOLDS:** verdict 0-delta (**BLOCK → BLOCK**); the **planted defect `FABRICATED_HISTORY` reproduces**. That is what the un-freeze had to preserve.
- **Secondary findings dispersed** — NOT un-freeze drift. The un-freeze is a deterministic data-resolution change, proven byte-identical offline (A2); it cannot alter verdict logic. The shift (MED dropped, `HALLUCINATED_DETAIL` appeared) is ordinary live LLM run-to-run non-determinism (per the dispersion study: verdict-layer deterministic, finding-code emission dispersed in ~7/12 cases) — the same variance would appear re-running `acc4973` live today.
- **`FABRICATED_CONSENT` absent — cleanly attributable to `:8002` being down** (its KB-grounded leg via `KbRagTool`); an intentional run condition, not a regression.
- No grounded corrections fired (`(none)`): `:8002`/KB down + the `record_presence` suppress remains unwired (see [[grounding-floor-is-the-moat-next]]).

**Conclusion:** verdict-level live confirmation + the offline byte-identity (A2) together confirm the 1b/2b/2c un-freeze is behavior-preserving on the real council. The owed PAID before/after is DISCHARGED. Honest-Δ: a verdict-level PASS, NOT a manufactured perfect-match.

## Seam surfaced — S-BS-128 (config-plane migration gap)

The run first failed at **$0**: `ws0_default`'s stored `ontology_path = data/ontology/clinical_v1.json` (the pre-PACK-1 location). PACK-1 relocated the ontology to `packs/healthcare/ontology.json` (byte-identical `git mv`) and migrated the core's resolution, but the **persisted agent configs** in the local (gitignored) config plane `out/config/bench_config.sqlite` were not migrated — they still store the old literal path. Ran via a transient symlink shim (`data/ontology/clinical_v1.json → ../../packs/healthcare/ontology.json`), removed after. Low severity (local runtime state; a fresh seed points at the pack). The robust fix is pack-relative ontology resolution for agents, or a config-plane migration on relocation.
