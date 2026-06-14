"""PACK-5a layer-5a — the core resolves its scribe DATASET-GENERATION from the active
`healthcare` pack, not from the engine (healthcare-realm-as-pack; the FIRST packs-as-CODE
*generation* step, unifying data + grading + generation in one pack).

The dataset layer of the core↔domain boundary: the scribe synthesizers + injectors + the
``SCRIBE_PACK`` recipe relocated into ``packs/healthcare/generators/``, behind the pack
generator-registration interface (``pack.load_pack_generators``). The generic generation
FRAMEWORK stays core (``PackDefinition`` the class, ``DefectInjector``/``InjectionRecipe``
the by-construction label machinery, ``packager``, the Synthea loaders, ``encounter_spec``,
the shared ``_pmh`` helper). ``lithrim_bench.packs.active_packs()`` merges the pack's
``PACKS`` over the core's non-scribe recipes LAZILY (pack→core, no cycle).

The boundary is grep-verifiable like layer1a/2/3: the scribe generator CODE is ABSENT from
the engine AND PRESENT under the pack (relocation, not deletion). Needles are unambiguous
code definitions (``class …Injector`` / ``def synthesize_scribe_*`` / ``def mutate_soap_body``)
— not domain words that recur in generic code — so prose mentioning the bare names does not
trip them, and no carve-out is needed (5a is scribe-scoped; the full ``grep lithrim_bench/ →
empty`` is 5b).

The crux (HARD GATE): the relocation is a MOVE, not an edit — the ``InjectionRecipe`` IS the
label justification (CLAUDE.md "labels are true by construction"), so the by-construction
corpus regenerates byte-identical (``test_judge_calib_regenerates_byte_identical``).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from lithrim_bench.harness import pack

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "lithrim_bench"
PACK_GEN = REPO_ROOT / "packs" / "healthcare" / "generators"
COHORT = REPO_ROOT / "data" / "synthea_sample_data_csv_latest"

# The SCRIBE generator CODE that relocated. Unambiguous code definitions (class / def) — a
# re-introduced scribe generator in the engine trips these; prose using the bare names does not.
_SCRIBE_CODE_NEEDLES = (
    "class WrongDosageInjector",
    "class MissingAllergyInjector",
    "class FabricatedHistoryInjector",
    "class ValueMismatchInjector",
    "class HallucinatedDetailInjector",
    "def synthesize_scribe_transcript",
    "def synthesize_scribe_artifact",
    "def mutate_soap_body",
)


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


# ───────────────────────────── A1 — the boundary ─────────────────────────────
def test_engine_carries_no_scribe_generator_code():
    """The domain-agnostic engine (lithrim_bench/) carries NO scribe generator code."""
    hits = _grep(CORE_DIR, _SCRIBE_CODE_NEEDLES)
    assert hits == [], "the engine still carries scribe generator code:\n" + "\n".join(hits)


# PACK-DIST-2 D5: test_scribe_generators_live_in_the_pack relocated to the pack repo
# (tests/test_pack_layer5a_relocated.py) — it reads the pack's relocated generators/ dir. The
# generic engine-boundary funcs + the NEEDS_PACK active_packs funcs stay here.


def test_core_never_imports_top_level_packs():
    """Dependency direction: the core (lithrim_bench/) never imports the top-level ``packs``
    package — the pack→core invariant. The core resolves pack code by FILE PATH via the
    manifest, never by ``import packs.*`` (AST-checked, so prose/docstrings don't count)."""
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


# ──────────── A3 — the registration interface (non-vacuous + fail-clean) ────────────
def test_active_packs_resolves_scribe_from_pack():
    """active_packs() includes the pack's relocated scribe recipe — scribe_v1 is the PACK's
    instance (by identity). PACK-5b relocated the other 4 agent-types too; the full
    all-pack-sourced + ``_CORE_PACKS == {}`` resolution is asserted in test_pack_layer5b."""
    import lithrim_bench.packs as P

    ap = P.active_packs()
    assert set(ap) == {"scribe_v1", "scheduling_v1", "coding_v1", "triage_v1", "hl7_adt_v1"}

    gen = pack.load_pack_generators()
    assert ap["scribe_v1"] is gen.PACKS["scribe_v1"]  # scribe from the PACK

    assert ap["scribe_v1"].agent_type == "scribe"
    assert ap["scribe_v1"].requires_active_medication is True
    assert [c.__name__ for c in ap["scribe_v1"].injectors] == [
        "WrongDosageInjector",
        "MissingAllergyInjector",
        "FabricatedHistoryInjector",
        "ValueMismatchInjector",
        "HallucinatedDetailInjector",
    ]


def test_load_pack_generators_cache_identity():
    """Cached on the resolved pack id → load_pack_generators() and (…"healthcare") are one
    object (one class identity for the relocated injectors across engine and callers)."""
    assert pack.load_pack_generators() is pack.load_pack_generators("healthcare")
    assert pack.load_pack_generators().PACKS["scribe_v1"].name == "scribe_v1"


def test_no_generators_pack_degrades(monkeypatch):
    """A pack that declares no ``generators`` degrades cleanly: load returns None, and
    active_packs() yields ONLY the (post-5b empty) core recipes — every recipe absent, since
    there is no core fallback. NON-VACUOUS: unregister the pack generators → scribe_v1
    disappears, proving it is pack-sourced, not core."""
    import lithrim_bench.packs as P

    monkeypatch.setattr(pack, "_manifest", lambda _p: {"generators": None})
    pack._load_pack_generators.cache_clear()
    assert pack.load_pack_generators("nogen") is None

    monkeypatch.setattr(pack, "active_pack", lambda: "nogen")
    P._active_packs.cache_clear()
    ap = P.active_packs()
    assert "scribe_v1" not in ap
    assert set(ap) == set(P._CORE_PACKS)

    # restore: drop the synthetic 'nogen' entries so later tests reload the real pack
    pack._load_pack_generators.cache_clear()
    P._active_packs.cache_clear()


def test_import_lithrim_bench_packs_heavy_dep_free():
    """``import lithrim_bench.packs`` + active_packs() (which lazily loads the pack generators)
    stays heavy-dep-free — the generation framework + the relocated scribe package are pure
    template code (no httpx/dspy/onnx/pinecone at import)."""
    code = (
        "import sys; import lithrim_bench.packs as P; P.active_packs();"
        "leaked=[m for m in ('httpx','dspy','onnxruntime','pinecone') if m in sys.modules];"
        "print(leaked); assert leaked==[], leaked"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]"


# PACK-DIST-2 D5: the by-construction byte-identity regen func (test_judge_calib_regenerates_byte_identical)
# relocated to the pack repo (tests/test_pack_layer5a_relocated.py) — it subprocesses
# scripts/generate_judge_calib.py over the Synthea cohort, both of which moved to the pack; there it
# guard-skips when the cohort is absent.
