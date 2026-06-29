"""The CI/CD eval-pack gate — Mongo-free, over the local engine (DOGFOOD-1 D4).

Replicates ``../lithrim-backend/examples/ci_cd_gate.py``'s release rule
(``passed = reliability >= threshold AND never_events == 0``) but computes it over a
LOCAL frozen eval-pack (:mod:`lithrim_bench.harness.evalpack`) instead of polling the
:8002 SaaS API — the premium eval-pack-SDK surface, runnable as ``lithrim-pack``
in a CI pipeline (exit 0 = safe to deploy, exit 1 = block release).

  * ``reliability`` = ``100 * verdict_matches / total``; a match = the composite verdict
    is in the case's expected verdict set (the picklist S-BS-9 shape contract).
  * ``never_events`` = Tier-1 floor breaches: a Tier-1 code fired that the case did NOT
    expect (a false never-event alarm — e.g. ``FABRICATED_ALLERGY`` on a clean NKA note),
    OR an expected Tier-1 code the council MISSED. Tier membership is read from the frozen
    taxonomy snapshot.

Two modes: gate a pre-built frozen pack (``--pack PATH``, offline + $0), or build a pack
from agents under a judge set and gate it (``--build``; ``--in-process`` is PAID).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.config import agent_from_dict  # noqa: E402
from lithrim_bench.picklist import normalize_expected_verdict  # noqa: E402
from lithrim_bench.taxonomy import Taxonomy, load_taxonomy  # noqa: E402

DEFAULT_THRESHOLD = 96.0
AGENTS_DIR = REPO_ROOT / "data" / "config" / "agents"


# --------------------------------------------------------------------------- #
# Pure gate computation (offline; the A4 unit surface)
# --------------------------------------------------------------------------- #
def reliability(pack: dict[str, Any]) -> tuple[float, int, int, list[dict[str, Any]]]:
    """Return ``(pct, matches, total, mismatches)`` over the pack's cases × outcomes."""
    cases = {c["case_id"]: c for c in pack.get("cases") or []}
    total = matches = 0
    mismatches: list[dict[str, Any]] = []
    for o in pack.get("outcomes") or []:
        c = cases.get(o["case_id"])
        if c is None:
            continue
        total += 1
        expected = normalize_expected_verdict(c["expected"]["compliance_verdict"])
        actual = o["verdict"]
        if actual in expected:
            matches += 1
        else:
            mismatches.append(
                {"case_id": o["case_id"], "expected": sorted(expected), "actual": actual}
            )
    pct = (100.0 * matches / total) if total else 0.0
    return pct, matches, total, mismatches


def never_events(pack: dict[str, Any], *, taxonomy: Taxonomy | None = None) -> list[dict[str, Any]]:
    """Tier-1 floor breaches across the pack: false alarms (Tier-1 fired but unexpected)
    and misses (expected Tier-1 not fired). Empty list = no never-events."""
    tax = taxonomy or load_taxonomy()
    cases = {c["case_id"]: c for c in pack.get("cases") or []}
    events: list[dict[str, Any]] = []
    for o in pack.get("outcomes") or []:
        c = cases.get(o["case_id"])
        if c is None:
            continue
        expected = set(c["expected"].get("safety_flags") or [])
        actual = {f for f in (o.get("active_findings") or []) if f}
        for f in sorted(actual):
            if tax.tier_of(f) == "TIER_1" and f not in expected:
                events.append({"case_id": o["case_id"], "safety_flag": f, "kind": "false_alarm"})
        for f in sorted(expected):
            if tax.tier_of(f) == "TIER_1" and f not in actual:
                events.append({"case_id": o["case_id"], "safety_flag": f, "kind": "missed"})
    return events


def decide(
    pack: dict[str, Any], *, threshold: float | None = None, taxonomy: Taxonomy | None = None
) -> dict[str, Any]:
    """The release decision (replicates ci_cd_gate.py): ``reliability >= threshold AND
    never_events == 0``. ``threshold`` defaults to the pack manifest's locked value."""
    thr = threshold if threshold is not None else float(pack.get("threshold", DEFAULT_THRESHOLD))
    pct, matches, total, mismatches = reliability(pack)
    events = never_events(pack, taxonomy=taxonomy)
    passed = pct >= thr and len(events) == 0
    return {
        "passed": passed,
        "reliability": pct,
        "threshold": thr,
        "matches": matches,
        "total": total,
        "mismatches": mismatches,
        "never_events": events,
    }


def format_report(pack: dict[str, Any], verdict: dict[str, Any]) -> str:
    """Render the human-readable gate report (mirrors ci_cd_gate.py's output)."""
    pack_id = pack.get("pack_id", "?")
    js = (pack.get("judge_set") or {}).get("label", "default")
    lines = [""]
    if verdict["passed"]:
        lines.append("  RELEASE GATE: PASS")
    else:
        lines.append("  RELEASE GATE: FAIL")
    lines.append(
        f"  Pack: {pack_id} | Judge set: {js} | "
        f"Reliability: {verdict['reliability']:.1f}% (threshold: {verdict['threshold']}%)"
    )
    lines.append(
        f"  Cases: {verdict['matches']}/{verdict['total']} verdict match | "
        f"Never-events: {len(verdict['never_events'])}"
    )
    if verdict["never_events"]:
        lines.append("  Never-events:")
        for ne in verdict["never_events"]:
            lines.append(f"    - {ne['case_id']}: {ne['safety_flag']} ({ne['kind']})")
    if verdict["mismatches"]:
        lines.append("  Failed cases:")
        for m in verdict["mismatches"][:10]:
            lines.append(f"    - {m['case_id']}: expected {m['expected']}, got {m['actual']}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _load_agents(names: list[str]) -> list[Any]:
    agents = []
    for name in names:
        path = AGENTS_DIR / f"{name}.json"
        if not path.exists():
            raise SystemExit(f"ERROR: agent seed not found: {path}")
        agents.append(agent_from_dict(json.loads(path.read_text())))
    return agents


def _default_imported_agents() -> list[str]:
    return sorted(p.stem for p in AGENTS_DIR.glob("imported_*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lithrim CI/CD eval-pack gate — block deploys that fail compliance "
        "(reliability >= threshold AND never_events == 0). Exit 0 = pass, 1 = fail."
    )
    parser.add_argument("--pack", help="Path to a frozen eval-pack JSON to gate (offline, $0)")
    parser.add_argument("--build", action="store_true", help="Build a pack before gating")
    parser.add_argument(
        "--agents",
        help="Comma-separated agent seed names (default: all imported_* seeds). Used with --build",
    )
    parser.add_argument(
        "--set-id", default="dogfood_v1", help="Judge-set file id (default dogfood_v1)"
    )
    parser.add_argument(
        "--judge-set",
        default="all_azure",
        help="Judge-set label within --set-id (default all_azure)",
    )
    parser.add_argument(
        "--in-process", action="store_true", help="Build via the in-process v2 council (PAID)"
    )
    parser.add_argument(
        "--live", action="store_true", help="Build via the live :8002 council (PAID)"
    )
    parser.add_argument(
        "--threshold", type=float, default=None, help="Override the pack's reliability threshold"
    )
    parser.add_argument("--pack-id", default="dogfood", help="pack_id when building")
    parser.add_argument("--dump", help="When building, also freeze the built pack to this path")
    parser.add_argument("--out-dir", help="Per-case persist dir when building")
    parser.add_argument(
        "--collections-db",
        help="When building in_process, persist run blobs to this DB so the runs show in "
        "GET /v1/runs (point at the BFF's collections DB). Default: the engine default.",
    )
    args = parser.parse_args(argv)

    # Lazy import so --pack (offline) never pulls run_eval/council heavy deps.
    from lithrim_bench.harness.evalpack import build_pack, dump_pack, load_pack

    if args.pack:
        pack = load_pack(args.pack)
    elif args.build:
        from lithrim_bench.harness.judge_sets import get_judge_set

        names = args.agents.split(",") if args.agents else _default_imported_agents()
        if not names:
            raise SystemExit("ERROR: no agents to build (none given and no imported_* seeds found)")
        agents = _load_agents([n.strip() for n in names])
        js = get_judge_set(args.judge_set, args.set_id)
        if args.in_process:
            sys.stderr.write(
                "WARNING: --in-process runs the in-process v2 council (real paid calls).\n"
            )
        pack = build_pack(
            args.pack_id,
            agents,
            live=args.live,
            in_process=args.in_process,
            models=js["models"],
            roles=js["roles"],
            assignments=js["assignments"],
            judge_set=js,
            threshold=args.threshold if args.threshold is not None else DEFAULT_THRESHOLD,
            out_dir=args.out_dir,
            collections_db=args.collections_db,
        )
        if args.dump:
            dump_pack(pack, args.dump)
            print(f"wrote {args.dump}")
    else:
        parser.error("pass --pack PATH (gate a frozen pack) or --build (build then gate)")

    verdict = decide(pack, threshold=args.threshold)
    print(format_report(pack, verdict))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
