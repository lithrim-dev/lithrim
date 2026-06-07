"""Shared frozen-seam helper for the council moat guards (BYOC-1 reconciliation).

``build_judge_lm`` + ``build_trio`` are the AUTHORIZED BYOC-1 provider-seam change (driver
A6 explicitly excludes ``build_judge_lm`` from the frozen set). The UAP-3b / UAP-3b-2 moat
guards therefore no longer whole-file-pin ``judges_dspy.py`` to ``acc4973``; instead they
call :func:`assert_judges_dspy_consensus_seam_frozen`, which proves that every OTHER
top-level symbol — the JudgeSignature (``_build_signature``), the per-judge seam dict
(``class Judge``), the finding shape + normalizers (``Finding`` / ``EvidenceSpan`` /
``_validate_findings`` / …), and ``evaluate_dspy`` (the unchanged ``_apply_consensus``
call) — is byte-identical to ``acc4973``. The consensus seam stays provably frozen; only
the provider binder may evolve. Single-sourced so the two guards can never drift apart.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

_JUDGES_DSPY_REL = "lithrim_bench/runtime/council/judges_dspy.py"
_SEAM_BASELINE = "acc4973"  # the UAP-3b parent — the moat-seam pin
# The ONLY symbols BYOC-1 is authorized to change in judges_dspy.py (the provider binder).
_BYOC1_PROVIDER_SEAM = frozenset({"build_judge_lm", "build_trio"})


def _toplevel_defs(src_text: str, *, exclude: frozenset[str]) -> dict[str, str]:
    """Map ``{name: verbatim source}`` for every top-level def/class not in ``exclude``."""
    tree = ast.parse(src_text)
    return {
        node.name: ast.get_source_segment(src_text, node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name not in exclude
    }


def assert_judges_dspy_consensus_seam_frozen(repo: Path) -> None:
    """The consensus seam in ``judges_dspy.py`` (everything except the BYOC-1 provider
    binder ``build_judge_lm``/``build_trio``) is byte-identical to ``acc4973``."""
    base_src = subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{_JUDGES_DSPY_REL}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    cur_src = (repo / _JUDGES_DSPY_REL).read_text()
    base = _toplevel_defs(base_src, exclude=_BYOC1_PROVIDER_SEAM)
    cur = _toplevel_defs(cur_src, exclude=_BYOC1_PROVIDER_SEAM)
    assert set(cur) == set(base), (
        "judges_dspy.py consensus-seam symbol set changed: "
        f"added={sorted(set(cur) - set(base))} removed={sorted(set(base) - set(cur))}"
    )
    drifted = [name for name, src in base.items() if cur[name] != src]
    assert not drifted, f"consensus-seam symbol(s) drifted in judges_dspy.py: {drifted}"
