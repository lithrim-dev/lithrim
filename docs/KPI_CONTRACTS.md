# KPI contracts and OpenTelemetry traces

Two things a user can do before any judge runs: prove a KPI deterministically on the data, and
bring the data in straight from an OpenTelemetry trace export. Both are core, pure stdlib, and
follow the floor's rule: the check answers only where it can verify, declines everywhere else,
and never clears a genuine defect.

## KPI contracts

Two floor contract types read a **structured record**, the JSON the case carries at `transcript`
when its `source_kind` is `record` (a data-to-text source, an imported record, a span), or the
artifact itself when it is JSON (`target: artifact`).

| contract type | pin | holds | fails | unknown |
|---|---|---|---|---|
| `kpi_threshold` | `field` (dotted path), `op` one of `>= <= > < == != between`, `value` or `min`+`max` | a recorded floor pass | the pinned flag is injected; evidence names the expected bound and the actual value | field absent or not numeric, no record, prose source |
| `field_in_set` | `field`, `allowed` (list), `mode` `in` (default) or `not_in`, `case_insensitive` (default true) | a recorded floor pass | the pinned flag is injected; evidence names the allowed set and the actual value | field absent, no record, prose source |

Unknown is never a violation and never a silent pass: it is surfaced as an inconclusive floor
result the reviewer can see. A malformed pin (an empty `field`, an unknown `op`, a missing or
non-numeric bound, `min > max`, an empty or non-list `allowed`, an unknown `mode` or `target`)
is refused when the contract is authored; the grade applies the same rule.

KPI contracts **stack**: a flag can carry several, one per `field` (a latency KPI and a token KPI
on the same flag), and pinning one never displaces the flag's other checks. A pin with the same
flag, type and field as an existing one replaces it, whatever its version, so a flag never runs
two versions of one KPI. Every other contract type stays one per flag, as before.

Author one from the shell with **⌘K → Add a check or KPI contract** (the contract builder; the
type list is the pack's registered executors), or in the ontology:

```json
{
  "flag_code": "KPI_BREACH",
  "question": "Is the call within the latency budget?",
  "contract_type": "kpi_threshold",
  "version": "latency-budget/1",
  "params": {
    "field": "duration_ms", "op": "<=", "value": 2000,
    "inject_flag_code": "KPI_BREACH", "inject_severity": "HIGH", "artifact_kind": "llm_response"
  }
}
```

The flag it injects must exist in the pack's taxonomy and have an owner in the roster, as for
every contract. Every result rides the run's provenance (`floor_blocks` / `floor_passes`) with
its evidence and a `deterministic: true` manifest.

## OpenTelemetry trace exports

Drop an OTLP/JSON trace export (the `{"resourceSpans": [...]}` shape an OpenTelemetry collector
or SDK file exporter writes) on the upload button. It is recognised by shape, whatever the file
is called, and decoded with no mapper into native cases:

- one case per **LLM span**: a span carrying `gen_ai.*` attributes (the OpenTelemetry GenAI
  semantic conventions), OpenInference `openinference.span.kind = LLM`, or `llm.*` attributes;
- the prompt or messages (`gen_ai.prompt`, `gen_ai.input.messages`, `input.value`,
  `llm.prompts`, or the `gen_ai.*.message` events) as the transcript's `input`;
- the completion or choice (`gen_ai.completion`, `gen_ai.output.messages`, `output.value`,
  `llm.completions`, or the `gen_ai.choice` / `gen_ai.content.completion` events) as the graded
  artifact; a span with no output is counted and skipped, never fabricated;
- the span's attributes with dotted keys nested (`gen_ai.usage.output_tokens` becomes the path
  `gen_ai.usage.output_tokens` for a KPI pin), the resource attributes, `service`, `duration_ms`,
  `status.code`, `scope`, and the trace and span ids, as the structured record.

The preview shows `spans`, `llm_spans`, `cases` and `skipped_no_output` before anything is
written; approve commits the cases verbatim. Traces are unlabeled by construction: the KPI
floor and the judges decide, the review queue is where a person labels.

A typical first set of KPI contracts over a trace export:

| KPI | contract | params |
|---|---|---|
| latency budget | `kpi_threshold` | `field: duration_ms, op: <=, value: 2000` |
| output size | `kpi_threshold` | `field: gen_ai.usage.output_tokens, op: between, min: 20, max: 800` |
| call succeeded | `field_in_set` | `field: status.code, allowed: [OK]` |
| approved model | `field_in_set` | `field: gen_ai.request.model, allowed: [gpt-4.1, gpt-4.1-mini]` |

These run on every case at grade time, free, before the judges, and a breach blocks the case
with the numbers in the evidence.
