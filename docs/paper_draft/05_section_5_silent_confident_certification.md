# §5 — Silent Confident Certification

*Why generative-validator composition matters: an LLM-judge council does not hedge on spec-violating clinical artifacts. It confidently approves them, and the failure is invisible at the API surface.*

[NUMBERS FROM EXPERIMENT — VERIFY AGAINST `out/p1_exp_0_council_confidence.summary.json`]

## The measurement

We ran a live three-judge council (policy / risk / behavior, gpt-4.1) against the 28 defect-bearing cases of the HL7 ADT^A04 conformance pack (`out/hl7_adt_v1.jsonl`), with `validator_id=93` (the §4-generated mapping). Each case carries a single structural defect — a malformed date, a missing segment, an invalid PID-8 administrative sex, a missing required field, or a trigger-event mismatch — labeled `expected_compliance_verdict=reject` by construction.

## What the council did

On the 28 defects the council was unanimous-approve on **10 (35 %)**, split on **15 (54 %)**, and unanimous-reject on **3 (11 %)** — at least one judge approves a spec-violating message on **25 / 28 = 89 %** of defects. On the unanimous-approve subset, per-judge confidence is **mean = median = min = max = 1.000** for every judge: 30 / 30 votes are at the maximum the model emits, all in the `0.9–1.0` histogram bucket (`out/p1_exp_0_council_confidence.summary.md`).

This is silent confident certification. The council does not return `needs_review`. It does not emit a hedging finding. It returns `verdict=approve` at the highest confidence the model ever produces, on artifacts the HL7 v2 specification rejects.

## What §6 recovers

The 10 silent-confident-certified defects break down as 5 malformed dates, 3 missing segments, 1 missing required field, and 1 invalid field format. The strict ADT^A04 validator (§4, mapping 93) emits `structural_verdict=WARN` on **all 10**, with the specific check-name (e.g. `gender-value-valid`, `dtm-format-valid`) attached. The composed worst-of pipeline gate therefore lands `compliance_verdict=needs_review` on **10 / 10** silent cases — the validator drags the gate off the council's unanimous approval.

## Why this is not "judges are 85 % accurate"

A judge-accuracy framing implies hedging on the missed cases. The data does not. The judge is not uncertain about a spec-violating message; it is confident, in the model's own confidence metric, that the message is fine. Adding more judges of the same kind, or tuning their accuracy, does not move this distribution. The remediation is not a better judge; it is a deterministic conformance check the council does not have access to. Paper 1's §6 is that check.

[Source: `out/p1_exp_0_council_confidence.ndjson` (N=1, 40 cases, mapping 93, 2026-05-27); aggregation in `out/p1_exp_0_council_confidence.summary.{json,md}`.]
