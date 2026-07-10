"""Per-claim routing + verdict composition — the false-negative guardrail.

The v3 spike taught the load-bearing lesson: a tool-grounded contract that flips
a verdict by DROPPING a flag is dangerous unless it is

  (1) defect-class-matched  — the right tool for the claim type, and
  (2) verdict-aware         — only move toward approve when EVERY implicated flag
                              is POSITIVELY cleared (conforms=True), with no flag
                              left CONFIRMED or UNRESOLVED.

`Router` holds the SME-authored `flag -> spec` map (the ontology table) and the
tool instances. `compose_verdict` runs each open flag through its routed tool and
applies the rule above. A flag with no route, or whose tool returns inconclusive,
stays OPEN — it is never cleared by silence. The per-flag manifest is returned for
logging (the audit trail / RLVR correction record).
"""

from __future__ import annotations

from collections.abc import Callable

from .spec import Claim, VerificationSpec
from .tools import VerificationTool

# dispositions
CLEARED = "CLEARED"  # tool positively disproved the violation -> flag dropped
CONFIRMED = "CONFIRMED"  # tool positively confirmed the violation -> flag kept
UNRESOLVED = "UNRESOLVED"  # no route / inconclusive / tool error -> flag stays open


class Router:
    def __init__(self, specs: list[VerificationSpec], tools: list[VerificationTool]) -> None:
        self._specs = list(specs)
        self._tools = {t.name: t for t in tools}
        self._by_flag: dict[str, VerificationSpec] = {}
        for spec in specs:
            for flag in spec.applies_to_flags:
                self._by_flag[flag] = spec  # last spec wins for a flag

    def spec_for(self, flag: str) -> VerificationSpec | None:
        return self._by_flag.get(flag)

    def tool_for(self, spec: VerificationSpec | None) -> VerificationTool | None:
        return self._tools.get(spec.tool) if spec is not None else None

    @property
    def routed_flags(self) -> set[str]:
        return set(self._by_flag)


# claim_builder: (flag, spec) -> Claim. Supplied by the caller, which knows the row shape.
ClaimBuilder = Callable[[str, VerificationSpec], Claim]


def compose_verdict(
    *,
    open_flags: list[str],
    router: Router,
    claim_builder: ClaimBuilder,
    base_verdict_if_no_flags: str = "approve",
) -> dict:
    """Route each open flag, classify its disposition, and compose the verdict.

    approve  iff  there are flags AND every one is CLEARED.
    reject   iff  any flag is CONFIRMED or UNRESOLVED.
    """
    decisions: list[dict] = []
    for flag in open_flags:
        spec = router.spec_for(flag)
        if spec is None:
            decisions.append(
                _decide(flag, UNRESOLVED, None, "no routed tool for this flag", {}, {})
            )
            continue
        tool = router.tool_for(spec)
        if tool is None:
            decisions.append(
                _decide(flag, UNRESOLVED, None, f"no tool instance for {spec.tool!r}", {}, {})
            )
            continue
        try:
            res = tool.verify(claim_builder(flag, spec), spec)
        except Exception as exc:  # noqa: BLE001 - a tool failure must NOT clear a flag
            decisions.append(
                _decide(flag, UNRESOLVED, None, f"tool error: {type(exc).__name__}: {exc}", {}, {})
            )
            continue
        if res.conforms is True:
            disp, reason = CLEARED, f"{spec.tool} disproved the violation (locus={spec.locus})"
        elif res.conforms is False:
            disp, reason = CONFIRMED, f"{spec.tool} confirmed the violation (locus={spec.locus})"
        else:
            disp, reason = UNRESOLVED, f"{spec.tool} inconclusive (locus={spec.locus})"
        decisions.append(_decide(flag, disp, res.conforms, reason, res.evidence, res.manifest))

    still_open = [d["flag"] for d in decisions if d["disposition"] != CLEARED]
    if not open_flags:
        verdict = base_verdict_if_no_flags
    else:
        verdict = "approve" if not still_open else "reject"

    return {
        "verdict": verdict,
        "decisions": decisions,
        "cleared": [d["flag"] for d in decisions if d["disposition"] == CLEARED],
        "confirmed": [d["flag"] for d in decisions if d["disposition"] == CONFIRMED],
        "unresolved": [d["flag"] for d in decisions if d["disposition"] == UNRESOLVED],
        "still_open": still_open,
    }


def _decide(
    flag: str, disposition: str, conforms: bool | None, reason: str, evidence: dict, manifest: dict
) -> dict:
    return {
        "flag": flag,
        "disposition": disposition,
        "conforms": conforms,
        "reason": reason,
        "evidence": evidence,
        "manifest": manifest,
    }
