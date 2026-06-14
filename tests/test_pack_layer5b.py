"""PACK-5b layer-5b — the core-boundary FINISHER: the engine carries no relocatable clinical
DATASET-GENERATION code.

5b is the SAME proven mechanism as 5a (``load_pack_generators`` + ``active_packs`` + the
multi-file package loader + the by-construction byte-identity gate), applied to the last four
agent-types (hl7_adt / coding / scheduling / triage) plus the ``_pmh`` scribe residual and the
core-thinning 5a deferred. After 5b ALL five per-agent recipes — with their synthesizers,
injectors and helpers — live in ``packs/healthcare/generators/``; the core resolves the FULL
recipe set from the active pack and ``lithrim_bench.packs._CORE_PACKS == {}`` (a thin resolver).

The boundary is grep- and structure-verifiable like layer1a/2/3/5a: the agent-type generator
CODE is ABSENT from the engine AND PRESENT under the pack (relocation, not deletion); the core
``injectors/`` package is base-only and the core ``synthesizers/`` package is gone. The residue
in ``lithrim_bench/`` is the FROZEN council (1b/2b), the PACK-3 enumerated carve-out, and
generic-engine docstring examples — none of which is relocatable generation code.

The crux (HARD GATE): each relocation is a MOVE, not an edit — the ``InjectionRecipe`` IS the
label justification (CLAUDE.md "labels are true by construction"), so EACH of the four
non-scribe corpora regenerates byte-identical to its committed pre-move baseline (the C1
baselines, generated from the pre-move code with a frozen ``generated_at``).
"""

from __future__ import annotations

import ast
from pathlib import Path

from lithrim_bench.harness import pack

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "lithrim_bench"
PACK_GEN = REPO_ROOT / "packs" / "healthcare" / "generators"
COHORT = REPO_ROOT / "data" / "synthea_sample_data_csv_latest"
EXAMPLES = REPO_ROOT / "examples"
FROZEN_TS = "2026-06-10T00:00:00+00:00"

# The agent-type generator CODE that relocated (5b's four agent-types + the _pmh scribe
# residual). Unambiguous code definitions (class / def) — a re-introduced generator in the
# engine trips these; prose using the bare names does not.
_AGENT_CODE_NEEDLES = (
    # hl7_adt
    "class Hl7MalformedDateInjector",
    "class Hl7MissingSegmentInjector",
    "class Hl7InvalidFieldFormatInjector",
    "class Hl7MissingRequiredFieldInjector",
    "class Hl7TriggerEventMismatchInjector",
    "def synthesize_hl7_adt_artifact",
    "def synthesize_hl7_adt_transcript",
    "def mutate_hl7",
    # coding
    "class UpcodingRiskInjector",
    "def synthesize_coding_artifact",
    "def synthesize_coding_transcript",
    "def synthesize_coding_note",
    "def resolve_primary_dx",
    # scheduling
    "class FabricatedConsentInjector",
    "class PhiDisclosurePreVerificationInjector",
    "def synthesize_scheduling_artifact",
    "def synthesize_scheduling_transcript",
    # triage
    "class MissedEscalationInjector",
    "def synthesize_triage_artifact",
    "def synthesize_triage_transcript",
    "def pick_scenario",
    # scribe residual (_pmh relocated in 5b, closing S-BS-121)
    "def clinical_conditions",
)

# The four non-scribe corpora. The C1 baselines (examples/<pack>.jsonl) were generated from
# the PRE-move code with a frozen generated_at; regenerating post-move must reproduce them.
_CORPORA = ("coding_v1", "hl7_adt_v1", "scheduling_v1", "triage_v1")


def _iter_py(root: Path) -> list[Path]:
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    return [f for f in files if "__pycache__" not in f.parts]


def _grep(root: Path, needles: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for f in _iter_py(root):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if any(n in line for n in needles):
                out.append(f"{f.relative_to(REPO_ROOT)}:{i}: {line.strip()}")
    return out


# ───────────────────────── A1 — the core-boundary finisher ─────────────────────────
def test_engine_carries_no_agent_type_generator_code():
    """The domain-agnostic engine (lithrim_bench/) carries NO agent-type generator code — the
    relocation FINISHER (5a scribe + 5b hl7_adt/coding/scheduling/triage + the _pmh residual)."""
    hits = _grep(CORE_DIR, _AGENT_CODE_NEEDLES)
    assert hits == [], "the engine still carries agent-type generator code:\n" + "\n".join(hits)


# PACK-DIST-2 D5: test_agent_type_generators_live_in_the_pack relocated to the pack repo
# (tests/test_pack_layer5b_relocated.py) — it reads the pack's relocated generators/ dir. The
# generic engine-boundary funcs + the NEEDS_PACK active_packs func stay here.


def test_core_injectors_dir_is_base_only():
    """The core injectors/ package carries ONLY the generic base (base.py + __init__.py) —
    every concrete injector relocated to the pack (the A1 structural milestone)."""
    files = {f.name for f in _iter_py(CORE_DIR / "injectors")}
    assert files == {"__init__.py", "base.py"}, f"unexpected core injector files: {sorted(files)}"


def test_core_synthesizers_dir_is_relocated():
    """The core synthesizers/ package is fully relocated — it carries no .py (the directory is
    removed; only a local __pycache__ may linger, which is gitignored)."""
    syn = CORE_DIR / "synthesizers"
    remaining = _iter_py(syn) if syn.exists() else []
    assert remaining == [], f"core synthesizers/ still carries: {[str(p) for p in remaining]}"


# ───────────────── A3 — the thin resolver (all five recipes pack-sourced) ─────────────────
def test_active_packs_all_five_pack_sourced_and_core_empty():
    """active_packs() resolves the FULL 5-recipe set entirely from the pack; _CORE_PACKS == {}
    (the thin resolver — there is no core recipe fallback post-5b)."""
    import lithrim_bench.packs as P

    assert P._CORE_PACKS == {}, f"core recipes not emptied: {sorted(P._CORE_PACKS)}"
    ap = P.active_packs()
    assert set(ap) == {"scribe_v1", "hl7_adt_v1", "coding_v1", "scheduling_v1", "triage_v1"}
    gen = pack.load_pack_generators()
    for name in ap:
        assert ap[name] is gen.PACKS[name], f"{name} is not pack-sourced"


def test_core_never_imports_top_level_packs():
    """Dependency direction: the core never imports the top-level ``packs`` package — the
    pack→core invariant. The core resolves pack code by FILE PATH via the manifest, never by
    ``import packs.*`` (AST-checked, so prose/docstrings don't count)."""
    offenders: list[str] = []
    for f in _iter_py(CORE_DIR):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{f.relative_to(REPO_ROOT)}: import {a.name}"
                    for a in node.names
                    if a.name == "packs" or a.name.startswith("packs.")
                ]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mod = node.module or ""
                if mod == "packs" or mod.startswith("packs."):
                    offenders.append(f"{f.relative_to(REPO_ROOT)}: from {mod} import …")
    assert offenders == [], "core imports the pack package (pack→core violated):\n" + "\n".join(
        offenders
    )


# PACK-DIST-2 D5: the by-construction byte-identity regen func (test_corpus_regenerates_byte_identical)
# relocated to the pack repo (tests/test_pack_layer5b_relocated.py) — it subprocesses
# scripts/generate_pack.py over the Synthea cohort, both of which moved to the pack; there it
# guard-skips when the cohort is absent.
