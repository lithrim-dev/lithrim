# REPORT: R3(d) pre-check falsifies the consensus-evidence-gate diagnosis

> Pre-check finding for `bench-salvage` phase `COUNCIL-EVIDENCE-GATE`
> (`consensus-evidence-gate`, R3(d)). **The specified fix is wrong for the
> observed defect.** The `MEDICATION_NOT_IN_TRANSCRIPT` false positive on
> `scribe_v1` case 1 is a **findings-first, fully-evidenced, semantically-
> validated** finding — not the legacy `violations_found` span-less bypass the
> spec diagnosed. No aggregation lever can separate it from the true defect.
>
> **Date:** 2026-05-30 · **Verdict:** HALT / BLOCKED-AND-RE-SCOPE · **Cost:** ~$0.10 (3 gpt-4.1 calls, `--limit 1`)
> **Falsifies:** `docs/research/SPEC_consensus_evidence_gate_bypass_2026-05-30.md` §2b + confidence-ledger lines 199–201
> **Diagnose-before-edit:** every causal claim below is tagged CONFIRMED / INFERRED / HYPOTHESIS per `CLAUDE.md`; evidence is verbatim raw judge JSON + `file:line`.

---

## 0. What this pre-check was, and why it ran first

The COUNCIL-EVIDENCE-GATE driver gated its paid 30-case sweep (~$5) behind two
near-zero-cost pre-checks (driver §6, P0 + P1). P0 = a `--limit 1` reproduction
with a temporary, flag-guarded debug log of each judge's **raw** `findings[]` /
`violations_found` / per-finding `evidence_spans`, captured **before** the
`validated_findings` span-gate. It exists because the standard NDJSON projection
**drops `evidence_spans` by schema** (`evidence_spans` appears **0 times** in
every persisted file), so the question "did the v1 judges emit pure-legacy
output or findings-first?" (open seam **S-BS-1**) is physically unanswerable
offline.

The debug instrumentation was fully reverted after capture (no code change ships
from this cycle). The raw evidence it produced is preserved in-repo. **Canonical
(version-controlled) copy:** `docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson`
— because `out/` is gitignored (`.gitignore:4`), this tracked path is the one the
SPEC §2b correction should reference. The `out/` companions
(`out/scribe_v1.local.r3d_precheck_raw.ndjson` raw, `out/scribe_v1.local.r3d_precheck.ndjson`
run row) are durable-on-disk run artifacts per the existing A/B-anchor convention
(the M1 anchors `out/scribe_v1.local{,.guardfix}.ndjson` are gitignored the same way).

---

## 1. The defect under test (unchanged from M1)

`scribe_v1` case 1 (`bench_scribe_v1_inject_condition_1bd0f10dc7b5`) carries one
injected defect — a fabricated diabetes PMH — yet the v1 council emits a second
HIGH flag, `MEDICATION_NOT_IN_TRANSCRIPT`, on `zidovudine 300 MG`, which is
verbatim in the transcript and was never mutated. Verdict (`reject`) is correct;
the flag set is wrong. Reproduced this session: `got=reject exp=reject
flags=[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]` (1/1).

---

## 2. The raw judge evidence (CONFIRMED — verbatim)

From `out/scribe_v1.local.r3d_precheck_raw.ndjson` (P0 capture, deterministic
seed). Each judge's **raw, pre-gate** output:

```
policy_judge    decision=reject
  findings_raw:
    FABRICATED_HISTORY            n_evidence_spans=2
    MEDICATION_NOT_IN_TRANSCRIPT  n_evidence_spans=2
        span 1: "ALLERGIES:\n  NKDA (no known drug allergies)."            ← from ARTIFACT
        span 2: "Dr: …I see you're on zidovudine 300 MG Oral Tablet.
                 Continue at 300 MG daily…"                                 ← from TRANSCRIPT
risk_judge      decision=reject
  findings_raw:
    FABRICATED_HISTORY            n_evidence_spans=2        (no MED at all)
behavior_judge  decision=reject
  findings_raw:
    FABRICATED_HISTORY            n_evidence_spans=2
    MEDICATION_NOT_IN_TRANSCRIPT  n_evidence_spans=2        (same two spans as policy)
```

**The whole story in one line:** the second span the judge cites as *proof that
the medication is not in the transcript* **is the transcript line that contains
the medication.** The judge quotes the zidovudine line verbatim and then labels
it `MEDICATION_NOT_IN_TRANSCRIPT`. This is a reasoning error wearing valid
evidence — not a padding/aggregation artifact.

### 2a. The flag is findings-first, not legacy (CONFIRMED)

All three judges returned a **non-empty `findings[]`** with per-code
`evidence_spans`. In `_apply_consensus` the format selector
(`compliance_council.py:1907`, `if raw_findings and isinstance(raw_findings,
list)`) therefore routes to the **per-finding-evidence branch**; the legacy
branch at `:1962-1971` **never executes** on this case.

### 2b. The persisted `spans=[]` was a projection artifact (CONFIRMED)

The M1 reasoning-capture (`out/scribe_v1.local.guardfix.ndjson`) shows
`findings_rich` with `MEDICATION_NOT_IN_TRANSCRIPT (judges=2)` and **no spans**.
The spec read that as "empty consensus spans ⇒ legacy judge-level-evidence path"
(SPEC §2b, confidence-ledger line 199). **That inference is false.** The spans
exist in the raw judge JSON (§2 above); `findings_rich` simply does not carry an
`evidence_spans` field — it is a lossy summary projection. `evidence_spans`
occurs **0 times** across all persisted NDJSON.

### 2c. The MED spans survive semantic validation (CONFIRMED)

`_validate_evidence_spans` (`compliance_council.py:1699`, `min_overlap=0.80`)
runs before consensus. `MEDICATION_NOT_IN_TRANSCRIPT ∉ OMISSION_TYPE_CODES`
(`:336`, which is `{"MISSING_ALLERGY"}` only), so MED is validated against the
**full corpus** (transcript + artifact). Token-overlap of the captured MED
spans:

```
"ALLERGIES: NKDA…"             full_corpus_overlap = 1.000  → SURVIVES
"Dr: …zidovudine 300 MG…"      full_corpus_overlap = 1.000  → SURVIVES  (also transcript-only = 1.000)
```

So after validation `evidence_judge_count(MED) = 2` and `judge_count(MED) = 2` —
**identical evidence status to the true defect** `FABRICATED_HISTORY`.

---

## 3. D1 determination: SYMMETRIC (CONFIRMED)

The spec left open (HYPOTHESIS, ledger line 201) whether the v1 judges emitted
pure-legacy output. **Settled: they did not.** The defect is findings-first,
fully-evidenced, semantically-validated, and **symmetric** with the true defect
on every signal the aggregation layer can read (presence in `findings[]`,
per-code span count, validation survival, judge count). The only thing that
distinguishes MED from FABRICATED_HISTORY is the **semantic content of the
quoted span** — which no aggregation lever inspects.

---

## 4. All three authorized levers are inert (CONFIRMED)

| Lever (driver-authorized) | Site | Effect on this FP | Why |
|---|---|---|---|
| `evidenced_codes` reconcile | `_normalize_result` :1530 | **No effect** — keeps MED | MED has a validated `findings[]` entry → `MED ∈ evidenced_codes` → filter retains it |
| Legacy-branch evidence gate | `_apply_consensus` :1962-1971 | **No effect** — dead branch | judges emitted findings-first → `:1907` branch runs; legacy `else` never executes |
| Evidence-aware Tier-2 gate | `_apply_consensus` :2170-2190 (proposed extension) | **No effect** — still escalates | `evidence_judge_count(MED) = 2 ≥ 2` and `judge_count = 2` → `tier2_triggered` → BLOCK |

The output-contract edits (`:742/:748-750`, `:1080/:1128`) only affect which
shape judges return; the judges already return the strict findings-first shape,
so the contract change would not alter this case either.

**Conclusion:** R3(d) as specified cannot suppress this FP without also dropping
the true defect (both are symmetric). It is the wrong fix for the observed
defect, confirmed for $0.10 before the $5 sweep.

---

## 5. The OMISSION-code shortcut does NOT work (CONFIRMED — ruled out)

`_validate_evidence_spans` already has an absence-claim lever: for
`OMISSION_TYPE_CODES` (`:336`, `:1773`) it narrows the corpus to **transcript-
only** and strips artifact-self-quotes, downgrading omission findings whose only
evidence is the artifact quoting itself. The obvious cheap patch is "add
`MEDICATION_NOT_IN_TRANSCRIPT` to that set." **It fails here:**

- MED span 1 `"ALLERGIES: NKDA…"` is from the **artifact** → would be stripped (transcript-only overlap = 0.000). ✓ stripped
- MED span 2 `"Dr: …zidovudine 300 MG…"` is from the **transcript** → transcript-only overlap = **1.000** → **survives** any corpus-narrowing gate.

The self-refuting span is itself transcript text, so corpus narrowing cannot
remove it. The only lever that closes this reasons about **span content** ("the
line you cited as proof-of-absence contains the thing") — i.e. a presence-check
/ KB-query tool, not a corpus filter. The omission-code shortcut is ruled out;
close-out should not spend a cycle on it.

---

## 6. D2 (S-BS-2): the v2 over-fire question is NOT answerable offline (CONFIRMED)

Re-inspected the existing 2026-05-28 v2 NDJSON offline (no new calls):

- `out/p1_canonical_n5_pilot.ndjson`: `judge_votes[*].findings` persisted as
  **flat code strings** — 109 records, **0** carrying dict/spans.
- `out/fhir_mini_harness_results.ndjson`: same — 7 records, **0** with spans;
  `semantic_findings` has **no `evidence_spans` field** by schema.

So "span-less in the v2 NDJSON" is **uninformative** — identical projection-
lossiness to scribe (§2b). The v2 over-fire span question **cannot** be settled
offline; it needs the same `R3D_DEBUG_RAW` raw-capture under
`COMPLIANCE_COUNCIL_VERSION=v2` (a P2-COUNCIL paid step). **S-BS-2 stays open.**

What the v2 data *does* show for free (INFERRED): the same FP case under v2
over-fires harder still — the canonical pilot adds `FABRICATED_CONSENT`,
`HALLUCINATED_DETAIL`, `INCOMPLETE_DOCUMENTATION` across runs, and
`Mistral-Large-3` (`policy_judge`) is the consistent over-firer while gpt-4.1
`risk_judge` abstains. That pattern is consistent with a **calibration** class,
not an aggregation class — same direction as the v1 finding.

---

## 7. Re-route: this is a P1 / P1-VEC calibration target

The evidence-gate premise — "true defects come with evidence, false positives
without" — is **violated** for this case: the FP carries valid, validated
evidence. No aggregation gate can separate signal from noise when both sides are
evidenced. The fix lives one layer up, in judge calibration:

> A per-question **presence-check / KB-query tool** that lets a judge verify
> "is `zidovudine` actually in the transcript?" before emitting
> `MEDICATION_NOT_IN_TRANSCRIPT`.

That is exactly the **P1 (SME-Question Ontology) / P1-VEC (local retrieval)**
capability. This FP becomes P1's first concrete SME presence-check question. The
bench worked as designed: it isolated the miss to judge reasoning, not
aggregation, for $0.10.

---

## 8. Confidence ledger

| Claim | Tag | Basis |
|---|---|---|
| MED flag is findings-first, not legacy | CONFIRMED | raw `findings_raw` non-empty for all 3 judges (§2, §2a); `:1907` selector |
| MED carries per-code evidence spans | CONFIRMED | `n_evidence_spans=2` for policy + behavior (§2) |
| MED spans survive semantic validation | CONFIRMED | full-corpus overlap 1.000 both spans; MED ∉ OMISSION_TYPE_CODES (§2c) |
| MED is symmetric with FABRICATED_HISTORY on all aggregation-readable signals | CONFIRMED | identical judge_count / evidence_judge_count / validation survival (§3) |
| Persisted `spans=[]` was a projection artifact | CONFIRMED | raw spans exist; `evidence_spans` 0× in NDJSON (§2b) |
| Spec §2b "legacy span-less bypass" is false for this case | CONFIRMED | §2a + §2b |
| All three authorized levers are inert | CONFIRMED | lever table (§4) |
| OMISSION-code shortcut fails | CONFIRMED | self-refuting span is transcript text, survives corpus narrowing (§5) |
| v2 over-fire span question unanswerable offline | CONFIRMED | v2 NDJSON projection drops spans (§6) |
| v2 FP is a calibration (not aggregation) class | INFERRED | Mistral consistent over-firer, gpt-4.1 abstains, no raw spans checked (§6) |
| A presence-check tool would close the FP | HYPOTHESIS | not built/tested; falsifier = P1-VEC presence-check prototype on this case (§7) |

---

## 9. References

- Spec being falsified: `docs/research/SPEC_consensus_evidence_gate_bypass_2026-05-30.md` (§2b, ledger 199–201)
- Driver: `.devloop/prompts/bench-salvage_phaseCOUNCIL-EVIDENCE-GATE_consensus_evidence_gate_driver.md` (§6 pre-checks)
- Raw evidence (P0), canonical tracked path: `docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson` (mirrored at gitignored `out/scribe_v1.local.r3d_precheck_raw.ndjson`); run row: `out/scribe_v1.local.r3d_precheck.ndjson`
- A/B anchors: `out/scribe_v1.local.ndjson` (M1 baseline), `out/scribe_v1.local.guardfix.ndjson` (reasoning-captured)
- v2 NDJSON (D2): `out/p1_canonical_n5_pilot.ndjson`, `out/fhir_mini_harness_results.ndjson`
- Council code: `compliance_council.py:1907` (selector), `:1962-1971` (legacy branch), `:1530` (reconcile), `:2170-2190` (Tier-2), `:1699` (`_validate_evidence_spans`), `:336` (`OMISSION_TYPE_CODES`)
- Session log: `.devloop/sessions/session-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.json`
