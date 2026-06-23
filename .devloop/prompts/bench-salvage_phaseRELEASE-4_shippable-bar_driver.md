# Driver — `bench-salvage` phase `RELEASE-4`: the shippable bar (make demo + honest README + secrets)

> **Bundle ID:** `bench-salvage-phaseRELEASE-4-shippable-bar-driver`
> **Version:** v1 · **Authored:** 2026-06-23 · **Last re-verified against code:** 2026-06-23 (Phase 1a; the replay path was RUN at $0 during scoping)
> Release context: `docs/COMMUNITY_RELEASE_v1_PLAN.md` Cycle 4 (release hygiene). The frozen council engine is NEVER touched.

---

## KICKOFF (spawn as the devloop-executor subagent, or paste into a fresh session)

```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase RELEASE-4 (shippable-bar).
Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseRELEASE-4_shippable-bar_driver.md  (this doc)
  3. docs/RELEASE_README_DRAFT.md  (the honest current README — ADAPT this, don't invent claims)
  4. README.md  (the STALE current README — to be replaced)
  5. scripts/run_eval.py:380-410  (the replay branch — the $0/no-key/no-pack demo engine)
Then post plan-review per EXECUTOR.md. Do not write code until I say "go".
```

---

## 0. Why this cycle (the done-bar)

Make the harness **cloneable-and-runnable by a stranger**: a `git clone` → `make demo` shows the flagship loop ($0, no keys, no network, no external pack), an HONEST `README.md` documents what it does *and where it doesn't*, and a stranger knows their `.env` stays local. This is the actual June-30 release artifact. **Auth is explicitly DEFERRED** (a local self-hosted run doesn't need it — the README says "coming for exposed deployments"; do not build it).

**Scoping (RUN at $0 during authoring — `docs/research`-style evidence):** the replay path already produces the flagship loop. On the built-in domain-neutral `_core` case `_core_fabricated_claim`, `grade_replay` (replays the captured council votes) + a LIVE `ground()` floor flip (PASS→BLOCK, deterministic, $0) + `composite()` yields: `verdict: reject`, `original PASS → after-ground BLOCK`, votes `{risk:BLOCK, policy:WARN, faithfulness:BLOCK}`, findings `[UNSUPPORTED_ASSERTION, SOURCE_CONTRADICTION, MISSING_CONTEXT]`. **0 LLM calls, 0 network, 0 keys.** That IS the demo. The work is wiring + honesty + hygiene, not new engine code.

---

## 1. Pre-flight reading (ordered)

1. `docs/RELEASE_README_DRAFT.md` — the honest, current README (the source for the new `README.md`; preserves the "What Lithrim Bench honestly does — and does NOT do" boundary section — that honesty IS the product).
2. `README.md` — the STALE one (old Synthea/paper framing, depends on `lithrim-backend`, contains a HARDCODED personal path `/Users/aregee/...` lines ~108/118/122/126 — must NOT survive into the shipped README).
3. `scripts/run_eval.py:380-410` — the grade dispatch: `--live` (paid), `--in-process` (paid), else **replay** ($0). Replay reads `agent.dataset.baseline` (committed file) else falls to `_resolve_from_provenance` (the SQLite path that FAILS on a clean clone). The fix is to give the demo agent a TRACKED baseline file.
4. `lithrim_bench/harness/grade.py:40-47` — `grade_replay(case, baseline_path)` (pure JSON read; the $0 core).
5. `data/config/agents/ws0_default.json` — the demo agent; `dataset.baseline` is currently `""` (the blocker) and `dataset.source` → `tests/fixtures/standalone/case._core_fabricated_claim.jsonl`.
6. The baseline DATA: `out/ws0/_core_fabricated_claim.json` (record with a nested `"result"` PipelineResult). **`out/` is likely GITIGNORED** — verify with `git check-ignore out/ws0/_core_fabricated_claim.json`; if ignored, the baseline must be RELOCATED to a TRACKED path (e.g. `examples/` or `data/`) so a clean clone has it.
7. `Makefile` — `test`/`lint`/`up`/`health` exist; no `demo`. The `## help` comment idiom is shell-comment-safe.
8. `.gitignore` — confirm `.env`, `.live_env`, `.connector_env` are ignored.
9. `.devloop/state/STREAM_bench-salvage.md` — the release-program entry (top) + open seams.

> **Citation discipline:** re-verify the cited lines on read (the scoping ran 2026-06-23). app.py / run_eval.py drift between cycles.

---

## 2. Deliverables (file-by-file — TESTS FIRST for the demo)

1. **`tests/test_demo.py`** (NEW) — the acceptance test, written first (RED before the demo is wired):
   - **A1** `test_make_demo_replays_the_flagship_loop_zero_config` — simulate a CLEAN CLONE: a tmp HOME/cwd or an explicit no-`.env`, no-`LITHRIM_BENCH_PACKS_DIR`, `_core`-pack environment. Invoke the demo's underlying command (NOT a paid grade) and assert the flagship loop: `composite verdict == "reject"`, the floor flip `original_verdict PASS → verdict BLOCK`, the per-judge votes present (3 roles), and the audit findings include `UNSUPPORTED_ASSERTION` + `SOURCE_CONTRADICTION`. Assert ZERO network/LM (e.g. no `openai`/`AZURE_*` needed; the test must pass with `OPENAI_API_KEY=""`). Mirror the replay assertions in `tests/test_ws0.py` / `tests/test_ws1.py` if they exist for the pattern.
   - **A3a** `test_demo_inputs_are_tracked_for_a_clean_clone` — assert (via `git ls-files`) that the demo CASE + BASELINE files the agent config points at are TRACKED (so `git clone` → `make demo` works). RED if the baseline lives only under gitignored `out/`.
   - **A3b** `test_secrets_are_gitignored` — assert `.env`, `.live_env`, `.connector_env` are git-ignored and NOT tracked; assert `.env.example` IS tracked.

2. **The demo wiring** (make A1 green):
   - Relocate/commit the demo baseline to a TRACKED path; extract the nested `"result"` PipelineResult into the clean shape `grade_replay` expects (or make `grade_replay` unwrap a `{"result": …}` wrapper — pick the smaller change, justify in plan-review).
   - Point `data/config/agents/ws0_default.json` `dataset.baseline` at the tracked file.
   - `Makefile`: add `demo: ; <command>  ## $0 demo: council votes → floor flip → audit (no keys)`. If `run_eval.py --agent ws0_default` CLI output isn't a legible flagship-loop view, add a thin `scripts/demo.py` that formats verdict → per-judge votes → floor flip → audit (the scoping's output shape is the target) and point `make demo` at it. Keep it $0/no-key/no-pack.

3. **`README.md`** — REPLACE the stale content by ADAPTING `docs/RELEASE_README_DRAFT.md`: the open-core framing, the `make demo` zero-config quickstart + the BYOK live quickstart (`LITHRIM_LLM_PROVIDER=openai` + `OPENAI_API_KEY` — the Cycle-1 path), the flagship-loop diagram, the architecture table, the **honest "where the floor does / does NOT generalize" boundary section (KEEP verbatim-ish — no over-claims)**, the connector/MCP note, the open-core/license note. **NO hardcoded personal paths** (`/Users/...`), no `lithrim-backend` dependency in the quickstart, no over-claims. The OLD `README.md` Synthea/paper content that's still true may move to `docs/` or be dropped — do not delete the paper reference, but the README's FRONT must be the product, not the paper.

4. **`.env.example`** (NEW, tracked) — a commented template: DEMO needs nothing; LIVE/BYOK = `LITHRIM_LLM_PROVIDER=openai` + `OPENAI_API_KEY=` (note `=azure` + `AZURE_OPENAI_*` as the alternative); external packs = `LITHRIM_BENCH_PACKS_DIR` + `LITHRIM_BENCH_PACK`. A one-line "this file is a template; your real `.env` stays local and is gitignored." Add a short README "Your data & keys stay local" section pointing at it.

---

## 3. Plan-review checkpoint (non-negotiable)

Post: understanding · the demo command + the baseline-relocation decision (relocate-file vs unwrap-in-grade_replay) · the README adaptation plan (what moves, what's preserved verbatim — especially the honesty section) · the clean-clone test mechanism · risks · any deviation. Wait for "go".

---

## 4. Scope guardrails — NOT in scope

- **Auth** — deferred (local self-host doesn't need it; the README says so). Do not build it.
- **The ruff mass-fix** — the separate refinements sweep (it entangles with the concurrent `spec.py`).
- **A broad hardcoded-path / secret hygiene sweep** beyond the README + `.env.example` — the refinements sweep. (But DO remove personal paths from the README you're rewriting.)
- **Cycle 2b shell DELETE UI · Cycle 3 connectors** — separate cycles. Do not touch `apps/shell/`.
- **The frozen council** (`compliance_council.py`, the `judges_dspy.py` consensus seam) — NEVER touch; seam-freeze 0-delta.
- **No live/paid grade** in the demo or tests — replay only.
- **The foreign files** `lithrim_bench/verification/spec.py` (staged) + `apps/shell/src/app.jsx` (unstaged) — NEVER commit them.

If something feels load-bearing-but-unlisted, HALT and surface in plan-review.

---

## 5. Acceptance criteria (each a test or a concrete grep)

- **A1.** `make demo` shows the flagship loop $0/no-key/no-pack on a clean-clone sim — test `tests/test_demo.py::test_make_demo_replays_the_flagship_loop_zero_config`.
- **A2.** `README.md` is the honest product README — no `/Users/` path, the `make demo` + BYOK quickstarts present, the honest boundary section preserved. Test/grep `tests/test_demo.py::test_readme_is_clean_and_current` (assert no `/Users/` in README.md; assert `make demo` + `LITHRIM_LLM_PROVIDER` + the "does NOT generalize" honesty phrase present).
- **A3.** Clean-clone inputs tracked + secrets gitignored — `...::test_demo_inputs_are_tracked_for_a_clean_clone` + `...::test_secrets_are_gitignored`.
- **A4 (Gate 0).** Full bare-CE suite GREEN + lint clean + seam-freeze 0-delta. Run `PYENV_VERSION=debuglithrim python -m pytest -q -p no:cacheprovider -W ignore`. The ONLY allowed pre-existing red is the foreign-`spec.py` `tests/test_pack_layer3.py::test_broad_domain_sweep_residual_is_the_closed_carveout`.

---

## 6. Commit structure (atomic; tests first; SCOPED PATHSPEC)

**Dirty index:** never bare-commit (foreign `spec.py` staged + `app.jsx` unstaged). Every commit names only this cycle's files; `git add <new file>` then `git commit -- <files>`; `git show --stat HEAD` after each.

1. **`test(demo): zero-config make demo + README/secrets hygiene — red`**
2. **`feat(demo): make demo — $0 flagship-loop replay on the _core case`** (baseline relocate + agent config + Makefile + optional scripts/demo.py)
3. **`docs(release): honest product README + .env.example`** (README replace + .env.example + the secrets section)

Bodies end with `Executed per bench-salvage-phaseRELEASE-4-shippable-bar-driver by session-2026-06-23-N.` + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## 7. Verification checklist

- [ ] A1/A2/A3a/A3b pass; `test(...)` precedes the impl commits
- [ ] `make demo` runs $0 on THIS checkout AND the test simulates a clean clone (no .env, no pack, OPENAI_API_KEY="")
- [ ] README.md has NO `/Users/` path; the honesty boundary section is preserved; quickstarts are accurate
- [ ] `.env.example` tracked; `.env`/`.live_env`/`.connector_env` gitignored + untracked
- [ ] Full bare-CE suite GREEN + lint clean + seam-freeze 0-delta (record commands)
- [ ] No file outside §2 (no `apps/shell/`, no frozen council, no foreign `spec.py`/`app.jsx`)
- [ ] No services autostarted; no paid grade; no push/tag
- [ ] Session log at `.devloop/sessions/session-bench-salvage-RELEASE-4-2026-06-23.json`

---

## 8. First move

1. Read `.devloop/personas/EXECUTOR.md`.
2. Read §1 pre-flight (re-verify lines; check `git check-ignore out/ws0/_core_fabricated_claim.json` early — it decides the baseline relocation).
3. Post plan-review per §3.

---

## 9. References

- Plan: `docs/COMMUNITY_RELEASE_v1_PLAN.md` (Cycle 4)
- Honest README source: `docs/RELEASE_README_DRAFT.md`
- BYOK quickstart context: `docs/research/PROOF_byok_openai_council_2026-06-23.md`
- Stream state: `.devloop/state/STREAM_bench-salvage.md`

## Hardness
- [x] Routine cycle — monitor inline close + cold devloop-critic subagent (the README is the public face: the critic checks the honesty boundary + no over-claims + no personal paths, and Gate 0).
