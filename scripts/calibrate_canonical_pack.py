#!/usr/bin/env python3
"""Calibration run against ``eval_pack=paper_v1_n12_canonical``.

Drives each of the 12 spec.json cases through ``POST /v1/pipeline/evaluate``
on the local backend (assumes ``COMPLIANCE_COUNCIL_VERSION=v2``) and grades
against the Path T contract baked into the spec. **Replaces P1-VALIDATE-12
measurement under the new contract** — driver §2.4. Acceptance: verdict_match
>= 9/12 (per driver §5 A5).

Run:
    PYENV_VERSION=debuglithrim \\
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    LITHRIM_AGENT_ID=69e8eed80774d8129275bb4a \\
    pyenv exec python scripts/calibrate_canonical_pack.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from lithrim import Lithrim  # type: ignore
except ImportError:
    sys.stderr.write(
        "ERROR: lithrim SDK not importable. Either pip install lithrim-sdk or\n"
        "       PYTHONPATH=/Users/aregee/Workspace/github.com/lithrim-sdk\n"
    )
    sys.exit(2)

from lithrim_bench.picklist import resolve_case_fixtures
from scripts.validate_canonical_12_via_sdk import _build_context, _grade  # noqa: E402

SPEC_PATH = REPO_ROOT / "out" / "paper_v1_n12_canonical.spec.json"
OUT_DIR = REPO_ROOT / "out"
RESULTS_NDJSON = OUT_DIR / "paper_v1_n12_canonical_calibration.ndjson"
RESULTS_REPORT = OUT_DIR / "paper_v1_n12_canonical_calibration.md"


def main() -> int:
    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None
    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set.\n")
        return 2
    if not SPEC_PATH.exists():
        sys.stderr.write(f"ERROR: spec not found at {SPEC_PATH}\n")
        return 2

    spec = json.loads(SPEC_PATH.read_text())
    case_specs = spec["cases"]
    case_ids = {c["case_id"] for c in case_specs}
    fixtures = resolve_case_fixtures(case_ids)
    missing = case_ids - fixtures.keys()
    if missing:
        sys.stderr.write(f"ERROR: {len(missing)} cases unresolved: {missing}\n")
        return 2

    print(
        f"Calibrating {len(case_specs)} canonical cases against {base_url} "
        f"(agent_id={agent_id or '<none>'})"
    )
    print(f"Spec: {SPEC_PATH.name}  sha256-prefix: {spec.get('source_picklist','')}")
    print()

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=120.0)
    rows: list[dict[str, Any]] = []
    for case_spec in case_specs:
        pick_label = case_spec["paper_pick_label"]
        case_id = case_spec["case_id"]
        case = fixtures[case_id]
        artifacts = case.get("artifacts") or []
        if not artifacts:
            print(f"  {pick_label}: SKIP — case has no artifacts")
            continue
        artifact = artifacts[0]
        artifact_type = artifact.get("type") or "clinical_note"

        # The Path-T-aware _grade reads its expected_* fields from the case
        # row passed in; the spec row already carries them in the right shape.
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

        if error:
            graded = {
                "verdict_match": False,
                "flags_match": False,
                "structural_over_fired": False,
                "all_three_pass": False,
                "actual_verdict": "ERROR",
                "actual_verdict_raw": "ERROR",
                "expected_verdict": case_spec["expected_compliance_verdict_list"],
                "flags_matched": [],
                "flags_missed": case_spec["expected_safety_flags_strict"],
                "flag_match_via": {},
                "actual_codes": [],
                "structural_findings_count": 0,
                "structural_finding_codes": [],
                "structural_block_with_high": False,
            }
        else:
            graded = _grade(case_spec, payload)

        verdict_g = "✓" if graded["verdict_match"] else "✗"
        flags_g = "✓" if graded["flags_match"] else "✗"
        struct_g = "✓" if not graded["structural_over_fired"] else "✗"
        overall = "PASS" if graded["all_three_pass"] else "FAIL"
        n_exp = len(case_spec["expected_safety_flags_strict"])
        n_match = len(graded["flags_matched"])
        print(
            f"  {pick_label:>3}  v={verdict_g}({graded['actual_verdict_raw']}->"
            f"{graded['actual_verdict']} ∈ {graded['expected_verdict']})  "
            f"flags={flags_g}({n_match}/{n_exp})  "
            f"struct={struct_g}({graded['structural_findings_count']} findings)  "
            f"{overall}  ({elapsed:.1f}s)"
            + (f"  ERROR: {error}" if error else "")
        )
        rows.append({
            "pick_label": pick_label,
            "case_id": case_id,
            "source_pack": case_spec["source_pack"],
            "promotion_disposition": case_spec["promotion_disposition"],
            "clean_negative": case_spec["clean_negative"],
            "expected_compliance_verdict_list": case_spec["expected_compliance_verdict_list"],
            "expected_safety_flags_strict": case_spec["expected_safety_flags_strict"],
            "expected_safety_flags_accepted_substitutes": case_spec["expected_safety_flags_accepted_substitutes"],
            "expected_structural_verdict": case_spec["expected_structural_verdict"],
            "structural_catch_via": case_spec.get("structural_catch_via"),
            "artifact_type": artifact_type,
            "elapsed_s": round(elapsed, 2),
            "error": error,
            "graded": graded,
            "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
            "gate_decision": payload.get("gate_decision"),
            "judge_models": [
                jv.get("model")
                for jv in ((payload.get("semantic") or {}).get("judge_votes") or [])
            ]
            if isinstance((payload.get("semantic") or {}).get("judge_votes"), list)
            else None,
        })

    OUT_DIR.mkdir(exist_ok=True)
    RESULTS_NDJSON.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    pass_count = sum(1 for r in rows if r["graded"]["all_three_pass"])
    verdict_pass = sum(1 for r in rows if r["graded"]["verdict_match"])
    flags_pass = sum(1 for r in rows if r["graded"]["flags_match"])
    struct_pass = sum(1 for r in rows if not r["graded"]["structural_over_fired"])
    total = len(rows)

    print()
    print("=== CALIBRATION SUMMARY ===")
    print(f"  all-three-pass     : {pass_count}/{total}")
    print(f"  verdict match      : {verdict_pass}/{total}  (A5 floor: >= 9)")
    print(f"  flags match        : {flags_pass}/{total}    (Path T contract)")
    print(f"  no structural FP   : {struct_pass}/{total}")
    print()
    print(f"NDJSON: {RESULTS_NDJSON}")

    # Markdown summary (committable artifact).
    lines = ["# paper_v1_n12_canonical — calibration run\n\n"]
    lines.append(f"- Backend: `{base_url}`  agent: `{agent_id or 'none'}`\n")
    lines.append(f"- Spec: `{SPEC_PATH.relative_to(REPO_ROOT)}`\n")
    lines.append(f"- Cases run: **{total}**\n")
    lines.append(f"- All three gates: **{pass_count}/{total}**\n")
    lines.append(
        f"- Verdict match: **{verdict_pass}/{total}** (A5 floor 9/12) | "
        f"Flags match: {flags_pass}/{total} | No structural FP: {struct_pass}/{total}\n\n"
    )
    lines.append("## Per-case outcome (Path T contract)\n\n")
    lines.append(
        "| Pick | Disposition | v_raw | v | v_match | flags_match (via) | struct_OK | all-3 |\n"
    )
    lines.append("|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        g = r["graded"]
        via = ",".join(f"{k}={v}" for k, v in (g.get("flag_match_via") or {}).items()) or "—"
        lines.append(
            f"| {r['pick_label']} | {r['promotion_disposition']} | "
            f"{g['actual_verdict_raw']} | {g['actual_verdict']} | "
            f"{'✓' if g['verdict_match'] else '✗'} | "
            f"{'✓' if g['flags_match'] else '✗'} ({via}) | "
            f"{'✓' if not g['structural_over_fired'] else '✗'} | "
            f"{'PASS' if g['all_three_pass'] else 'FAIL'} |\n"
        )
    RESULTS_REPORT.write_text("".join(lines))
    print(f"Markdown: {RESULTS_REPORT}")

    return 0 if verdict_pass >= 9 else 4


if __name__ == "__main__":
    sys.exit(main())
