#!/usr/bin/env python
"""Config-driven eval runner — the canonical WS-1 entrypoint.

    load_agent(name) -> grade(replay|live) -> ground(ontology) -> composite + calibration

Everything comes from the SQLite config plane (the Agent eval-profile) + the
ontology: the case, the source/baseline, the contracts, the severity map, the
council disposition. There are NO hardcoded ``--case/--baseline/contracts`` args —
that is the whole point of WS-1 (acceptance A1). ``scripts/run_ws0.py`` is a thin
compat shim that builds an ephemeral Agent from CLI args and delegates to the
:func:`run` core here, so there is exactly ONE grounding path.

Defaults run the captured-baseline REPLAY path (zero new paid calls). ``--live``
opts into a real, paid ``:8002 /v1/pipeline/evaluate`` call and is OFF by default.

    python scripts/run_eval.py                       # agent 'ws0_default', replay
    python scripts/run_eval.py --agent ws0_default
    python scripts/run_eval.py --live                # paid; opt-in only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.config import (  # noqa: E402
    DEFAULT_CONFIG_DB,
    Agent,
    load_agent,
    seed_config_db,
)
from lithrim_bench.harness.correction import (  # noqa: E402
    build_correction,
    build_floor_correction,
    emit,
)
from lithrim_bench.harness.grade import grade_live, grade_replay  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.persist import persist  # noqa: E402
from lithrim_bench.harness.report import calibration, composite  # noqa: E402
from lithrim_bench.picklist import expected_block, load_case  # noqa: E402


def build_record(case, result, grounded, comp, cal, corrections, *, grade_path, agent):
    return {
        "case_id": case.get("case_id"),
        "agent": agent.name,
        "result": result,
        "grounded": {
            "verdict": grounded.verdict,
            "original_verdict": grounded.original_verdict,
            "active": grounded.active,
            "suppressed": [
                {
                    "code": s["finding"].get("code"),
                    "contract": s["contract"].version,
                    "disproved": s["verdict"].disproved,
                    "matched_token": s["verdict"].matched_token,
                    "evidence": s["verdict"].evidence,
                    "reason": s["verdict"].reason,
                }
                for s in grounded.suppressed
            ],
            "ungrounded": grounded.ungrounded,
            "skipped_non_gradeable": grounded.skipped_non_gradeable,
            "floor_blocks": [
                {
                    "flag": (b["injected_finding"] or {}).get("code")
                    or b["decl"].params.get("inject_flag_code"),
                    "contract_type": b["decl"].contract_type,
                    "contract": b["decl"].version,
                    "conforms": b["result"].conforms,
                    "disposition": b["result"].disposition,
                    "injected": b["injected_finding"] is not None,
                    "evidence": b["result"].evidence,
                    "manifest": b["result"].manifest,
                }
                for b in grounded.floor_blocks
            ],
        },
        "composite": comp,
        "calibration": cal,
        "corrections": corrections,
        "provenance": {
            "ontology_ref": agent.eval_profile.ontology_ref,
            "council_config": agent.eval_profile.council_config,
            "expected_compliance_verdict": case.get("expected_compliance_verdict"),
            "expected_safety_flags": case.get("expected_safety_flags"),
            "grade_path": grade_path,
        },
    }


def run(agent: Agent, *, live: bool = False, out_dir: str | Path | None = None) -> dict:
    """Drive one case end-to-end from an Agent eval-profile. Returns the record."""
    ontology = load_ontology(agent.ontology_abspath())
    case = load_case(agent.dataset.case_id, source=agent.source_abspath())
    if case is None:
        raise SystemExit(
            f"ERROR: case {agent.dataset.case_id!r} not found in {agent.dataset.source}"
        )

    if live:
        sys.stderr.write("WARNING: --live makes a real paid council call.\n")
        # WS-2: inject the Agent's stored council_config + ontology so the live
        # council is driven by config, not backend code. The ontology is sent as
        # its committed JSON dict (the faithful "stored ontology"); council_config
        # is the S-BS-6 disposition from the eval-profile. Both are additive —
        # absent => exactly the WS-0/WS-1 body.
        council_config = agent.eval_profile.council_config or None
        ontology_payload = json.loads(agent.ontology_abspath().read_text())
        result = grade_live(case, council_config=council_config, ontology=ontology_payload)
        grade_path = "live"
    else:
        result = grade_replay(case, agent.baseline_abspath())
        grade_path = "replay"

    grounded = ground(result, case, ontology=ontology)
    comp = composite(grounded)
    cal = calibration(result, expected_block=expected_block(case))

    corrections = []
    for entry in grounded.suppressed:
        rec = build_correction(
            suppressed_entry=entry,
            result=result,
            composite_before=grounded.original_verdict or comp["stage_verdict"],
            composite_after=grounded.verdict,
            ontology=ontology,
        )
        emit(rec)
        corrections.append(rec)
    # WS-3 structural-floor flips emit the inverse correction (council missed it).
    for block in grounded.floor_blocks:
        if block["injected_finding"] is None:
            continue  # inconclusive floor: surfaced in composite, no flip => no correction
        rec = build_floor_correction(
            floor_block=block,
            result=result,
            composite_before=grounded.original_verdict or comp["stage_verdict"],
            composite_after=grounded.verdict,
            ontology=ontology,
        )
        emit(rec)
        corrections.append(rec)

    out_dir = out_dir or (REPO_ROOT / "out" / "ws0")
    record = build_record(
        case, result, grounded, comp, cal, corrections, grade_path=grade_path, agent=agent
    )
    paths = persist(agent.dataset.case_id, record, out_dir=out_dir)
    record["_persisted"] = paths
    return record


def _print(agent: Agent, record: dict, *, live: bool) -> None:
    comp = record["composite"]
    cal = record["calibration"]
    g = record["grounded"]
    print(f"=== config-driven eval ({'live' if live else 'replay'}) — agent '{agent.name}' ===")
    print(f"case: {record['case_id']} | ontology: {agent.eval_profile.ontology_ref}")
    print(
        f"verdict: {comp['verdict']} (stage {comp['stage_verdict']}, was {g['original_verdict']})"
    )
    print(f"composite score: {comp['score']}")
    print(f"active findings: {comp['active_findings']}")
    print(f"ungrounded (null-code, skip-logged): {comp['ungrounded_count']}")
    print(f"reference (out-of-snapshot, skip-logged): {comp['skipped_non_gradeable_count']}")
    print("--- grounded corrections (S-BS-7) ---")
    if not record["corrections"]:
        print("  (none)")
    for rec in record["corrections"]:
        print(
            f"  {rec['original_label']} -> SUPPRESSED via {rec['contract_version']}: "
            f"{rec['tool_result']['reason']}"
        )
    print("--- calibration (REPORT-ONLY, not a gate) ---")
    print(f"  ECE: {cal['ece']} over {cal['n_with_confidence']} non-null confidence(s)")
    if cal["caveat"]:
        print(f"  caveat: {cal['caveat']}")
    print(f"persisted: {record['_persisted']['blob']} | {record['_persisted']['sqlite']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="config-driven eval runner")
    parser.add_argument("--agent", default="ws0_default")
    parser.add_argument("--config-db", default=str(DEFAULT_CONFIG_DB))
    parser.add_argument(
        "--live",
        action="store_true",
        help="opt into a real, PAID :8002 call (default: replay the baseline)",
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    db_path = Path(args.config_db)
    # Build the config DB from the committed agent seeds if it does not exist yet
    # (gitignored-built; source-of-truth is data/config/agents/*.json).
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    agent = load_agent(args.agent, db_path=db_path)

    record = run(agent, live=args.live, out_dir=args.out_dir)
    _print(agent, record, live=args.live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
