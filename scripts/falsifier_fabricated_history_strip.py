#!/usr/bin/env python3
"""P0-2 falsifier — does FABRICATED_HISTORY over-fire on clean structured
artifacts because of artifact-vs-transcript structured-detail asymmetry?

Hypothesis (REPORT_council_overfire_convergence_2026-05-28.md, Finding 3,
INFERRED): the council reads "the artifact carries valid structured detail the
transcript does not verbalize" as fabrication. The convergence report's R2 asks
for the decisive cheap test: strip the clean artifact to the minimal fields the
transcript verbalizes and re-run. If FABRICATED_HISTORY disappears -> asymmetry
confirmed, fix is prompt-level / pre-stage normalization. If it persists ->
deeper cause; any prompt-narrowing cycle was built on a wrong premise.

The case-A baseline (out/fhir_mini_harness_results.ndjson) over-fires from
faithfulness_judge (Llama-4-Maverick), whose reason cites TWO asymmetry sources:
"extensive patient information not discussed in the transcript" AND "the name in
the artifact differs from what was confirmed". So this runs a 3-arm ladder to
disentangle the extra-fields driver from the name-mismatch driver:

  A control_full          full case-A artifact (all 14 keys, Synthea name)
  B strip_fields_keep_name minimal keys, but Synthea suffixed name kept
  C strip_all_fix_name     minimal keys + transcript-faithful name "Leila Hoeger"

Decision:
  B clears FABRICATED_HISTORY  -> extra structured fields are the driver
  B fires, C clears            -> name mismatch is the driver
  C still fires                -> NOT asymmetry; prompt-narrowing premise falsified

This inspects the SEMANTIC council output only. The stripped arms WILL fail
structural validation (mapping 41 requires identifier/extensions) and the
worst-of verdict will be BLOCK regardless -- irrelevant here; the falsifier
question is purely whether the council EMITS FABRICATED_HISTORY in its semantic
findings / per-judge votes.

Run (backend up @ :8002 with COMPLIANCE_COUNCIL_VERSION=v2, etlp-mapper @ :3031):
    LITHRIM_API_KEY=lth_xxx \\
    LITHRIM_BASE_URL=http://localhost:8002 \\
    python scripts/falsifier_fabricated_history_strip.py [--n 3]

Outputs:
    out/falsifier_fabricated_history_strip.ndjson  — per-run raw + per-judge votes
    (summary table printed to stdout)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from lithrim import Lithrim  # type: ignore
except ImportError:
    sys.stderr.write("ERROR: lithrim SDK not importable (pip install lithrim-sdk).\n")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_JSONL = REPO_ROOT / "out" / "fhir_patient_mini.jsonl"
OUT_NDJSON = REPO_ROOT / "out" / "falsifier_fabricated_history_strip.ndjson"

FABRICATION_FAMILY = {
    "FABRICATED_HISTORY",
    "FABRICATED_CONSENT",
    "IMPLICIT_CONFIRMATION_OF_RECORD",
}

# Minimal field set the clean transcript actually verbalizes: name, DOB, gender.
MINIMAL_KEYS = {"resourceType", "name", "gender", "birthDate"}


def _load_case_a() -> tuple[dict[str, Any], str]:
    """Return (artifact_dict, transcript) for the clean A_CLEAN case, byte-faithful
    to what produced the baseline over-fire."""
    for line in PACK_JSONL.read_text().splitlines():
        case = json.loads(line)
        if "a_clean" in case["case_id"]:
            artifact = json.loads(case["artifacts"][0]["content"])
            return artifact, case["transcript"]
    raise SystemExit(f"A_CLEAN case not found in {PACK_JSONL}")


def _build_arms(full: dict[str, Any]) -> dict[str, dict[str, Any]]:
    strip_keep_name = {k: v for k, v in full.items() if k in MINIMAL_KEYS}

    strip_fix_name = dict(strip_keep_name)
    # Transcript-faithful name: single official name, no Synthea numeric suffix,
    # no maiden alias. Transcript says only "Leila Hoeger".
    strip_fix_name["name"] = [
        {"use": "official", "family": "Hoeger", "given": ["Leila"]}
    ]

    return {
        "A_control_full": full,
        "B_strip_fields_keep_name": strip_keep_name,
        "C_strip_all_fix_name": strip_fix_name,
    }


def _judge_summary(judge_votes: Any) -> list[dict[str, Any]]:
    out = []
    for jv in judge_votes or []:
        if not isinstance(jv, dict):
            continue
        out.append(
            {
                "role": jv.get("judge_role") or jv.get("role"),
                "model": jv.get("model"),
                "vote": jv.get("vote") or jv.get("verdict"),
                "findings": list(jv.get("findings") or []),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3, help="runs per arm (default 3)")
    args = ap.parse_args()

    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None
    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set.\n")
        return 2

    full, transcript = _load_case_a()
    arms = _build_arms(full)

    print(f"P0-2 falsifier — {args.n} runs/arm against {base_url} (v2 council)")
    print("Transcript verbalizes: name 'Leila Hoeger', DOB 1972-04-02, gender female")
    print(f"Arms: {list(arms)}\n")

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=120.0)
    rows: list[dict[str, Any]] = []
    fab_history_count: Counter[str] = Counter()
    fab_history_block_vote: Counter[str] = Counter()

    for arm, artifact in arms.items():
        artifact_json = json.dumps(artifact, sort_keys=True)
        artifact_keys = sorted(artifact.keys())
        for i in range(args.n):
            t0 = time.time()
            try:
                result = client.evaluate(
                    artifact=artifact_json,
                    artifact_type="fhir_patient",
                    context_kind="transcript",
                    context=transcript,
                    agent_id=agent_id,
                )
                payload = result.model_dump(mode="json")
                error = None
            except Exception as exc:  # noqa: BLE001
                payload, error = {}, f"{type(exc).__name__}: {exc}"
            elapsed = time.time() - t0

            semantic = payload.get("semantic") or {}
            sem_findings = semantic.get("findings") or []
            sem_codes = [f.get("code") or f.get("check_name") for f in sem_findings]
            judges = _judge_summary(semantic.get("judge_votes"))

            fired = "FABRICATED_HISTORY" in sem_codes
            if fired:
                fab_history_count[arm] += 1
            # Did any judge VOTE BLOCK while emitting FABRICATED_HISTORY?
            blocked_on_fab = any(
                (j["vote"] or "").upper() == "BLOCK" and "FABRICATED_HISTORY" in j["findings"]
                for j in judges
            )
            if blocked_on_fab:
                fab_history_block_vote[arm] += 1

            fam_codes = sorted(set(sem_codes) & FABRICATION_FAMILY)
            print(
                f"  {arm:>26} [{i+1}/{args.n}] verdict={payload.get('verdict','ERR'):<5} "
                f"FAB_HIST={'YES' if fired else 'no':<3} "
                f"block_vote={'YES' if blocked_on_fab else 'no':<3} "
                f"fam={fam_codes} ({elapsed:.1f}s)"
                + (f"  ERROR: {error}" if error else "")
            )

            rows.append(
                {
                    "arm": arm,
                    "run": i + 1,
                    "artifact_keys": artifact_keys,
                    "verdict": payload.get("verdict"),
                    "gate_decision": payload.get("gate_decision"),
                    "structural_status": (payload.get("structural") or {}).get("status"),
                    "semantic_codes": sem_codes,
                    "fabricated_history_fired": fired,
                    "fabricated_history_block_vote": blocked_on_fab,
                    "judges": judges,
                    "pipeline_run_id": (payload.get("provenance") or {}).get("pipeline_run_id"),
                    "elapsed_s": round(elapsed, 2),
                    "error": error,
                }
            )

    OUT_NDJSON.parent.mkdir(exist_ok=True)
    with OUT_NDJSON.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    print("\n=== FABRICATED_HISTORY emission per arm ===")
    for arm in arms:
        print(
            f"  {arm:>26}: fired {fab_history_count[arm]}/{args.n}  "
            f"| BLOCK-vote {fab_history_block_vote[arm]}/{args.n}"
        )

    # Verdict on the hypothesis. The convergence report (Finding 2) established
    # that the meaningful signal is the BLOCK *vote* on FABRICATED_HISTORY, not
    # mere code emission -- the code is a wash code that fires on ~11/12 cases.
    # So key the verdict on the BLOCK-vote counts, and report code emission
    # separately as the (expected) wash-code background.
    a = fab_history_block_vote["A_control_full"]
    b = fab_history_block_vote["B_strip_fields_keep_name"]
    c = fab_history_block_vote["C_strip_all_fix_name"]
    print("\n=== FALSIFIER VERDICT (keyed on FABRICATED_HISTORY BLOCK-vote) ===")
    if a == 0:
        print("  INCONCLUSIVE: control arm never produced a BLOCK-voting over-fire.")
    elif c == 0 and b == 0:
        print("  ASYMMETRY = EXTRA FIELDS: stripping non-verbalized structured fields")
        print("  removes the BLOCK vote. Fix = pre-stage normalization / 'record-captured")
        print("  fields are not fabrication' coaching (convergence R3a/R3b).")
    elif c == 0 and b > 0:
        print("  ASYMMETRY = NAME FIDELITY: extra fields alone still drive a BLOCK vote;")
        print("  only the transcript-faithful name clears it. The dominant driver is the")
        print("  artifact-vs-transcript NAME mismatch (Synthea suffixes/maiden name), NOT")
        print("  the extensions/identifiers the convergence report inferred. The R3 fix")
        print("  shape must address name normalization, not just structured-field framing.")
    elif c > 0:
        print("  FALSIFIED: BLOCK-voting over-fire persists on the fully-stripped,")
        print("  name-faithful clean. Root cause is NOT artifact-vs-transcript asymmetry.")
        print("  Any prompt-narrowing/normalization cycle would be built on a wrong premise")
        print("  — open deeper council triage.")
    print(
        "\n  NOTE: the FABRICATED_HISTORY *code* is expected to persist across all arms"
        "\n  (wash code, 11/12 cases per convergence Finding 2). Read code emission as"
        "\n  background; the BLOCK-vote counts above are the decision-relevant signal."
    )
    print(f"\nPer-run NDJSON: {OUT_NDJSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
