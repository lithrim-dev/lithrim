"""The ontology data model — the single source for flags, tiers, owners,
per-role judge questions, verification-contract declarations, and the
severity→verdict map.

Domain-agnostic by construction: nothing here is clinical. A domain is a JSON
seed (``packs/healthcare/ontology.json`` is the first one), loaded into the typed
model below. The harness depends only on this model + the committed seed — never
on a live ``import lithrim_bench.runtime.*`` (the seed sources are read once, at
seed-build time, by ``scripts/seed_ontology.py``; see that script and WS-1 §3.1).

Shapes (all data, no behaviour):
  - ``FlagDefinition``        — flag + category + definition + when_to_use /
    when_NOT_to_use + owner_roles + tier + ``gradeable`` (+ reliability_pillar,
    carried from the seed source as free structured data). ``gradeable`` is the
    S-BS-10 partition: True iff the flag is in ``packs/healthcare/taxonomy_snapshot.json``
    (the contract-of-record). Out-of-snapshot "reference" flags carry
    ``gradeable=False, tier=None`` and are never scored (grounding skip-logs them).
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

from .pack import pack_ontology_path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Resolved via the active pack (default ``healthcare``), not a hardcoded clinical
# path: the core carries no clinical content path (healthcare-realm-as-pack, 1a).
DEFAULT_ONTOLOGY_PATH = pack_ontology_path()


@dataclass(frozen=True)
class FlagDefinition:
    flag: str
    category: str
    definition: str
    when_to_use: str
    when_NOT_to_use: str
    owner_roles: tuple[str, ...]
    tier: str | None
    gradeable: bool = False
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

    def gradeable_flags(self) -> tuple[FlagDefinition, ...]:
        """The in-snapshot flags that may drive a verdict (S-BS-10 partition)."""
        return tuple(f for f in self.flags if f.gradeable)

    def is_gradeable(self, code: str) -> bool:
        """True iff ``code`` is a known, in-snapshot (gradeable) flag."""
        f = self.flag(code)
        return bool(f and f.gradeable)

    def is_reference(self, code: str) -> bool:
        """True iff ``code`` is a known but out-of-snapshot (reference) flag.

        Reference flags are skip-logged by grounding, never scored. An unknown
        code (not a declared flag at all) is neither gradeable nor reference.
        """
        f = self.flag(code)
        return bool(f and not f.gradeable)

    def owners_of(self, code: str) -> tuple[str, ...]:
        f = self.flag(code)
        return f.owner_roles if f else ()

    def contract_for(self, flag_code: str) -> VerificationContractDecl | None:
        # FIRST match — the frozen withstands read (signals.py) binds through this, so the
        # pick must stay first-declared even now that a code may declare a contract CHAIN.
        return next((c for c in self.contracts if c.flag_code == flag_code), None)

    def contracts_for(self, flag_code: str) -> tuple[VerificationContractDecl, ...]:
        """Every contract declared for ``flag_code``, in declaration order — the suppress
        CHAIN ``ground()`` runs (LAYER2-SUPPRESS-1). ``contract_for`` stays the single
        first-declared pick the pre-consensus withstands gate challenges with."""
        return tuple(c for c in self.contracts if c.flag_code == flag_code)

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
            gradeable=bool(f.get("gradeable", False)),
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


def load_ontology(path: str | Path = DEFAULT_ONTOLOGY_PATH) -> Ontology:
    """Load + cache an ontology, keyed on ``(path, mtime)``.

    The cache key includes the file's mtime, NOT just the path: R3 (draft→grade,
    S-BS-26b) loads the **mutable** working-copy draft through here, not only the
    immutable committed seed. Keying on path alone (the original ``@lru_cache``) meant
    an edit to the same draft path was silently ignored within a long-running process
    (e.g. the BFF) — the re-grade reused the stale ontology, breaking iterative
    "edit the flag → see it grade" (S-BS-58). An unchanged file still hits cache.
    """
    p = Path(path)
    return _load_ontology_cached(str(p), p.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _load_ontology_cached(path: str, _mtime_ns: int) -> Ontology:
    return from_dict(json.loads(Path(path).read_text()))
