#!/usr/bin/env python3
"""Validate the P1-FHIR-CONFORMANCE-MINI 3-case pack via lithrim-sdk -> backend.

Port of ``scripts/validate_canonical_12_via_sdk.py`` (verbatim grading logic;
divergence at PICKLIST_PATH + output paths only). MINI scope: 3 cases on the
``fhir_patient`` artifact_type, against live etlp-mapper mapping 41
(``fhir-patient-validator-strict``, pinned to US Core 7.0.0 STU7
``us-core-patient``).

Pre-flight assumptions (verified at session start, see plan-review):

  - Backend up at LITHRIM_BASE_URL (default http://localhost:8002)
  - etlp-mapper up at :3031 with mapping 41 reachable
  - Backend env has ``COMPLIANCE_COUNCIL_VERSION=v2``
  - ``velto.artifact_profiles`` has the active ``fhir_patient`` profile
    pointing at ``etlp_mapping_id=41``

Run:
    PYENV_VERSION=debuglithrim \\
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    LITHRIM_AGENT_ID=<your_agent_id> \\
    pyenv exec python scripts/validate_fhir_mini_via_sdk.py

Outputs:
    out/fhir_mini_harness_results.ndjson  — per-case raw + graded payload
    out/fhir_mini_harness_results.md      — table for the REPORT

No mutations to artifact_profile / eval_pack / eval_case Mongo state. The
``evaluate`` call lands a ``pipeline_runs`` record per case (side-effect of
the agent-id binding).
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.picklist import resolve_case_fixtures as _resolve_case_fixtures  # noqa: E402

PICKLIST_PATH = REPO_ROOT / "data" / "picklist_fhir_mini.json"
OUT_DIR = REPO_ROOT / "out"
RESULTS_NDJSON = OUT_DIR / "fhir_mini_harness_results.ndjson"
RESULTS_REPORT = OUT_DIR / "fhir_mini_harness_results.md"


def _normalize_expected_verdict(expected: Any) -> tuple[str, ...]:
    if isinstance(expected, list):
        return tuple(expected)
    return (expected,)


def _build_context(case: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    """MINI scope: single Patient artifact + transcript only. No SOAP fold-in.

    Kept structurally similar to canonical-12 harness so a FULL cycle that
    introduces a second artifact (e.g. an Encounter alongside a Patient) can
    fold in extra context the same way the scribe harness does.
    """
    return case.get("transcript", "") or ""


def _grade(pick: dict[str, Any], evaluate_payload: dict[str, Any]) -> dict[str, Any]:
    """Verbatim port of validate_canonical_12_via_sdk._grade.

    Three gates:
      - VERDICT match
      - FLAGS match (with Path T strict + accepted_substitutes + structural_catch_via)
      - STRUCTURAL no-false-fire on clean / structural=PASS cases
    """
    verdict_map = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}
    actual_v_raw = evaluate_payload.get("verdict", "PASS")
    actual_v = verdict_map.get(actual_v_raw, "approve")
    expected_v_raw = (
        pick.get("expected_compliance_verdict_list")
        if pick.get("expected_compliance_verdict_list") is not None
        else pick.get("expected_compliance_verdict")
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

    strict_flags = pick.get("expected_safety_flags_strict")
    if strict_flags is None:
        strict_flags = pick.get("expected_safety_flags") or []
    accepted_substitutes = pick.get("expected_safety_flags_accepted_substitutes") or {}
    structural_catch_via = pick.get("structural_catch_via")

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

    expected_structural_v = pick.get("expected_structural_verdict") or "PASS"
    is_clean_artifact = pick.get("clean_negative") or expected_structural_v == "PASS"
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
        "structural_status": structural_status,
        "structural_block_with_high": structural_block_with_high,
        "all_three_pass": (
            verdict_match
            and flags_match
            and not structural_over_fired
        ),
    }


def main() -> int:
    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None

    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set.\n")
        return 2
    if not PICKLIST_PATH.exists():
        sys.stderr.write(f"ERROR: picklist not at {PICKLIST_PATH}\n")
        return 2

    picklist = json.loads(PICKLIST_PATH.read_text())
    case_ids = {p["case_id"] for p in picklist}
    fixtures = _resolve_case_fixtures(case_ids)
    missing = case_ids - fixtures.keys()
    if missing:
        sys.stderr.write(f"ERROR: {len(missing)} picklist cases unresolved: {missing}\n")
        return 2

    print(
        f"Validating {len(picklist)} FHIR Patient MINI cases against {base_url} "
        f"(agent_id={agent_id or '<none>'})"
    )
    print("Pre-flight: COMPLIANCE_COUNCIL_VERSION should be 'v2' in backend env.")
    print("Validator under test: etlp-mapper mapping 41 (fhir-patient-validator-strict)")
    print()

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=120.0)

    rows: list[dict[str, Any]] = []
    for pick in picklist:
        pick_label = pick["pick_label"]
        case = fixtures[pick["case_id"]]
        artifacts = case.get("artifacts") or []
        if not artifacts:
            print(f"  {pick_label}: SKIP — case has no artifacts")
            continue
        artifact = artifacts[0]
        artifact_type = artifact.get("type") or "fhir_patient"

        t0 = time.time()
        try:
            result = client.evaluate(
                artifact=artifact["content"],
                artifact_type=artifact_type,
                context_kind="transcript",
                context=_build_context(case, artifacts),
                agent_id=agent_id,
            )
            payload = result.model_dump(mode="json")
            error = None
        except Exception as exc:
            payload = {}
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - t0

        graded = _grade(pick, payload) if not error else {
            "verdict_match": False, "flags_match": False, "structural_over_fired": False,
            "all_three_pass": False, "actual_verdict": "ERROR", "actual_verdict_raw": "ERROR",
            "expected_verdict": pick.get("expected_compliance_verdict_list")
                or pick.get("expected_compliance_verdict"),
            "flags_matched": [], "flags_missed": pick.get("expected_safety_flags_strict")
                or pick.get("expected_safety_flags") or [],
            "actual_codes": [], "structural_findings_count": 0, "structural_finding_codes": [],
            "structural_status": "", "structural_block_with_high": False, "flag_match_via": {},
        }

        verdict_glyph = "✓" if graded["verdict_match"] else "✗"
        flags_glyph = "✓" if graded["flags_match"] else "✗"
        struct_glyph = "✓" if not graded["structural_over_fired"] else "✗"
        overall_glyph = "PASS" if graded["all_three_pass"] else "FAIL"

        print(
            f"  {pick_label:>26}  v={verdict_glyph}({graded['actual_verdict_raw']}->"
            f"{graded['actual_verdict']} ∈ {graded['expected_verdict']})  "
            f"flags={flags_glyph}({len(graded['flags_matched'])}/"
            f"{len(graded['flags_matched']) + len(graded['flags_missed'])})  "
            f"struct={struct_glyph}({graded['structural_findings_count']} findings, "
            f"status={graded['structural_status']})  "
            f"{overall_glyph}  ({elapsed:.1f}s)"
            + (f"  ERROR: {error}" if error else "")
        )

        rows.append({
            "pick_label": pick_label,
            "case_id": pick["case_id"],
            "pack": pick.get("pack"),
            "kind": pick.get("kind"),
            "clean_negative": pick.get("clean_negative"),
            "expected_compliance_verdict_list": pick.get("expected_compliance_verdict_list"),
            "expected_safety_flags_strict": pick.get("expected_safety_flags_strict"),
            "expected_structural_verdict": pick.get("expected_structural_verdict"),
            "structural_catch_via": pick.get("structural_catch_via"),
            "artifact_type": artifact_type,
            "elapsed_s": round(elapsed, 2),
            "error": error,
            "graded": graded,
            "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
            "gate_decision": payload.get("gate_decision"),
            "structural_payload": payload.get("structural"),
            "semantic_findings": (payload.get("semantic") or {}).get("findings"),
            "judge_votes": (payload.get("semantic") or {}).get("judge_votes"),
            "judge_models": [
                jv.get("model") for jv in (
                    (payload.get("semantic") or {}).get("judge_votes") or []
                )
            ] if isinstance((payload.get("semantic") or {}).get("judge_votes"), list) else None,
        })

    OUT_DIR.mkdir(exist_ok=True)
    with RESULTS_NDJSON.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    pass_count = sum(1 for r in rows if r["graded"]["all_three_pass"])
    verdict_pass = sum(1 for r in rows if r["graded"]["verdict_match"])
    flags_pass = sum(1 for r in rows if r["graded"]["flags_match"])
    struct_pass = sum(1 for r in rows if not r["graded"]["structural_over_fired"])
    total = len(rows)

    print()
    print("=== SUMMARY ===")
    print(f"  all-three-pass     : {pass_count}/{total}")
    print(f"  verdict match      : {verdict_pass}/{total}")
    print(f"  flags match        : {flags_pass}/{total}")
    print(f"  no structural FP   : {struct_pass}/{total}")
    print()
    print(f"Per-case NDJSON: {RESULTS_NDJSON}")

    lines = ["# P1-FHIR-CONFORMANCE-MINI harness results\n"]
    lines.append(f"\n- Backend: `{base_url}`  agent: `{agent_id or 'none'}`")
    lines.append(f"- Validator: etlp-mapper mapping 41 (`fhir-patient-validator-strict`, profile `us-core-patient`)")
    lines.append(f"- Cases run: **{total}**")
    lines.append(f"- All three gates: **{pass_count}/{total}**")
    lines.append(f"- Verdict match: {verdict_pass}/{total} | Flags match: {flags_pass}/{total} | No structural FP: {struct_pass}/{total}")
    lines.append("\n## Per-case\n")
    lines.append("| pick | verdict | flags | structural | overall | notes |")
    lines.append("|------|---------|-------|------------|---------|-------|")
    for r in rows:
        g = r["graded"]
        overall = "PASS" if g["all_three_pass"] else "FAIL"
        notes = []
        if not g["verdict_match"]:
            notes.append(f"got {g['actual_verdict']}")
        if g["flags_missed"]:
            notes.append(f"missed: {', '.join(g['flags_missed'])}")
        if g["flag_match_via"]:
            via = ', '.join(f'{k}:{v}' for k,v in g['flag_match_via'].items())
            notes.append(f"via {via}")
        if g["structural_over_fired"]:
            notes.append(f"structural FP: {','.join(c for c in g['structural_finding_codes'] if c)}")
        if r["error"]:
            notes.append(r["error"])
        lines.append(
            f"| {r['pick_label']} "
            f"| {'✓' if g['verdict_match'] else '✗'} {g['actual_verdict_raw']} "
            f"| {'✓' if g['flags_match'] else '✗'} {len(g['flags_matched'])}/{len(g['flags_matched']) + len(g['flags_missed'])} "
            f"| {'✓' if not g['structural_over_fired'] else '✗'} {g['structural_findings_count']} findings, status={g['structural_status'] or '—'} "
            f"| **{overall}** "
            f"| {' / '.join(notes) or '—'} |"
        )
    RESULTS_REPORT.write_text("\n".join(lines) + "\n")
    print(f"Markdown report: {RESULTS_REPORT}")

    return 0 if pass_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
