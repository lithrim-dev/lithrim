# HANDOFF — bench-salvage — NARR-5 closed → NARR-6 (2026-06-17)

> **For the next session.** The narrative-eval wedge now has a **live, honest, multi-model demo**.
> **NARR-5 (offline foundation D1-D4 + the PAID live 3-model council run D5) is CLOSED CLEAN**
> (HARD GATE; fresh cold critic CLEAN + monitor audit CLEAN; the D5 proof capsule honestly matches the
> run artifacts — no manufactured win). Next is **NARR-6** — the polished walkthrough + zyng video +
> the 4 carried seams. **Resume:** `/devloop-resume bench-salvage`, then read this doc + the proof capsule.

---

## What just landed (NARR-5)

| Commit | What |
|---|---|
| `2f65ce6` | test-RED — `tests/test_narrative_corpus_bridge.py` (D1) + `tests/test_narrative_multimodel_seam.py` (D3/D4) + `artifact.test.jsx` (D2); D1+D2 RED at parent |
| `76c00ed` | **D1** — `load_case` workspace-corpus fallback (`picklist.py:101-145`, `S-BS-NARR2-1`; lazy-guarded, strictly-last → S-BS-9 PACK_FILES-first preserved) |
| `0361fee` | **D2** — ReportTab Floor Blocks section (`artifact.jsx:111-132` renders `composite.floor_adjustments`) |
| `2e8b421` | **D3/D4** — pack-gate the seam proofs (`models=` alone; LENGTH_VIOLATION MOCK) |
| `f0ac250` | ruff clean the D1 test |
| `e74e6a9` | the D1-D4 session log |
| `550f1f5` | **D5** — the live multi-model proof capsule (`docs/research/PROOF_narrative_live_council_2026-06-17.md`) |

**D5 — the visceral live proof (honest-Δ, owner-go'd PAID):** 3 `in_process` v2 Azure council runs via the live BFF (`storyworld_`/narrative pack). **SILENT_DEGRADATION floor flips PASS→BLOCK→reject LIVE** on both the default GPT/Mistral/Llama trio AND a Claude-swapped trio; the **clean case approves** (no false-fire); `risk_judge` confidence **0.97 (Azure GPT) → None (BYO-Claude)** = a record-visible per-judge model swap; and the strongest point — **`risk_judge`'s own verdict was model-dependent (WARN on GPT → PASS on Claude) but the deterministic floor caught it BOTH ways → reject** = the moat thesis demonstrated live. Run artifacts: `out/narr5_d5/*.json` (gitignored).

**The headline finding (from the reassessment):** the multi-model council is **config-only** — no engine work; the default trio is already 3 distinct Azure deployments (`_ROLE_DEPLOYMENT`), and a per-judge `byo-claude` binding swaps a role live. **MOAT byte-frozen** throughout.

**Gate 0:** pack=narrative 19/0; pack=healthcare 587p / 5 pre-existing-flaky / **0 new deterministic**; vitest 0-new. RED→GREEN non-vacuous for D1+D2.

---

## ⚠️ What NARR-5 honestly did NOT prove (the carried seams)

- **`S-BS-NARR4-1` (NARR-6 obligation):** the REAL live `LENGTH_VIOLATION` positive-catch is still owed. D4 proved it offline via a **predictor mock**; D5's cases weren't over-length scenes, so the live `policy_judge` never fired it. Prove it with a genuine over-length-preamble scene + a real `policy_judge` LM call (honest-Δ — it may or may not fire).
- **`S-BS-97`:** the per-vote `.model` carries the ROLE NAME (`"risk_judge"`), and `deployment`/`provider` are null — so the "3 distinct models" claim is evidenced by the wiring + the confidence-swap, NOT the vote record. Surface the real per-judge deployment in the vote record + the JudgeTab (the record-proof + the provenance UI).
- **`S-BS-NARR5-1`:** the subprocess `in_process` grade path returns `cost_tokens={0,0,0}` — a real PAID run's spend isn't captured. Wire cost surfacing for the subprocess path.
- **`S-BS-NARR5-2`** (coverage): `test_pack_files_first_precedence_preserved_on_collision` is **vacuous** under the canonical env (its collision id isn't in `PACK_FILES`, so it always takes the else-branch). The precedence is correct in code; strengthen the test with a real `PACK_FILES` case_id. (Minor twin: the D2 fixture `disposition:"inject_block"` vs the live `"VIOLATION"`.)

---

## What's next — NARR-6 (the polished demo + the seams)

Per the v2 split: the live 3-model run is DONE (D5); NARR-6 is the POLISHED surface + the carried seams. **Order of work (do a live reassessment first — services were up this session; confirm before locking):**
1. The **Claude_in_Chrome browser-driven walkthrough** — drop-JSON → `:3031` live ingest (`ingest_cases`) → 3 cases appear → grade → the ReportTab floor-block + the multi-model verdict, all 4 services. (Caveat `[[browser-mcp-confirm-blocks-renderer]]`: drive PAID ops via the BFF API, not a native confirm.)
2. The **zyng-narrated proof-capsule VIDEO** of the D5 honest-Δ moment (the proof capsule is the doc half; `[[proof-capsule-convention]]`).
3. **`S-BS-NARR4-1`** (the real live LENGTH_VIOLATION catch) + **`S-BS-97`** (per-judge model provenance) — these two most strengthen the multi-model + judge story.
4. **`S-BS-NARR5-1`** (cost surfacing) + **`S-BS-NARR5-2`** (the precedence test) — hygiene; fold opportunistically.

## Standing prefs (unchanged)
Services are UP this session (curl /health before use; NEVER autostart) · no push without owner approval (branch `bench-salvage/ws6c-dspy`, **NOT pushed**) · pathspec-only atomic commits · tests-first (RED before code) · canonical env `LITHRIM_BENCH_PACK=healthcare LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim` for the green bar (`LITHRIM_BENCH_PACK=narrative` for the targeted tests) · diagnose-before-edit · honest-Δ / BYO-key, deliberate PAID runs (D5 was owner-go'd) · MOAT byte-frozen · proof-capsule convention for every A-LIVE attestation.

## First move (next session)
1. Read this doc + `docs/research/PROOF_narrative_live_council_2026-06-17.md` + the NARR-5 critique (`.devloop/sessions/critique-bench-salvage-phaseNARR-5-2026-06-17.md`).
2. Live reassessment (services up): confirm the browser-walkthrough reuse surface + decide whether to attack the seams (S-BS-NARR4-1/S-BS-97) before or alongside the video.
3. `/devloop-expand-driver bench-salvage NARR-6` (author from the spec + this handoff; re-grep every anchor; fold in the 4 seams + the walkthrough + the video).
