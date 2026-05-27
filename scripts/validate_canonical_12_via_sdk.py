#!/usr/bin/env python3
"""Validate the N=12 canonical picklist via lithrim-sdk → backend → council-v2.

Runs each picklist case once through ``POST /v1/pipeline/evaluate`` on the
local backend (assumes ``COMPLIANCE_COUNCIL_VERSION=v2`` is in the backend's
environment so the cross-provider trio fires). Compares each per-case result
against the picklist's expected verdict/flags. Emits a pass/fail table the
user can read to decide which cases are ready for promotion into the
``paper_v1_n12_canonical`` eval-pack.

Run:
    PYENV_VERSION=debuglithrim \\
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    LITHRIM_AGENT_ID=69e8eed80774d8129275bb4a \\
    pyenv exec python scripts/validate_canonical_12_via_sdk.py

The script never deletes or mutates state — eval_cases and eval_packs are NOT
created here; that's the next cycle. Each call lands a ``pipeline_runs``
record in Mongo plus (because we pass agent_id) attaches the verdict to the
agent's audit trail, which makes per-case dispersion visible in the UI at
``/agents/<id>/results`` as a side-effect.
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

PICKLIST_PATH = Path("/tmp/pilot_picklist.json")
OUT_DIR = REPO_ROOT / "out"
RESULTS_NDJSON = OUT_DIR / "canonical_12_sdk_validation.ndjson"
RESULTS_REPORT = OUT_DIR / "canonical_12_sdk_validation.md"


def _normalize_expected_verdict(expected: Any) -> tuple[str, ...]:
    """Return the accepted set of compliance verdicts as a tuple."""
    if isinstance(expected, list):
        return tuple(expected)
    return (expected,)


def _build_context(case: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    """Same context-stitching the bench's LithrimPipelineBackend uses.

    The artifact under test is artifacts[0]. A coding case carries a
    ``fhir_document_reference`` SOAP-note alongside the FHIR Claim; we fold
    the SOAP text into context so the council sees the documentation of
    record. Verbatim port of
    lithrim_bench/backends/lithrim_pipeline.py:_build_context.
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


def _grade(pick: dict[str, Any], evaluate_payload: dict[str, Any]) -> dict[str, Any]:
    """Compute pass/fail per case.

    Three independent gates so we can see *which* contract a case fails:

    - VERDICT match: backend ``verdict`` (BLOCK/WARN/PASS) maps to
      reject/needs_review/approve and must be in the case's accepted-verdict
      set. The case can carry ``expected_compliance_verdict`` (legacy single
      or list) OR ``expected_compliance_verdict_list`` (Path T list); the
      latter wins when both are present.
    - FLAGS match: every code in ``expected_safety_flags_strict`` (or legacy
      ``expected_safety_flags``) must be matched by either (a) the exact code
      appearing in the backend's semantic findings, or (b) ANY substitute in
      ``expected_safety_flags_accepted_substitutes[code]`` appearing in those
      findings, or (c) — when the case carries
      ``structural_catch_via="structural_block_with_high_severity"`` and the
      strict code is a STRUCTURAL_* flag — the structural stage producing
      status=BLOCK with at least one severity≥HIGH finding (works around
      S-P1-16 ``code:null`` until backfilled).
    - STRUCTURAL no-false-fire: for cases the picklist marks
      ``clean_negative`` OR where ``expected_structural_verdict == "PASS"``,
      the backend's structural stage MUST NOT produce a finding above LOW
      severity. Catches the ``medications_well_formed`` over-fire we saw on
      ``council_v2_smoke_nka_clean``.

    Backwards-compatible: a case-fixture with NO ``_strict`` /
    ``_accepted_substitutes`` / ``structural_catch_via`` fields falls back to
    strict exact-code matching (current pre-Path-T behavior).
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

    # Path T contract: strict + accepted_substitutes. Falls back to legacy
    # `expected_safety_flags` when the strict field is absent.
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
        f"Validating {len(picklist)} canonical cases against {base_url} "
        f"(agent_id={agent_id or '<none>'})"
    )
    print(f"Pre-flight: COMPLIANCE_COUNCIL_VERSION should be 'v2' in backend env.")
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
        artifact_type = artifact.get("type") or "clinical_note"

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
            "expected_verdict": pick.get("expected_compliance_verdict"),
            "flags_matched": [], "flags_missed": pick.get("expected_safety_flags") or [],
            "actual_codes": [], "structural_findings_count": 0, "structural_finding_codes": [],
        }

        verdict_glyph = "✓" if graded["verdict_match"] else "✗"
        flags_glyph = "✓" if graded["flags_match"] else "✗"
        struct_glyph = "✓" if not graded["structural_over_fired"] else "✗"
        overall_glyph = "PASS" if graded["all_three_pass"] else "FAIL"

        print(
            f"  {pick_label:>3}  v={verdict_glyph}({graded['actual_verdict_raw']}->"
            f"{graded['actual_verdict']} ∈ {graded['expected_verdict']})  "
            f"flags={flags_glyph}({len(graded['flags_matched'])}/"
            f"{len(graded['flags_matched']) + len(graded['flags_missed'])})  "
            f"struct={struct_glyph}({graded['structural_findings_count']} findings)  "
            f"{overall_glyph}  ({elapsed:.1f}s)"
            + (f"  ERROR: {error}" if error else "")
        )
        rows.append({
            "pick_label": pick_label,
            "case_id": pick["case_id"],
            "pack": pick.get("pack"),
            "kind": pick.get("kind"),
            "clean_negative": pick.get("clean_negative"),
            "expected_compliance_verdict": pick.get("expected_compliance_verdict"),
            "expected_safety_flags": pick.get("expected_safety_flags"),
            "expected_structural_verdict": pick.get("expected_structural_verdict"),
            "artifact_type": artifact_type,
            "elapsed_s": round(elapsed, 2),
            "error": error,
            "graded": graded,
            "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
            "gate_decision": payload.get("gate_decision"),
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
    print(f"=== SUMMARY ===")
    print(f"  all-three-pass     : {pass_count}/{total}")
    print(f"  verdict match      : {verdict_pass}/{total}")
    print(f"  flags match        : {flags_pass}/{total}")
    print(f"  no structural FP   : {struct_pass}/{total}")
    print()
    print(f"Per-case NDJSON: {RESULTS_NDJSON}")

    # Write a markdown summary suitable for committing.
    lines = ["# Canonical N=12 SDK validation\n"]
    lines.append(f"\n- Backend: `{base_url}`  agent: `{agent_id or 'none'}`")
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
        if g["structural_over_fired"]:
            notes.append(f"structural FP: {','.join(c for c in g['structural_finding_codes'] if c)}")
        if r["error"]:
            notes.append(r["error"])
        lines.append(
            f"| {r['pick_label']} "
            f"| {'✓' if g['verdict_match'] else '✗'} {g['actual_verdict_raw']} "
            f"| {'✓' if g['flags_match'] else '✗'} {len(g['flags_matched'])}/{len(g['flags_matched']) + len(g['flags_missed'])} "
            f"| {'✓' if not g['structural_over_fired'] else '✗'} {g['structural_findings_count']} findings "
            f"| **{overall}** "
            f"| {' / '.join(notes) or '—'} |"
        )
    RESULTS_REPORT.write_text("\n".join(lines) + "\n")
    print(f"Markdown report: {RESULTS_REPORT}")

    return 0 if pass_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
