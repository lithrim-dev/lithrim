#!/usr/bin/env python3
"""S-P1-14 reverification — re-run C1 + C2 after NKA-exception patch.

Targeted reverification of the two clean-negative cases that regressed
in P1-VALIDATE-12. The lithrim-backend patch at commit ``e8147d8``
propagated the NKA paragraph from ``faithfulness_judge.txt`` into
``risk_judge.txt`` (where the NEGATION_REVERSAL coaching lives) and
``policy_judge.txt`` (defensive parity).

Expected outcomes per ``docs/research/REPORT_s_p1_14_triage_2026-05-28.md``
§4 + §6:

- **C2** (clean HL7 NKA): gpt-4.1 (risk_judge) previously fired
  NEGATION_REVERSAL → BLOCK. After patch the risk_judge sees the NKA
  exception both at the top of its role prompt AND inline at the
  NEGATION_REVERSAL coaching site, so it should NOT fire NEGATION_REVERSAL.
  Expected on-backend verdict: ``approve`` or ``needs_review`` (matching
  offline bench's ``needs_review`` FP).
- **C1** (clean scribe): Mistral (policy_judge) previously fired
  FABRICATED_CONSENT + INCOMPLETE_DOCUMENTATION → BLOCK. The NKA patch
  is NOT expected to close this — the FABRICATED_CONSENT firing comes
  from ``compliance_council.py:build_prompt`` lines 564-579 (the
  Saucedo v. Sharp consent rule), not from policy_judge.txt. C1 is
  expected to stay at BLOCK. The P1-CONSENT-RULE-AUDIT cycle is the
  next move for C1.

This script does NOT modify state — it only emits per-case verdict +
judge-vote records into ``out/s_p1_14_c1c2_rerun.{ndjson,md}`` for the
S-P1-14 partial-close report.

Run:
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    LITHRIM_AGENT_ID=69e8eed80774d8129275bb4a \\
    PYENV_VERSION=debuglithrim pyenv exec python \\
    scripts/s_p1_14_rerun_c1c2_after_nka_patch.py
"""

from __future__ import annotations

import json
import os
import sys
import time
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


REPO_ROOT = Path(__file__).resolve().parents[1]
PICKLIST_PATH = Path("/tmp/pilot_picklist.json")
OUT_DIR = REPO_ROOT / "out"
RESULTS_NDJSON = OUT_DIR / "s_p1_14_c1c2_rerun.ndjson"
RESULTS_REPORT = OUT_DIR / "s_p1_14_c1c2_rerun.md"
PRIOR_RUN_NDJSON = OUT_DIR / "canonical_12_sdk_validation.ndjson"

# Per-pack fixture resolution — mirrored from scripts/validate_canonical_12_via_sdk.py.
PACK_FILES: dict[str, list[Path]] = {
    "scribe_v1": [
        REPO_ROOT / "out" / "scribe_v1.n10.jsonl",
        REPO_ROOT / "out" / "scribe_v1.jsonl",
    ],
    "scheduling_v1": [
        REPO_ROOT / "out" / "scheduling_v1.n10.jsonl",
        REPO_ROOT / "out" / "scheduling_v1.jsonl",
    ],
    "coding_v1": [REPO_ROOT / "out" / "coding_v1.jsonl"],
    "triage_v1": [
        REPO_ROOT / "out" / "triage_v1.n10.jsonl",
        REPO_ROOT / "out" / "triage_v1.jsonl",
    ],
    "hl7_adt_v1": [REPO_ROOT / "out" / "hl7_adt_v1.jsonl"],
}


def _resolve_case(pack_name: str, case_id: str) -> dict[str, Any] | None:
    for fp in PACK_FILES[pack_name]:
        if not fp.exists():
            continue
        for line in fp.open():
            row = json.loads(line)
            if (row.get("case_id") or row.get("id")) == case_id:
                return row
    return None


def _build_context(case: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    """Verbatim port of harness _build_context for byte-identical context."""
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


def _summarize_judge_vote(jv: Any) -> dict[str, Any]:
    """Extract the minimal judge-vote shape we need for delta comparison."""
    return {
        "judge_role": getattr(jv, "judge_role", None),
        "vote": getattr(jv, "vote", None),
        "confidence": getattr(jv, "confidence", None),
        "model": getattr(jv, "model", None),
        "findings_codes": sorted(
            {
                (getattr(f, "code", None) or getattr(f, "check_name", None))
                for f in (getattr(jv, "findings", None) or [])
                if (getattr(f, "code", None) or getattr(f, "check_name", None))
            }
        ),
    }


def _load_prior_run() -> dict[str, dict[str, Any]]:
    """Index the prior NDJSON run by pick_label → row for delta comparison."""
    if not PRIOR_RUN_NDJSON.exists():
        return {}
    return {
        json.loads(line)["pick_label"]: json.loads(line)
        for line in PRIOR_RUN_NDJSON.open()
        if line.strip()
    }


def _grade_delta(pick_label: str, prior: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Per-case delta — what changed from VALIDATE-12 to this rerun."""
    return {
        "verdict_before": prior.get("actual_verdict_raw") if prior else None,
        "verdict_after": current.get("verdict"),
        "verdict_lifted": (
            prior is not None
            and prior.get("actual_verdict_raw") == "BLOCK"
            and current.get("verdict") in {"PASS", "WARN"}
        ),
        "judge_votes_changed": _diff_judge_votes(
            prior.get("judge_votes_summary") if prior else None,
            current.get("judge_votes_summary"),
        ),
    }


def _diff_judge_votes(
    before: list[dict[str, Any]] | None, after: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Per-judge before/after diff. Returns rows for any judge whose vote
    or finding-codes changed."""
    if not (before and after):
        return []
    by_role_before = {v.get("judge_role"): v for v in before}
    by_role_after = {v.get("judge_role"): v for v in after}
    changed: list[dict[str, Any]] = []
    for role in sorted(set(by_role_before) | set(by_role_after)):
        b = by_role_before.get(role) or {}
        a = by_role_after.get(role) or {}
        if b.get("vote") != a.get("vote") or b.get("findings_codes") != a.get("findings_codes"):
            changed.append(
                {
                    "judge_role": role,
                    "vote_before": b.get("vote"),
                    "vote_after": a.get("vote"),
                    "findings_before": b.get("findings_codes") or [],
                    "findings_after": a.get("findings_codes") or [],
                }
            )
    return changed


def main() -> int:
    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None
    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set\n")
        return 2

    if not PICKLIST_PATH.exists():
        sys.stderr.write(f"ERROR: {PICKLIST_PATH} not found\n")
        return 2

    picks = [
        p for p in json.loads(PICKLIST_PATH.read_text())
        if p["pick_label"] in {"C1", "C2"}
    ]
    if len(picks) != 2:
        sys.stderr.write(f"ERROR: expected 2 picks (C1, C2); got {len(picks)}\n")
        return 2

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=120.0)
    prior_runs = _load_prior_run()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for pick in picks:
        case = _resolve_case(pick["pack"], pick["case_id"])
        if case is None:
            rows.append({"pick_label": pick["pick_label"], "error": "case fixture not found"})
            continue
        artifacts = case.get("artifacts") or []
        if not artifacts:
            rows.append({"pick_label": pick["pick_label"], "error": "no artifacts in case fixture"})
            continue
        primary = artifacts[0]
        context = _build_context(case, artifacts)

        t0 = time.monotonic()
        try:
            result = client.evaluate(
                artifact=primary.get("content"),
                artifact_type=primary.get("type", "clinical_note"),
                context_kind="transcript",
                context=context,
                agent_id=agent_id,
            )
            elapsed = time.monotonic() - t0
            verdict = result.verdict
            sem = result.semantic
            judge_votes = [_summarize_judge_vote(jv) for jv in (sem.judge_votes or [])]
            error = None
        except Exception as exc:  # broad on purpose — we want raw signal not bubbling up
            elapsed = time.monotonic() - t0
            verdict = None
            judge_votes = []
            error = f"{type(exc).__name__}: {exc}"
            result = None

        current = {
            "pick_label": pick["pick_label"],
            "case_id": pick["case_id"],
            "pack": pick["pack"],
            "expected_compliance_verdict": pick.get("expected_compliance_verdict"),
            "verdict": verdict,
            "judge_votes_summary": judge_votes,
            "elapsed_s": round(elapsed, 2),
            "pipeline_run_id": getattr(result, "pipeline_run_id", None) if result else None,
            "error": error,
        }
        prior = prior_runs.get(pick["pick_label"])
        delta = _grade_delta(pick["pick_label"], prior, current)
        current["delta"] = delta
        rows.append(current)

        # Per-case console echo so the user sees signal in real time.
        if error:
            print(f"  {pick['pick_label']}  ERROR  {error}", flush=True)
        else:
            roles = ", ".join(
                f"{v.get('judge_role')}={v.get('vote')}"
                for v in judge_votes
                if v.get("judge_role")
            )
            print(
                f"  {pick['pick_label']}  verdict={verdict}  judges={{ {roles} }}  "
                f"changes_vs_prior={len(delta['judge_votes_changed'])}  "
                f"({current['elapsed_s']}s)",
                flush=True,
            )

    # NDJSON output
    with RESULTS_NDJSON.open("w") as fp:
        for row in rows:
            fp.write(json.dumps(row) + "\n")

    # Markdown delta report
    md_lines: list[str] = []
    md_lines.append("# S-P1-14 reverification — C1 + C2 after NKA propagation patch\n")
    md_lines.append(f"Backend patch: lithrim-backend `e8147d8` "
                    "(`feat(council-roles): propagate NKA exception to risk_judge + policy_judge`)\n")
    md_lines.append("\n## Per-case delta\n\n")
    md_lines.append("| pick | verdict before → after | verdict_lifted? | judges that changed | findings before → after |\n")
    md_lines.append("|---|---|---|---|---|\n")
    for row in rows:
        if row.get("error"):
            md_lines.append(
                f"| **{row['pick_label']}** | ERROR | — | — | {row['error']} |\n"
            )
            continue
        d = row.get("delta", {})
        before_v = d.get("verdict_before") or "?"
        after_v = d.get("verdict_after") or "?"
        lifted = "✓" if d.get("verdict_lifted") else "✗"
        changes = d.get("judge_votes_changed") or []
        if changes:
            judge_summary = "; ".join(
                f"**{c['judge_role']}** {c.get('vote_before')}→{c.get('vote_after')}"
                for c in changes
            )
            findings_summary = "; ".join(
                f"**{c['judge_role']}** [{', '.join(c.get('findings_before') or []) or '-'}] → [{', '.join(c.get('findings_after') or []) or '-'}]"
                for c in changes
            )
        else:
            judge_summary = "(no changes)"
            findings_summary = "(no changes)"
        md_lines.append(
            f"| **{row['pick_label']}** | {before_v} → {after_v} | {lifted} "
            f"| {judge_summary} | {findings_summary} |\n"
        )

    md_lines.append("\n## Raw judge votes after patch\n")
    for row in rows:
        if row.get("error"):
            continue
        md_lines.append(f"\n### {row['pick_label']} (`{row['case_id']}`)\n")
        md_lines.append(f"- Expected: `{row['expected_compliance_verdict']}`\n")
        md_lines.append(f"- Actual: `{row['verdict']}`\n")
        md_lines.append(f"- pipeline_run_id: `{row['pipeline_run_id']}`\n")
        md_lines.append("- Judge votes:\n")
        for jv in row.get("judge_votes_summary") or []:
            md_lines.append(
                f"  - `{jv.get('judge_role')}` ({jv.get('model')}): "
                f"`{jv.get('vote')}` conf={jv.get('confidence')} "
                f"codes={jv.get('findings_codes')}\n"
            )

    RESULTS_REPORT.write_text("".join(md_lines))
    print(f"\nWrote: {RESULTS_NDJSON}", flush=True)
    print(f"Wrote: {RESULTS_REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
