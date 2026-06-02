# Critique — `bench-salvage` WS-6c-AGENTIC (HARD GATE, fresh-critic)

**Verdict:** NON-BLOCKING → close-with-conditions (conditions now DISCHARGED by the A5 option-B addendum).
**Mode:** genuinely-independent fresh-critic — a 6-agent, fresh-context, from-source/git workflow (`wf_fdb93c9c-776`), the independence budget deliberately reserved for this grade-wire cycle since WS-6c (inline) + WS-6c-DSPy (inline-by-continuation). Synthesized + adjudicated by the monitor.
**Commit span audited:** bench `b619f2e..69188b8` (branch `bench-salvage/ws6c-dspy`) + backend `6720c70` (@ `mvp-ready`). A4 baseline `6bae3c0`.

## The crux — test integrity (C3): PRINCIPLED, not gamed

The single most important question for the cycle where the council first scores real cases: were the 2 stale S-BS-32 tests (`test_single_defect_pack`/WRONG_DOSAGE, `test_missed_escalation`/MISSED_ESCALATION) fixed *principledly* or *gamed green*? **Clean from source.** Three independent guards confirm discriminating power was preserved:
1. the negative-control oracle `test_s_bs_31_ownership_gate_still_holds_for_nonowner` survived intact — a non-owner (risk_judge) firing MISSING_ALLERGY solo still downgrades to `needs_review` (`tier1_triggered==[]`, `reason=='tier1_off_domain_single_judge'`); a blanket-open fix would have deleted exactly this assertion;
2. each one-strike oracle isolates the S-BS-31 mechanism (firing judge votes `needs_review`, the other two `approve`, so the `reject` can ONLY come from the ownership floor);
3. the consensus IP is byte-frozen (A4): a single `_TIER1_OWNERS` data hunk vs `6bae3c0`; the 4 consensus functions + tier tables byte-identical.
The one literal weakening (`{behavior_judge,risk_judge}⊆` → `{risk_judge}⊆`) is **defensible**: `behavior_judge` genuinely left the v2 trio; `risk_judge` is the real owns+emits production owner; the assertion still requires it. By-construction integrity MAINTAINED.

## Per-gate

| Gate | Verdict | Evidence |
|---|---|---|
| A0 (S-BS-31 closed) | PASS | one-strike restored offline for the 3 codes; the negative-control test proves the gate still downgrades non-owners |
| A4 (consensus byte-frozen) | PASS | single `_TIER1_OWNERS` data hunk vs `6bae3c0`; functions + tier tables identical |
| A6 (scope held) | PASS | orchestrator/stages **0 files**; backend = `_TIER1_OWNERS` + 2 prompts only |
| A7 (default install) | PASS | 187 passed/7 skipped; zero new lint in the cycle's own code |
| D0 (owner↔emit) | PASS | no inert owners; faithfulness emits MISSING_ALLERGY+VALUE_MISMATCH, policy emits FABRICATED_CONSENT; `risk_judge` correctly **dropped** from MISSING_ALLERGY (would be inert) |
| A5 (live) | was should-fix → **DISCHARGED** | see below |
| D3 (grade-wire) | was should-fix → **DISCHARGED** | real & wired; now in-suite covered by the env-gated real-council test |

## The two findings — monitor adjudication

**A5 live evidence.** The critic (C4) framed this as "fabricated/misrepresented" — **the monitor overruled that framing as a misread**: it conflated the A5 call with the separate committed `test_live_smoke.py` fixture. The A5 paid call ran `grade_inprocess` on the **committed** `proof_case:drop_allergy` (MISSING_ALLERGY); `test_live_smoke.py` is a distinct `council.evaluate(ws6c_live_smoke_fabricated_history)` smoke. The call was real (specific per-judge codes, Mistral `None`, ~30k tok) and the executor *volunteered* the recipe≠code caveat. **Valid residual:** no committed execution artifact + ambiguous narrative + the MISSING_ALLERGY one-strike was offline-only. → user chose **option (B)**: complete A5 to the milestone evidence standard before close.

**D3 coverage (C6).** Grade-wire real and wired, but the in-suite tests used injected stages (skip on default-deps) — the real council path wasn't asserted in-suite. Plus the `run_eval.run` "signature unchanged" claim was false (gained `in_process=`, backward-compatibly).

## Conditions → DISCHARGED by the A5 option-B addendum (`9b2a9ce`, `5cf438b`)

- (a) **on-disk artifact** — `tests/fixtures/ws0/a5_live.drop_allergy.json` (verdict BLOCK / composite reject / Mistral `None` / 29,679 tok), one cost-confirmed paid call.
- (b) **in-suite real-council coverage** — `test_grade_wire.py::test_v2_trio_grade_inprocess_live`, env-gated (importorskip openai), passes live / skips $0 by default. Closes S-BS-35(b).
- (c) **A5 narrative corrected** — disambiguated from `test_live_smoke.py`; MISSING_ALLERGY one-strike marked offline-only.
- (d) **run_eval claim corrected** — "extended backward-compatibly (`in_process=` added)".
- A4 re-verified intact after the addendum (0-delta `118af7d..HEAD`); A7 still 187/7.

## Disposition

Test integrity principled; consensus byte-frozen; D0 owner↔emit clean; A5 milestone evidence now verifiable on-disk; scope held. **CLOSE** WS-6c-AGENTIC. Carryforward: **S-BS-34** (pre-existing ruff — `ruff.toml` exclude, not a reformat) and **S-BS-33** (citations_used seam-doc, reroute to WS-6d-KB; inert until KB lands).
