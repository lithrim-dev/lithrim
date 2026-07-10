"""Refresh the active pack's taxonomy_snapshot.json from a lithrim-backend checkout.

Run when compliance_council.py changes upstream. The snapshot is the
contract between this repo and the backend; never hand-edit it.

Council fields (tiers/owners) are re-derived from compliance_council.py.
The bench-curated ``structural_codes`` block is NOT council-derived and is
preserved verbatim from the existing snapshot on refresh.

``--out`` defaults to the ``healthcare`` pack's snapshot, resolved via the pack
discovery seam (set ``LITHRIM_BENCH_PACKS_DIR`` to the external pack repo, e.g.
``../lithrim-pack-healthcare``). With no pack discoverable, resolution
fail-closes — there is no in-repo default to silently write into (the clinical
realm relocated out per PACK-DIST-1).

Usage:
    LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare \
    python scripts/snapshot_taxonomy.py \
        --backend-path /path/to/lithrim-backend \
        [--out /path/to/taxonomy_snapshot.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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


def _derive_production_judges(council) -> list[str]:
    """S-BS-30: derive the production trio from the v2 council config instead of
    hardcoding it.

    ``ComplianceCouncil.__init__`` builds the v2 cross-provider trio inline
    (risk_judge / policy_judge / faithfulness_judge) when
    ``COMPLIANCE_COUNCIL_VERSION == "v2"`` — there is no module-level constant to
    read, so instantiating the council and reading ``[m.name for m in
    council.models]`` is the single source of truth for "which judges actually
    run". ``main`` forces ``COMPLIANCE_COUNCIL_VERSION=v2`` +
    ``LITHRIM_LLM_PROVIDER=openai`` before the backend module is imported, so this
    stays offline (no Azure endpoint/key validation; the trio *names* are
    provider-independent) and pins the ratified v2-only production set.
    """
    return [m.name for m in council.ComplianceCouncil().models]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-path", required=True, type=Path)
    ap.add_argument("--out", default=None, type=Path)
    args = ap.parse_args()

    # Resolve the write target via the pack discovery seam so the snapshot lands
    # in the active ``healthcare`` pack (in-repo, or external via
    # LITHRIM_BENCH_PACKS_DIR). No in-repo default — fail-closed if undiscoverable.
    if args.out is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from lithrim_bench.harness.pack import pack_taxonomy_path

        args.out = pack_taxonomy_path("healthcare")

    # S-BS-30: the snapshot documents the *running* production trio, which under
    # the ratified v2-only decision is the cross-provider v2 trio. Force v2 +
    # provider=openai BEFORE importing the backend council so its module-level
    # Settings() singleton resolves the v2 trio, and the derivation stays offline
    # (provider=openai skips Azure validation; trio names are provider-independent).
    os.environ["COMPLIANCE_COUNCIL_VERSION"] = "v2"
    os.environ["LITHRIM_LLM_PROVIDER"] = "openai"

    council = _load_council_module(args.backend_path)
    production_judges = _derive_production_judges(council)

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
        "production_judges": production_judges,
        "declared_but_not_running": [],
    }

    declared_owners = {j for owners in snapshot["tier1_owners"].values() for j in owners}
    snapshot["declared_but_not_running"] = sorted(
        declared_owners - set(snapshot["production_judges"])
    )

    # Preserve the bench-curated fields. These are NOT derived from
    # compliance_council.py and must be carried over from the existing snapshot
    # so refreshing the council fields never silently drops them:
    #   * structural_codes / structural_codes_note — the WS-3a structural FLOOR
    #     augmentation (the council has no structural taxonomy).
    #   * lenses — the PACK-2c per-role lens authority. Post-2c the live
    #     judge_metric.LENS_BY_ROLE reads this block FROM the snapshot, so it
    #     cannot be re-derived here (that would read the file being written);
    #     it is bench-curated, carried over exactly like structural_codes.
    if args.out.exists():
        try:
            prior = json.loads(args.out.read_text())
        except (json.JSONDecodeError, OSError):
            prior = {}
        for key in ("lenses", "structural_codes", "structural_codes_note"):
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
