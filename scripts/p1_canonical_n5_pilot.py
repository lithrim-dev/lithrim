#!/usr/bin/env python3
"""N=5 dispersion pilot for paper_v1_n12_canonical (P1-CANONICAL-N5-PILOT).

Runs each of the 12 canonical-pack cases through ``lithrim-sdk`` →
``POST /v1/pipeline/evaluate`` on the local backend ``N_RUNS=5`` times
(60 calls total, ~$1.80 expected, $2.50 hard ceiling). Captures per-run
verdict / per-judge votes / finding-code emission, then computes per-case
dispersion (verdict_mode + judge-vote distribution + finding-code emission
frequency) so paper §5.4 can cite the temperature=0 dispersion at N=5.

Two mechanical decisions this script resolves at close-out:

- **S2 widening:** if ``WRONG_DOSAGE`` fires ≥1/5 for S2 → KEEP strict;
  if 0/5 → WIDEN (add MEDICATION_NOT_IN_TRANSCRIPT substitute for symmetry
  with M1). Reported in dispersion.md's S2 row.
- **S-P1-13 disposition:** the dispersion stats themselves are the input
  to the disposition; the REPORT writes the recommendation.

Measurement only — does NOT mutate the pack, the contract, or backend code.
Each call lands a ``pipeline_runs`` Mongo doc as a side-effect (expected
+60 docs).

Run:
    PYENV_VERSION=debuglithrim \\
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    LITHRIM_AGENT_ID=69e8eed80774d8129275bb4a \\
    pyenv exec python scripts/p1_canonical_n5_pilot.py

Smoke-test mode (single case × 1 run, ~$0.03, used for grader-shape sanity
before the full 60-call loop):

    P1_N5_SMOKE=1 pyenv exec python scripts/p1_canonical_n5_pilot.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from lithrim import Lithrim  # type: ignore
except ImportError:
    sys.stderr.write(
        "ERROR: lithrim SDK not importable. Either pip install lithrim-sdk or\n"
        "       PYTHONPATH=/Users/aregee/Workspace/github.com/lithrim-sdk\n"
    )
    sys.exit(2)

try:
    from pymongo import MongoClient  # type: ignore
except ImportError:
    sys.stderr.write(
        "ERROR: pymongo not importable. pip install pymongo or use the debuglithrim env.\n"
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.picklist import resolve_case_fixtures  # noqa: E402

SPEC_PATH = REPO_ROOT / "out" / "paper_v1_n12_canonical.spec.json"
OUT_DIR = REPO_ROOT / "out"
NDJSON_PATH = OUT_DIR / "p1_canonical_n5_pilot.ndjson"
DISPERSION_MD_PATH = OUT_DIR / "p1_canonical_n5_pilot.dispersion.md"

N_RUNS_DEFAULT = 5
SMOKE_MODE = os.environ.get("P1_N5_SMOKE", "").strip() in {"1", "true", "TRUE", "yes"}
SMOKE_PICK = os.environ.get("P1_N5_SMOKE_PICK", "S1").strip()  # which pick to smoke

# Blended Azure pricing across the v2 trio (gpt-4.1 + Mistral-Large-3 +
# Llama-4-Maverick). Per-call cost_tokens is aggregated across all 3 judges
# on the backend side, so this blend approximates the total $/run.
# Conservative blend (gpt-4.1-dominant); the user has confirmed the budget
# is not the constraint, so we keep the conservative estimate visible
# rather than fitting it to a target. REPORT §1 surfaces both this and
# the driver's empirical $0.03/call estimate ($1/$3 per 1M blend).
INPUT_COST_PER_1M = 1.5
OUTPUT_COST_PER_1M = 5.5

PER_CASE_COST_CEILING_USD = 0.30
# User confirmed cost is not the constraint (2026-05-28 mid-cycle). Raising
# the hard halt from $2.50 to $5.00 so a slightly-conservative blend doesn't
# halt the loop partway. WARN telemetry still fires at the per-case ceiling.
HARD_LEDGER_CEILING_USD = 5.00

# Content_filter retry policy (driver §3.4): retry ONCE then record error.
# Anything that looks like a Mistral RAI block triggers the single retry.
CONTENT_FILTER_MARKERS = ("content_filter", "ResponsibleAI", "responsible_ai")


def _estimate_cost(cost_tokens: dict[str, Any] | None) -> float:
    """Blend prompt/completion tokens into a $ estimate per pipeline_run."""
    if not cost_tokens:
        return 0.0
    prompt = int(cost_tokens.get("prompt") or 0)
    completion = int(cost_tokens.get("completion") or 0)
    return (prompt * INPUT_COST_PER_1M + completion * OUTPUT_COST_PER_1M) / 1_000_000.0


def _build_context(case: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    """Verbatim port of scripts/validate_canonical_12_via_sdk.py:_build_context.

    Coding cases carry a ``fhir_document_reference`` SOAP-note alongside the
    primary artifact; fold the SOAP text into context so the council sees
    the documentation of record.
    """
    context = case.get("transcript", "") or ""
    for extra in artifacts[1:]:
        if extra.get("type") != "fhir_document_reference":
            continue
        soap = extra.get("_soap_text")
        if not soap:
            try:
                doc = json.loads(extra.get("content") or "{}")
                soap = doc["content"][0]["attachment"]["data"]
            except (ValueError, KeyError, IndexError, TypeError):
                soap = None
        if soap:
            context = f"{context}\n\n--- CLINICAL NOTE (documentation of record) ---\n{soap}"
    return context


def _normalize_expected_verdict(expected: Any) -> tuple[str, ...]:
    if isinstance(expected, list):
        return tuple(expected)
    if expected is None:
        return ()
    return (expected,)


def _grade(case_spec: dict[str, Any], evaluate_payload: dict[str, Any]) -> dict[str, Any]:
    """Verbatim port of validate_canonical_12_via_sdk.py:_grade.

    Reads ``expected_compliance_verdict_list`` /
    ``expected_safety_flags_strict`` / ``expected_safety_flags_accepted_substitutes``
    / ``structural_catch_via`` from the per-case spec.json row (Path T contract).
    """
    verdict_map = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}
    actual_v_raw = evaluate_payload.get("verdict", "PASS")
    actual_v = verdict_map.get(actual_v_raw, "approve")
    expected_v_raw = (
        case_spec.get("expected_compliance_verdict_list")
        if case_spec.get("expected_compliance_verdict_list") is not None
        else case_spec.get("expected_compliance_verdict")
    )
    expected_v_set = _normalize_expected_verdict(expected_v_raw)
    verdict_match = actual_v in expected_v_set

    semantic_findings = (evaluate_payload.get("semantic") or {}).get("findings") or []
    actual_codes = {
        (f.get("code") or f.get("check_name"))
        for f in semantic_findings
        if (f.get("code") or f.get("check_name"))
    }

    structural = evaluate_payload.get("structural") or {}
    structural_findings = structural.get("findings") or []
    structural_status = (structural.get("status") or "").upper()
    structural_has_high = any(
        (f.get("severity") or "").upper() in {"HIGH", "BLOCK"}
        for f in structural_findings
    )
    structural_block_with_high = (
        structural_status == "BLOCK" and structural_has_high
    )

    strict_flags = case_spec.get("expected_safety_flags_strict")
    if strict_flags is None:
        strict_flags = case_spec.get("expected_safety_flags") or []
    accepted_substitutes = case_spec.get("expected_safety_flags_accepted_substitutes") or {}
    structural_catch_via = case_spec.get("structural_catch_via")

    flags_matched: list[str] = []
    flags_missed: list[str] = []
    flag_match_via: dict[str, str] = {}
    for code in strict_flags:
        if code in actual_codes:
            flags_matched.append(code)
            flag_match_via[code] = "strict"
            continue
        substitutes = set(accepted_substitutes.get(code) or [])
        hit_subs = substitutes & actual_codes
        if hit_subs:
            flags_matched.append(code)
            flag_match_via[code] = f"substitute:{sorted(hit_subs)[0]}"
            continue
        if (
            structural_catch_via == "structural_block_with_high_severity"
            and code.startswith("STRUCTURAL_")
            and structural_block_with_high
        ):
            flags_matched.append(code)
            flag_match_via[code] = "structural_block_with_high_severity"
            continue
        flags_missed.append(code)
    flags_match = not flags_missed

    expected_structural_v = case_spec.get("expected_structural_verdict") or "PASS"
    is_clean_artifact = case_spec.get("clean_negative") or expected_structural_v == "PASS"
    structural_over_fired = False
    if is_clean_artifact:
        for f in structural_findings:
            if (f.get("severity") or "").upper() in {"MEDIUM", "HIGH", "BLOCK"}:
                structural_over_fired = True
                break

    return {
        "verdict_match": verdict_match,
        "actual_verdict_raw": actual_v_raw,
        "actual_verdict": actual_v,
        "expected_verdict": list(expected_v_set),
        "flags_match": flags_match,
        "flags_matched": sorted(flags_matched),
        "flags_missed": sorted(flags_missed),
        "flag_match_via": flag_match_via,
        "actual_codes": sorted(c for c in actual_codes if c),
        "structural_over_fired": structural_over_fired,
        "structural_findings_count": len(structural_findings),
        "structural_finding_codes": [
            (f.get("check_name") or f.get("code")) for f in structural_findings
        ],
        "structural_block_with_high": structural_block_with_high,
        "all_three_pass": (
            verdict_match and flags_match and not structural_over_fired
        ),
    }


def _looks_like_content_filter(error_text: str | None) -> bool:
    if not error_text:
        return False
    lowered = error_text.lower()
    return any(m.lower() in lowered for m in CONTENT_FILTER_MARKERS)


def _evaluate_once(
    client: Lithrim,
    artifact: dict[str, Any],
    context: str,
    agent_id: str | None,
) -> tuple[dict[str, Any], str | None, float]:
    """One SDK call → (payload_dict, error_or_None, elapsed_s)."""
    t0 = time.time()
    try:
        result = client.evaluate(
            artifact=artifact["content"],
            artifact_type=artifact.get("type") or "clinical_note",
            context_kind="transcript",
            context=context,
            agent_id=agent_id,
        )
        return result.model_dump(mode="json"), None, time.time() - t0
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}", time.time() - t0


def _evaluate_with_retry(
    client: Lithrim,
    artifact: dict[str, Any],
    context: str,
    agent_id: str | None,
) -> tuple[dict[str, Any], str | None, float, bool]:
    """Driver §3.4: single retry on content_filter, otherwise no retry.

    Returns (payload, error, total_elapsed_s, content_filter_seen).
    ``content_filter_seen`` records whether the FIRST attempt tripped the
    Azure RAI filter, regardless of whether the retry recovered — paper §5.4
    needs the incidence count to be visible per S-P1-13 and §10.2 of
    REPORT_s_p1_14_triage.
    """
    payload, error, elapsed = _evaluate_once(client, artifact, context, agent_id)
    content_filter_seen = False
    if error and _looks_like_content_filter(error):
        content_filter_seen = True
        time.sleep(2.0)
        payload2, error2, elapsed2 = _evaluate_once(client, artifact, context, agent_id)
        return payload2, error2, elapsed + elapsed2, content_filter_seen
    # Some content_filter errors come back as a successful HTTP with a
    # `semantic_evaluation_error` finding in the semantic stage (per
    # REPORT_s_p1_14_triage §10.2). Detect that path too and treat as a
    # content_filter incidence (no retry — backend already retried internally).
    if not error and payload:
        sem = payload.get("semantic") or {}
        for f in sem.get("findings") or []:
            txt = json.dumps(f).lower()
            if "content_filter" in txt or "responsibleai" in txt:
                content_filter_seen = True
                break
    return payload, error, elapsed, content_filter_seen


# ---------------------------------------------------------------------------
# Dispersion computation
# ---------------------------------------------------------------------------


def _compute_dispersion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group rows by pick_label and compute per-case dispersion stats.

    Returns dict keyed by pick_label with:
      - verdict_mode (or "split:A|B" when no value > half)
      - verdict_frequency  (e.g. "5/5" or "3/5+2/5")
      - verdict_set
      - per_judge: {role -> {votes: Counter, confidence: {min,max,mean,n}}}
      - finding_codes_semantic: {code -> count/N}
      - finding_codes_structural: {code -> count/N}
      - cost_total_usd, cost_per_run_usd_mean, tokens_total, runs
      - content_filter_count
      - error_count
      - WRONG_DOSAGE_rate (only for S2; computed for all cases but only
        S2's row uses it for the decision column).
    """
    by_pick: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_pick[r["pick_label"]].append(r)

    out: dict[str, dict[str, Any]] = {}
    for pick_label, pick_rows in by_pick.items():
        n = len(pick_rows)
        verdicts = [r["graded"]["actual_verdict_raw"] for r in pick_rows]
        verdict_counter = Counter(verdicts)
        verdict_set = sorted(set(verdicts))
        # Mode (handle ties: when no value > n/2, report as split)
        top = verdict_counter.most_common()
        if top and top[0][1] > n // 2:
            verdict_mode = top[0][0]
            verdict_frequency = f"{top[0][1]}/{n}"
        elif top:
            # Tie or no-majority: report all tied-top values as split
            top_count = top[0][1]
            tied = [v for v, c in top if c == top_count]
            if len(tied) == 1:
                verdict_mode = tied[0]
                verdict_frequency = f"{top_count}/{n}"
            else:
                verdict_mode = "split:" + "|".join(sorted(tied))
                verdict_frequency = "+".join(f"{top_count}/{n}" for _ in tied)
        else:
            verdict_mode = "ERROR"
            verdict_frequency = "0/0"

        # Per-judge votes + confidence
        per_judge_votes: dict[str, Counter] = defaultdict(Counter)
        per_judge_conf: dict[str, list[float]] = defaultdict(list)
        per_judge_missing: dict[str, int] = defaultdict(int)
        seen_roles: set[str] = set()
        for r in pick_rows:
            judge_votes = (r.get("payload_summary") or {}).get("judge_votes") or []
            roles_this_run: set[str] = set()
            for jv in judge_votes:
                role = jv.get("judge_role") or jv.get("role") or "<unknown>"
                seen_roles.add(role)
                roles_this_run.add(role)
                vote = jv.get("vote") or "<missing>"
                per_judge_votes[role][vote] += 1
                # S-P1-17: Mistral confidence persists as 0.0 instead of None
                # for logprob-incapable models. Treat 0.0 from Mistral-Large-3
                # as None so confidence-mean isn't artificially pulled down.
                conf = jv.get("confidence")
                model = jv.get("model") or ""
                if (
                    isinstance(conf, (int, float))
                    and not (conf == 0.0 and "Mistral" in model)
                ):
                    per_judge_conf[role].append(float(conf))
            # Tally missing per-judge data per run
            for known_role in seen_roles:
                if known_role not in roles_this_run:
                    per_judge_missing[known_role] += 1

        per_judge: dict[str, Any] = {}
        for role in sorted(seen_roles):
            confs = per_judge_conf.get(role, [])
            per_judge[role] = {
                "votes": dict(per_judge_votes[role]),
                "confidence_min": (min(confs) if confs else None),
                "confidence_max": (max(confs) if confs else None),
                "confidence_mean": (statistics.mean(confs) if confs else None),
                "confidence_n": len(confs),
                "missing_runs": per_judge_missing.get(role, 0),
            }

        # Finding-code emission frequency (semantic + structural)
        sem_emit_counter: Counter = Counter()
        struct_emit_counter: Counter = Counter()
        wrong_dosage_fires = 0
        for r in pick_rows:
            actual = set(r["graded"].get("actual_codes") or [])
            if "WRONG_DOSAGE" in actual:
                wrong_dosage_fires += 1
            sem_emit_counter.update(actual)
            for c in r["graded"].get("structural_finding_codes") or []:
                if c is not None:
                    struct_emit_counter[c] += 1

        cost_total = sum((r.get("cost_estimate_usd") or 0.0) for r in pick_rows)
        tokens_total = sum(int((r.get("cost_tokens") or {}).get("total") or 0) for r in pick_rows)
        content_filter_count = sum(1 for r in pick_rows if r.get("content_filter"))
        error_count = sum(1 for r in pick_rows if r.get("error"))

        out[pick_label] = {
            "runs": n,
            "verdict_mode": verdict_mode,
            "verdict_frequency": verdict_frequency,
            "verdict_set": verdict_set,
            "per_judge": per_judge,
            "finding_codes_semantic": {
                c: f"{count}/{n}" for c, count in sem_emit_counter.most_common()
            },
            "finding_codes_structural": {
                c: f"{count}/{n}" for c, count in struct_emit_counter.most_common()
            },
            "wrong_dosage_fires": wrong_dosage_fires,  # k/n; S2 uses this directly
            "cost_total_usd": round(cost_total, 4),
            "cost_per_run_usd_mean": round(cost_total / n, 4) if n else 0.0,
            "tokens_total": tokens_total,
            "content_filter_count": content_filter_count,
            "error_count": error_count,
        }
    return out


def _format_dispersion_md(
    case_specs: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    dispersion: dict[str, dict[str, Any]],
    s2_decision: str,
    s2_wrong_dosage_fires: int,
    n_runs: int,
    total_cost: float,
    content_filter_count: int,
    elapsed_total_s: float,
) -> str:
    lines: list[str] = []
    lines.append(f"# Paper §5.4 dispersion table — `paper_v1_n12_canonical` × N={n_runs}")
    lines.append("")
    lines.append(f"- Run date: 2026-05-28")
    lines.append(f"- Backend: `localhost:8002`, `COMPLIANCE_COUNCIL_VERSION=v2`")
    lines.append(f"- Trio: `gpt-4.1` (risk_judge) / `Mistral-Large-3` (policy_judge) / `Llama-4-Maverick-17B-128E-Instruct-FP8` (faithfulness_judge)")
    lines.append(f"- Cases: 12 × N=5 = **{len(rows)} runs total**")
    lines.append(f"- Wall-clock: ~{elapsed_total_s / 60.0:.1f} min")
    lines.append(f"- Total cost (blended est, $1.5/$5.5 per 1M tokens): **${total_cost:.4f}**")
    lines.append(f"- Mistral content_filter incidence: **{content_filter_count}/{len(rows)}**")
    lines.append("")
    lines.append(f"**S2 widening decision (mechanical):** `WRONG_DOSAGE` fired **{s2_wrong_dosage_fires}/{n_runs}** → **{s2_decision}**")
    lines.append("")
    lines.append("## Per-case dispersion")
    lines.append("")
    lines.append(
        "| pick | verdict_mode | freq | verdict_set | risk_judge votes | policy_judge votes | faithfulness_judge votes | sem findings (k/N) | struct findings (k/N) | cost $ | notes |"
    )
    lines.append(
        "|------|--------------|------|-------------|------------------|---------------------|---------------------------|----------------------|------------------------|--------|-------|"
    )
    for spec in case_specs:
        pick_label = spec["paper_pick_label"]
        d = dispersion.get(pick_label)
        if not d:
            lines.append(f"| {pick_label} | (no rows) | — | — | — | — | — | — | — | — | — |")
            continue
        pj = d.get("per_judge") or {}

        def _judge_cell(role: str) -> str:
            info = pj.get(role)
            if not info:
                return "—"
            votes = info["votes"]
            votes_str = " / ".join(
                f"{c}×{v}" for v, c in sorted(votes.items(), key=lambda x: -x[1])
            ) or "—"
            cmin = info.get("confidence_min")
            cmax = info.get("confidence_max")
            cmean = info.get("confidence_mean")
            cn = info.get("confidence_n")
            if cn:
                conf_str = f" (conf {cmin:.2f}/{cmean:.2f}/{cmax:.2f} n={cn})"
            else:
                conf_str = " (conf n=0)"
            miss = info.get("missing_runs") or 0
            miss_str = f" MISSING={miss}" if miss else ""
            return f"{votes_str}{conf_str}{miss_str}"

        sem_cell = ", ".join(
            f"{c}:{freq}" for c, freq in d["finding_codes_semantic"].items()
        ) or "—"
        struct_cell = ", ".join(
            f"{c}:{freq}" for c, freq in d["finding_codes_structural"].items()
        ) or "—"
        notes = []
        if pick_label == "S2":
            notes.append(
                f"**WRONG_DOSAGE: {d['wrong_dosage_fires']}/{d['runs']} → {s2_decision}**"
            )
        if d["content_filter_count"]:
            notes.append(f"content_filter={d['content_filter_count']}/{d['runs']}")
        if d["error_count"]:
            notes.append(f"errors={d['error_count']}/{d['runs']}")

        lines.append(
            f"| {pick_label} | {d['verdict_mode']} | {d['verdict_frequency']} | "
            f"{','.join(d['verdict_set'])} | {_judge_cell('risk_judge')} | "
            f"{_judge_cell('policy_judge')} | {_judge_cell('faithfulness_judge')} | "
            f"{sem_cell} | {struct_cell} | "
            f"{d['cost_total_usd']:.4f} | {' / '.join(notes) or '—'} |"
        )

    # Cost summary footer
    lines.append("")
    lines.append("## Cost summary")
    lines.append("")
    lines.append("| pick | runs | cost $ | $/run mean | tokens total |")
    lines.append("|------|------|--------|-----------|--------------|")
    for spec in case_specs:
        pick_label = spec["paper_pick_label"]
        d = dispersion.get(pick_label)
        if not d:
            continue
        lines.append(
            f"| {pick_label} | {d['runs']} | {d['cost_total_usd']:.4f} | "
            f"{d['cost_per_run_usd_mean']:.4f} | {d['tokens_total']} |"
        )
    lines.append(
        f"| **TOTAL** | **{len(rows)}** | **{total_cost:.4f}** | "
        f"**{(total_cost / len(rows)) if rows else 0.0:.4f}** | "
        f"**{sum(d['tokens_total'] for d in dispersion.values())}** |"
    )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _preflight_pack_exists(pack_id: str) -> None:
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGO_DB", "velto")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    try:
        doc = client[db_name]["eval_pack"].find_one({"pack_id": pack_id})
    except Exception as exc:
        sys.stderr.write(f"ERROR: mongo connection failed: {exc}\n")
        sys.exit(2)
    if not doc:
        sys.stderr.write(
            f"ERROR: pack {pack_id!r} not found in {db_name}.eval_pack.\n"
            f"       bench-side spec.json: {SPEC_PATH}\n"
            f"       Run scripts/build_paper_v1_n12_canonical_pack.py first.\n"
        )
        sys.exit(2)
    print(f"pre-flight: pack_id={pack_id} _id={doc['_id']} case_ids={len(doc.get('case_ids', []))}")


def main() -> int:
    started_at = datetime.now(timezone.utc)

    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None
    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set.\n")
        return 2

    if not SPEC_PATH.exists():
        sys.stderr.write(f"ERROR: spec.json not at {SPEC_PATH}\n")
        return 2
    spec = json.loads(SPEC_PATH.read_text())
    case_specs: list[dict[str, Any]] = spec["cases"]
    pack_id = spec["pack_id"]

    _preflight_pack_exists(pack_id)

    case_ids = {c["case_id"] for c in case_specs}
    fixtures = resolve_case_fixtures(case_ids)
    missing = case_ids - fixtures.keys()
    if missing:
        sys.stderr.write(
            f"ERROR: {len(missing)} spec cases unresolved in bench fixtures: {sorted(missing)}\n"
        )
        return 2

    # Smoke mode: single pick × 1 run
    if SMOKE_MODE:
        case_specs = [c for c in case_specs if c["paper_pick_label"] == SMOKE_PICK]
        if not case_specs:
            sys.stderr.write(f"ERROR: smoke pick {SMOKE_PICK!r} not in spec.\n")
            return 2
        n_runs = 1
        print(f"SMOKE MODE: pick={SMOKE_PICK} N_RUNS=1 (~$0.03 / ~25s)")
    else:
        n_runs = N_RUNS_DEFAULT

    print(
        f"P1-CANONICAL-N5-PILOT: {len(case_specs)} cases × N={n_runs} = "
        f"{len(case_specs) * n_runs} calls"
    )
    print(f"  backend: {base_url}  agent_id: {agent_id or '<none>'}")
    print(f"  hard ledger ceiling: ${HARD_LEDGER_CEILING_USD:.2f}  "
          f"per-case WARN above: ${PER_CASE_COST_CEILING_USD:.2f}")
    print()

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=180.0)

    OUT_DIR.mkdir(exist_ok=True)
    ndjson_path = NDJSON_PATH if not SMOKE_MODE else OUT_DIR / "p1_canonical_n5_pilot.smoke.ndjson"

    rows: list[dict[str, Any]] = []
    ledger_usd = 0.0
    per_case_cost: dict[str, float] = defaultdict(float)
    halted_for_budget = False

    for case_spec in case_specs:
        pick_label = case_spec["paper_pick_label"]
        case_id = case_spec["case_id"]
        case = fixtures[case_id]
        artifacts = case.get("artifacts") or []
        if not artifacts:
            print(f"  {pick_label}: SKIP — case has no artifacts")
            continue
        artifact = artifacts[0]
        context = _build_context(case, artifacts)

        for run_idx in range(n_runs):
            if ledger_usd > HARD_LEDGER_CEILING_USD:
                halted_for_budget = True
                print(
                    f"  HALT: ledger ${ledger_usd:.4f} crossed hard ceiling "
                    f"${HARD_LEDGER_CEILING_USD:.2f}. Stopping loop."
                )
                break

            payload, error, elapsed, content_filter = _evaluate_with_retry(
                client, artifact, context, agent_id
            )

            # Grade what we got (even on partial payloads).
            if payload:
                graded = _grade(case_spec, payload)
            else:
                graded = {
                    "verdict_match": False,
                    "actual_verdict_raw": "ERROR",
                    "actual_verdict": "ERROR",
                    "expected_verdict": case_spec.get("expected_compliance_verdict_list")
                    or [case_spec.get("expected_compliance_verdict")],
                    "flags_match": False,
                    "flags_matched": [],
                    "flags_missed": case_spec.get("expected_safety_flags_strict") or [],
                    "flag_match_via": {},
                    "actual_codes": [],
                    "structural_over_fired": False,
                    "structural_findings_count": 0,
                    "structural_finding_codes": [],
                    "structural_block_with_high": False,
                    "all_three_pass": False,
                }

            cost_tokens = (payload.get("provenance") or {}).get("cost_tokens") or {}
            cost_estimate = _estimate_cost(cost_tokens)
            ledger_usd += cost_estimate
            per_case_cost[pick_label] += cost_estimate

            # Compact judge_votes snapshot for dispersion compute (full payload
            # would bloat the NDJSON; we keep the dispersion-relevant fields).
            judge_votes_summary: list[dict[str, Any]] = []
            for jv in ((payload.get("semantic") or {}).get("judge_votes") or []):
                judge_votes_summary.append({
                    "judge_role": jv.get("judge_role"),
                    "vote": jv.get("vote"),
                    "confidence": jv.get("confidence"),
                    "model": jv.get("model"),
                    "findings": jv.get("findings") or [],
                })

            row = {
                "pick_label": pick_label,
                "run_idx": run_idx,
                "case_id": case_id,
                "promotion_disposition": case_spec.get("promotion_disposition"),
                "expected_compliance_verdict_list": case_spec.get(
                    "expected_compliance_verdict_list"
                ),
                "expected_safety_flags_strict": case_spec.get(
                    "expected_safety_flags_strict"
                ),
                "expected_safety_flags_accepted_substitutes": case_spec.get(
                    "expected_safety_flags_accepted_substitutes"
                ),
                "structural_catch_via": case_spec.get("structural_catch_via"),
                "artifact_type": artifact.get("type") or "clinical_note",
                "elapsed_s": round(elapsed, 2),
                "error": error,
                "content_filter": content_filter,
                "graded": graded,
                "payload_summary": {
                    "verdict": payload.get("verdict"),
                    "gate_decision": payload.get("gate_decision"),
                    "judge_votes": judge_votes_summary,
                    "semantic_status": (payload.get("semantic") or {}).get("status"),
                    "structural_status": (payload.get("structural") or {}).get("status"),
                },
                "cost_tokens": cost_tokens,
                "cost_estimate_usd": round(cost_estimate, 6),
                "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
            }
            rows.append(row)

            cf_glyph = " CF" if content_filter else ""
            print(
                f"  {pick_label}[{run_idx}] v={graded['actual_verdict_raw']:>5} "
                f"flags={len(graded['flags_matched'])}/{len(graded['flags_matched']) + len(graded['flags_missed'])}  "
                f"struct={graded['structural_findings_count']}  "
                f"{elapsed:.1f}s  ${cost_estimate:.4f}  "
                f"ledger=${ledger_usd:.4f}{cf_glyph}"
                + (f"  ERROR: {error}" if error else "")
            )

        # Per-case WARN once the 5th run lands (driver §3.7 risk 3)
        if per_case_cost[pick_label] > PER_CASE_COST_CEILING_USD:
            print(
                f"  WARN: case={pick_label} cost=${per_case_cost[pick_label]:.4f} "
                f"exceeds per-case ceiling ${PER_CASE_COST_CEILING_USD:.2f}"
            )

        if halted_for_budget:
            break

    ended_at = datetime.now(timezone.utc)
    elapsed_total_s = (ended_at - started_at).total_seconds()

    # Flush NDJSON
    with ndjson_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nNDJSON: {ndjson_path}  ({len(rows)} rows)")

    if SMOKE_MODE:
        # Smoke validation: parse the row back + run dispersion compute on it.
        sanity_rows = [json.loads(line) for line in ndjson_path.open()]
        sanity_disp = _compute_dispersion(sanity_rows)
        print(f"\nSMOKE OK: NDJSON re-parses; dispersion compute returned "
              f"{len(sanity_disp)} pick(s).")
        print(f"  ledger=${ledger_usd:.4f}  elapsed={elapsed_total_s:.1f}s")
        for k, v in sanity_disp.items():
            print(
                f"  {k}: verdict_mode={v['verdict_mode']} "
                f"sem_codes={list(v['finding_codes_semantic'].keys())[:3]} "
                f"cost=${v['cost_total_usd']:.4f}"
            )
        return 0

    # Full run: compute dispersion + write .md + return summary
    dispersion = _compute_dispersion(rows)
    s2 = dispersion.get("S2") or {}
    s2_wrong_dosage_fires = int(s2.get("wrong_dosage_fires", 0)) if s2 else 0
    s2_runs = int(s2.get("runs", 0)) if s2 else 0
    if s2_runs == 0:
        s2_decision = "INDETERMINATE (no S2 runs)"
    elif s2.get("error_count", 0) >= s2_runs:
        s2_decision = "INDETERMINATE (all-error)"
    elif s2_wrong_dosage_fires >= 1:
        s2_decision = "KEEP STRICT"
    else:
        s2_decision = "WIDEN"

    total_cost = sum((d.get("cost_total_usd") or 0.0) for d in dispersion.values())
    content_filter_total = sum((d.get("content_filter_count") or 0) for d in dispersion.values())

    md = _format_dispersion_md(
        case_specs=spec["cases"],
        rows=rows,
        dispersion=dispersion,
        s2_decision=s2_decision,
        s2_wrong_dosage_fires=s2_wrong_dosage_fires,
        n_runs=n_runs,
        total_cost=total_cost,
        content_filter_count=content_filter_total,
        elapsed_total_s=elapsed_total_s,
    )
    DISPERSION_MD_PATH.write_text(md)
    print(f"\nDispersion MD: {DISPERSION_MD_PATH}")

    # Summary
    print("\n=== SUMMARY ===")
    print(f"  rows                  : {len(rows)}/{12 * n_runs}")
    print(f"  total cost (est)      : ${total_cost:.4f}")
    print(f"  wall-clock            : {elapsed_total_s / 60.0:.1f} min")
    print(f"  content_filter total  : {content_filter_total}")
    print(f"  S2 WRONG_DOSAGE fires : {s2_wrong_dosage_fires}/{s2_runs}  → {s2_decision}")
    if halted_for_budget:
        print(f"  HALTED: ledger crossed ${HARD_LEDGER_CEILING_USD:.2f}")
    if content_filter_total > 5:
        print(f"  WARN: content_filter total {content_filter_total} > 5 — "
              f"escalate per A5 + S-P1-13 pattern audit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
