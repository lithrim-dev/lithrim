# Runbook — DOGFOOD-1: real cases → judge-set ladder → eval pack → CI/CD gate

> End-to-end on the current app: import real lithrim-backend cases, run them through a
> **judge-set ladder** (model-mix + roster size), freeze a **reusable eval pack**, and gate
> it with a **CI/CD pass/fail exit**. The cases are synthetic (Synthea, no PHI).
>
> **The live (`--in-process`) legs are PAID and USER-RUN.** Nothing here autostarts a
> service. Check health first; the `$0` smoke comes first.

---

## 0. What this proves

The generic eval platform works on real data, and the **premium eval-pack-SDK** surface
(`lithrim-bench-pack`, the open-bench CI/CD gate) is real and Mongo-free. The judge-set
ladder is the **honest composition contrast**: the same 5 cases, the same flag
assignments on every set, graded by different council compositions — report the Δ **as
measured**, never as a "Claude wins" narrative (the BYO-Claude legs carry
`confidence=None` by construction; disclose it).

---

## 1. Import the starter cases (idempotent, `$0`, offline)

```bash
python scripts/import_backend_cases.py            # reads ../lithrim-backend (read-only)
# → examples/imported_demo_{scribe,coding,scheduling}.jsonl  (5 cases, lint-exempt)
# → data/config/agents/imported_*.json             (5 in-process v2 agent seeds)
# Prints the taxonomy drop/rename report (expected: zero drops on the chosen 5).
```

The 5 starters (all synthetic): `scribe_diabetes_soap_clean_compliant` (approve) + its
`..._violation` twin (reject / HALLUCINATED_DETAIL); `coding_followup_99213_violation`
(reject / UPCODING_RISK); `gold_scheduling_clean_booking_comp` (approve); and
`council_v2_smoke_nka_clean` (approve — the NKA clean v1 monoculture false-flags
FABRICATED_ALLERGY; the high-value calibration anchor).

---

## 2. The judge-set ladder

`data/config/judge_sets/dogfood_v1.json` — five rungs. The **same** flag assignments are
applied to **every** set (gate ON for all), so `models`/`roles` are the only variables
(apples-to-apples, no withstands-gate-on/off confound):

| label | models | roles | Azure calls/case |
|---|---|---|---|
| `all_azure` | all Azure | full trio | 3 |
| `claude_risk` | risk_judge → BYO-Claude | full trio | 2 |
| `all_claude` | all three → BYO-Claude | full trio | **0** (the `$0`-API smoke) |
| `roster_2_risk_policy` | all Azure | risk + policy | 2 |
| `roster_3_full` | all Azure | full trio (explicit) | 3 |

> **Roster seam (documented):** a *single-judge* roster is intentionally absent. The
> frozen `_apply_consensus` requires `len(valid) >= 2` in full-council mode; a 1-judge
> roster returns `insufficient_valid_models` (a degenerate `needs_review`). True
> single-judge support is a consensus-policy decision, **not** a seam edit — out of scope.

---

## 3. Health checks first (NO autostart)

```bash
curl -s localhost:8002/health   # the live council (only needed for --live; in_process does not use it)
curl -s localhost:8787/health   # the BFF (only needed for the GET /v1/runs comparison in §6)
```

If a service is down, **stop and start it yourself** (or skip the step that needs it).
The `--in-process` path needs neither `:8002` nor `:8787` — it runs the v2 council in
this process. `:8787` is only for the run-history comparison in §6.

---

## 4. The `$0`-API smoke (do this first)

Either gate a hand-built/pre-frozen pack (fully offline):

```bash
python scripts/run_eval_pack.py --pack out/pack_all_azure.json     # exit 0 (pass) / 1 (fail)
```

…or run the `all_claude` set (BYO-Claude only → **0 Azure spend**; uses your local
`claude -p`, free but not instant):

```bash
python scripts/run_eval_pack.py --build --judge-set all_claude --in-process \
    --dump out/pack_all_claude.json
```

---

## 5. The paid ladder — 3 model-mix sets × 5 cases (USER-RUN, cost-gated)

Estimated spend: **~25 Azure judge calls total** (all_azure 15 + claude_risk 10 +
all_claude 0), temperature 0, ≤1024 tokens each — well under \$1. BYO-Claude legs are \$0.

```bash
# also exposed as the console script `lithrim-bench-pack` after `pip install -e .`
python scripts/run_eval_pack.py --build --judge-set all_azure   --in-process --dump out/pack_all_azure.json
python scripts/run_eval_pack.py --build --judge-set claude_risk --in-process --dump out/pack_claude_risk.json
python scripts/run_eval_pack.py --build --judge-set all_claude  --in-process --dump out/pack_all_claude.json

# optional: the roster-size rungs (all Azure)
python scripts/run_eval_pack.py --build --judge-set roster_2_risk_policy --in-process --dump out/pack_roster2.json
python scripts/run_eval_pack.py --build --judge-set roster_3_full        --in-process --dump out/pack_roster3.json
```

Each command prints `RELEASE GATE: PASS|FAIL` (reliability % vs the 96% threshold +
never-event count) and **exits 0 (pass) or 1 (fail)** — the CI/CD contract. The dumped
`out/pack_*.json` are the frozen, reusable, round-trippable artifacts.

**To land the runs in the BFF's run history** (for §6), add
`--collections-db <bff collections db>` so the in_process run blobs persist where
`GET /v1/runs` reads.

---

## 6. Compare in run history

```bash
curl -s localhost:8787/v1/runs | python3 -m json.tool   # newest-first; one blob per case×set
```

Each in_process case persists a distinct run blob (`pipeline_run_id`, carried on each
pack outcome). Compare the same case across sets to see the composition effect.

---

## 7. Re-gate a frozen pack in CI (the premium surface)

A pre-built pack gates offline with no engine and `$0`:

```bash
lithrim-bench-pack --pack out/pack_all_azure.json    # exit 0/1 for the CI step
# or: lithrim-bench-pack --pack out/pack_all_azure.json --threshold 100
```

The rule (mirrors `../lithrim-backend/examples/ci_cd_gate.py`):
`passed = reliability ≥ threshold AND never_events == 0`, where `never_events` are Tier-1
floor breaches (a Tier-1 fired-but-unexpected — e.g. FABRICATED_ALLERGY on the NKA clean
— or an expected Tier-1 missed).

---

## 8. Honest-Δ recording

Report the per-set verdicts/reliability/never-events **as measured**. A no-flip or a
BYO-Claude leg that doesn't "win" is a documented result, never a manufactured win — the
honesty IS the commercial moat. Disclose that BYO-Claude legs have `confidence=None` (no
logprobs), so the calibration axis is unavailable for those legs.
