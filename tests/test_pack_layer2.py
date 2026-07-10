"""PACK-2 layer-2 — the core loads its council role prompts from the active
`healthcare` pack, not a hardcoded `council_roles/` path (healthcare-realm-as-pack).

The judges layer of the core↔domain boundary: the 5 clinical role prompts relocated
into `packs/healthcare/council_roles/`, and BOTH readers (the above-seam council-light
`judge_assignment.py` and the FROZEN live council `compliance_council.py:470`, via an
authorized path-only carve-out) resolve via `pack.pack_prompts_path()`. The judges
consistency gate (D4/A3) keeps the loaded pack roster-compatible while the council's
roster stays FROZEN (layer 2b un-hardcodes it). Mirrors `test_pack_layer1a.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from lithrim_bench.harness import pack

REPO_ROOT = Path(__file__).resolve().parents[1]

# The council_roles LOAD-PATH construction that relocated into the pack. Both the
# Path-join form and the exact pre-move literal, so a re-introduced hardcode in either
# style is caught. Bare ``council_roles/`` prose in comments/docstrings is NOT a load
# path and is deliberately not matched.
_CORE_NEEDLES = (
    '/ "council_roles"',
    'Path(__file__).parent / "council_roles"',
)
# In scripts/, the live LOAD path of the OLD core location. The ``question_source``
# provenance LABEL (documented carve-out, mirrors PACK-1's taxonomy_snapshot labels) is
# output metadata recording where the prompts lived at build time, not a live dependency.
_OLD_CORE_DIR_NEEDLE = "runtime/council/council_roles"


def _hits(root: Path, needles: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in {".py", ".json"} or "__pycache__" in f.parts:
            continue
        try:
            text = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(n in line for n in needles):
                out.append(f"{f.relative_to(REPO_ROOT)}:{i}: {line.strip()}")
    return out


# ───────────────────────────── D5 / A1 — the boundary ─────────────────────────────
def test_core_package_carries_no_council_roles_dir():
    """The core no longer carries the clinical role-prompt directory."""
    assert not (REPO_ROOT / "lithrim_bench" / "runtime" / "council" / "council_roles").exists()


def test_core_package_carries_no_council_roles_load_path():
    """``lithrim_bench/`` (the core) constructs no ``council_roles`` load path — both
    readers resolve via the active pack. Comment/docstring prose is not matched."""
    hits = _hits(REPO_ROOT / "lithrim_bench", _CORE_NEEDLES)
    assert hits == [], "core still hardcodes a council_roles load path:\n" + "\n".join(hits)


def test_scripts_live_load_path_is_clean():
    """In ``scripts/`` the ONLY permitted residual old-path string is the
    ``question_source`` provenance LABEL (documented carve-out). Any other residual (a
    live load of the OLD core council_roles dir) fails — keeping this guard non-vacuous."""
    residual = [
        h
        for h in _hits(REPO_ROOT / "scripts", (_OLD_CORE_DIR_NEEDLE,))
        if "question_source" not in h
    ]
    assert residual == [], (
        "a script still loads from the old core council_roles path:\n" + "\n".join(residual)
    )


# ───────────────────────── active-pack resolution (D1/D3) ─────────────────────────
def test_pack_prompts_path_resolves_to_the_pack():
    p = pack.pack_prompts_path()
    assert p.name == "council_roles"
    assert p.parent.name == "healthcare"
    assert p.exists()
    assert sorted(f.stem for f in p.glob("*.txt")) == [
        "behavior_judge",
        "faithfulness_judge",
        "policy_judge",
        "risk_judge",
        "source_message_judge",
    ]


# PACK-DIST-2 D5: test_council_light_reader_resolves_through_the_pack relocated (GENERICIZED) to the
# pack repo (tests/test_pack_layer2_relocated.py) — it asserted the literal 'packs/healthcare' in the
# resolved prompts dir, STALE once the pack lives outside the CE tree; the pack version asserts
# resolution to pack._pack_root('healthcare')/'council_roles' instead. The generic boundary funcs +
# NEEDS_PACK funcs stay.


def test_frozen_council_reader_resolves_through_the_pack_textually():
    """The FROZEN ``compliance_council.py:470`` carve-out resolves via ``pack_prompts_path``
    — asserted by AST (no import: ``openai`` is absent in the core env)."""
    src = (
        REPO_ROOT / "lithrim_bench" / "runtime" / "council" / "compliance_council.py"
    ).read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_ROLE_PROMPTS_DIR" for t in node.targets
        ):
            found = "pack_prompts_path" in ast.get_source_segment(src, node.value)
    assert found, "compliance_council.py _ROLE_PROMPTS_DIR does not resolve via pack_prompts_path"


# ─────────────────── D4 / A3 — the consistency gate (non-vacuous) ───────────────────
def test_healthcare_pack_is_judge_consistent():
    # does not raise; the declared trio has prompts and is ⊆ the council roster.
    pack.assert_pack_judges_consistent("healthcare")
    roster = pack.council_roster()
    assert {"risk_judge", "policy_judge", "faithfulness_judge"} <= roster
    # the dormant v1 roles are roster-known too (so the relocated provenance .txt are not stray)
    assert {"behavior_judge", "source_message_judge"} <= roster


def test_gate_fails_closed_on_a_declared_judge_with_no_prompt():
    roster = pack.council_roster()
    # the declared trio with prompts present passes…
    pack.assert_judges_known(["risk_judge"], ["risk_judge", "policy_judge"], roster=roster)
    # …a declared judge with no prompt file fails closed.
    with pytest.raises(pack.PackConsistencyError) as ei:
        pack.assert_judges_known(["risk_judge", "policy_judge"], ["risk_judge"], roster=roster)
    assert "no council-role prompt" in str(ei.value)


def test_gate_fails_closed_on_a_stray_non_roster_prompt():
    roster = pack.council_roster()
    with pytest.raises(pack.PackConsistencyError) as ei:
        pack.assert_judges_known(["risk_judge"], ["risk_judge", "FOO_judge"], roster=roster)
    assert "FOO_judge" in str(ei.value)


def test_gate_fails_closed_on_a_declared_judge_off_the_roster():
    roster = pack.council_roster()
    with pytest.raises(pack.PackConsistencyError) as ei:
        pack.assert_judges_known(["NOPE_judge"], ["NOPE_judge"], roster=roster)
    assert "NOPE_judge" in str(ei.value)


def test_council_roster_is_ast_parsed_without_importing_openai():
    """The gate reads the frozen council roster without importing it — so it runs in the
    core (no-openai) env. Post-layer-2b the ``CouncilModel`` roster NAMES are still AST-parsed
    from the source, while the Tier-1 owner roles come from the pack snapshot; both legs are
    openai-free. The green run with openai absent is itself the proof; here we pin that the
    resolution yields the real roles (not an empty/vacuous set)."""
    roster = pack.council_roster()
    assert "risk_judge" in roster and "source_message_judge" in roster
    assert len(roster) == 5
