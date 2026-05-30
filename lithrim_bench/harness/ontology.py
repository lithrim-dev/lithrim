"""The ontology data model — the single source for flags, tiers, owners,
per-role judge questions, verification-contract declarations, and the
severity→verdict map.

Domain-agnostic by construction: nothing here is clinical. A domain is a JSON
seed (``data/ontology/clinical_v1.json`` is the first one), loaded into the typed
model below. The harness depends only on this model + the committed seed — never
on a live ``import lithrim_bench.runtime.*`` (the seed sources are read once, at
seed-build time, by ``scripts/seed_ontology.py``; see that script and WS-1 §3.1).

Shapes (all data, no behaviour):
  - ``FlagDefinition``        — flag + category + definition + when_to_use /
    when_NOT_to_use + owner_roles + tier (+ reliability_pillar, carried from the
    seed source as free structured data).
  - ``JudgeQuestion``         — (role, ordinal, text) parsed from a role prompt's
    numbered "KEY QUESTIONS TO ANSWER" block.
  - ``VerificationContractDecl`` — the *declaration* of a tool-check: flag_code,
    question, contract_type, params, version. The harness maps contract_type to an
    executor (grounding.py); the params (e.g. extraction strategy) live here as
    data, not as buried module constants (WS-0 critique Q4.3).
  - ``severity_map``          — severity→weight + the verdict thresholds, recorded
    as data so "lone MEDIUM → BLOCK" is a ratified config value, not a magic
    constant (WS-0 critique Q4.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONTOLOGY_PATH = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"


@dataclass(frozen=True)
class FlagDefinition:
    flag: str
    category: str
    definition: str
    when_to_use: str
    when_NOT_to_use: str
    owner_roles: tuple[str, ...]
    tier: str | None
    reliability_pillar: str | None = None


@dataclass(frozen=True)
class JudgeQuestion:
    role: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class VerificationContractDecl:
    flag_code: str
    question: str
    contract_type: str
    params: dict[str, Any]
    version: str


@dataclass(frozen=True)
class SeverityMap:
    """severity→[0,1] weight + the verdict thresholds (WS-0 critique Q4.2 as data).

    ``rescore`` reproduces the WS-0 ``_rescore`` disposition exactly: the active
    set's worst severity drives the verdict; ``block_at_or_above`` blocks (so a
    lone MEDIUM blocks), anything above ``warn_above`` warns, else passes.
    """

    weights: dict[str, float]
    block_at_or_above: float
    warn_above: float

    def weight_of(self, severity: str | None) -> float:
        return self.weights.get(severity or "", 0.0)

    def rescore(self, active: list[dict[str, Any]]) -> str:
        weight = max((self.weight_of(f.get("severity")) for f in active), default=0.0)
        if weight >= self.block_at_or_above:
            return "BLOCK"
        if weight > self.warn_above:
            return "WARN"
        return "PASS"


@dataclass(frozen=True)
class Ontology:
    ontology_version: str
    domain: str
    flags: tuple[FlagDefinition, ...]
    questions: tuple[JudgeQuestion, ...]
    contracts: tuple[VerificationContractDecl, ...]
    severity_map: SeverityMap

    def flag(self, code: str) -> FlagDefinition | None:
        return next((f for f in self.flags if f.flag == code), None)

    def owners_of(self, code: str) -> tuple[str, ...]:
        f = self.flag(code)
        return f.owner_roles if f else ()

    def contract_for(self, flag_code: str) -> VerificationContractDecl | None:
        return next((c for c in self.contracts if c.flag_code == flag_code), None)

    def questions_for(self, role: str) -> tuple[JudgeQuestion, ...]:
        return tuple(q for q in self.questions if q.role == role)


def from_dict(data: dict[str, Any]) -> Ontology:
    """Build an :class:`Ontology` from the seed-JSON shape (no I/O)."""
    flags = tuple(
        FlagDefinition(
            flag=f["flag"],
            category=f["category"],
            definition=f["definition"],
            when_to_use=f["when_to_use"],
            when_NOT_to_use=f["when_NOT_to_use"],
            owner_roles=tuple(f.get("owner_roles") or ()),
            tier=f.get("tier"),
            reliability_pillar=f.get("reliability_pillar"),
        )
        for f in data["flags"]
    )
    questions = tuple(
        JudgeQuestion(role=q["role"], ordinal=q["ordinal"], text=q["text"])
        for q in data.get("questions") or ()
    )
    contracts = tuple(
        VerificationContractDecl(
            flag_code=c["flag_code"],
            question=c["question"],
            contract_type=c["contract_type"],
            params=c.get("params") or {},
            version=c["version"],
        )
        for c in data.get("verification_contracts") or ()
    )
    sm = data["severity_map"]
    severity_map = SeverityMap(
        weights={k: float(v) for k, v in sm["weights"].items()},
        block_at_or_above=float(sm["block_at_or_above"]),
        warn_above=float(sm["warn_above"]),
    )
    return Ontology(
        ontology_version=data["ontology_version"],
        domain=data["domain"],
        flags=flags,
        questions=questions,
        contracts=contracts,
        severity_map=severity_map,
    )


@lru_cache(maxsize=8)
def load_ontology(path: str | Path = DEFAULT_ONTOLOGY_PATH) -> Ontology:
    """Load + cache an ontology from its committed JSON seed."""
    data = json.loads(Path(path).read_text())
    return from_dict(data)
