"""Agent↔pack readiness preflight — catch a declared verification contract that will silently
never fire, *before* it silently mis-grades.

The one silent hole this closes: the council votes with the **pack** lens
(``pack_lenses``/``pack_production_judges``) but ``ground()`` reads its verification-contract set
from the **agent** ontology (``_resolve_ontology_path`` → ``run_eval.run`` → ``ground``). Nothing
reconciles the two. When they disagree — a workspace pinned to a pack that declares a
``snomed_subsumption`` floor, graded by an agent whose ontology carries zero contracts — the floor
is registered, the tool + executor are live, and the floor *still never runs*
(``grounding.py`` ``contract = contracts.get(code); if contract is None: active.append(finding)``).
No error, no ``_grounding_error``, verdict stands. A floor that silently does not fire is the worst
failure of the honesty moat.

This module is the missing reconciliation. :func:`assess_agent_pack_readiness` is a **pure**,
offline, ``$0`` set-difference over already-present data (an agent ontology, a pack ontology, the
registered executors, a tool resolver, the raiseable lens codes) — no LLM, no service, no grade.
It sits **above** the frozen grade seam: it reads the same inputs ``ground()`` already receives and
returns advisory metadata; it never touches ``_apply_consensus`` or the withstands mechanism.

stdlib + ``harness.{ontology,pack,grounding,plugins}`` (the latter three imported LAZILY in the
resolver only) — no ``openai``/``dspy``, import-safe on the BFF startup path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any

from .ontology import Ontology, load_ontology

Severity = str  # "ERROR" | "WARN"

# High-stakes fabrication codes that SHOULD carry a deterministic grounding floor (C5). A
# raiseable fabrication code with no floor is the precise honesty-moat gap: a confident false
# positive with nothing deterministic to catch it. Curated (not a hard invariant) → WARN.
HIGH_STAKES_FABRICATION_CODES = frozenset(
    {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "FABRICATED_HISTORY"}
)


@dataclass(frozen=True)
class ReadinessFinding:
    check: str  # "CONTRACT_COVERAGE" | "EXECUTOR_PRESENCE" | "TOOL_REACHABILITY" | ...
    severity: Severity
    code: str | None  # the flag_code / contract_type / tool_id at fault
    message: str  # user-facing (route through copy.js on the client)
    remediation: str  # one-line actionable fix


@dataclass(frozen=True)
class ReadinessReport:
    ok: bool  # False iff any ERROR finding
    pack: str
    agent: str
    ontology_source: str  # "draft" | "committed"
    findings: tuple[ReadinessFinding, ...]

    def errors(self) -> tuple[ReadinessFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "ERROR")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "pack": self.pack,
            "agent": self.agent,
            "ontology_source": self.ontology_source,
            "findings": [asdict(f) for f in self.findings],
        }


def assess_agent_pack_readiness(
    *,
    agent_ontology: Ontology,
    ontology_source: str,
    pack: str,
    agent_name: str,
    pack_ontology: Ontology | None,
    registered_executors: frozenset[str],
    resolve_tool: Callable[[str], Any],
    raiseable_codes: frozenset[str],
) -> ReadinessReport:
    """Pure, offline readiness assessment. Takes already-resolved values (no I/O of its own) so
    it is trivially unit-testable with hand-built ``Ontology`` fixtures and reusable by both the
    BFF and the CLI. See :func:`resolve_and_assess` for the resolver that gathers these.

    - ``pack_ontology=None`` skips C1 (pack ontology unresolvable — e.g. license-denied); the
      other checks still run.
    - ``raiseable_codes`` empty skips the lens-dependent halves of C4/C5.
    """
    findings: list[ReadinessFinding] = []
    # LAYER2 composition: a flag_code may declare a CHAIN of contracts, so coverage is a
    # (contract_type, flag_code) PAIR match — the old {flag_code: contract} dict kept only
    # the last-declared link and false-alarmed the rest as missing (live: clinverdict_mts's
    # 3-contract HALLUCINATED_DETAIL chain produced 2 phantom CONTRACT_COVERAGE errors).
    agent_pairs = {(c.contract_type, c.flag_code) for c in agent_ontology.contracts}
    contracted_codes = frozenset(c.flag_code for c in agent_ontology.contracts)

    # C1 — CONTRACT_COVERAGE (ERROR): every pack-declared contract present on the agent ontology.
    if pack_ontology is not None:
        for pc in pack_ontology.contracts:
            if (pc.contract_type, pc.flag_code) not in agent_pairs:
                findings.append(
                    ReadinessFinding(
                        check="CONTRACT_COVERAGE",
                        severity="ERROR",
                        code=f"{pc.contract_type}({pc.flag_code})",
                        message=(
                            f"The {pack} pack declares a {pc.contract_type} fact-check for "
                            f"{pc.flag_code}, but agent {agent_name}'s checklist has no matching "
                            f"fact-check — the floor will silently never fire."
                        ),
                        remediation=(
                            f"Add the {pc.contract_type} fact-check for {pc.flag_code} to this "
                            f"agent, or switch to a {pack}-aligned agent."
                        ),
                    )
                )

    # C3 — EXECUTOR_PRESENCE (ERROR): every agent contract_type has a registered executor.
    for ac in agent_ontology.contracts:
        if ac.contract_type not in registered_executors:
            findings.append(
                ReadinessFinding(
                    check="EXECUTOR_PRESENCE",
                    severity="ERROR",
                    code=ac.contract_type,
                    message=(
                        f"Agent {agent_name} declares a {ac.contract_type} fact-check, but the "
                        f"{pack} pack registers no executor for it — the grade would error."
                    ),
                    remediation=(
                        f"Remove the {ac.contract_type} fact-check, or load a pack that "
                        f"registers its executor."
                    ),
                )
            )

    # C2 — TOOL_REACHABILITY (ERROR): every tool a contract names is declared + license-permitted.
    for ac in agent_ontology.contracts:
        tool_id = (ac.params or {}).get("tool")
        if not tool_id:
            continue
        if resolve_tool(tool_id) is None:
            findings.append(
                ReadinessFinding(
                    check="TOOL_REACHABILITY",
                    severity="ERROR",
                    code=tool_id,
                    message=(
                        f"The {ac.contract_type} fact-check needs tool {tool_id!r}, which is not "
                        f"declared for the {pack} pack (or is not permitted by the active "
                        f"license) — the floor would silently not ground."
                    ),
                    remediation=(
                        f"Declare {tool_id!r} in the pack's tools, or use a license that "
                        f"permits it."
                    ),
                )
            )

    # C4 — CONTRACT_FLAG_VALIDITY (WARN): each contract is keyed to a flag that can actually fire.
    for ac in agent_ontology.contracts:
        reasons: list[str] = []
        if agent_ontology.flag(ac.flag_code) is None:
            reasons.append("it is not a declared flag in this agent's ontology")
        if raiseable_codes and ac.flag_code not in raiseable_codes:
            reasons.append("no running judge can raise it")
        if reasons:
            findings.append(
                ReadinessFinding(
                    check="CONTRACT_FLAG_VALIDITY",
                    severity="WARN",
                    code=ac.flag_code,
                    message=(
                        f"The {ac.contract_type} fact-check is keyed to {ac.flag_code}, but "
                        f"{' and '.join(reasons)} — it can never fire."
                    ),
                    remediation=(
                        f"Key the fact-check to a raiseable flag, or add {ac.flag_code} to the "
                        f"ontology / a judge's lens."
                    ),
                )
            )

    # C5 — LENS_VS_CONTRACT_GAP (WARN): a raiseable high-stakes fabrication code with no floor.
    for code in sorted((HIGH_STAKES_FABRICATION_CODES & raiseable_codes) - contracted_codes):
        findings.append(
            ReadinessFinding(
                check="LENS_VS_CONTRACT_GAP",
                severity="WARN",
                code=code,
                message=(
                    f"The council can raise {code} but agent {agent_name} has no grounding floor "
                    f"for it — a confident false positive can't be caught."
                ),
                remediation=f"Add a grounding fact-check for {code}.",
            )
        )

    ok = not any(f.severity == "ERROR" for f in findings)
    return ReadinessReport(
        ok=ok,
        pack=pack,
        agent=agent_name,
        ontology_source=ontology_source,
        findings=tuple(findings),
    )


def resolve_and_assess(
    *,
    agent_name: str,
    agent_ontology_path: str | Path,
    ontology_source: str,
    pack: str,
    license: Any = None,
) -> ReadinessReport:
    """Gather the pack-side inputs for :func:`assess_agent_pack_readiness` and assess.

    The caller supplies the AGENT side it already resolved (``_resolve_ontology_path`` →
    ``agent_ontology_path`` + ``ontology_source``); this pulls the PACK side with the existing
    accessors. Every dependency is offline/declaration-only — no MCP server is opened, no grade
    runs. Lazy imports keep this module import-light on the BFF startup path.
    """
    from lithrim_bench.harness import grounding, plugins
    from lithrim_bench.harness import pack as pack_mod

    agent_ontology = load_ontology(agent_ontology_path)

    pack_ontology: Ontology | None
    try:
        pack_ontology = load_ontology(pack_mod.pack_ontology_path(pack, check_consistency=False))
    except Exception:  # noqa: BLE001 — pack ontology unresolvable (license/absent) → skip C1
        pack_ontology = None

    registered = frozenset(grounding.suppress_executors(pack)) | frozenset(
        grounding.floor_executors(pack)
    )

    lic = license or plugins.default_license()
    resolver = partial(plugins.resolve_tool, pack=pack, license=lic)

    raiseable: set[str] = set()
    try:
        lenses = pack_mod.pack_lenses(pack)
        for role in pack_mod.pack_production_judges(pack):
            raiseable |= set(lenses.get(role, ()))
    except Exception:  # noqa: BLE001 — pack has no lens/roster snapshot → skip lens-dependent checks
        raiseable = set()

    return assess_agent_pack_readiness(
        agent_ontology=agent_ontology,
        ontology_source=ontology_source,
        pack=pack,
        agent_name=agent_name,
        pack_ontology=pack_ontology,
        registered_executors=registered,
        resolve_tool=resolver,
        raiseable_codes=frozenset(raiseable),
    )
