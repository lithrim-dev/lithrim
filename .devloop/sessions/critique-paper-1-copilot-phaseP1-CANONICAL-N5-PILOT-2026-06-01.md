# Spec-Adherence Critique — `paper-1-copilot` phase `P1-CANONICAL-N5-PILOT`

> Inline mode (routine). **Catch-up close** — the cycle was executor-closed
> 2026-05-28 (PROCEED-WITH-CAVEATS); the monitor formal close (this critique +
> index verdict-flip) was run 2026-06-01. Monitor independently re-verified the
> dispersion numbers against `dispersion.md` + the raw 60-row ndjson rather than
> trusting the REPORT prose.

## Metadata

- **Stream / phase:** `paper-1-copilot` / `P1-CANONICAL-N5-PILOT`
- **Driver bundle:** `paper-1-copilot-phaseP1-CANONICAL-N5-PILOT-dispersion-measurement-driver`
- **Commits audited:** `1e07e94` (pilot script) · `b09b567` (raw outputs + dispersion.md) · `b92ca3d` (REPORT) — all confirmed HEAD ancestors
- **Critique mode:** `inline` (catch-up)
- **Date:** 2026-06-01 (cycle ran 2026-05-28)
- **Reviewer:** monitor

---

## Verdict

**`NON-BLOCKING FINDINGS`** — cycle MAY close (0 BLOCKING). This was a **measurement** cycle; the deliverable is the dispersion table + the two mechanical decisions (S2, S-P1-13). All re-verified against the artifacts.

---

## 1. Surface fidelity

The driver's acceptance is output-shaped (A1–A10), not API-shaped. All present + re-verified:

| Spec (driver §5) | Artifact | Match? |
|---|---|---|
| A2 — 60-row ndjson (12×5) | `out/p1_canonical_n5_pilot.ndjson` `wc -l` = 60 | ✓ |
| A3 — 12-row dispersion.md + §2.2 columns | `out/p1_canonical_n5_pilot.dispersion.md` (12 case rows + cost table; TOTAL $3.4002) | ✓ |
| A5 — content_filter incidence | `0/60` (all rows `"content_filter": false` — monitor-verified, not just reported) | ✓ |
| A6 — S2 decision recorded **mechanically** | `WRONG_DOSAGE 0/5` → **WIDEN**; dispersion.md S2 row + REPORT §3; no "magnitude" override | ✓ |
| A7/A8 — REPORT §1–§11 + S-P1-13 disposition | `docs/research/REPORT_p1_canonical_n5_pilot_2026-05-28.md` | ✓ |

**Findings:** none. Decisions follow the empirical rule, not a judgment override.

## 2. Behavioral fidelity

- **S2 WIDEN (mechanical).** dispersion.md S2 row: sem findings `MEDICATION_NOT_IN_TRANSCRIPT:5/5`, no `WRONG_DOSAGE` → `0/5` → WIDEN. The rule (`≥1/5 KEEP, 0/5 WIDEN`) applied without override; contract change deferred to `P1-PACK-V2-WIDEN`. **Chain closes.** ✓
- **Verdict-layer determinism.** All 12 cases at `5/5` modal verdict frequency (dispersion.md `freq` column); per-judge vote splits in 4/12 (S1, S3, S4, M1), finding-code emission dispersed in 7/12. The paper-§5.4 claim ("verdict deterministic, flag-emission disperses") is exactly what the table shows. **Chain closes.** ✓
- **S-P1-21 (C1 regression).** dispersion.md C1 row: BLOCK 5/5, `risk_judge` 5×PASS, `faithfulness_judge` 5×PASS, `policy_judge` 5×BLOCK, `FABRICATED_CONSENT:4/5`. Matches the session-log raw-row evidence. The §5.5 "0/2 FP on cleans" claim genuinely does NOT replicate at N=5. **Chain closes.** ✓

## 3. Out-of-scope intrusion

`git show --stat` on the 3 commits: `scripts/p1_canonical_n5_pilot.py` (812) + `out/p1_canonical_n5_pilot.*` + the REPORT (241). **lithrim-bench only — no `../lithrim-backend` edit** (backend scope held empty, as the session log claimed). No intrusion. ✓

## 4. Spec ambiguity surfaced

- `[NON-BLOCKING]` **A4 cost overage.** $3.40 actual (conservative $1.5/$5.5 blend) vs the $2.50 envelope / $1.80 driver budget — the gap is a **cost-blend assumption** difference (driver assumed a more permissive $1/$3 blend = $2.20). Surfaced in REPORT §1/§8; user approved mid-cycle ($2.50→$5.00 ceiling). Documented, not silent. Real Azure invoice remains source-of-truth.
- `[OPEN-QUESTION]` **S-P1-13 disposition** — KEEP OPEN as a paper-§5.4 methodology limitation (the driver A8 explicitly invited open/closed/footnote). Sound: the dispersion stats *are* the published characterization; investigation deferred post-arXiv.
- `[OPEN-QUESTION]` **S-P1-21 root-cause attribution** — the *behavior* (C1 BLOCK 5/5, policy_judge `FABRICATED_CONSENT` 4/5) is **CONFIRMED** from the raw ndjson; the *cause* (`compliance_council.py:build_prompt()` over-coaching) is **INFERRED** and honestly tagged as such. The fix belongs to a follow-up triage cycle (diagnose-before-edit discipline), not this measurement cycle.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity | 0 | 1 | 2 |

**Total BLOCKING: 0** → cycle MAY close.

## Required actions

None blocking. Carry-forwards (already in the STREAM First move):
1. **P1-PACK-V2-WIDEN** — apply the S2 substitute (`WRONG_DOSAGE`→`MEDICATION_NOT_IN_TRANSCRIPT`) per the measurement-only deferral.
2. **S-P1-21 follow-up** — policy_judge `FABRICATED_CONSENT` narrowing (shape of S-P1-18 NKA propagation); §5.5 needs the C1 N=5 caveat or the post-patch state.
3. **S-P1-13** — paper §5.4 reads the dispersion table directly; investigation post-arXiv.

## Discipline self-check (inline, catch-up)

- [x] Monitor re-verified the dispersion stats against `dispersion.md` + the raw 60-row ndjson (60 rows; 12/12 @ 5/5; content_filter 0/60 by value, not just reported; S2 0/5; C1 BLOCK 5/5 + FABRICATED_CONSENT 4/5; total $3.4002) — not trusted from REPORT prose
- [x] Verified scope via `git show --stat` (lithrim-bench only) and commit ancestry (`merge-base --is-ancestor`)
- [x] Inline-mode caveat: monitor authored the driver (spec-vs-impl independence reduced); the executor was a separate session 2026-05-28 (executor-vs-critique independence preserved); the S-P1-21 INFERRED-cause tag is the executor's own honesty, confirmed here
