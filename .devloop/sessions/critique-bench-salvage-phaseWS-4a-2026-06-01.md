# Spec-Adherence Critique — `bench-salvage` phase `WS-4a`

> Inline mode (routine hardness). Monitor authored the driver, so spec-vs-impl
> independence is reduced — but the executor ran as a separate session, so
> executor-vs-critique independence is preserved. Monitor independently re-read
> the shipped code + re-ran the suite rather than trusting the session-log prose.

## Metadata

- **Stream / phase:** `bench-salvage` / `WS-4a` (flywheel slice)
- **Driver bundle:** `bench-salvage-phaseWS-4a-flywheel-slice-driver`
- **Commits audited:** `894cc4d..da05779` (5 atomic: D0 corpus / D1 evalpack / D2 calibration-check / D3 tests / session log) on base `e1f1e4a`
- **Critique mode:** `inline`
- **Date:** 2026-06-01
- **Reviewer:** monitor

---

## Verdict

**`NON-BLOCKING FINDINGS`** — cycle MAY close (0 BLOCKING).

The load-bearing plan-review correction (the `corpus-row/1` schema) shipped **verbatim**: no label field, single `flag_code` (= `tool_call.flag_code`, not the contract), `contract` = `tool_call.contract`/`contract_type`, `verdict_before/after`, `owner_roles` present, `rollout_ref` = sha256 canonical-JSON. The required both-directions test addition is present and real. Scope held to exactly the 5 §2 files; clinical_v1 stays floor-less so S-BS-13/16 are inert. A1–A4 re-verified by the monitor.

---

## 1. Surface fidelity

| Spec (plan-review decision) | Implementation | Match? |
|---|---|---|
| `corpus-row/1`: drop the conflated `original_label\|injected_label`; `action` encodes direction | `corpus.py:75-87` — no label field; `action` from `schema_version` (`_action_for:44`) | ✓ verbatim |
| single `flag_code` = `tool_call.flag_code` (both directions) | `corpus.py:79` `tool_call.get("flag_code")` | ✓ |
| `contract` = `tool_call.contract` (suppress) / `contract_type` (floor), **not** the flag | `corpus.py:74` | ✓ |
| `verdict_before/after` (neutral, not `council_verdict`) | `corpus.py:80-81` ← `composite_before/after` | ✓ |
| add `owner_roles` (provenance for WS-4b / Q4.2) | `corpus.py:85` ← `record.owner_roles` | ✓ |
| `rollout_ref` = sha256(canonical JSON), mirroring `emit`'s sort-keys | `corpus.py:54-61` | ✓ |

**Findings:**
- `[NON-BLOCKING]` The module docstring (`corpus.py:17-24`) records *why* the schema is shaped this way (case_id absent; flag_code in both; action≠column) — the correction is internalized, not just applied. No surface drift.

## 2. Behavioral fidelity

- **Both-direction projection (the required addition).** `test_project_suppress_record` (action=suppress, flag_code=`MEDICATION_NOT_IN_TRANSCRIPT`, contract=`PresenceCheck` — explicitly asserted "the class name, not the flag", owner_roles=[]) **and** `test_project_floor_record` (action=floor, flag_code=`FHIR_STRUCTURAL_VIOLATION`, contract=`jute_gen`, PASS→BLOCK, owner_roles=[`structural_validator`]). The floor record is synthesized offline via the `test_grounding_floor` `_ReplayHttp` pattern + a floor-declaring **test** ontology — so the floor projection is proven without shipping a floor in clinical_v1. **Chain closes.** ✓
- **Eval-pack round-trip.** `test_evalpack_build_load_roundtrip` — build over the WS-0 case → `cases==[CASE_ID]` (one-case-thin), expected `{reject, [FABRICATED_HISTORY]}`, outcome verdict=reject, `corrections[0].action=="suppress"` (corpus-row provenance carried into the pack), dump→load identical. **Chain closes.** ✓
- **Calibration verdict-match-only.** `test_calibration_check_warns_on_verdict_mismatch` — a record with perfect ECE (0.0) but a verdict miss → `status=WARN`, `verdict_match_rate=0.0`. This is the proof ECE never moves status. **Chain closes.** ✓

## 3. Out-of-scope intrusion

`git diff --name-only e1f1e4a..da05779` = exactly `corpus.py`, `evalpack.py`, `report.py` (+59, the `calibration_check` addition), `tests/fixtures/ws4a/corpus.example.ndjson`, `tests/test_ws4a.py`, + the session log. **No intrusion** — no backend, no floor added to a shipped ontology, no WS-2 dep, no `/eval-runs/compare`, no locked gate, no drive-by. ✓

## 4. Spec ambiguity surfaced

- `[OPEN-QUESTION]` **Q4a-1 — the shipped flywheel corpus is suppress-only.** On clinical_v1 (floor-less) the corpus will only ever accumulate `action="suppress"` rows; `action="floor"` rows require a floor-declaring ontology, which is gated by **S-BS-16** (inject-param validation) and is WS-4b / a-floor-domain territory. This is correct and expected — the floor *projection* is proven by `test_project_floor_record` — but the *demonstrable corpus* is one-directional until a floor ships. Characterization, not a defect.
- `[OPEN-QUESTION]` **Q4a-2 — one-baseline → one-case eval-pack.** Only `baseline.<case>.json` exists, so the thin pack is genuinely one case; `build_pack` is N-case-general but the committed pack = `[ws0_default]`. Acknowledged-not-hidden (`evalpack.py` docstring + comment). Multi-case breadth needs real `--live` baselines → WS-4b (gated S-BS-13).
- `[NON-BLOCKING]` **rollout_ref not resolvable from committed files** — the example fixture's `rollout_ref` points to a record that lives only in the gitignored lake. `test_committed_example_corpus_fixture_shape` deliberately does NOT assert resolvability. Handled as the monitor flagged at plan-review.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity | 0 | 1 | 2 |

**Total BLOCKING: 0** → cycle MAY close.

## Required actions

None blocking. Carry-forwards:
1. **Q4a-1 (suppress-only corpus)** — when the first floor-declaring ontology ships, S-BS-16 (inject-param validation) must close first; that's where `action="floor"` corpus rows begin to accumulate. Owner: WS-4b / a-floor-domain cycle.
2. **Q4a-2 (one-case pack)** — multi-case breadth + floor-apply replay → WS-4b (gated S-BS-13).

## Discipline self-check (inline mode)

- [x] Monitor re-read the shipped `corpus.py` + `test_ws4a.py` and re-ran `pytest -q` (171/3) + ruff, rather than trusting the session-log prose
- [x] Independently confirmed the corrected `corpus-row/1` schema shipped verbatim (the load-bearing plan-review correction)
- [x] Verified scope via `git diff --name-only` (exactly the 5 §2 files + log) and clinical_v1 floor-lessness (`['presence_check']`)
- [x] Inline-mode caveat recorded: monitor authored the driver (spec-vs-impl independence reduced); executor was a separate session (executor-vs-critique independence preserved)
