# DRIVER — CE-INGEST-FASTFAIL (Build D): bound the BYO-data ingest grind — AFTER Build A

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §5.2-D. Both A and D edit `apps/bff/app.py`
(different regions) — run D AFTER A merges to avoid a self-conflict.

**Goal:** when a user loads/pastes BYO JSON, the DSPy/JUTE extractor can grind ~2 min (up to 6 LLM
attempts, no timeout) before failing. Make it **fast-fail** with a bounded timeout + a clear,
actionable error — nothing pinned.

## CONSTRAINTS (hard)
- Frozen seam untouched (this is the ingest path, not the council). The A3 invariant holds: on
  failure NOTHING is pinned, no audit row. Tests-first. Scoped pathspec. **Never stage `app.jsx`.**
  No push. `debuglithrim` pyenv. bare-CE ≥706p/0f.

## DELIVERABLES
1. Wrap `best_of_n_extractor(make_gen, rules, sample, n=2)` at `apps/bff/app.py:2885-2886` in a
   bounded timeout — default **30s**, configurable via `LITHRIM_INGEST_TIMEOUT`. On timeout, raise
   into the existing `RuntimeError` path (already caught at `app.py:2888` → tools.py surfaces it,
   nothing pinned).
2. Clear remediation message at the user surface (`apps/bff/agent/tools.py:767-777`): detect the
   timeout and say e.g. "ingest timed out after Ns — the extractor couldn't converge to a valid case
   structure; simplify the extraction rules, reduce the JSON, or name the join key explicitly."
3. (Optional, defensive) drop `max_iters` 3→2 at the call site (`app.py:2860`) and/or a 15s ingest
   `EtlpJuteClient` timeout (`etlp_client.py:61` is 30s). Keep these small + justified.
   Note: there is NO deterministic fallback for arbitrary BYO-JSON (the `_to_envelope` path is
   schema-known only) → bounded-timeout-then-clear-error IS the correct fix.

## TESTS (RED first) — hermetic, no network/LM
- A — monkeypatch `best_of_n_extractor` to sleep past the timeout → ingest raises a bounded error
  within ~the timeout (not a 2-min hang). Extend `tests/bff/test_ingest_cases_tool.py`.
- B — on that timeout: **nothing pinned** (corpus file absent / unchanged) and **no audit row** (A3).
- C — the user-facing error message names the timeout + a remediation hint.
- D — a fast/valid ingest path still succeeds (regression: the timeout doesn't break the happy path).

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` bare-CE ≥706p/0f. `ruff check .` clean.
- Scoped commit (`app.py` + `tools.py` [+ `etlp_client.py`] + the test). Exclude `app.jsx`. No push.
- Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
