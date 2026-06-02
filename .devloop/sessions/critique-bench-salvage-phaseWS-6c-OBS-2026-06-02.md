# Critique — `bench-salvage` WS-6c-OBS (ROUTINE, inline + monitor deep-read)

**Verdict:** NON-BLOCKING → CLOSE.
**Mode:** inline critique by the monitor (ROUTINE phase: KPIs not compliance verdicts, grade-path-independent, no consensus-IP/contract/grade-seam touched, executor self-reported deviations → not a fresh-critic trigger). **Extended with a monitor deep-read** of the 3 LLM agent ports after the user (correctly) pushed on the producer-bias risk: the inline critic here is the same monitor who authored the driver, and that driver carried a citation error (DRIFT-2b).
**Commit span audited:** bench `2321090..3cda9df` (4 code commits) + `5900877` (session log), branch `bench-salvage/ws6c-dspy`, not pushed. Backend untouched (`6720c70`).

## The crux — is the "faithful port" of the 3 LLM agents real? VERIFIED FAITHFUL

The one substantive gap the mechanical audit left: the executor called the intent/sentiment/safety agents "real faithful ports," but A1–A5 only prove they're isolated/lazy and wire up — not that the ported **scoring logic** matches the backend. Closed by a from-source deep-read (1,528 lines across the 3 bodies vs `../lithrim-backend/app/agents/*/agent.py`):

1. **Scoring math identical.** The float-constant multiset (thresholds / weights / defaults) is byte-identical backend↔bench for all three agents (`diff` of sorted `uniq -c` float literals = empty). The numeric scoring is preserved.
2. **Prompt text identical.** AST-level string-literal multiset comparison (incl. f-string fragments — the actual LLM prompt text): **every** delta is a docstring rewording (mostly adding "Ported from `lithrim-backend@mvp-ready`" provenance) or a dropped debug/error **log** line (`"Init X Agent: initializing…"`, `"Failed to parse sentiment JSON:"`, `"Error parsing JSON response:"`). **No prompt f-string content changed.**
3. **Method surface preserved.** Nothing dropped/renamed except `__init__` on `intent_quality` + `sentiment` — the sanctioned injectable-LLM / dropped-singleton refactor (the LLM client moved to the `_LlmBackedAgent` base). `safety` correctly **kept** its custom `__init__` (the regex PII patterns).

The port changes only the sanctioned axes (lazy LLM via the council `llm_provider`/`phi_redaction`, dropped module-singleton, docstring/log cleanup, modern typing). **By-construction scoring fidelity maintained.**

## Per-gate (mechanical audit, independently re-verified)

| Gate | Verdict | Evidence (monitor re-verified) |
|---|---|---|
| A1 (in-process KPI pipeline) | PASS | text case → `status=completed`, `overall_score≈99.3`, `CallKPI` emitted; 4-way `asyncio.gather` exercised |
| A2 (default install unchanged) | PASS | `import lithrim_bench` + observation pkg leak **NONE** of openai/whisper/torch/librosa/boto3/pydantic_settings/dspy/mongo/langgraph (sys.modules probe); full suite **200 passed / 7 skipped**; `ruff` All-checks-passed |
| A3 (boundary held) | PASS | only `council/` reach is `_llm.py:30/42` **lazy** `llm_provider`/`phi_redaction` infra reuse (sanctioned A+); every `ComplianceWorkflow` ref is docstring/comment/test prose; `run()` stops at `_aggregate_kpis`, returns `state`; no grade/run_eval/report ref |
| A4 (agent map) | PASS | 7 agents hoisted in `ObservationAgents` (built once); `evaluation_agent` not imported; `simulation_agent` not in path; gather fan-out preserved (peak-concurrency probe). Audio-DSP trio = interface-complete, bodies deferred (A+; S-BS-36) |
| A5 (state contract) | PASS | `ObservationState` = 28 KPI fields ⟂ 9 seam fields; `CallKPI` = pinned 19-field upstream set |

## The 4 questions

1. **Surface fidelity** — package surface matches D1–D3; contract pinned. The A+ tier (audio bodies deferred behind `[observation]`) is a user-approved scope boundary (S-BS-36), not drift.
2. **Behavioral fidelity** — traced gather/boundary/hoist claims to test + site; all chains demonstrate the behavior. Deep-read adds: scoring math + prompt text fidelity for the 3 LLM ports.
3. **Out-of-scope intrusion** — none. Diff confined to `observation/` + `pyproject.toml` + log (3794 ins / 1 del); no backend edit; no grade-wire/persistence/KB.
4. **Spec ambiguity** — "recomposed" for the audio trio = interface-hoisted-bodies-deferred (A+) vs full-port (B); resolved by the user's A+ election. **Disposition: S-BS-36 stays deferred** — no harness consumer reads the KPI output yet, so text-path-real is the correct scope; promote to a tier-B follow-up only when a consumer materializes.

## Monitor self-correction (DRIFT-2b)

The executor caught a citation miss in the monitor's own expand-driver re-grep: the driver §1.3 called `transcription_agent` "dep-light" and grouped a "dep-light slice = transcription + technical_metrics + kpi_aggregation." Confirmed wrong from source — `transcription_service.py:4 import whisper` (module-top, a **sibling** the per-`agent.py` grep never opened) + `technical_metrics_agent/agent.py:21 import librosa` (**indented**, so the `^(import|from)` anchor skipped it). Only `kpi_aggregation` is pure. **No harm** (A+ gated the whole audio trio behind `[observation]`, so A2 holds), but per the symmetric diagnose-before-edit discipline the driver text was corrected at close (3 sites marked "CORRECTION (DRIFT-2b, 2026-06-02)"). Root cause logged for future re-greps: anchored-import grep misses indented/lazy imports + sibling-module deps.

## Seams

- **S-BS-36** (low) — audio-DSP bodies (whisper/torch/librosa/numpy) deferred behind `[observation]`; the tier-B full-audio-port follow-up. Inert until a KPI consumer exists. CONFIRMED.
- **S-BS-37** (low) — ported models use `datetime.utcnow` (py3.12 DeprecationWarning; faithful to backend `call_kpi.py`). Cosmetic. CONFIRMED.

## Disposition

Audit CLEAN; inline critique + deep-read NON-BLOCKING; the LLM-port fidelity gap closed (scoring math + prompt text identical). Scope held; backend untouched; zero live cost. **CLOSE** WS-6c-OBS. Carryforward: **S-BS-36** (defer until consumer) + **S-BS-37** (cosmetic) + **S-BS-34** (pre-existing ruff exclude, prior cycle).
