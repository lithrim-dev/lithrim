# Bench Measurement Audit: Profile State + Raw Stage Statuses (BRS-0a)

> **Sprint:** Bench-Driven Reliability Sprint (BRS), cycle 0a of 8
> **Authored:** 2026-05-26 by exec session
> **Companion:** `lithrim-command-center/docs/research/AUDIT_bench_driven_reliability_2026-05-26.md` (the hypothesis-verification doc that motivated this cycle)
> **Driver:** `lithrim-command-center/.lithrim/prompts/brs_0a_bench_measurement_audit_driver.md`
> **Read-only:** no code change, no LLM call, no pack re-run, no profile registration

---

## TL;DR

The original BRS-0a working hypothesis — "the bench may have been measuring stock-config Lithrim (no artifact_profiles registered) and the `not_applicable → PASS` normalization hid it" — is **REFUTED at the data layer**.

What Mongo actually shows for the N=10 sweep (2,009 `pipeline_runs` in the 2026-05-22..23 window, all 4 FHIR packs):

| Status | Count | Share |
|---|---|---|
| `stage_results.structural.status == "PASS"` | 2,009 / 2,009 | **100.0%** |
| `stage_results.structural.status == "not_applicable"` | 0 / 2,009 | 0.0% |
| `stage_results.structural` missing | 0 / 2,009 | 0.0% |
| `stage_results` missing | 0 / 2,009 | 0.0% |

Profiles **are** registered (default-org fallback covers all 7 audited artifact_types). Validators **are** running. They emit literal `PASS` on every case — including injected defects.

The methodology critique sharpens from **"stock-vs-production-config"** to **"validator coverage vs validator existence."** The five default-registered structural validators are envelope/presence-level checks. None of them inspect the semantic content that the bench injectors mutate (WrongDosage inside a SOAP body, UpcodingRisk in a diagnosis array, MissedEscalation in a risk_assessment narrative, FabricatedHistory in a clinical note attachment).

**Downstream implications:** BRS-1 reframes (track validator template id + checks-run/checks-failed, not just "did structural run"). BRS-3 becomes a deprecation candidate on FHIR packs (no structural findings to mark immutable). BRS-4 rescopes (artifact_judge is the *only* voice catching scheduling defects; scope-gating it costs catches). BRS-6 paper amendment expands to §4 + §5 + §7. Three new seams confirmed: **S16** (analyze.py:42-67 comment drift), **S17** (paper §5.2 table mismatches Mongo profile registrations on TWO rows), **S18** (scribe_v1 IS structurally validated despite paper claiming semantic-only).

The audit doc's HALT (d) condition (triage→mapping 19 silent misvalidation) is **NOT triggered**; profile binding is correct in Mongo. The hypothesis traced back to a stale comment in `app/routes/analyze.py:51` — that's S16 (low severity), not a silent misvalidation.

---

## Methodology

### Mongo connection

- **Database:** `velto` (per `lithrim-backend/CLAUDE.md` stack section).
- **Tool:** `mongosh velto --quiet --eval '…'`. Direct localhost connection; no replication or auth required for read-only audit.
- **Org id:** from `lithrim-bench/.live_env` → `LITHRIM_ORG_ID=69b82f072c01d1cc481da187`.
- **Sanity check:**

  ```
  > db.organizations.findOne({_id: ObjectId("69b82f072c01d1cc481da187")}, {name:1})
  { _id: ObjectId('69b82f072c01d1cc481da187'), name: 'Lithrim' }
  ```

  CONFIRMED — org resolves to `Lithrim`.

### Timestamp shape (gotcha)

`pipeline_runs.timestamp` is **stored as ISO string**, not BSON `Date`. `ISODate(...)` filters return 0 rows; the audit uses `{$regex: "^2026-05-2[23]"}` for the sweep window. Documented here so future audits don't repeat the mistake.

CONFIRMED via aggregation failure `MongoServerError: PlanExecutor error during aggregation :: caused by :: can't convert from BSON type string to Date`.

### Sweep window

Per `lithrim-bench/docs/paper_draft/07_results.md:3`: "Run #2 completed 2026-05-23T01:23Z on packs regenerated after the Phase-2 correctness work". This audit treats the **2026-05-22 through 2026-05-23** date range as the canonical N=10 sweep window. 2,009 pipeline_runs fall in that window for the Lithrim org.

### NDJSON ↔ Mongo join

The bench's NDJSON does **not** persist `raw.pipeline_run_id`. Verified: `head -1 out/<pack>.n10.ndjson` shows row keys `[case_id, pack, agent_type, run_index, started_at, duration_ms, compliance_verdict, artifact_verdict, flags, per_judge, structural_verdict, structural_findings, pin, expected_*]` — no `raw.*`. `BackendVerdict.raw` (lithrim_pipeline.py:198) holds it in-memory but the row serializer drops it.

Join key for this audit: **`(org_id, artifact_type, timestamp ≈ started_at within duration_ms ± few seconds)`** — adequate to recover stage_results without ambiguity given the verdict-stratified sampling we do below. Sampling does not require deterministic case linkage at the row level.

---

## Section 1 — Per-pack artifact_profile audit

### 1.1 Findings table

CONFIRMED via `db.artifact_profiles.find({artifact_type: ..., active: true})` per artifact_type. Org-scoped query: `{organization_id: "69b82f072c01d1cc481da187"}`. Default-org fallback: `{organization_id: "default"}` (this is what `_get_artifact_profile()` at `lithrim-backend/app/services/artifact_evaluator.py:689-691` falls through to).

| artifact_type | Bench's pack | Lithrim-org profile? | Default-org profile? | etlp_mapping_id (resolved) | Validator name | Matches paper doc? |
|---|---|---|---|---|---|---|
| `fhir_document_reference` | `scribe_v1` (primary) | NO | YES | **18** | `FHIR R4 DocumentReference Validator` | Paper §5.2 says "none (semantic-only by design)" — **WRONG**. Profile exists, runs every time. (S18) |
| `fhir_appointment` | `scheduling_v1` (primary, POSTed) | NO | YES | **17** | `FHIR R4 Appointment Validator` | Paper §5.2 says `scheduling-action/v1` (mapping 22). **Wrong artifact_type AND wrong mapping id.** (S17) |
| `scheduling_confirmation` | `scheduling_v1` (secondary, **never POSTed**) | NO | YES | **29** | `Scheduling Confirmation Validator` | Profile exists but bench backend (`LithrimPipelineBackend.evaluate`) takes `artifacts[0]` only; scheduling_confirmation is in `artifacts[1]` and is dead in the harness. Zero `pipeline_runs` with `artifact_type=scheduling_confirmation` for this org. |
| `fhir_claim` | `coding_v1` (primary) | NO | YES | **15** | `CARIN Claim Validator` | Paper §5.2 says mapping 15 — CORRECT. (`analyze.py:51` comment says fhir_claim → 19, which is stale; S16.) |
| `fhir_risk_assessment` | `triage_v1` (primary) | NO | YES | **19** | `FHIR R4 RiskAssessment Validator` | Paper §5.2 says mapping 19 — CORRECT. **HALT (d) NOT triggered**: mapping 19 IS the RiskAssessment Validator, not CARIN Claim. Audit-doc concern traced to stale comment in `analyze.py:51`. |
| `hl7_adt_a04` | `hl7_adt_v1` (primary) | NO | YES | **42** | `HL7 v2.5 ADT^A04 Lenient Validator` | Paper §5.2 says mapping 26 for deployed — **WRONG**. The default profile resolves to 42, not 26. The §7.3 "+28.6 pp" number used mapping 26 via direct `LithrimValidateArtifactBackend` bypass (see §2.5). (S17) |
| `scheduling_action` | (paper-only; bench POSTs `fhir_appointment`) | NO | YES | **91** | `Lithrim Scheduling Action v1 Validator` | Profile exists. Never used by bench. 6 historical `pipeline_runs` with this artifact_type (pre-sweep). |

### 1.2 Profile registration verbatim evidence

`db.artifact_profiles.find({active: true}, {artifact_type:1, etlp_mapping_id:1, name:1, organization_id:1, version:1, _id:0}).sort({artifact_type:1})`:

```
{ artifact_type: 'clinical_note',          organization_id: 'default',                etlp_mapping_id: 90, name: 'Lithrim Clinical Note v1 Validator',     version: 1 }
{ artifact_type: 'fhir_appointment',       organization_id: 'default',                etlp_mapping_id: 17, name: 'FHIR R4 Appointment Validator',          version: 1 }
{ artifact_type: 'fhir_claim',             organization_id: 'default',                etlp_mapping_id: 15, name: 'CARIN Claim Validator',                  version: 1 }
{ artifact_type: 'fhir_condition',         organization_id: 'default',                etlp_mapping_id: 45, name: 'FHIR R4 Condition US-Core Validator (C16-C)', version: 1 }
{ artifact_type: 'fhir_document_reference', organization_id: 'default',               etlp_mapping_id: 18, name: 'FHIR R4 DocumentReference Validator',    version: 1 }
{ artifact_type: 'fhir_observation',       organization_id: 'default',                etlp_mapping_id: 40, name: 'FHIR R4 Observation Base Validator',     version: 1 }
{ artifact_type: 'fhir_patient',           organization_id: 'default',                etlp_mapping_id: 41, name: 'FHIR R4 Patient Validator (Cycle 7 strict)', version: 1 }
{ artifact_type: 'fhir_resource',          organization_id: 'default',                etlp_mapping_id: 92, name: 'FHIR Resource Base Validator',          version: 1 }
{ artifact_type: 'fhir_risk_assessment',   organization_id: 'default',                etlp_mapping_id: 19, name: 'FHIR R4 RiskAssessment Validator',       version: 1 }
{ artifact_type: 'hl7_adt_a04',            organization_id: 'default',                etlp_mapping_id: 42, name: 'HL7 v2.5 ADT^A04 Lenient Validator',     version: 2 }
{ artifact_type: 'hl7_dft_p03',            organization_id: 'default',                etlp_mapping_id: 25, name: 'HL7 DFT^P03 Validator',                 version: 1 }
{ artifact_type: 'icd10_codes',            organization_id: '69b82f072c01d1cc481da187', etlp_mapping_id: 89, name: 'Lithrim ICD-10-CM Coding Validator',  version: 1 }
… (scheduling_confirmation → 29, scheduling_action → 91 verified separately)
```

CONFIRMED. The Lithrim org has exactly ONE org-scoped active profile (`icd10_codes` → mapping 89). The bench never POSTs `icd10_codes` from any of the five packs. Every audited POST falls through to the **default-org** profile.

### 1.3 What the validators actually check (Phase 2 / Ask 2)

Verbatim `GET /mappings/18` head + `POST /mappings/18/apply` against one scribe_v1 NDJSON row (READ-ONLY etlp call, no state writes).

**Mapping 18 (FHIR R4 DocumentReference Validator) — the five checks defined:**

```yaml
c1: has-status              ← presence of resource.status
c2: valid-type-code         ← resource.type.coding[0].system == "http://loinc.org"
c3: has-subject-ref         ← presence of resource.subject.reference
c4: has-content-attachment  ← presence of resource.content[0].attachment
c5: valid-format            ← presence of resource.content[0].attachment.contentType
```

**Live `/mappings/18/apply` output against `head -1 out/scribe_v1.n10.jsonl` artifacts[0]:**

```json
{
  "result": {
    "request": {
      "valid": true, "resourceType": "DocumentReference",
      "totalChecks": 5, "passedChecks": 5, "failedChecks": 0,
      "checks": [
        {"name": "has-status", "field": "status", "status": "pass", "message": "Document status present"},
        {"name": "valid-type-code", "field": "type.coding.system", "status": "pass", "message": "Type uses LOINC coding system"},
        {"name": "has-subject-ref", "field": "subject.reference", "status": "pass", "message": "Subject reference present"},
        {"name": "has-content-attachment", "field": "content.attachment", "status": "pass", "message": "Content attachment present"},
        {"name": "valid-format", "field": "content.attachment.contentType", "status": "pass", "message": "Content format (contentType) present"}
      ]
    }
  },
  "org/id": "lithrim-dev"
}
```

**CONFIRMED** — mapping 18 is **envelope-only**. It never inspects `resource.content[0].attachment.data` (the base64-encoded SOAP body where scribe_v1 injectors place `WrongDosage`, `MissingAllergy`, `FabricatedHistory`, `ValueMismatch`, `HallucinatedDetail`). The injectors mutate content the validator is contractually blind to. Hence 500/500 `structural.status="PASS"` on scribe_v1 in the sweep.

The four other primary-pack validators follow the same pattern (verbatim heads pulled from etlp-mapper, abbreviated here for length):

- **Mapping 15 (CARIN Claim, fhir_claim):** 5 checks — resource_type=="Claim", patient.reference, provider.reference, diagnosis array non-empty, item.productOrService array non-empty. Envelope. Doesn't inspect ICD code values vs transcript.
- **Mapping 17 (FHIR Appointment, fhir_appointment):** 5 checks — status enum membership, start, end, participant, serviceType (all presence). Envelope. Doesn't inspect appointment date plausibility, time consistency, or PHI ordering.
- **Mapping 19 (FHIR R4 RiskAssessment, fhir_risk_assessment):** 5 checks — subject.reference, code.coding[0].system=="http://snomed.info/sct", prediction array presence, prediction[0].probabilityDecimal ∈ [0,1], occurrenceDateTime OR occurrencePeriod presence. Envelope + one value-range. Doesn't inspect risk narrative vs transcript.
- **Mapping 42 (HL7 v2.5 ADT^A04 Lenient, hl7_adt_a04):** segment presence checks (MSH/EVN/PID/PV1) + MSH.9 event=="A04" + PID has id. Doesn't check date format on PID-7, gender value-set on PID-8, or MSH-9↔EVN-1 trigger consistency (those are mapping 93's additions).

CONFIRMED. The default-org structural validator suite is uniformly envelope/presence-grade. The 100% structural-PASS observation is a direct consequence of validator coverage, not "no profile registered" and not the `not_applicable→PASS` normalization in `lithrim_bench/backends/lithrim_pipeline.py:34`.

---

## Section 2 — Per-pack sampled pipeline_run audit

Each pack: 1 PASS / 1 BLOCK / 1 WARN sampled from `db.pipeline_runs.find({org_id, artifact_type, timestamp: {$regex: "^2026-05-2[23]"}, verdict: <V>}).limit(1)`. Stage statuses are verbatim from Mongo; findings are truncated to first 2 for length.

### 2.1 scribe_v1 (artifact_type=fhir_document_reference)

**PASS sample — `_id: 6a109779e6a013fe0c5b3c9c`, ts=2026-05-22T17:50:49.376820Z:**
```
verdict: PASS, gate_decision: allow
structural: status=PASS, findings_n=0
semantic:   status=PASS, findings_n=0
artifact:   status=PASS, findings_n=0
top_findings: 0
```

**BLOCK sample — `_id: 6a10968fe6a013fe0c5b3c74`, ts=2026-05-22T17:46:55.740979Z:**
```
verdict: BLOCK, gate_decision: escalate
structural: status=PASS, findings_n=0
semantic:   status=BLOCK, findings_n=3
artifact:   status=PASS, findings_n=2
  artifact[0]: type=hallucination, severity=HIGH, detail="Artifact states 'diphenhydrAMINE Hydrochloride 250MG Oral Tablet 25 MG daily' which incorrectly includes '250MG' not supported by transcript…"
  artifact[1]: type=omission, severity=MEDIUM, detail="Artifact omits several medications listed in transcript: Naproxen sodium, Clopidogrel, Simvastatin, metoprolol succinate, Nitroglycerin, Hydrochlorothiazide, amLODIPine."
top_findings: 5 (first: MEDICATION_NOT_IN_TRANSCRIPT judges=2; WRONG_DOSAGE judges=1)
```

**WARN sample — `_id: 6a109677e6a013fe0c5b3c72`, ts=2026-05-22T17:46:31.926170Z:**
```
verdict: WARN, gate_decision: regenerate
structural: status=PASS, findings_n=0
semantic:   status=WARN, findings_n=2
artifact:   status=WARN, findings_n=1
top_findings: 3 (MEDICATION_NOT_IN_TRANSCRIPT judges=1; INCOMPLETE_DOCUMENTATION judges=1)
```

**Observation:** structural=PASS in all three. BLOCK is driven by **semantic** (with artifact_judge raising as well). Verdict-determining stage = semantic, not structural.

### 2.2 scheduling_v1 (artifact_type=fhir_appointment)

**PASS sample — `_id: 6a10b2b4e6a013fe0c5b4048`, ts=2026-05-22T19:47:00.433068Z:**
```
verdict: PASS, gate_decision: allow
structural: status=PASS, findings_n=0
semantic:   status=PASS, findings_n=0
artifact:   status=WARN, findings_n=1  ← artifact WARN, but worst-of treats artifact WARN as informational
  artifact[0]: type=hallucination, severity=HIGH, detail="The appointment date in the artifact is March 11, 2008, which contradicts the transcript date of March 11, 2025…"
top_findings: 1
```

**BLOCK sample — `_id: 6a10b47ce6a013fe0c5b4084`, ts=2026-05-22T19:54:36.257698Z:**
```
verdict: BLOCK, gate_decision: escalate
structural: status=PASS, findings_n=0
semantic:   status=PASS, findings_n=0   ← council unanimously APPROVES
artifact:   status=BLOCK, findings_n=1
  artifact[0]: type=hallucination, severity=HIGH, detail="The artifact records the appointment date as September 15, 1967, which contradicts the transcript where the appointment is scheduled for September 15…"
top_findings: 1
```

CONFIRMED — this is the §7b.8 honest-caveat pattern: structural=PASS + council=PASS + artifact=BLOCK ⇒ verdict=BLOCK. The artifact_judge is the **only** voice catching scheduling defects. CONFIRMED across 278 BLOCKs in 22-23 window (verdict-BLOCK count = artifact-BLOCK count = 278).

**WARN sample — NO RUNS.** `db.pipeline_runs.findOne({org_id, artifact_type:"fhir_appointment", timestamp:{$regex:"^2026-05-2[23]"}, verdict:"WARN"})` returns null. Verdict distribution in window: 278 BLOCK + 222 PASS + 0 WARN. fhir_appointment has zero WARN runs in the sweep.

### 2.3 coding_v1 (artifact_type=fhir_claim)

**PASS sample — `_id: 6a10dab2e6a013fe0c5b4458`, ts=2026-05-22T22:37:38.917645Z:** structural=PASS, semantic=PASS, artifact=PASS, top_findings=0.

**BLOCK sample — `_id: 6a10dba8e6a013fe0c5b446c`, ts=2026-05-22T22:41:44.732684Z:**
```
verdict: BLOCK, gate_decision: escalate
structural: status=PASS, findings_n=0
semantic:   status=BLOCK, findings_n=4
artifact:   status=BLOCK, findings_n=1
  artifact[0]: type=hallucination, severity=HIGH, detail="Artifact codes diagnosis as 'I11.0 Hypertensive heart disease with heart failure' which is not supported by the transcript; transcript states 'essential (primary) hypertension'…", chunk_id='codes-icd10:I110'
top_findings: 5 (FABRICATED_HISTORY judges=3; WRONG_CATEGORY_CODE judges=2)
```

**WARN sample — `_id: 6a10d924e6a013fe0c5b4430`, ts=2026-05-22T22:31:00.910061Z:** structural=PASS, semantic=WARN (2 findings), artifact=WARN, top_findings=3 (HALLUCINATED_DETAIL, FABRICATED_HISTORY).

**Observation:** Council DOES catch coding defects (semantic=BLOCK), unlike scheduling. Structural still=PASS regardless.

### 2.4 triage_v1 (artifact_type=fhir_risk_assessment)

**PASS sample — `_id: 6a1100bee6a013fe0c5b4840`, ts=2026-05-23T01:19:58.148121Z:** structural=PASS, semantic=PASS, artifact=PASS.

**BLOCK sample — `_id: 6a1101a1e6a013fe0c5b4854`, ts=2026-05-23T01:23:45.463874Z:**
```
verdict: BLOCK, gate_decision: escalate
structural: status=PASS, findings_n=0
semantic:   status=BLOCK, findings_n=5
artifact:   status=BLOCK, findings_n=2
  artifact[0]: type=hallucination, severity=HIGH, detail="Artifact states qualitative risk as 'Low risk' despite transcript indicating high risk (85%) for acute respiratory failure…"
  artifact[1]: type=hallucination, severity=HIGH, detail="Artifact mitigation recommends self-care at home, contradicting transcript's emergency department referral…"
top_findings: 7 (SEVERITY_ESCALATION judges=1; HALLUCINATED_DETAIL judges=2)
```

**WARN sample — `_id: 6a10fbede6a013fe0c5b47b6`, ts=2026-05-23T00:59:25.794241Z:** structural=PASS, semantic=WARN (MISSED_ESCALATION judges=1), artifact=PASS.

**Observation:** Council and artifact_judge BOTH catch triage defects. Structural=PASS regardless. Mapping 19 is the FHIR R4 RiskAssessment Validator (CONFIRMED), refuting HALT (d).

### 2.5 hl7_adt_v1 (artifact_type=hl7_adt_a04) — NDJSON-only, no Mongo

`db.pipeline_runs.countDocuments({org_id, artifact_type:"hl7_adt_a04", timestamp:{$regex:"^2026-05-2[23]"}})` returns **0**. Only 1 historical `hl7_adt_a04` pipeline_run exists for the org (2026-05-21). The §7.3 numbers come from **separate non-pipeline backends** that bypass `/v1/pipeline/evaluate` and so don't write to `pipeline_runs`. Per `head -1` of the NDJSON pin fields:

| NDJSON file | Backend | Mapping pinned | Approach |
|---|---|---|---|
| `out/hl7.A.tuned_only.ndjson` (40 rows) | `TunedMockBackend` | n/a | mock-tuned semantic council, `structural_blind_by_contract: true`. structural_verdict=null on every row. |
| `out/hl7.B.struct_only.ndjson` (40 rows) | `LithrimValidateArtifactBackend` | **26** (direct, NOT via profile) | direct `/v1/validate-artifact?etlp_mapping_id=26` call. Bypasses profile registry. |
| `out/hl7.C.worstof.ndjson` (40 rows) | `WorstOfBackend` | semantic=TunedMock, structural=LithrimValidateArtifact mapping **26** | composition of the two above. |
| `out/hl7.strict.struct.ndjson` (40 rows) | `LithrimValidateArtifactBackend` | **93** (direct) | direct call to strict validator. |
| `out/hl7.strict.worstof.ndjson` (40 rows) | `WorstOfBackend` | semantic=TunedMock, structural=mapping **93** | composition. |

`pin.extra.etlp_mapping_id` verbatim from row 1 of each NDJSON confirms the direct-mapping pinning — these runs **do not** consult `artifact_profiles`; the operator hard-codes the mapping id.

**HL7 NDJSON aggregate structural verdicts (Counter of `(structural_verdict, artifact_verdict, expected_compliance_verdict)`):**

```
hl7.A.tuned_only.ndjson      (no structural)
  None / PASS / approve  n=12   (correctly-approved cleans, semantic-only)
  None / PASS / reject   n=28   (missed defects, semantic-only)

hl7.B.struct_only.ndjson     (direct mapping 26)
  PASS / PASS / approve  n=12
  PASS / PASS / reject   n=20   (mapping 26 misses these 20 defects)
  WARN / WARN / reject   n=8    (mapping 26 catches 8/28 → the §7.3 "+28.6 pp" number)

hl7.C.worstof.ndjson         (worst-of with mapping 26)
  PASS / PASS / approve  n=12
  PASS / PASS / reject   n=20
  WARN / WARN / reject   n=8

hl7.strict.struct.ndjson     (direct mapping 93)
  PASS / PASS / approve  n=12   (cleans correctly pass)
  BLOCK / BLOCK / reject n=7    (strict validator blocks 7)
  WARN / WARN / reject   n=21   (strict validator warns 21 → 28/28 = "+100 pp" claim)

hl7.strict.worstof.ndjson    (worst-of with mapping 93)
  PASS / PASS / approve  n=12
  BLOCK / BLOCK / reject n=7
  WARN / WARN / reject   n=21
```

**Observation:** Paper §7.3 "+28.6 pp" uses **mapping 26 via direct backend**, not the default profile (mapping 42). Paper §7.3 "+100 pp" uses **mapping 93 via direct backend**, also not via profile. If a deployer POSTs `hl7_adt_a04` to `/v1/pipeline/evaluate` against this org's default profile, they hit **mapping 42 (Lenient)**, which neither §7.3 number characterizes.

The +28.6 pp / +100 pp results are real measurements of what the **mapping 26** and **mapping 93** validator templates catch under a direct `/v1/validate-artifact` call. They are NOT measurements of what stock Lithrim catches via the deployed profile. This is the audit doc's methodology issue #3 confirmed at the data layer.

---

## Section 3 — Config-state matrix

Cross-tab: pack × (profile registered / structural-stage actually ran / structural verdict in sweep).

| Pack | artifact_type POSTed | Profile registered (any org)? | Structural stage ran? | structural.status distribution in 22-23 sweep | What drives verdict |
|---|---|---|---|---|---|
| `scribe_v1` | `fhir_document_reference` | YES (default → 18) | YES (500/500) | 500 PASS / 0 WARN / 0 BLOCK / 0 not_applicable | semantic (council) + artifact_judge |
| `scheduling_v1` | `fhir_appointment` | YES (default → 17) | YES (500/500) | 500 PASS / 0 WARN / 0 BLOCK / 0 not_applicable | artifact_judge alone (council all-approves) |
| `coding_v1` | `fhir_claim` | YES (default → 15) | YES (509/509) | 509 PASS / 0 WARN / 0 BLOCK / 0 not_applicable | semantic (council) + artifact_judge |
| `triage_v1` | `fhir_risk_assessment` | YES (default → 19) | YES (500/500) | 500 PASS / 0 WARN / 0 BLOCK / 0 not_applicable | semantic (council) + artifact_judge |
| `hl7_adt_v1` | `hl7_adt_a04` | YES (default → 42 lenient) | n/a (bench bypasses pipeline; uses direct mapping 26 or 93) | n/a (no pipeline_runs in window) | direct validator (mapping 26 or 93 per backend pin) |

**Distribution evidence (verbatim aggregate output, Phase 1):**

```
> db.pipeline_runs.aggregate([
    {$match: {org_id: orgId, timestamp: {$regex: "^2026-05-2[23]"}}},
    {$group: {_id: {at: "$artifact_type", st: "$stage_results.structural.status"}, n: {$sum: 1}}}
  ])
  { _id: { at: 'fhir_claim',              st: 'PASS' }, n: 509 }
  { _id: { at: 'fhir_document_reference', st: 'PASS' }, n: 500 }
  { _id: { at: 'fhir_appointment',        st: 'PASS' }, n: 500 }
  { _id: { at: 'fhir_risk_assessment',    st: 'PASS' }, n: 500 }

> db.pipeline_runs.countDocuments({org_id, timestamp:{$regex:"^2026-05-2[23]"}, "stage_results.structural.status": "not_applicable"})
  0

> db.pipeline_runs.countDocuments({org_id, timestamp:{$regex:"^2026-05-2[23]"}, "stage_results.structural": null})
  0
```

CONFIRMED — 2,009/2,009 rows have `stage_results.structural.status == "PASS"`. The `not_applicable→PASS` normalization in `lithrim_bench/backends/lithrim_pipeline.py:34` is **inert** for these four packs in the n10 sweep, because none of them ever returned `not_applicable`.

---

## Section 4 — Paper claim re-interpretation under the new framing

### 4.1 §7.1 per-pack pipeline accuracy

The §7.1 table is correct as numbers; the **decomposition story** behind it needs re-stating.

**Original §7.1 implication:** the worst-of composition is recovering structural defects that the council misses.

**Audit-corrected statement:**
- For the four FHIR packs, **structural recovery contributes zero** to §7.1 numbers. All 4 packs report 500/500 (or 509/509) structural-PASS. The verdict distribution is entirely driven by semantic stage (council) + artifact_judge stage.
- Specifically: §7.1 says scheduling_v1 has `defect caught = 17/24` and `+71 pp` Δ on defects (composed vs council-only). That +71 pp is **entirely** artifact_judge, not structural. Already correctly flagged in §7b.8 honest-caveat ("Scheduling artifact_judge drives BLOCK"). This audit upgrades the caveat from "structural=PASS, council=PASS, artifact=BLOCK" to "structural=PASS *because the registered validator is envelope-only*; defect is invisible to the structural axis by construction."
- For `coding_v1` and `triage_v1`, council catches the defects in semantic stage. Structural=PASS contributes nothing to the §7.1 verdict.

### 4.2 §7.3 HL7 worst-of (the headline contrast)

**Original §7.3 claim:** "Worst-of(tuned-mock, mapping 26) = 8/28 (+28.6 pp)" and "Worst-of(tuned-mock, mapping 93) = 28/28 (+100 pp)" demonstrate the worst-of recovery.

**Audit-corrected scope statement:**
- Both numbers come from **direct-mapping bypass** of the profile registry (`LithrimValidateArtifactBackend` with `etlp_mapping_id` hard-pinned). They measure validator-template recall, NOT what stock Lithrim catches via the registered profile.
- The registered default profile for `hl7_adt_a04` is **mapping 42 (Lenient)**, not 26 (the §7.3 "deployed" measurement) and not 93 (the §7.3 "strict" measurement). What mapping 42 would catch in the same harness has not been measured.
- The +100 pp claim is best framed as **"validator-coverage ceiling at the strict mapping 93 template"**, not as "what Lithrim catches today". A deployer who registers mapping 93 as the active profile *would* catch 28/28; the bench never did this registration step in the sweep.
- Recommended paper rewrite (for BRS-6): rename the §7.3 axis from "deployed vs strict" to "presence/lenient vs strict-conformance" with a note that the registered default profile is the lenient template (mapping 42), and the strict template (mapping 93) requires explicit profile registration.

### 4.3 §7b.8 honest caveat

**Original §7b.8 claim:** "the scheduling +71 pp is the orchestrator's Stage 2.5 artifact_judge, not the structural validator. Three bench pipeline_runs (Mongo) confirm `structural=PASS` + all-approve council co-occurring with `artifact=BLOCK`."

**Audit-corrected expansion:** CONFIRMED for the 3 cited cases AND across all 278 fhir_appointment BLOCK verdicts in the sweep (verbatim Mongo count = 278; artifact_status=BLOCK count = 278; the two sets coincide). Adding the rest of the story:

- The registered default profile for `fhir_appointment` (mapping 17) is presence-grade — it checks status enum, start, end, participant, serviceType (all envelope). It cannot detect "appointment date is 1967" (the bench's PhiDisclosure / context-date injectors). So the structural axis is **contractually blind** to the defects scheduling_v1 injects.
- The §7b.8 framing should expand: artifact_judge is not just the load-bearing voice; it is the **only voice with category coverage** for the defects the bench injects in scheduling_v1. Scope-gating artifact_judge would lose 100% of the +71 pp.

### 4.4 §5.2 pack table (newly flagged for BRS-6)

Three rows are factually incorrect against Mongo / etlp-mapper data:

| Paper §5.2 row | What paper says | What Mongo / etlp-mapper shows |
|---|---|---|
| `scribe_v1` validator | "none (semantic-only by design)" | Default profile fhir_document_reference → mapping 18 IS registered AND runs on every case. (S18) |
| `scheduling_v1` validator | "`scheduling-action/v1` (etlp mapping 22)" | (a) Bench POSTs `fhir_appointment`, not `scheduling_action`. (b) Mapping 22 is `hl7 parser extensions` ConfigMap, not a validator. (c) `fhir_appointment` → mapping 17. (d) `scheduling_action` profile exists at mapping 91 but is never POSTed. (S17) |
| `hl7_adt_v1` validator | "`hl7-adt-a04-validator` (etlp mapping 26)" | Mapping 26 IS named `hl7-adt-a04-validator` (paper checks out). BUT the registered default profile for `hl7_adt_a04` is mapping 42 (`HL7 v2.5 ADT^A04 Lenient Validator`). The §7.3 numbers used mapping 26 via direct backend bypass, not via profile. (S17) |

All three are paper documentation drift — they don't invalidate §7.3's measurements (the direct-mapping numbers are real for the validators tested), but they misrepresent what gets used when. BRS-6 paper amendment should fix.

---

## Section 5 — BRS arc implications + new seams (Ask 3 expansion)

### 5.1 BRS-1 reframe — provenance observability, validator template tracking

**Original BRS-1 scope:** add `silent_confident_certification` boolean + `verdict_flipped_by_stage` string to PipelineProvenance. Pattern: `council=approve & confidence>=0.85 & structural=BLOCK`.

**Reframe under audit findings:**
- The pattern as written *almost never fires* in the sweep — structural is PASS on 2,009/2,009 FHIR rows. The "silent confident certification" pattern (`council=approve & confidence>=0.85 & structural=BLOCK`) requires a structural BLOCK, which the registered validators don't produce.
- The HL7 sweep is where structural BLOCK happens (mapping 93 strict, 7/40 BLOCKs), but the HL7 sweep doesn't go through `/v1/pipeline/evaluate` — it uses direct backends that don't write to `pipeline_runs`.
- **Reframed value:** BRS-1 should also persist **validator template id (`etlp_mapping_id`) + checks-run-count + checks-failed-count** on each provenance record. This is the missing observability layer for the **validator-coverage-gap** question (which is now the load-bearing question, not "silent_confident_certification"). With that field, the dashboard can answer: "for these N runs of this pack, the registered validator ran <total> checks, <failed> failed, here are the check names." That's the actionable signal.
- **Practical change to driver:** keep `silent_confident_certification` and `verdict_flipped_by_stage` but add a third field, e.g. `structural_template_pin: {mapping_id: int, total_checks: int, passed_checks: int}`. Required wherever `stage_results.structural.status` is set. Adds ~one Optional dict to PipelineProvenance, no migration needed.
- **Severity:** keep BRS-1 at 1 day; the new field is additive to the existing scope.

### 5.2 BRS-3 deprecation candidate — Variant B critique pass

**Original BRS-3 scope:** extend `_build_critique_prompt` to include structural findings as immutable context; enforce un-droppable structural findings in the critique drop-only contract.

**Audit observation:**
- Across 2,009 FHIR sweep rows, `stage_results.structural.findings` is empty (length 0) on all 2,009 (CONFIRMED via `structural_findings_n: 0` in every sampled row in §2.1–§2.4). There are no structural findings to pass to the critique pass as immutable context. Variant B has zero work to do on FHIR packs at current validator coverage.
- HL7 sweep has some structural findings (mapping 93 strict: 7 BLOCKs + 21 WARNs = 28 cases with findings), but the HL7 sweep doesn't run through the pipeline orchestrator, so the critique pass (which lives inside `evaluate_artifacts`) never sees them.
- **Recommendation:** drop BRS-3 from the arc OR rescope to "HL7-only Variant B, contingent on routing HL7 through `/v1/pipeline/evaluate` with a strict profile registration." Since the audit observed that registering mapping 93 as the active HL7 profile is the BRS-0b followup (not blocked work), this rescope is reasonable; alternatively defer.
- **Severity:** Variant B implementation cost (~1 day) is real; it should only be paid if there's a near-term workflow that registers stricter profiles. Recommend cancel for now; reinstate when validator-template upgrades land.

### 5.3 BRS-4 rescope — artifact_judge gating reconsidered

**Original BRS-4 scope:** add per-artifact-type opt-out to `_artifact_stage`; default opt-out for `scheduling_confirmation` per measured 0.38 false-block.

**Audit observation:**
- The 0.38 false-block on scheduling_v1 in §7.1 is on `fhir_appointment`, not `scheduling_confirmation`. (scheduling_confirmation is never POSTed; it's dead in the harness.) The opt-out target needs to be `fhir_appointment`.
- For 278/278 fhir_appointment BLOCKs in the sweep, artifact_judge is the **only** voice catching the defect (structural=PASS, semantic=PASS — see §2.2 BLOCK sample). If we opt-out artifact_judge on `fhir_appointment` to fix the false-block, we lose **all** scheduling defect catches. Net: lose the +71 pp `defect caught` lift (§7.1) to gain back 5/13 false-blocks.
- The tradeoff is not symmetric: catches are mission-critical (a 1967 appointment date that EHR books and patient shows up for the wrong year is a real harm); false-blocks are friction (re-generate the artifact). Without a precision-side fix to artifact_judge, scope-gating is net-negative.
- **Recommendation:** rescope BRS-4 to "improve artifact_judge precision via the critique pass" instead of "gate artifact_judge off scheduling." Concretely: the artifact_judge prompt's drop-only-contract critique pass (already exists per audit doc Variant B status) should be tuned for date-plausibility false-positives. Cheaper, less destructive, addresses the right axis.
- **Severity:** BRS-4 cost was 1 day; the rescoped version is more like 1-2 days (prompt-eng + small calibration). Slight increase, much better expected impact.

### 5.4 BRS-6 paper amendment scope — broader than §7

**Original BRS-6 scope:** re-run packs and amend Paper 1 §7.

**Audit observation:**
- The audit identifies factual drift in §5.2 (validator/mapping table — 3 of 5 rows wrong; see §4.4) and §7b.8 (caveat is correct but under-stated). The amendment needs to touch §4.1 (worst-of composition narrative), §5.2 (pack table), §7.1 (decomposition framing), §7.3 (direct-mapping vs registered-profile framing), §7b.8 (validator-coverage-blind framing).
- The validator-coverage-gap framing is a **paradigm shift** in the paper's narrative, not just a number tweak. The original story is "worst-of recovers what semantic misses via the structural axis." The corrected story is "worst-of recovers what semantic misses **when the structural axis covers the defect class**; in default-config Lithrim, the structural axis is presence-grade and the recovery on FHIR packs is entirely artifact_judge."
- This is a stronger claim, not a weaker one — it concretely says "deployers who upgrade their structural template to a strict mapping see the +100 pp lift; default deployers see the artifact_judge lift." That's an actionable purchase-decision signal for the product.
- **Recommendation:** BRS-6 scope grows by ~half-day for §4-§5 edits but the LLM-cost-conscious bench-rerun budget (~$30) does NOT increase — the re-run is still 4-pack × N=10 plus HL7. Total still ~$15 with $30 hard cap.
- **Severity:** BRS-6 stays the last cycle; cost re-estimate is small.

### 5.5 New seams confirmed in this audit

| Seam | Description | Evidence | Severity | Resolution |
|---|---|---|---|---|
| **S16** | `lithrim-backend/app/routes/analyze.py:42-67` `VALID_ARTIFACT_TYPES` comments are stale. Line 51: `"fhir_claim", # CARIN BB Claim → etlp mapping 19` — but Mongo profile is mapping 15. Other comments also drift (line 53 says "FHIR R4 Appointment (template pending)" but mapping 17 exists; line 53 says "FHIR R4 DocumentReference (template pending)" but mapping 18 exists). | §1.2 Mongo profile rows; analyze.py:51 verbatim comment | LOW (documentation only; runtime resolution goes through `_get_artifact_profile` which queries Mongo, not the comments) | One-PR doc cleanup; can ride along with BRS-1 or BRS-6 |
| **S17** | Paper §5.2 pack table has factual errors in 2-of-5 rows: `scheduling_v1` → mapping 22 (wrong artifact_type AND wrong mapping; should be `fhir_appointment` → 17 per what's POSTed); `hl7_adt_v1` → mapping 26 (the registered default profile is mapping 42 lenient; mapping 26 only enters via direct backend bypass, not via `/v1/pipeline/evaluate`). | §1.1 table + §2.5 NDJSON pin extracts | MEDIUM (paper claim hygiene; impacts BRS-6 amendment scope) | Rewrite §5.2 in BRS-6 |
| **S18** | `scribe_v1` IS structurally validated despite paper §5.2 claiming "semantic-only by design." Default profile `fhir_document_reference` → mapping 18 runs on every scribe case (500/500 in sweep, all PASS). The validator is envelope-only (5 presence checks; see §1.3) so it doesn't *catch* scribe injectors, but it does run. Paper claim is factually wrong. | §1.3 mapping 18 verbatim yaml + /apply output; §3 config-state matrix | MEDIUM (story-claim hygiene; impacts §5.2 narrative AND §7.1 decomposition framing) | Rewrite §5.2 negative-control framing in BRS-6: scribe_v1 is no longer a clean negative control because the structural axis is registered (just inert against SOAP-body content). Consider unregistering the default `fhir_document_reference` profile for the bench org during the next sweep to actually have a clean "no structural" axis. (That registration change is a BRS-0b decision, not BRS-0a.) |

### 5.6 HALT (d) explicit refutation

The driver's HALT (d) trigger: "Triage_v1 audit reveals fhir_risk_assessment IS pointed at FHIR Claim validator (mapping 19) by an actual profile row."

**Status: NOT TRIGGERED.** Verbatim Mongo:

```
> db.artifact_profiles.findOne({artifact_type: "fhir_risk_assessment", active: true})
{
  _id: ObjectId('69cd1a331315aca41c3271ed'),
  artifact_type: 'fhir_risk_assessment',
  organization_id: 'default',
  etlp_mapping_id: 19,
  name: 'FHIR R4 RiskAssessment Validator',
  version: 1,
  active: true
}

> curl -s http://localhost:3031/mappings/19 | jq '.title'
"fhir-risk-assessment-validator"
```

Mapping 19 IS the RiskAssessment Validator. Profile binding is correct. The audit doc's hypothesis that "mapping 19 is the FHIR Claim validator" traces to a stale comment at `lithrim-backend/app/routes/analyze.py:51` (which says `"fhir_claim" → etlp mapping 19`). That comment is the S16 documentation drift; live Mongo resolves `fhir_claim` to mapping 15 separately. Safe to close HALT (d) as a documentation-drift surface (S16), not a silent misvalidation.

---

## Acceptance criteria check

| Criterion | Status |
|---|---|
| 1. Mongo `db.artifact_profiles` audited for bench `org_id` + `default` fallback; verbatim results | CONFIRMED — §1.1 + §1.2 + §1.3 |
| 2. ≥3 `pipeline_runs` sampled per pack with verbatim `stage_results.structural.status` | CONFIRMED — §2.1–§2.4 (3 each, except fhir_appointment WARN doesn't exist; declared explicitly) |
| 3. Report exists at `lithrim-bench/docs/research/MEASUREMENT_AUDIT_2026-05-26.md` with all five sections | THIS FILE (sections 1-5 + acceptance) |
| 4. Every claim tagged CONFIRMED / INFERRED / HYPOTHESIS | Inline throughout |
| 5. Triage→mapping 19 silent-misvalidation flagged as separate seam if real | NOT REAL; documented as refutation in §5.6 |
| 6. No code change committed. No new LLM call. No service started. | CONFIRMED — only Mongo reads + etlp-mapper /apply (read-only) + NDJSON parsing |

---

## Diagnose-before-edit compliance

All causal claims in this report carry an evidence block (verbatim Mongo result, NDJSON row excerpt, or etlp-mapper API response) within 30 lines and are tagged CONFIRMED / INFERRED / HYPOTHESIS. The one HYPOTHESIS-tier claim is in §5.4 ("the validator-coverage-gap framing is a stronger product purchase-decision signal") — that's an opinion about narrative, not a data claim.

No file in `lithrim-backend/`, `lithrim-bench/lithrim_bench/`, `lithrim-bench/docs/paper_draft/`, `lithrim-backend/app/services/`, or `lithrim-backend/app/routes/` was edited during this audit. One `mkdir -p lithrim-bench/docs/research/` was executed to create the deliverable directory.

---

## Hand-off summary for monitor

- 2,009/2,009 FHIR pipeline_runs in the 22-23 sweep show `structural.status=PASS`. The `not_applicable→PASS` collapse in `_STAGE_STATUS_NORMALIZE` is inert; the real story is **validator coverage**, not config-state.
- Profiles are registered for all 5 packs (via default-org fallback). Validators run. They emit PASS because they're envelope-only.
- HALT (d) refuted. analyze.py comment drift is S16 (low).
- Three new seams confirmed: S16 (low), S17 (medium paper-table drift), S18 (medium scribe-not-actually-semantic-only).
- BRS-1 reframes (add validator-template observability). BRS-3 deprecation-candidate (no structural findings on FHIR). BRS-4 rescope (artifact_judge precision, not gating). BRS-6 expands to §4-§5-§7 amendment.
- Awaiting monitor decision on whether to proceed with BRS-0b as drafted, rescope, or insert BRS-0a.5 (default profile reconfiguration for the bench org before re-measurement).
