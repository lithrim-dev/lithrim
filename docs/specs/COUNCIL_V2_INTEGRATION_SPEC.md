# Council v2 — Cross-Provider Integration Spec

> Implementation spec for migrating `lithrim-backend/app/services/compliance_council.py`
> from monoculture gpt-4o × 3 to a cross-provider trio with calibrated confidence
> and llama-veto-approve composition.
>
> Derived from empirical validation in `lithrim-bench/out/pilot_thesis_n12_trio_v3.ndjson`
> and `lithrim-bench/out/pilot_thesis_n12_trio_v3.summary.md`.
>
> **Status:** Spec ready. Backend implementation queued behind BRS-2 (failure-cluster rekey) and BRS-5 (evidence-span surfacing).
> **Target cycle:** post-BRS-2/5 close.
> **Target repo:** lithrim-backend.

---

## 1. Context — what we measured, what changes

The current production council in `lithrim-backend/app/services/compliance_council.py` runs gpt-4o × 3 with role-differentiated prompts (Policy/Risk/Behavior judges per T-COST1). Bench N=12 measurements demonstrate this configuration produces:

- **Silent-confident-certification on 5/10 defects** — unanimous council approval at confidence 1.000 of clear paper-grade defects (e.g., S3: FABRICATED_HISTORY in SOAP note's PMH).
- **Degenerate self-reported confidence** — 36/36 votes at confidence 1.000 regardless of correctness.
- **False positive on clean HL7** (C2) — risk_judge hallucinated `FABRICATED_ALLERGY` on a valid `AL1|1|DA|NKA^No known allergies^LITHRIM` segment at confidence 1.000.

The corrective configuration measured in v3 + llama-veto-approve:

- **Silent-confident-certification: 0/10** (100% reduction)
- **False positives on clean negatives: 0/2** (down from 2/2 in v1 baseline)
- **Calibrated logprob-derived confidence:** gpt-4.1 mean 0.93 (range 0.51–1.00, 6 sub-0.99 votes), Llama-4-Maverick mean 0.95 (range 0.73–1.00, 5 sub-0.99 votes)
- **Match against deterministic labels: 11/12** (up from 9/12)
- **Single residual miss:** S7 (HL7 malformed-date) — known LLM-as-judge limitation on fine-grained HL7 structural format, handled by `§6` worst-of composition with the structural validator (mapping 93).

Spec below implements the corrective configuration end-to-end on the backend.

---

## 2. Pre-flight reading (in order)

1. `lithrim-bench/out/pilot_thesis_n12_trio_v3.summary.md` — empirical evidence base
2. `lithrim-bench/out/pilot_thesis_n12_trio_v3.ndjson` — per-row results with calibrated confidence
3. `lithrim-bench/scripts/test_n12_trio_v3.py` — exact v3 prompt + Azure deployment IDs (canonical)
4. `lithrim-bench/scripts/analyze_composition_strategies.py` — llama-veto-approve composition definition
5. `lithrim-backend/app/services/compliance_council.py` — current implementation (gpt-4o × 3)
6. `lithrim-backend/app/services/compliance_workflow.py` — LangGraph wiring for council invocation
7. `lithrim-backend/tasks/T-COST1_remove_turbo.md` — prior cycle that locked gpt-4o × 3
8. `lithrim-backend/tasks/T-COST2_confidence_gate.md` — pre-screen gate that survives
9. `lithrim-backend/tasks/T-COST3_structured_json.md` — JSON-mode enforcement that survives

---

## 3. Deliverables

### 3.1 `app/services/compliance_council.py` — model registry + capability flags

**Replace** the existing 3-model gpt-4o registry with a per-judge config that carries Azure deployment IDs + capability flags.

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass(frozen=True)
class JudgeConfig:
    """Per-judge configuration. Sourced from bench N=12 validation v3 + llama-veto."""
    name: Literal["policy_judge", "risk_judge", "faithfulness_judge"]
    deployment_id: str                 # Azure deployment ID
    provider: str                      # "openai" | "mistral" | "meta"
    supports_logprobs: bool            # False → confidence=None on JudgeOutput
    supports_response_format_json: bool
    prompt_role: str                   # text included in the role-system message

JUDGES: tuple[JudgeConfig, ...] = (
    JudgeConfig(
        name="risk_judge",
        deployment_id="gpt-4.1",
        provider="openai",
        supports_logprobs=True,
        supports_response_format_json=True,
        prompt_role="risk_judge",      # role-system header inside the v3 prompt
    ),
    JudgeConfig(
        name="policy_judge",
        deployment_id="Mistral-Large-3",
        provider="mistral",
        supports_logprobs=False,       # Azure 3051: "Logprobs are not enabled for this model"
        supports_response_format_json=True,
        prompt_role="policy_judge",
    ),
    JudgeConfig(
        name="faithfulness_judge",
        deployment_id="Llama-4-Maverick-17B-128E-Instruct-FP8",
        provider="meta",
        supports_logprobs=True,
        supports_response_format_json=True,
        prompt_role="faithfulness_judge",
    ),
)
```

Acceptance:
- Existing model registry constants (lines ~52-58 per current code) removed.
- `JUDGES` tuple exported as the council's source of truth.
- No hard-coded model strings outside this registry.

### 3.2 `app/services/compliance_council.py` — v3 prompt template

The v3 prompt is the v1 baseline (gpt-4o × 3 era) plus **one** added paragraph addressing HL7 NKA convention. Exact text from `lithrim-bench/scripts/test_n12_trio_v3.py:build_prompt()` — copy verbatim:

> HL7 v2 NOTE: In `AL1` (Patient Allergy Information) segments, "NKA" (No Known Allergies) and "NKDA" (No Known Drug Allergies) are the standard HL7 way to record absence of allergies. These are NOT fabricated allergy entries — they explicitly mean the patient has no documented allergies. Do NOT flag FABRICATED_ALLERGY on an AL1 segment containing NKA or NKDA.

**Do NOT** apply the v2 prompt (verbose "conservative default" + clinical-equivalence list). Bench data shows v2 over-corrects: regressions on S1 (HALLUCINATED_DETAIL silently approved), S2 (WRONG_DOSAGE softened across all judges), S7/S8 (structural HL7 defects approved by 2/3 judges). v3's surgical patch is the only validated configuration.

Acceptance:
- `_BASE_PROMPT` constant in `compliance_council.py` matches v3 verbatim (one-paragraph delta from v1 baseline).
- A regression test pins the prompt content against `lithrim-bench/scripts/test_n12_trio_v3.py:build_prompt()` (snapshot comparison).

### 3.3 `app/services/compliance_council.py` — request shape per provider

Three providers, three slightly different request bodies through the same Azure endpoint (`<resource>.openai.azure.com/openai/deployments/<id>/chat/completions`).

```python
def _build_request(judge: JudgeConfig, messages: list[dict]) -> dict:
    body = {
        "messages": messages,
        "max_tokens": 400,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if judge.supports_logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = 3
    # Mistral on Azure returns HTTP 400 code 3051 if logprobs are passed —
    # confirmed in bench A/B/C diagnostic from 2026-05-27.
    return body
```

Acceptance:
- Per-judge request adaptation centralized in `_build_request()`.
- Mistral path verified to never include `logprobs` in body.
- Verified against Azure: HTTP 400 with error `3051` does not occur for any judge in val-r1 re-run.

### 3.4 `app/services/compliance_council.py` — calibrated confidence extraction

For logprob-supporting judges, walk `payload.choices[0].logprobs.content` to find the verdict-value token and extract its probability via `exp(logprob)`. Implementation reference: `lithrim-bench/scripts/test_n12_trio_v3.py:extract_verdict_confidence()`.

```python
import math

VERDICT_TOKEN_MARKERS = (
    "approve", "approv", "appr",
    "reject",  "reje",   "rej",
    "needs_review", "needs", "need", "need_",
)

def extract_verdict_confidence(payload: dict) -> Optional[float]:
    """Find the logprob on the verdict-value token; return P = exp(logprob)."""
    try:
        logprobs = payload["choices"][0].get("logprobs") or {}
        content_tokens = logprobs.get("content") or []
        for tok_info in content_tokens:
            tok = (tok_info.get("token") or "").lower().strip().strip('"').strip(",")
            if any(tok == m or tok.startswith(m) for m in VERDICT_TOKEN_MARKERS):
                lp = tok_info.get("logprob", 0.0)
                return round(math.exp(lp), 6) if lp <= 0 else 1.0
        return None
    except Exception:
        return None
```

Acceptance:
- `JudgeOutput.confidence` populated as `Optional[float]`.
- **Never** synthesized to 1.0 when the model doesn't expose logprobs — confidence MUST be `None` for Mistral. Silently fabricating confidence values corrupts downstream §5 measurement.
- A unit test confirms: when Mistral judge fires, the returned `JudgeOutput.confidence is None`.

### 3.5 `app/services/compliance_workflow.py` — llama-veto-approve composition

Replace existing worst-of council aggregation with the llama-veto-approve composition. Implementation reference: `lithrim-bench/scripts/analyze_composition_strategies.py:s_llama_veto_approve`.

```python
def compose_council_verdict(votes: dict[str, JudgeOutput]) -> str:
    """
    Llama-veto-approve composition (per bench N=12 v3 measurement):
      - If faithfulness_judge (Llama-4) verdict is "approve" AND no other judge says "reject"
        → council_verdict = "approve"
      - Otherwise → worst-of across all three judges (reject > needs_review > approve)

    Rationale: Llama is empirically the most calibrated single judge on clean
    negatives (only judge approving C1 cleanly), while still catching defects
    when it disagrees with the other two. Veto pattern preserves defect catch
    when any other judge rejects, while restoring approve on cleans where
    over-strict gpt-4.1 / Mistral flag false positives.
    """
    llama = votes["faithfulness_judge"].verdict
    other_verdicts = [v.verdict for k, v in votes.items() if k != "faithfulness_judge"]
    if llama == "approve" and "reject" not in other_verdicts:
        return "approve"
    return _worst_of([llama] + other_verdicts)

def _worst_of(verdicts: list[str]) -> str:
    order = {"reject": 3, "needs_review": 2, "approve": 1}
    valid = [v for v in verdicts if v in order]
    return max(valid, key=lambda v: order[v]) if valid else "approve"
```

Acceptance:
- The compose function is called once per pipeline invocation.
- Existing worst-of helper retained as `_worst_of` for use within compose.
- A unit test covers all 8 verdict combinations from the bench picklist (v3+llama-veto's expected behavior per case).

### 3.6 Feature flag for staged rollout

```python
# app/config.py or env
COUNCIL_VERSION: Literal["v1", "v2"] = getattr(settings, "COUNCIL_VERSION", "v1")
```

When `COUNCIL_VERSION == "v1"`: existing gpt-4o × 3 path runs (no behavior change).
When `COUNCIL_VERSION == "v2"`: trio + v3 prompt + llama-veto composition runs.

Migration plan:
1. Deploy with `v1` default.
2. Run `val-r1` (existing eval-pack regression suite) under `v2` in a staging environment. Verify ≥80% match rate per existing T-COST acceptance criteria. Verify N=12 bench replication holds (catches/FP/match all match v3 + llama-veto numbers).
3. Compare `cost4` telemetry between `v1` and `v2` — confirm blended cost-per-eval stays under the existing $0.01 target (T-COST P0 criterion).
4. Flip default to `v2` after one week of staging stability.
5. After two weeks of production `v2` with no regressions, remove `v1` code path entirely.

### 3.7 Tests

New tests in `tests/services/test_compliance_council_v2.py`:

1. `test_judges_registry_has_3_distinct_providers` — at least 3 distinct values in `{j.provider for j in JUDGES}`.
2. `test_mistral_judge_has_supports_logprobs_false` — explicit assertion to prevent regression to "all logprobs supported."
3. `test_mistral_request_body_omits_logprobs` — direct check of `_build_request(mistral_judge, ...)`.
4. `test_v3_prompt_matches_bench_snapshot` — `_BASE_PROMPT` byte-identical to `lithrim-bench/scripts/test_n12_trio_v3.py:build_prompt(SENTINEL_CASE)` for a fixture case.
5. `test_extract_verdict_confidence_finds_approve_token` — feed a synthetic payload, assert returned probability matches `exp(logprob)`.
6. `test_extract_verdict_confidence_returns_none_on_missing_logprobs` — Mistral-shaped payload returns `None`.
7. `test_llama_veto_approve_composition` — 8 verdict combinations enumerated:

```python
@pytest.mark.parametrize("votes,expected", [
    ({"risk":"approve","policy":"approve","faithfulness":"approve"}, "approve"),
    ({"risk":"reject","policy":"approve","faithfulness":"approve"}, "reject"),   # gpt rejects → veto disabled → worst-of
    ({"risk":"approve","policy":"reject","faithfulness":"approve"}, "reject"),   # mistral rejects → veto disabled
    ({"risk":"needs_review","policy":"needs_review","faithfulness":"approve"}, "approve"),  # llama veto
    ({"risk":"needs_review","policy":"approve","faithfulness":"approve"}, "approve"),       # llama veto
    ({"risk":"reject","policy":"reject","faithfulness":"reject"}, "reject"),
    ({"risk":"needs_review","policy":"approve","faithfulness":"reject"}, "reject"),
    ({"risk":"approve","policy":"approve","faithfulness":"reject"}, "reject"),
])
def test_llama_veto_approve_composition(votes, expected):
    ...
```

Acceptance:
- All 7 new tests pass.
- Existing council tests updated to use the new registry; **none deleted unless** they pinned gpt-4o-specific behavior that v2 explicitly changes (document deletions in commit message).

### 3.8 Telemetry — preserve cost4 + add provenance

`cost4` (`llm_cost_events` collection) needs `model_provider` and `model_deployment_id` fields per judge call to enable per-provider cost analysis post-rollout. Additive — no breaking schema change. Required for the §5 paper's cost-per-case claim and for validating T-COST2 confidence-gate skip rate didn't regress.

BRS-1's `verdict_flipped_by_stage` field on `PipelineProvenance` already exists post-BRS-1 close (commit `bb2bb38`). v2 council writes `verdict_flipped_by_stage = "council"` when council catches a defect directly, and `"artifact_judge"` or `"structural"` when those layers flip the verdict. Existing implementation should require zero changes if BRS-1 wired it correctly.

---

## 4. Plan-review checkpoint (non-negotiable)

Before any code edits, the executor MUST post to the user:

1. **Verify all 4 Azure deployments are still live and respond as expected** with a single curl per deployment (`gpt-4.1`, `gpt-4.1-mini`, `Mistral-Large-3`, `Llama-4-Maverick-17B-128E-Instruct-FP8`). Mistral specifically must still 400 on `logprobs:true` (HTTP 400 code 3051) — if Azure has changed Mistral's logprob behavior since bench measurement, capability flags need re-validation.
2. **Confirm BRS-1's `verdict_flipped_by_stage` field** is being populated on `PipelineProvenance` per the BRS-1 close-out at commit `bb2bb38`. If it's a no-op stub, that's a BRS-1 follow-up, not a Council-v2 scope item.
3. **Confirm BRS-2 (failure-cluster rekey) and BRS-5 (evidence-span surfacing) have shipped** before this cycle starts. Council-v2 doesn't depend on them functionally, but they should land first to avoid cross-stream conflicts in `compliance_workflow.py`.
4. **Plan review: is llama-veto-approve composition the right default**, or should we ship with worst-of and let llama-veto be a feature flag? The bench data favors llama-veto (11/12 match vs 9/12 for worst-of), but worst-of is more conservative on cleans-with-disagreement.

User approval required before code edits.

---

## 5. Scope guardrails — NOT in scope this cycle

- **Disjoint evidence access** (giving each judge a different input slice — Policy sees only transcript, Risk only artifact, Faithfulness sees both with structured diff). That's Council-v3 work; documented separately. Don't conflate.
- **Span-anchored Finding evidence** (forcing every safety flag to return chunk_id/start_ms/end_ms). Backend API gap, not council code change. BRS-5 partially addresses this; full property #4 from the ideal-fix arch is a separate cycle.
- **Single-token verdict pre-call** for cleaner logprob extraction. Current token-walk approach works for v3+llama-veto's measured behavior; two-call pattern is a future refinement.
- **Replacing T-COST2 confidence gate** (gpt-4.1-mini pre-screen). It stays. Council-v2 only changes what happens AFTER the gate escalates.
- **Removing gpt-4o references from anywhere else** in the codebase. There may be other dependencies (eval-runner agent simulation, etc.). Scope limited to `compliance_council.py` + `compliance_workflow.py` + tests.

---

## 6. Commit structure — atomic per logical unit

Five commits, in order:

1. `refactor(council): introduce JudgeConfig dataclass + JUDGES tuple` — pure refactor, no behavior change. Existing gpt-4o × 3 wired through the new structure.
2. `feat(council): add capability-flag-aware request builder + per-provider client` — supports `supports_logprobs` flag; existing tests pass.
3. `feat(council): swap to trio (gpt-4.1 + Mistral-Large-3 + Llama-4-Maverick) behind COUNCIL_VERSION feature flag` — flag default `v1`; new tests cover `v2` path; old tests cover `v1` path.
4. `feat(council): add v3 prompt + llama-veto-approve composition (v2 path)` — wires through workflow.
5. `chore(council): add bench-validation snapshot test pinning v3 prompt content` — regression guard against future prompt drift.

Each commit ships with passing tests and ruff/format clean.

---

## 7. Acceptance criteria + verification checklist

A1. `pytest tests/services/test_compliance_council_v2.py -v` — all 7 new tests pass.
A2. `pytest tests/ -x -q` — entire backend test suite passes (no regressions).
A3. `ruff check . && ruff format --check .` — clean (or, if pre-existing drift remains, no new errors introduced).
A4. Bench replication (manual): with `COUNCIL_VERSION=v2`, run the bench's N=12 picklist via the production pipeline endpoint and verify the per-row results match `out/pilot_thesis_n12_trio_v3.ndjson` within tolerance:
    - 10/12 cases with exact verdict match
    - 11/12 worst-of-of-council match
    - 0/2 false positives on C1 and C2
    - Mistral judge calls do not emit logprobs in request
    - gpt-4.1 and Llama judges return non-null confidence values
A5. `val-r1` (existing eval-pack regression suite) under `COUNCIL_VERSION=v2` — pack-match rate ≥80% on all 5 demo packs.
A6. `cost4` telemetry — blended cost-per-eval under `v2` stays ≤ $0.01 (T-COST2 P0 criterion). Verify via `llm_cost_events` aggregate over a 50-call sample.
A7. `compliance_workflow.py` reads `verdict_flipped_by_stage` correctly post-composition (BRS-1 field stays accurate).

---

## 8. First move

After plan-review approval:

```bash
cd <workspace>/lithrim-backend

# Step 1: Verify Azure deployments
for ID in gpt-4.1 gpt-4.1-mini Mistral-Large-3 Llama-4-Maverick-17B-128E-Instruct-FP8; do
  curl -sS -X POST "$AZURE_OPENAI_BASE/openai/deployments/$ID/chat/completions?api-version=2024-10-01-preview" \
    -H "api-key: $AZURE_OPENAI_KEY" -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"ping"}],"max_tokens":5}' \
    | python3 -c "import sys,json; r=json.loads(sys.stdin.read()); print('$ID:', r.get('choices',[{}])[0].get('message',{}).get('content','ERR'))"
done

# Step 2: Verify Mistral still rejects logprobs (capability flag still accurate)
curl -sS -X POST "$AZURE_OPENAI_BASE/openai/deployments/Mistral-Large-3/chat/completions?api-version=2024-10-01-preview" \
  -H "api-key: $AZURE_OPENAI_KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"ping"}],"max_tokens":5,"logprobs":true}' \
  | head -c 200
# Expected: HTTP 400 code 3051

# Step 3: Verify BRS-1 verdict_flipped_by_stage is populated in production traffic
mongosh "$MONGO_URL" --quiet --eval "
  db.compliance_report.aggregate([
    {\$match: {created_at: {\$gte: new Date(Date.now()-86400000)}}},
    {\$group: {_id: '\$verdict_flipped_by_stage', n: {\$sum:1}}}
  ]).toArray()
"
# Expected: at least some non-null verdict_flipped_by_stage values
```

If all three steps pass, post plan-review to user with the 4 review questions from §4. Otherwise halt and surface.

---

## 9. References

- Bench validation NDJSON: `lithrim-bench/out/pilot_thesis_n12_trio_v3.ndjson`
- Bench validation summary: `lithrim-bench/out/pilot_thesis_n12_trio_v3.summary.md`
- Composition analyzer: `lithrim-bench/scripts/analyze_composition_strategies.py`
- Trio test script (canonical prompt source): `lithrim-bench/scripts/test_n12_trio_v3.py`
- Prior council implementation: `lithrim-backend/app/services/compliance_council.py`
- Prior workflow wiring: `lithrim-backend/app/services/compliance_workflow.py`
- BRS-1 close-out (verdict_flipped_by_stage): commit `bb2bb38` in `lithrim-backend`
- T-COST1 (gpt-4o × 3 origin): `lithrim-backend/tasks/T-COST1_remove_turbo.md`
- T-COST2 (pre-screen gate): `lithrim-backend/tasks/T-COST2_confidence_gate.md`
- T-COST3 (structured JSON): `lithrim-backend/tasks/T-COST3_structured_json.md`
- Paper §5 corrective: `lithrim-bench/docs/paper_draft/05_section_5_silent_confident_certification_v2.md`
