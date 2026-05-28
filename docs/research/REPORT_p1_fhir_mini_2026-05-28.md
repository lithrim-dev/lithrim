# P1-FHIR-CONFORMANCE-MINI report — 2026-05-28

> Cycle: `paper-1-copilot` phase `P1-FHIR-CONFORMANCE-MINI` (derisk for the
> §6.5 paper claim).
> Driver: `.devloop/prompts/paper-1-copilot_phaseP1-FHIR-CONFORMANCE-MINI_one_validator_three_cases_driver.md`
> Verdict (this cycle): **PROCEED-WITH-CAVEATS** (cases + harness shipped,
> friction localized — see §5).
> FULL go/no-go: **NO-GO** until the FHIR-side §6.5 architecture friction is
> addressed (see §5 criteria).

---

## §1 Summary

The MINI cycle did NOT validate the §6.5 paper claim end-to-end on FHIR R4
Patient. The three cases ran cleanly through `lithrim-sdk →
POST /v1/pipeline/evaluate → backend → etlp-mapper /mappings/41/apply →
council-v2` and the harness produced one all-three-pass case (C), one
verdict-pass-but-wrong-attribution case (B), and one false-block on a clean
Patient (A). The structural validator (mapping 41) caught case B's
identifier-strip with two findings (`has_identifier severity=HIGH`,
`identifier_system_required severity=MEDIUM`), but the backend's structural
stage produced `status=WARN` not `BLOCK`, so the worst-of escalation to BLOCK
came from the council pathway — and the council BLOCKed for the wrong reason
on cases A and B (FABRICATED_HISTORY on the artifact's structured fields,
not the strip-identifier defect). The friction is a new seam (S-P1-20) on
the council side plus a generalization of the existing S-P1-15 onto FHIR
artifacts on the structural side. Net: the §6.5 worst-of-composition story
does not replicate on FHIR Patient with the current architecture; FULL
cycle should not proceed until both are resolved or the §6.5 claim is
pivoted to a different artifact shape.

---

## §2 Per-case outcomes

Backend: `http://localhost:8002` · agent_id: `<none>` · validator: etlp-mapper
mapping 41 (`fhir-patient-validator-strict`, profile `us-core-patient`) ·
COMPLIANCE_COUNCIL_VERSION: v2.

| Case | Verdict (expected → actual) | Structural (expected → actual) | Council flags (expected → actual) | Harness verdict | Worst-of correct attribution? |
|---|---|---|---|---|---|
| **A_CLEAN** | approve → **BLOCK** ✗ | PASS → PASS ✓ | [] → `FABRICATED_HISTORY, IMPLICIT_CONFIRMATION_OF_RECORD` ✗ | **FAIL** | No — council false-fires |
| **B_STRUCT_STRIP_IDENTIFIER** | needs_review/reject → BLOCK ✓ | BLOCK → **WARN** ✗ | `STRUCTURAL_MISSING_REQUIRED_FIELD` → `FABRICATED_HISTORY, FABRICATED_CONSENT, HALLUCINATED_DETAIL` ✗ | **FAIL** (flags missed) | No — structural caught defect but didn't drive verdict; council drove verdict for wrong reason |
| **C_SEM_GENDER_MISMATCH** | needs_review/reject → BLOCK ✓ | PASS → PASS ✓ | `VALUE_MISMATCH` → matched via substitute `FABRICATED_HISTORY` ✓ | **PASS** (via Path T substitute) | Partial — verdict right, but council didn't cite VALUE_MISMATCH/NEGATION_REVERSAL; matched only because we permissively substituted FABRICATED_HISTORY |

Three independent gates (per harness `_grade`): VERDICT match 2/3, FLAGS match
2/3, no structural FP 3/3, all-three-pass **1/3**.

Runtime: ~30s per case (council parallel-call). Total ~100s. LLM cost ~$0.10.

---

## §3 Per-stage attribution (with verbatim evidence per CLAUDE.md gate)

### Case A — clean Patient flagged as fabrication (CONFIRMED)

Patient resource (Synthea v4.0.0, seed=1, patient_id
`0149546a-da2d-4a21-7bb8-5f23044b1f92`, Leila Hoeger, female, DOB
1972-04-02) is fully US-Core-compliant: `meta.profile=us-core-patient`, 5
identifiers, name, address, race / ethnicity / birthsex extensions all
present. Mapping 41 returned 8/8 PASS:

```
structural.status: PASS
structural.findings: []
```

Council returned `gate_decision=escalate` and these semantic findings:

```
severity=MEDIUM code=FABRICATED_HISTORY check_name=None detail="FABRICATED_HISTORY (judges=1)"
severity=MEDIUM code=IMPLICIT_CONFIRMATION_OF_RECORD code=... detail="IMPLICIT_CONFIRMATION_OF_RECORD (judges=1)"
```

Per-judge votes:

```
gpt-4.1:        confidence=0.977  n_findings=1
Mistral-Large-3: confidence=0.000  n_findings=0
Llama-4-Maverick: confidence=1.000 n_findings=1
```

**INFERRED diagnosis (no direct judge-prompt inspection in this cycle):**
the transcript verbalizes only name + DOB + gender; the FHIR Patient
artifact carries 7 extensions + 5 identifiers + address + telecom that the
transcript does NOT confirm verbally. The council appears to interpret
structured-field richness in the artifact (which is normal for an EHR
Patient record on registration) as fabrication-by-the-scribe. This is the
canonical real-world case for FHIR Patient — clinician verbally confirms
demographic basics; the EHR captures full demographics + insurance + etc.
The §6.5 worst-of pattern (structural validator + council) does not yet
distinguish "artifact carries extra valid structured detail" from "artifact
carries fabricated detail not in the transcript."

This is **S-P1-20 (new)** — council over-fires fabrication codes on FHIR
Patient cleans whose artifact carries valid structured fields not
verbalized in transcript.

### Case B — structural validator catches the defect; backend status does not BLOCK (CONFIRMED)

Same Patient with `identifier` array stripped. Mapping 41 (validated via
direct `curl /mappings/41/apply` earlier in the session) returns 2/8
fail-status checks: `has_identifier "MISSING required identifier array"` +
`identifier_system_required "Missing identifier[0].system"`.

End-to-end via the SDK:

```
structural.status: WARN
structural.findings (n=2):
  severity=HIGH    check_name=has_identifier             code=None  detail="MISSING required identifier array"
  severity=MEDIUM  check_name=identifier_system_required code=None  detail="Missing identifier[0].system"
```

The structural validator DID fire — both findings carry the original
mapping-41 check_name (`has_identifier`, `identifier_system_required`) and
the severity grading is sensible (HIGH for missing-array, MEDIUM for
missing-component). **But the structural stage's `status` field is `WARN`,
not `BLOCK`,** even though one finding is `severity=HIGH`. This is
S-P1-15 generalized from HL7 ADT^A04 onto FHIR Patient — the etlp-mapper
fail-status → backend structural-status mapping does not escalate to BLOCK
when severity=HIGH.

The Path T sentinel `structural_catch_via=structural_block_with_high_severity`
in our picklist required `status==BLOCK AND any finding ≥ HIGH`. We got
`status==WARN AND any finding ≥ HIGH`, so the sentinel did not fire and the
strict flag `STRUCTURAL_MISSING_REQUIRED_FIELD` was not matched.

Council on case B fired three semantic codes (FABRICATED_HISTORY HIGH,
FABRICATED_CONSENT MEDIUM, HALLUCINATED_DETAIL MEDIUM) — the same
"structured-field-richness" pattern as case A, which drove the worst-of
verdict to BLOCK. The right verdict (BLOCK) came out, but for the wrong
reason from a paper-§6.5-attribution standpoint: the validator's
identifier-strip catch is invisible at the worst-of layer.

`structural_block_with_high` (per harness): **False** (would have been True
if the backend produced `status=BLOCK`).

**Generalization of S-P1-15 from HL7 to FHIR (logged as S-P1-15-fhir-extension):**
the structural validator emits the right findings but the backend's
status-translation layer doesn't see severity=HIGH on FHIR cases either.

### Case C — gender mismatch produces verdict BLOCK; not via the expected code

Patient 1 (Dong Morissette, male, DOB 2002-08-20). Transcript addresses
patient as `Mrs. Morissette ... gender female`. Artifact unchanged:
`gender: male`. Mapping 41 PASS 8/8 (gender field is present; no
value-set check).

```
structural.status: PASS
structural.findings: []
semantic.findings (n=4):
  severity=HIGH    code=FABRICATED_HISTORY                detail="FABRICATED_HISTORY (judges=2)"
  severity=MEDIUM  code=PHI_DISCLOSURE_PRE_VERIFICATION   detail="..."
  severity=MEDIUM  code=IMPLICIT_CONFIRMATION_OF_RECORD   detail="..."
  severity=MEDIUM  code=INCOMPLETE_DOCUMENTATION          detail="..."
```

`actual_codes` does NOT contain VALUE_MISMATCH or NEGATION_REVERSAL — both
of which are the natural codes for a gender-mismatch defect (VALUE_MISMATCH
is owned by behavior_judge per tier1_owners; NEGATION_REVERSAL is
tier3 owned by behavior_judge as a known nearby code per S-P1-14/18
context). The case passes the harness because our Path T picklist
permissively accepts `FABRICATED_HISTORY` as a substitute for
`VALUE_MISMATCH` — but FABRICATED_HISTORY fires on **every** case in this
cohort (A, B, AND C), so the "match" is uninformative as paper-§6.5
attribution evidence.

**HYPOTHESIS** (untested): the council's FABRICATED_HISTORY on case C may
be a coincidental hit driven by the same structured-field-richness pattern
as cases A+B, not by the gender mismatch. A diagnostic disambiguation
would be: re-run case C with the artifact stripped down to gender+name+DOB
only (no extensions, no extra identifiers, no telecom). If FABRICATED_HISTORY
still fires, attribution to gender mismatch is unsupported. If
FABRICATED_HISTORY disappears and VALUE_MISMATCH appears, attribution holds.
Out of scope for MINI; queued for FULL or a focused diagnostic cycle.

---

## §4 Forensic audit of mapping 41 vs US Core 7.0.0 STU7 Patient

Mapping 41 (`fhir-patient-validator-strict`, org `lithrim-dev`,
authored pre-this-session, profile pinned to
`http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient`) — 8
deterministic checks:

| Check | Status on clean Patient | Coverage in US Core 7.0.0 STU7 |
|---|---|---|
| `resource_type` | PASS — `resourceType == "Patient"` | resourceType binding (✓ required) |
| `has_identifier` | PASS — `len(resource.identifier) > 0` | identifier (✓ required cardinality 1..*) |
| `identifier_system_required` | PASS — `resource.identifier.0.system` present | identifier.system slice (✓ partial — US Core has slicing on identifier system per profile) |
| `has_name` | PASS — `len(resource.name) > 0` | name (✓ required cardinality 1..*) |
| `has_family_name` | PASS — `name.0.family` non-null | name.family (✓ required) |
| `has_given_name` | PASS — `len(name.0.given) > 0` | name.given (✓ required cardinality 1..*) |
| `has_gender` | PASS — `gender` present | gender (✓ required, presence-only — US Core also binds to AdministrativeGender valueset, NOT checked here) |
| `has_birth_date` | PASS — `birthDate` present | birthDate (✓ required) |

**Coverage:** 8/8 of the US Core 7.0.0 STU7 required cardinality MUST-haves
at the field-presence level. **Gaps** that mapping 41 does NOT validate
(despite the profile binding declaring them):

1. **us-core-race extension** (`http://hl7.org/fhir/us/core/StructureDefinition/us-core-race`) — US Core 7.0.0 declares cardinality `1..1` MUST-support. Synthea v4.0.0 always emits it (verified). Mapping 41 has no check.
2. **us-core-ethnicity extension** — same. MUST-support, Synthea always emits, mapping 41 doesn't check.
3. **us-core-birthsex extension** — `0..1` MUST-support. Synthea always emits, mapping 41 doesn't check.
4. **gender ValueSet binding** to `AdministrativeGender` `{male, female, other, unknown}` (REQUIRED binding) — mapping 41 only checks presence, not value-set membership. A FHIR Patient with `gender: "purple"` would PASS this validator.
5. **identifier.value** non-null — mapping 41 checks `identifier.0.system` but not `identifier.0.value`. A FHIR Patient with `[{system: "...", value: null}]` would pass `has_identifier` and `identifier_system_required`.
6. **name.use** — US Core marks `MS` (must-support); mapping 41 doesn't check.
7. **telecom** — US Core has slicing on telecom system (phone / email); mapping 41 doesn't check.
8. **communication / address** — US Core declares MS; mapping 41 doesn't check.

**Coverage quantification (paper-bearing):** mapping 41 covers
**8/15** of the US Core 7.0.0 STU7 MUST-support fields at the
presence level, **0/2** value-set bindings, **0/3** US Core
extension cardinalities. This is consistent with a Jute Copilot
output where the generate→test→refine loop validates against the
profile's `cardinality.min > 0` rules but not the cardinality of
profile-declared extensions nor required ValueSet bindings.

**Authoring attribution:** mapping 41 was authored prior to this cycle
(not by this executor); the etlp-mapper has a Jute Copilot mechanism
([etlp-mapper/src/etlp_mapper/copilot/prompt.clj](file:///Users/aregee/Workspace/github.com/etlp-mapper/src/etlp_mapper/copilot/prompt.clj))
that can generate validators from spec text, and there is prior
Copilot art at mapping 2 (`copilot-patient-validator-v1`, tags
`["copilot", "phase1", ...]`). Without direct authoring metadata on
mapping 41 (no commit history on persisted-in-DB mappings; no `created_by`
field captured), the strongest evidence for "Copilot-authored" is the
8-check structural pattern matching the Copilot's typical output shape
(presence-only checks, no value-set bindings) and the `org_id="lithrim-dev"`
authorship marker matching the same `org_id` on every other Copilot-flavored
mapping in the etlp-mapper DB.

**HYPOTHESIS** (not directly verifiable from persisted DB state): mapping
41 was produced by a single Jute Copilot session against US Core Patient
profile spec text, with no manual refinement pass to add extension /
value-set checks afterward. If true, this is paper-bearing for §2
mechanism credibility — the Copilot delivered a credible-looking validator
that covers presence but not value-set or extension structure. The
limitation aligns with the broader §5 thesis: structural validators
(deterministic) cover what they can verify cheaply; LLM council covers
semantic/value-set / extension richness.

---

## §5 P1-FHIR-CONFORMANCE-FULL decision: **NO-GO** (with criteria-grounded justification)

The pre-committed criteria (per plan-review v2):

- **GO if** A7 holds for all 3 cases AND `structural.findings_n ≥ 1` on case B AND case C structural fires PASS while council fires BLOCK with non-empty findings AND worst-of composition produces final BLOCK.
- **NO-GO if** any of:
  - Case B's structural stage returns PASS or null (S-P1-15-shaped failure on FHIR). → **TRIGGERED** (status=WARN, not BLOCK; sentinel didn't fire).
  - Case C's council returns approve. → not triggered (council returned BLOCK).
  - Worst-of composition fails to recover. → not triggered at verdict level (BLOCK fired on B and C).
  - Mapping 41 yaml is structurally incompatible with Synthea's FHIR Patient shape. → not triggered (mapping 41 produced sensible findings on the artifact).

**Trigger 1 alone is sufficient for NO-GO under the pre-committed criteria.**
Additionally, the per-stage attribution analysis in §3 reveals **two
independent friction sources** that the FULL cycle would inherit and amplify:

- **Friction 1 (S-P1-15 generalized to FHIR):** etlp-mapper fail-checks with
  severity=HIGH do not produce `structural.status=BLOCK` on the backend's
  structural stage. The validator does its job; the status-translation
  layer doesn't recognize HIGH-severity findings as BLOCK on FHIR.
- **Friction 2 (S-P1-20, NEW):** council over-fires FABRICATED_HISTORY on
  every FHIR Patient case in this cohort (A clean, B structural-defect, C
  semantic-defect). The signal-to-noise ratio for council attribution on
  FHIR Patient is too low to support a §6.5 paper claim that the council
  catches semantic defects the structural validator misses — the council
  catches semantic AND fabricated-extra-detail AND nothing-at-all-on-clean
  with the same code.

A FULL cycle that adds 4 more validators (Condition, MedicationRequest,
Observation, AllergyIntolerance) and 27 more cases at this attribution
quality would not materially strengthen the §6.5 paper claim — the wins
on those cycles would be subject to the same noise pattern unless one
or both friction sources are fixed.

### Recommended next cycles before P1-FHIR-CONFORMANCE-FULL revisits

1. **P1-FHIR-S-P1-15-EXTENSION** (small, ~half day, on-backend fix). Patch
   the structural-stage status-translation to honor `severity ≥ HIGH` as
   BLOCK on FHIR artifacts. Same fix likely closes both HL7 (original
   S-P1-15) and FHIR (this cycle's extension). Single backend commit;
   regression test on MINI case B should flip its harness verdict to
   all-three-pass.

2. **P1-FHIR-MINI-SEMANTIC-DECOMPOSITION** (small, ~half day, no
   backend changes). Author a SECOND mini-pack of 3 cases on FHIR Patient
   where the artifact is stripped to gender+name+DOB only (no extensions
   / no extra identifiers / no telecom / no address), so the council's
   FABRICATED_HISTORY is no longer the "wash code" on every case. Re-run
   on these stripped artifacts to verify whether council attribution
   becomes specific (case A → 0 findings; case B → still picks up
   structural-strip via different code; case C → cites
   VALUE_MISMATCH/NEGATION_REVERSAL). If yes: §6.5 paper claim is
   architectural-real on FHIR. If no: S-P1-20 is real.

3. **(Conditional on 1 + 2 outcomes)** then re-evaluate P1-FHIR-CONFORMANCE-FULL.

### Cost of NOT proceeding to FULL right now

~$15 (5 validators × N cases × council fee) plus ~6 days of executor time.
The MINI cycle paid ~$0.10 + ~5 hours to derisk that exact spend. **MINI did
its job.**

---

## §6 Open seams

| ID | Title | Severity | Status | Detail |
|---|---|---|---|---|
| **S-P1-20** | **(NEW)** Council over-fires FABRICATED_HISTORY on FHIR Patient cleans whose artifact carries valid structured fields (extensions, multiple identifiers, address) not verbalized in transcript | **medium** | **open** | Demonstrated on MINI case A (clean → BLOCK with FABRICATED_HISTORY+IMPLICIT_CONFIRMATION_OF_RECORD). Same pattern fires on cases B and C, making the council's per-case attribution noisy. Mitigation candidates: (a) prompt-engineer the council to distinguish "structured EHR fields are normal, not verbalized but not fabricated"; (b) restrict the FHIR Patient cases to skinny artifacts during paper §6.5 measurement; (c) decompose the §6.5 claim by artifact type — Patient (high-overhead structured fields) vs Observation (focused single-value) may produce different attribution signals. |
| **S-P1-15** (FHIR extension) | etlp-mapper structural findings with `severity=HIGH` do not produce `status=BLOCK` on the backend's structural stage; the worst-of recovery on FHIR cannot rely on the structural pathway driving BLOCK | medium | open (was open on HL7; now confirmed on FHIR also) | Backend `app/services/artifact_evaluator.py` status-translation layer; specific code path TBD. Reverify path: with patch in place, MINI case B should land all-three-pass (status=BLOCK + structural_block_with_high True + flag matched via sentinel). Closes both HL7 S-P1-15 and the FHIR extension. |
| **S-P1-17** (reconfirmed) | Mistral judge confidence persists as `0.0` instead of `None` on logprob-incapable model | low | open (still cosmetic) | Verified in this cycle: all 3 MINI cases had `Mistral-Large-3 confidence=0.0` in the SDK payload. Same disposition as P1-VALIDATE-12 — cosmetic for paper §5 calibration figure. |
| **Synthea reproducibility (notes)** | Synthea v4.0.0 at same seed is Patient-resource-deterministic but Encounter/Observation/Claim time-component non-deterministic (seconds drift) and downstream-resource-UUID non-deterministic | low | open as design constraint | Documented in `data/synthea_2026-05-28/MANIFEST.txt`. Sufficient for MINI (Patient-only). FULL needs either a Synthea config flag to lock timestamps OR a deterministic-resource-ID layer on top of the bench's loader for Encounter/Observation/etc. cases. |
| **Cohort-vs-CSV-cohort patient-id divergence** | The MINI FHIR cohort at `data/synthea_2026-05-28/` uses a NEW seed (1); the existing CSV cohort at `/Users/aregee/Workspace/github.com/synthea_sample_data_csv_latest/` has unknown original seed. Cross-format provenance join cannot be made across the two cohorts | low | open as design constraint | New cohort is self-consistent (CSV ↔ FHIR same-seed). FULL can choose: (a) build cases on the new cohort exclusively (loses the existing CSV-cohort patient_ids referenced in P1-CANONICAL-PACK eval_case docs); (b) replace the existing CSV cohort with the new one and reconcile P1-CANONICAL-PACK. For MINI we did (a) on FHIR side only, leaving existing CSV cohort untouched. |

---

## §7 What this cycle delivered (deliverables checklist)

- [x] **A1** `lithrim_bench/synthea_fhir_loader.py` + smoke (3 patients loaded; demographics projection works; cohort_sha256 stable across runs).
- [x] **A2** Reproducibility verified at Patient-resource level (SHA256 b00aadfd48e57c9a on both runs); time-component non-determinism documented in MANIFEST.
- [x] **A3'** Mapping 41 catches case-B structural defect (2 findings on `curl /apps/41/apply`: `has_identifier severity=HIGH` + `identifier_system_required severity=MEDIUM`). End-to-end the findings flow through to the SDK; backend translation to `status=BLOCK` does NOT happen (see S-P1-15 FHIR extension).
- [x] **A4'** `fhir_patient` profile already provisioned (`db.artifact_profiles.findOne({artifact_type:"fhir_patient"})` returns mapping 41 profile, version 1, active=true, org="default"). No Mongo writes performed this cycle.
- [x] **A5** Three cases in `out/fhir_patient_mini.jsonl` + `data/picklist_fhir_mini.json` (Path T contract).
- [x] **A6** Harness `scripts/validate_fhir_mini_via_sdk.py` runs end-to-end without unhandled exceptions.
- [x] **A7** Per-case outcomes:
  - Case A: structural PASS ✓ / council BLOCK (FABRICATED_HISTORY) ✗ / worst-of BLOCK / **FAIL** (expected approve).
  - Case B: structural WARN (2 findings, HIGH+MEDIUM) — partial / council BLOCK (FABRICATED_HISTORY+) / worst-of BLOCK / **FAIL** (flags missed; structural didn't drive verdict).
  - Case C: structural PASS ✓ / council BLOCK (matched via FABRICATED_HISTORY substitute for VALUE_MISMATCH) / worst-of BLOCK / **PASS** (verdict correct via permissive substitute).
- [x] **A8** `out/fhir_mini_harness_results.{ndjson,md}` written.
- [x] **A9** This REPORT with §1-§6 + criteria-grounded NO-GO recommendation in §5.
- [x] **A10** (session log + STREAM + state + index updates pending in this cycle's commit sequence — see §6 commit plan in driver).

---

## §8 References

- Driver: `.devloop/prompts/paper-1-copilot_phaseP1-FHIR-CONFORMANCE-MINI_one_validator_three_cases_driver.md`
- Cohort manifest: `data/synthea_2026-05-28/MANIFEST.txt`
- Cases: `out/fhir_patient_mini.jsonl`
- Picklist: `data/picklist_fhir_mini.json`
- Harness: `scripts/validate_fhir_mini_via_sdk.py`
- Harness output (raw): `out/fhir_mini_harness_results.ndjson`
- Harness output (table): `out/fhir_mini_harness_results.md`
- Validator under test: etlp-mapper mapping 41 (`fhir-patient-validator-strict`, `org_id=lithrim-dev`, profile `us-core-patient`)
- Existing Jute Copilot prior art on FHIR Patient: etlp-mapper mappings 2 (`copilot-patient-validator-v1`), 4 (`malaffi-fhir-patient-validator-v1`), 16 (`FHIR Patient Validator`), 23 (`fhir-patient-validator`).
- Linked seams: S-P1-15 (HL7 original; now confirmed on FHIR), S-P1-17 (Mistral confidence), S-P1-20 (NEW — council over-fire on FHIR cleans).
- Paper sections this cycle informs: §6.5 (cross-standard generalization — NO-GO under current architecture, criteria-grounded); §5.5 (paper-bearing limitation — extends the HL7-only residual to a FHIR residual on the structural-status pathway); §2 mechanism (forensic mapping-41-vs-spec analysis quantifies Jute Copilot output coverage 8/15 presence + 0/2 valueset + 0/3 extension cardinality).
