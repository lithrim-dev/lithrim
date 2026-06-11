# `tests/fixtures/ws0/` — captured baselines

These JSON files are **captured PipelineResult baselines** read by the `$0` REPLAY
path (`scripts/run_ws0.py --baseline …` / `grade_replay`). The REPLAY tests
(`tests/test_ws0.py`) parse them directly and ground/score them — they do **not**
re-grade through any council, so the CE-PACK-6b-ROUTE reroute (the in-process grade
now always uses the authored path) does not affect them.

## CE-PACK-6b-ROUTE note (2026-06-12)

`baseline.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json` is the **historical
default-council verdict** (`ComplianceCouncil.build_prompt`, the legacy clinical
default path). Post-6b-ROUTE the live in-process grade for `ws0_default` runs through
the **authored path** (each judge at its full pack lens), so a fresh live/in-process
grade may differ from this recorded baseline. The baseline is **kept as-is** (a
historical reference, replay-only); it is **not** regenerated via a live/non-deterministic
run. The authored-path reference verdict is documented in
`docs/research/RUN_ws0_default_post2c_in_process_2026-06-11.md`.
