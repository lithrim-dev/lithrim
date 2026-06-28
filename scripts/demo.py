#!/usr/bin/env python
"""`make demo` — the zero-config flagship loop, $0, no keys, no network, no external pack.

A stranger does ``git clone`` → ``make demo`` and sees the whole loop on the built-in
domain-neutral ``_core`` case ``_core_fabricated_claim``:

    council votes  →  deterministic floor flips PASS → BLOCK  →  immutable audit findings

This replays a COMMITTED council baseline (no LLM call) and runs the LIVE deterministic
``ground()`` + ``composite()`` stages, so the floor flip is real and reproducible — not a
recording. It needs no ``.env``, no API key, and no domain pack: the neutral ``_core`` pack
ships in-repo and is the default.

To grade YOUR OWN artifact live, bring a model key (BYOK):
    export LITHRIM_LLM_PROVIDER=openai
    export OPENAI_API_KEY=sk-...
    make up        # local BFF + UI — nothing leaves your machine
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.config import agent_from_dict  # noqa: E402
from lithrim_bench.harness.grade import grade_replay  # noqa: E402
from lithrim_bench.harness.grounding import ground  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.report import composite  # noqa: E402
from lithrim_bench.picklist import load_case  # noqa: E402

AGENT_SEED = REPO_ROOT / "data/config/agents/ws0_default.json"


def main() -> int:
    agent = agent_from_dict(json.loads(AGENT_SEED.read_text()))
    if not agent.dataset.baseline:
        sys.stderr.write(
            "ERROR: the demo agent has no committed baseline — a clean clone cannot replay.\n"
        )
        return 1

    ontology = load_ontology(agent.ontology_abspath())
    case = load_case(agent.dataset.case_id, source=agent.source_abspath())
    if case is None:
        sys.stderr.write(f"ERROR: demo case {agent.dataset.case_id!r} not found.\n")
        return 1

    # $0: replay the captured council baseline (no LLM), then run the LIVE deterministic floor.
    result = grade_replay(case, agent.baseline_abspath())
    grounded = ground(result, case, ontology=ontology)
    comp = composite(grounded)

    artifact = (case.get("artifacts") or [{}])[0].get("content", "")
    votes = result["semantic"]["judge_votes"]

    print("=" * 72)
    print("  Lithrim — flagship loop demo  ($0 · no keys · no network · no pack)")
    print("=" * 72)
    print(f"  case:     {case.get('case_id')}   (pack: {case.get('pack', '_core')})")
    print(f"  artifact: {artifact[:120]}{'…' if len(artifact) > 120 else ''}")
    print()
    print("  1. COUNCIL VOTES")
    for v in votes:
        conf = v.get("confidence")
        conf_s = f"{conf:.3f}" if isinstance(conf, (int, float)) else "—"
        findings = ", ".join(v.get("findings") or []) or "(none)"
        print(f"       {v['judge_role']:<20} {v['vote']:<6} conf={conf_s:<7} [{findings}]")
    print()
    print("  2. DETERMINISTIC FLOOR")
    print(f"       original verdict (council):  {grounded.original_verdict}")
    print(f"       after grounding floor:       {grounded.verdict}")
    flip = grounded.original_verdict != str(grounded.verdict)
    print(f"       => {'FLIPPED' if flip else 'unchanged'}: "
          f"{grounded.original_verdict} -> {grounded.verdict}")
    print()
    print("  3. AUDIT — active findings (the 'why')")
    for code in comp["active_findings"]:
        print(f"       - {code}")
    if not comp["active_findings"]:
        print("       (none)")
    print()
    print("-" * 72)
    print(f"  COMPOSITE VERDICT: {comp['verdict'].upper()}   "
          f"(stage {comp['stage_verdict']}, council said {grounded.original_verdict})")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
