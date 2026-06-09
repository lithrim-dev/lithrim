"""Read-only access to the frozen taxonomy snapshot.

The snapshot is the contract between this repo and lithrim-backend's
compliance_council.py. Refresh it via scripts/snapshot_taxonomy.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lithrim_bench.harness.pack import pack_taxonomy_path

# Resolved via the active pack (default ``healthcare``): the snapshot — the CLAUDE.md
# contract-of-record — relocated INTO the pack (healthcare-realm-as-pack, 1a).
_SNAPSHOT_PATH = pack_taxonomy_path()


@dataclass(frozen=True)
class Taxonomy:
    tier_1: frozenset[str]
    tier_2: frozenset[str]
    tier_3: frozenset[str]
    tier1_owners: dict[str, frozenset[str]]
    production_judges: frozenset[str]
    declared_but_not_running: frozenset[str]
    structural_codes: frozenset[str] = frozenset()

    @property
    def known_codes(self) -> frozenset[str]:
        return self.tier_1 | self.tier_2 | self.tier_3

    def is_structural(self, code: str) -> bool:
        return code in self.structural_codes

    def is_known(self, code: str) -> bool:
        return code in self.known_codes or code in self.structural_codes

    def tier_of(self, code: str) -> str | None:
        if code in self.tier_1:
            return "TIER_1"
        if code in self.tier_2:
            return "TIER_2"
        if code in self.tier_3:
            return "TIER_3"
        if code in self.structural_codes:
            return "STRUCTURAL"
        return None

    def owners_of(self, code: str) -> frozenset[str]:
        return self.tier1_owners.get(code, frozenset())

    def production_owners_of(self, code: str) -> frozenset[str]:
        return self.owners_of(code) & self.production_judges


@lru_cache(maxsize=1)
def load_taxonomy(path: Path | None = None) -> Taxonomy:
    src = path or _SNAPSHOT_PATH
    raw = json.loads(src.read_text())
    tiers = raw["tiers"]
    return Taxonomy(
        tier_1=frozenset(tiers["TIER_1_NEVER_EVENTS"]),
        tier_2=frozenset(tiers["TIER_2_HIGH_RISK"]),
        tier_3=frozenset(tiers["TIER_3_MEDIUM"]),
        tier1_owners={k: frozenset(v) for k, v in raw["tier1_owners"].items()},
        production_judges=frozenset(raw["production_judges"]),
        declared_but_not_running=frozenset(raw["declared_but_not_running"]),
        structural_codes=frozenset(raw.get("structural_codes", {}).keys()),
    )
