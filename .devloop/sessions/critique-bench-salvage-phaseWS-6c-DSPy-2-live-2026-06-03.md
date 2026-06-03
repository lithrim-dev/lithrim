# Critique — `bench-salvage` WS-6c-DSPy-2-live (inline, ROUTINE)

- **Mode:** inline (monitor), per driver Hardness = ROUTINE. Load-bearing focus (driver): A3 frozen-contract re-verify + result-honesty (the mandated caveats) + the S-BS-44 parity proof.
- **Range:** `c0a5463..7031466` (4 commits). **Verdict: NON-BLOCKING (0 BLOCKING) — cycle closes.**

## The confound the monitor ruled out (the load-bearing check this critique adds)

The headline A/B finding is: *the DSPy policy_judge (Mistral) is silent (fp=0) while the prompt-arm Mistral is verbose (fp=22), same model/deployment/`.strip()`-identical prompt → an elicitation-path gap.* A "silent" judge could equally be a **silently-errored** judge — `run_live:254` builds the DSPy seams without filtering `errors`, so a judge that threw would also show empty findings and read as fp=0.

**Ruled out (CONFIRMED):** the captured artifact `docs/research/ab_result_dspy2_live_2026-06-03.json` has **zero non-empty `errors` arrays** and **0** error/exception/content-filter/rate-limit indicators. The DSPy-arm Mistral genuinely ran and returned valid empty-findings responses on all 7 cases. The elicitation-path framing is sound, not an artifact of error-induced silence.

## Q1 — Surface fidelity · 0 BLOCKING / 0 NB / 0 OQ
Deliverables match driver §2 + the approved deviations: S-BS-44 `.strip()` (`judges_dspy.py`); D-1 `_context_payload` nesting (`ab_harness.py`, approved at plan-review); the live run; the artifact + REPORT relocated to `docs/research/` (monitor's D-3 ruling — NOT the driver's gitignored `out/` path); session log. Both code diffs are exactly as approved — thorough docstrings, no creep.

## Q2 — Behavioral fidelity · 0 / 0 / 0
- **A1 / S-BS-44:** `load_role_prompt` returns `.read_text(...).strip()` (matches `_load_role_prompts:527`); `test_build_trio_role_prompts_byte_match_the_prompt_council` asserts byte-parity for all `V2_ROLES`. **CLOSED.**
- **A3 frozen:** `compliance_council.py` = 0 delta vs `c0a5463` (monitor re-verified). No `_apply_consensus`/grade/lens change.
- **D-1:** `_context_payload` nests transcript under `call_context`; `test_context_payload_nests_transcript_under_call_context` guards it offline ($0). The cost-confirm smoke validated the fix live (the clean-negative reject is the documented transcript-only blind spot — exhibited by the bug-free DSPy arm too — not the payload bug).
- 72 passed / 2 skipped on `debuglithrim` (+2 guards over the prior 70).

## Q3 — Out-of-scope intrusion · 0 / 0 / 0
Scope = 7 files (4 council + 2 `docs/research/` + session log). No concurrent-session/paper file in the diff; the 3 staged paper files not swept; **no secret leaked** (diff + tree scanned; the extracted credential file was removed). A3 frozen. D-1 is an approved deviation, not intrusion.

## Q4 — Spec ambiguity / judgment · 0 / 0 / 2 OQ
- **OQ-1 (→ WS-6c-DSPy-3, S-BS-45):** the policy_judge elicitation divergence — confirmed genuine. Open question for the spec/judge author: is the DSPy `JudgeSignature` *under*-eliciting policy, or is `build_prompt` *over*-eliciting (fp=22 of out-of-lens noise)? Which is the calibrated target? Needs the optimizer + more cases.
- **OQ-2 (→ S-BS-42):** the policy PHI recall gap is unmeasurable on proof_case (no case carries `PHI_DISCLOSURE_PRE_VERIFICATION`). Needs a PHI-carrying case.

## Result-honesty (A4) — exemplary
The REPORT leads with four caveats (lower-bound precision S-BS-43 / captured-snapshot-not-deterministic / n=7-small / the transcript-only blind-spot saturating the fp columns), labels every number as-of-this-run, frames the divergence as a DSPy-3 question (not a paper claim), and ties the clean-negative false-reject to the known PMH blind spot. No over-claim.

## Disposition
Inline was correct — the divergence is not a paper claim, so no fresh-critic escalation (per the driver's escalation rule). **S-BS-44 CLOSED**; **S-BS-45 opened** (policy elicitation divergence → DSPy-3); **S-BS-42** (PHI recall, unmeasured) + **S-BS-43** (co-raise-aware lens) carry to DSPy-3. The latent payload bug (D-1) vindicates the DSPy-2 offline-only ruling + the "unvalidated against real behavior" caveat — the live path had a real bug that only surfaced on real wiring.
