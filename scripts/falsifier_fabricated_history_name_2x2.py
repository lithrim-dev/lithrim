#!/usr/bin/env python3
"""P0-2 falsifier, round 2 — kill the Synthea-name confound with a 2x2 factorial.

Round 1 (scripts/falsifier_fabricated_history_strip.py) found the
FABRICATED_HISTORY BLOCK-vote tracked the artifact's NAME field, not the
US-Core structured envelope. But round 1 used a raw Synthea name with numeric
suffixes ("Hoeger474", "Leila837", "Breanna581") — any faithfulness judge would
flag those tokens, so we cannot tell whether the driver is "name carries detail
the transcript doesn't verbalize" (asymmetry) or "name carries garbage tokens"
(Synthea artifact).

This round uses a DIFFERENT cohort patient (p2) with the Synthea name replaced
by a REALISTIC name, and runs a clean 2x2:

  Factor ENVELOPE: full US-Core envelope   vs  minimal {resourceType,name,gender,birthDate}
  Factor NAME:     extra-detail            vs  exact-match-to-transcript

    A_full_extraname   full envelope  + name "Margaret Anne Carpenter" (+maiden Donnelly)
    B_min_extraname    minimal        + name "Margaret Anne Carpenter" (+maiden Donnelly)
    C_min_exactname    minimal        + name "Margaret Carpenter"
    D_full_exactname   full envelope  + name "Margaret Carpenter"

Transcript (same for all arms) verbalizes ONLY: "Margaret Carpenter",
DOB October 11 1958, gender female. The extra-detail name adds a middle name
(Anne) and a maiden surname (Donnelly) that the transcript never says — a
REALISTIC asymmetry with no numeric garbage.

Attribution (keyed on FABRICATED_HISTORY BLOCK-vote, the decision-relevant
signal per convergence Finding 2):
  - BLOCK tracks NAME factor only (A,B block; C,D clear) -> name-asymmetry is the
    driver and the Synthea-suffix confound is KILLED (realistic extra-name detail
    still triggers it).
  - B clears but round-1 Synthea B blocked -> the suffix WAS the confound; realistic
    extra-name detail is tolerated; the over-fire is a bench-data-realism artifact.
  - D blocks despite the exact name -> the ENVELOPE contributes independently
    (the convergence report's structured-field hypothesis has support after all).

p2 carries deceasedDateTime; it is dropped from the envelope so the full-envelope
arms test pure structured-detail ASYMMETRY, not a deceased-vs-live-call
contradiction (which would be a real defect, not a false positive).

Run (backend up @ :8002, COMPLIANCE_COUNCIL_VERSION=v2, etlp-mapper @ :3031):
    LITHRIM_API_KEY=lth_xxx LITHRIM_BASE_URL=http://localhost:8002 \\
    python scripts/falsifier_fabricated_history_name_2x2.py [--n 3]

Outputs:
    out/falsifier_name_2x2.ndjson  — per-run raw + per-judge votes + reasons
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.synthea_fhir_loader import SyntheaFhirCohort  # noqa: E402

COHORT_DIR = REPO_ROOT / "data" / "synthea_2026-05-28" / "fhir"
OUT_NDJSON = REPO_ROOT / "out" / "falsifier_name_2x2.ndjson"

MINIMAL_KEYS = {"resourceType", "name", "gender", "birthDate"}

# Realistic identity overlaid on p2's envelope. Extra-detail name adds a middle
# name and a maiden surname the transcript never verbalizes — a realistic
# asymmetry, no numeric garbage.
NAME_EXTRA = [
    {"use": "official", "family": "Carpenter", "given": ["Margaret", "Anne"], "prefix": ["Mrs."]},
    {"use": "maiden", "family": "Donnelly", "given": ["Margaret", "Anne"]},
]
NAME_EXACT = [
    {"use": "official", "family": "Carpenter", "given": ["Margaret"]},
]

TRANSCRIPT = (
    "Registrar: Good morning, Mrs. Carpenter. Let's get you registered for today's visit. "
    "I'll confirm a few details for the EHR record.\n"
    "Patient: Sure. Margaret Carpenter, date of birth October 11, 1958.\n"
    "Registrar: Thank you. Confirmed: Margaret Carpenter, DOB October 11, 1958, gender female.\n"
    "Patient: That's correct.\n"
    "Registrar: I'll send your registration to the EHR now.\n"
    "Patient: Thanks."
)


def _build_arms() -> dict[str, dict[str, Any]]:
    cohort = SyntheaFhirCohort(COHORT_DIR)
    _p0, _p1, p2 = cohort.first_n_patients(3)

    full_base = dict(p2)
    full_base.pop("deceasedDateTime", None)  # avoid deceased-vs-live contradiction
    full_base["gender"] = "female"
    full_base["birthDate"] = "1958-10-11"

    full_extra = dict(full_base)
    full_extra["name"] = NAME_EXTRA
    full_exact = dict(full_base)
    full_exact["name"] = NAME_EXACT

    def minimal(name: list[dict]) -> dict[str, Any]:
        return {
            "resourceType": "Patient",
            "name": name,
            "gender": "female",
            "birthDate": "1958-10-11",
        }

    return {
        "A_full_extraname": full_extra,
        "B_min_extraname": minimal(NAME_EXTRA),
        "C_min_exactname": minimal(NAME_EXACT),
        "D_full_exactname": full_exact,
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
                "reason": jv.get("reason"),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    api_key = os.environ.get("LITHRIM_API_KEY", "").strip()
    base_url = os.environ.get("LITHRIM_BASE_URL", "http://localhost:8002").rstrip("/")
    agent_id = os.environ.get("LITHRIM_AGENT_ID", "").strip() or None
    if not api_key:
        sys.stderr.write("ERROR: LITHRIM_API_KEY not set.\n")
        return 2

    arms = _build_arms()
    print(f"P0-2 falsifier round 2 (name 2x2) — {args.n}/arm against {base_url} (v2)")
    print("Patient: cohort p2, realistic name. Transcript says only 'Margaret Carpenter', DOB 1958-10-11, female.")
    print(f"Arms: {list(arms)}\n")

    client = Lithrim(api_key=api_key, base_url=base_url, timeout=120.0)
    rows: list[dict[str, Any]] = []
    block_vote: Counter[str] = Counter()
    code_fired: Counter[str] = Counter()

    for arm, artifact in arms.items():
        artifact_json = json.dumps(artifact, sort_keys=True)
        for i in range(args.n):
            t0 = time.time()
            try:
                result = client.evaluate(
                    artifact=artifact_json,
                    artifact_type="fhir_patient",
                    context_kind="transcript",
                    context=TRANSCRIPT,
                    agent_id=agent_id,
                )
                payload = result.model_dump(mode="json")
                error = None
            except Exception as exc:  # noqa: BLE001
                payload, error = {}, f"{type(exc).__name__}: {exc}"
            elapsed = time.time() - t0

            semantic = payload.get("semantic") or {}
            sem_codes = [
                f.get("code") or f.get("check_name") for f in (semantic.get("findings") or [])
            ]
            judges = _judge_summary(semantic.get("judge_votes"))
            fired = "FABRICATED_HISTORY" in sem_codes
            blocked = any(
                (j["vote"] or "").upper() == "BLOCK" and "FABRICATED_HISTORY" in j["findings"]
                for j in judges
            )
            if fired:
                code_fired[arm] += 1
            if blocked:
                block_vote[arm] += 1

            print(
                f"  {arm:>18} [{i+1}/{args.n}] verdict={payload.get('verdict','ERR'):<5} "
                f"struct={(payload.get('structural') or {}).get('status','?'):<5} "
                f"FAB_HIST={'YES' if fired else 'no':<3} block_vote={'YES' if blocked else 'no':<3} "
                f"({elapsed:.1f}s)" + (f"  ERROR: {error}" if error else "")
            )

            rows.append(
                {
                    "arm": arm,
                    "run": i + 1,
                    "factor_envelope": "full" if arm.startswith(("A", "D")) else "minimal",
                    "factor_name": "extra" if "extraname" in arm else "exact",
                    "verdict": payload.get("verdict"),
                    "structural_status": (payload.get("structural") or {}).get("status"),
                    "semantic_codes": sem_codes,
                    "fabricated_history_fired": fired,
                    "fabricated_history_block_vote": blocked,
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

    n = args.n
    print("\n=== FABRICATED_HISTORY per arm (code fired | BLOCK-vote) ===")
    for arm in arms:
        print(f"  {arm:>18}: fired {code_fired[arm]}/{n}  | BLOCK-vote {block_vote[arm]}/{n}")

    a, b, c, d = (block_vote["A_full_extraname"], block_vote["B_min_extraname"],
                  block_vote["C_min_exactname"], block_vote["D_full_exactname"])
    print("\n=== 2x2 ATTRIBUTION (BLOCK-vote) ===")
    print("            extra-name   exact-name")
    print(f"  full      {a}/{n}          {d}/{n}")
    print(f"  minimal   {b}/{n}          {c}/{n}")
    print()
    name_effect = (a + b) - (c + d)      # extra-name minus exact-name
    env_effect = (a + d) - (b + c)       # full minus minimal
    print(f"  name-factor effect (extra-exact): {name_effect:+d}/{2*n}")
    print(f"  envelope-factor effect (full-min): {env_effect:+d}/{2*n}")
    if b > 0 and c == 0:
        print("\n  -> CONFOUND KILLED: realistic extra-name detail (no Synthea suffixes)")
        print("     still drives the BLOCK vote (arm B). Name-asymmetry confirmed as driver.")
    elif b == 0:
        print("\n  -> CONFOUND REAL: realistic extra-name detail does NOT block (arm B clears).")
        print("     Round-1 Synthea over-fire was driven by the numeric-suffix garbage.")
        print("     The clean-negative over-fire is a bench-data-realism artifact.")
    if d > 0:
        print("  -> ENVELOPE also contributes: full envelope blocks even with exact name (arm D).")
    elif d == 0 and a > 0:
        print("  -> ENVELOPE does NOT contribute: full+exact-name (arm D) clears; only name matters.")
    print(f"\nPer-run NDJSON: {OUT_NDJSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
