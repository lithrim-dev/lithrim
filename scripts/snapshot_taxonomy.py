"""Refresh taxonomy/taxonomy_snapshot.json from a lithrim-backend checkout.

Run when compliance_council.py changes upstream. The snapshot is the
contract between this repo and the backend; never hand-edit it.

Council fields (tiers/owners) are re-derived from compliance_council.py.
The bench-curated ``structural_codes`` block is NOT council-derived and is
preserved verbatim from the existing snapshot on refresh.

Usage:
    python scripts/snapshot_taxonomy.py \
        --backend-path /path/to/lithrim-backend \
        [--out taxonomy/taxonomy_snapshot.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


def _load_council_module(backend_path: Path):
    src = backend_path / "app" / "services" / "compliance_council.py"
    if not src.exists():
        sys.exit(f"compliance_council.py not found at {src}")
    spec = importlib.util.spec_from_file_location("_council", src)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(backend_path))
    # Register before exec: backend dataclasses (e.g. CouncilModel:360, KW_ONLY)
    # resolve field types via sys.modules.get(cls.__module__); without the
    # synthetic "_council" module registered, dataclass processing crashes with
    # AttributeError: 'NoneType' object has no attribute '__dict__'.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git_sha(backend_path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=backend_path,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-path", required=True, type=Path)
    ap.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / "taxonomy" / "taxonomy_snapshot.json",
        type=Path,
    )
    args = ap.parse_args()

    council = _load_council_module(args.backend_path)

    snapshot = {
        "snapshot_metadata": {
            "source": "lithrim-backend/app/services/compliance_council.py",
            "source_commit": _git_sha(args.backend_path),
            "snapshot_date": date.today().isoformat(),
            "snapshotted_by": "scripts/snapshot_taxonomy.py",
        },
        "tiers": {
            "TIER_1_NEVER_EVENTS": sorted(council.TIER_1_NEVER_EVENTS),
            "TIER_2_HIGH_RISK": sorted(council.TIER_2_HIGH_RISK),
            "TIER_3_MEDIUM": sorted(council.TIER_3_MEDIUM),
        },
        "tier1_owners": {k: sorted(v) for k, v in council._TIER1_OWNERS.items()},
        "production_judges": ["policy_judge", "risk_judge", "behavior_judge"],
        "declared_but_not_running": [],
    }

    declared_owners = {j for owners in snapshot["tier1_owners"].values() for j in owners}
    snapshot["declared_but_not_running"] = sorted(
        declared_owners - set(snapshot["production_judges"])
    )

    # Preserve the bench-curated structural-floor codes. These are NOT derived
    # from compliance_council.py (the council has no structural taxonomy); they
    # are a bench augmentation for the WS-3a structural FLOOR. Carry them over
    # from the existing snapshot so refreshing the council fields never silently
    # drops them.
    if args.out.exists():
        try:
            prior = json.loads(args.out.read_text())
        except (json.JSONDecodeError, OSError):
            prior = {}
        for key in ("structural_codes", "structural_codes_note"):
            if key in prior:
                snapshot[key] = prior[key]

    args.out.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"wrote {args.out}")
    print(f"  tier1: {len(snapshot['tiers']['TIER_1_NEVER_EVENTS'])} codes")
    print(f"  tier2: {len(snapshot['tiers']['TIER_2_HIGH_RISK'])} codes")
    print(f"  tier3: {len(snapshot['tiers']['TIER_3_MEDIUM'])} codes")
    if "structural_codes" in snapshot:
        print(f"  preserved structural_codes: {len(snapshot['structural_codes'])}")
    if snapshot["declared_but_not_running"]:
        print(f"  WARN: owners declared but not in production: {snapshot['declared_but_not_running']}")


if __name__ == "__main__":
    main()
